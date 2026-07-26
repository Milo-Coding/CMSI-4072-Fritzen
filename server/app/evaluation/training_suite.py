"""Scenario-based adaptive-agent training and validation suite."""

from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..engine import Game, Player
from ..engine.agents import AdaptiveAgent, AgentRegistry
from .metrics import ProfitabilityResult, bb_per_100, cluster_bootstrap_ci


@dataclass(frozen=True)
class OpponentSpec:
    """One seat's opponent configuration."""

    agent_type: str
    model_path: Optional[str] = None
    name: Optional[str] = None


@dataclass(frozen=True)
class TrainingScenario:
    """A repeatable table composition and match length."""

    name: str
    opponents: Sequence[OpponentSpec]
    games: int = 20
    hands_per_game: int = 50
    starting_chips: int = 1000
    small_blind: int = 10

    @property
    def player_count(self) -> int:
        return 1 + len(self.opponents)

    def validate(self) -> None:
        if not 2 <= self.player_count <= 6:
            raise ValueError("Scenarios must contain 2-6 total players")
        if self.games <= 0 or self.hands_per_game <= 0:
            raise ValueError("games and hands_per_game must be positive")
        if self.starting_chips <= 0 or self.small_blind <= 0:
            raise ValueError("chips and blinds must be positive")
        for opponent in self.opponents:
            if opponent.agent_type not in AgentRegistry.list_agents():
                raise ValueError(f"Unknown opponent type: {opponent.agent_type}")
            if opponent.agent_type == "dqn" and not opponent.model_path:
                raise ValueError("DQN opponents require a model_path")


@dataclass
class ScenarioResult:
    name: str
    player_count: int
    opponent_types: List[str]
    games: int
    hands: int
    game_wins: int
    game_ties: int
    net_chips: int
    bb_per_100: float
    early_bb_per_100: float
    late_bb_per_100: float
    has_hand_50_window: bool
    game_win_rate: float
    elapsed_seconds: float
    hands_per_second: float
    profiles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    hand_results_bb: List[float] = field(default_factory=list)

    @property
    def adaptation_delta_bb_per_100(self) -> float:
        return self.late_bb_per_100 - self.early_bb_per_100

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["adaptation_delta_bb_per_100"] = self.adaptation_delta_bb_per_100
        return payload


@dataclass
class SuiteResult:
    seed: int
    scenarios: List[ScenarioResult]
    elapsed_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": 1,
            "seed": self.seed,
            "elapsed_seconds": self.elapsed_seconds,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }


@dataclass
class MonteCarloResult:
    """Aggregate of independent games with a fresh learner in every trial."""

    scenario_name: str
    games_requested: int
    games_completed: int
    games_reaching_hand_50: int
    total_hands: int
    average_hands_per_game: float
    game_win_rate: float
    game_tie_rate: float
    average_net_bb_per_game: float
    net_bb_confidence_interval: ProfitabilityResult
    aggregate_bb_per_100: float
    hands_1_10_bb_per_100: float
    hands_41_50_bb_per_100: Optional[float]
    adaptation_delta_bb_per_100: Optional[float]
    hand_index_mean_bb: Dict[int, float]
    elapsed_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["hand_index_mean_bb"] = {
            str(key): value for key, value in self.hand_index_mean_bb.items()
        }
        return payload


def _reset_player(player: Player, chips: int) -> None:
    player.chips = chips
    player.hand = []
    player.is_playing_round = True
    player.current_bet_in_round = 0
    player.total_bet_in_hand = 0
    player.has_acted_this_round = False
    if hasattr(player, "last_chips"):
        player.last_chips = chips


def _create_opponent(
    spec: OpponentSpec,
    *,
    chips: int,
    player_id: str,
) -> Player:
    kwargs: Dict[str, Any] = {
        "name": spec.name or f"{spec.agent_type.title()}Bot",
        "chips": chips,
        "player_id": player_id,
    }
    if spec.agent_type == "dqn":
        kwargs.update(
            {
                "is_training": False,
                "model_load_path": spec.model_path,
            }
        )
    return AgentRegistry.create(spec.agent_type, **kwargs)


def _window_bb_per_100(values: Sequence[float], start: int, end: int) -> float:
    selected = [
        value
        for index, value in enumerate(values, start=1)
        if start <= index <= end
    ]
    if not selected:
        return 0.0
    return sum(selected) * 100.0 / len(selected)


def run_scenario(
    scenario: TrainingScenario,
    *,
    seed: int = 0,
    rollout_count: int = 64,
    seat_offset: int = 0,
) -> ScenarioResult:
    """Run one adaptive-training scenario with seat rotation."""
    scenario.validate()
    random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
    except ImportError:
        pass

    adaptive = AdaptiveAgent(
        name="AdaptiveTrainee",
        chips=scenario.starting_chips,
        player_id="adaptive_trainee",
        rollout_count=rollout_count,
        big_blind=scenario.small_blind * 2,
    )
    opponents = [
        _create_opponent(
            spec,
            chips=scenario.starting_chips,
            player_id=f"{scenario.name}:opponent:{index}",
        )
        for index, spec in enumerate(scenario.opponents)
    ]

    hand_results_bb: List[float] = []
    game_wins = 0
    game_ties = 0
    started = time.perf_counter()
    for game_index in range(scenario.games):
        for player in [adaptive, *opponents]:
            _reset_player(player, scenario.starting_chips)

        adaptive_seat = (seat_offset + game_index) % scenario.player_count
        players: List[Player] = []
        opponent_index = 0
        for seat in range(scenario.player_count):
            if seat == adaptive_seat:
                players.append(adaptive)
            else:
                players.append(opponents[opponent_index])
                opponent_index += 1

        game = Game(
            players,
            small_blind=scenario.small_blind,
            big_blind=scenario.small_blind * 2,
        )
        for _ in range(scenario.hands_per_game):
            if not game.is_still_playable():
                break
            before = adaptive.chips
            game.play_hand()
            hand_results_bb.append(
                (adaptive.chips - before) / float(scenario.small_blind * 2)
            )

        maximum = max(player.chips for player in players)
        winners = [player for player in players if player.chips == maximum]
        if adaptive in winners:
            if len(winners) == 1:
                game_wins += 1
            else:
                game_ties += 1

    elapsed = time.perf_counter() - started
    total_hands = len(hand_results_bb)
    net_chips = round(sum(hand_results_bb) * scenario.small_blind * 2)
    all_bb100 = (
        bb_per_100(
            net_chips=net_chips,
            big_blind=scenario.small_blind * 2,
            hands=total_hands,
        )
        if total_hands
        else 0.0
    )
    # Adaptation is measured at the plan's exact global observation horizons.
    early = _window_bb_per_100(hand_results_bb, 1, min(10, total_hands))
    has_hand_50_window = total_hands >= 50
    late = _window_bb_per_100(hand_results_bb, 41, 50)
    return ScenarioResult(
        name=scenario.name,
        player_count=scenario.player_count,
        opponent_types=[spec.agent_type for spec in scenario.opponents],
        games=scenario.games,
        hands=total_hands,
        game_wins=game_wins,
        game_ties=game_ties,
        net_chips=net_chips,
        bb_per_100=all_bb100,
        early_bb_per_100=early,
        late_bb_per_100=late,
        has_hand_50_window=has_hand_50_window,
        game_win_rate=game_wins / scenario.games,
        elapsed_seconds=elapsed,
        hands_per_second=total_hands / elapsed if elapsed else 0.0,
        profiles={
            player_id: profile.to_dict()
            for player_id, profile in adaptive.opponent_profiles.items()
        },
        hand_results_bb=hand_results_bb,
    )


def run_monte_carlo(
    scenario: TrainingScenario,
    *,
    games: int,
    seed: int = 0,
    rollout_count: int = 64,
    confidence: float = 0.95,
    bootstrap_samples: int = 2000,
) -> MonteCarloResult:
    """Average independent games with fresh profiles and rotated seats.

    Unlike ``run_scenario`` with multiple games, no opponent belief carries from
    one Monte Carlo trial into another. This estimates how a new table session
    adapts within its first fifty hands.
    """
    if games <= 0:
        raise ValueError("games must be positive")
    template = TrainingScenario(
        name=scenario.name,
        opponents=scenario.opponents,
        games=1,
        hands_per_game=scenario.hands_per_game,
        starting_chips=scenario.starting_chips,
        small_blind=scenario.small_blind,
    )
    started = time.perf_counter()
    trials = [
        run_scenario(
            template,
            seed=seed + index,
            rollout_count=rollout_count,
            seat_offset=index,
        )
        for index in range(games)
    ]
    total_hands = sum(trial.hands for trial in trials)
    all_results = [
        value
        for trial in trials
        for value in trial.hand_results_bb
    ]
    indexed: Dict[int, List[float]] = {}
    for trial in trials:
        for hand_index, value in enumerate(trial.hand_results_bb, start=1):
            indexed.setdefault(hand_index, []).append(value)
    hand_index_means = {
        index: sum(values) / len(values)
        for index, values in sorted(indexed.items())
    }

    early_values = [
        value
        for trial in trials
        for index, value in enumerate(trial.hand_results_bb, start=1)
        if 1 <= index <= 10
    ]
    late_values = [
        value
        for trial in trials
        for index, value in enumerate(trial.hand_results_bb, start=1)
        if 41 <= index <= 50
    ]
    early_bb100 = (
        sum(early_values) * 100.0 / len(early_values) if early_values else 0.0
    )
    late_bb100 = (
        sum(late_values) * 100.0 / len(late_values) if late_values else None
    )
    net_bb_rows = [
        {
            "game_id": index,
            "net_bb": sum(trial.hand_results_bb),
        }
        for index, trial in enumerate(trials)
    ]
    interval = cluster_bootstrap_ci(
        net_bb_rows,
        cluster_key="game_id",
        value_key="net_bb",
        confidence=confidence,
        samples=bootstrap_samples,
        seed=seed,
    )
    return MonteCarloResult(
        scenario_name=scenario.name,
        games_requested=games,
        games_completed=len(trials),
        games_reaching_hand_50=sum(trial.hands >= 50 for trial in trials),
        total_hands=total_hands,
        average_hands_per_game=total_hands / len(trials),
        game_win_rate=sum(trial.game_wins for trial in trials) / len(trials),
        game_tie_rate=sum(trial.game_ties for trial in trials) / len(trials),
        average_net_bb_per_game=sum(row["net_bb"] for row in net_bb_rows)
        / len(net_bb_rows),
        net_bb_confidence_interval=interval,
        aggregate_bb_per_100=(
            sum(all_results) * 100.0 / len(all_results) if all_results else 0.0
        ),
        hands_1_10_bb_per_100=early_bb100,
        hands_41_50_bb_per_100=late_bb100,
        adaptation_delta_bb_per_100=(
            late_bb100 - early_bb100 if late_bb100 is not None else None
        ),
        hand_index_mean_bb=hand_index_means,
        elapsed_seconds=time.perf_counter() - started,
    )


def run_suite(
    scenarios: Iterable[TrainingScenario],
    *,
    seed: int = 0,
    rollout_count: int = 64,
) -> SuiteResult:
    started = time.perf_counter()
    results = [
        run_scenario(
            scenario,
            seed=seed + index,
            rollout_count=rollout_count,
        )
        for index, scenario in enumerate(scenarios)
    ]
    return SuiteResult(
        seed=seed,
        scenarios=results,
        elapsed_seconds=time.perf_counter() - started,
    )


def default_scenarios(
    *,
    server_root: Path,
    games: int,
    hands_per_game: int,
) -> List[TrainingScenario]:
    """Build heads-up, homogeneous, and mixed scenarios for available agents."""
    simple = server_root / "models" / "simple_trained.pth"
    trained = server_root / "models" / "trained_vs_simple.pth"
    scenarios = [
        TrainingScenario(
            "heads_up_random",
            [OpponentSpec("random")],
            games,
            hands_per_game,
        ),
        TrainingScenario(
            "three_player_random",
            [OpponentSpec("random"), OpponentSpec("random")],
            games,
            hands_per_game,
        ),
        TrainingScenario(
            "six_player_random",
            [OpponentSpec("random") for _ in range(5)],
            games,
            hands_per_game,
        ),
    ]
    dqn_specs = [
        OpponentSpec("dqn", str(path), path.stem)
        for path in (simple, trained)
        if path.exists()
    ]
    for spec in dqn_specs:
        scenarios.append(
            TrainingScenario(
                f"heads_up_{Path(spec.model_path or '').stem}",
                [spec],
                games,
                hands_per_game,
            )
        )
    if dqn_specs:
        scenarios.extend(
            [
                TrainingScenario(
                    "four_player_mixed",
                    [OpponentSpec("random"), dqn_specs[0], OpponentSpec("random")],
                    games,
                    hands_per_game,
                ),
                TrainingScenario(
                    "six_player_mixed",
                    [
                        OpponentSpec("random"),
                        dqn_specs[0],
                        OpponentSpec("random"),
                        dqn_specs[-1],
                        OpponentSpec("random"),
                    ],
                    games,
                    hands_per_game,
                ),
            ]
        )
    return scenarios


def write_json_report(result: SuiteResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")


def write_markdown_report(result: SuiteResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Adaptive Training Suite Report",
        "",
        f"- Seed: `{result.seed}`",
        f"- Elapsed: `{result.elapsed_seconds:.2f}s`",
        "",
        "| Scenario | Players | Hands | Game wins | Win rate | bb/100 | Hands 1-10 bb/100 | Hands 41-50 bb/100 | Adaptation Δ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in result.scenarios:
        late_display = (
            f"{item.late_bb_per_100:.2f}"
            if item.has_hand_50_window
            else "N/A"
        )
        delta_display = (
            f"{item.adaptation_delta_bb_per_100:.2f}"
            if item.has_hand_50_window
            else "N/A"
        )
        lines.append(
            f"| {item.name} | {item.player_count} | {item.hands} | "
            f"{item.game_wins}/{item.games} | {item.game_win_rate:.1%} | "
            f"{item.bb_per_100:.2f} | {item.early_bb_per_100:.2f} | "
            f"{late_display} | {delta_display} |"
        )
    lines.extend(
        [
            "",
            "Short runs are smoke tests, not evidence of profitability. Use many",
            "independent matches and confidence intervals for release decisions.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_monte_carlo_reports(
    results: Sequence[MonteCarloResult],
    *,
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "results": [result.to_dict() for result in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        "# Adaptive Monte Carlo Report",
        "",
        "| Scenario | Games | Reached hand 50 | Avg hands | Win rate | Avg net bb/game | 95% CI | bb/100 | Hands 1-10 | Hands 41-50 | Adaptation Δ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        interval = result.net_bb_confidence_interval
        late = (
            f"{result.hands_41_50_bb_per_100:.2f}"
            if result.hands_41_50_bb_per_100 is not None
            else "N/A"
        )
        delta = (
            f"{result.adaptation_delta_bb_per_100:.2f}"
            if result.adaptation_delta_bb_per_100 is not None
            else "N/A"
        )
        lines.append(
            f"| {result.scenario_name} | {result.games_completed} | "
            f"{result.games_reaching_hand_50} | "
            f"{result.average_hands_per_game:.1f} | {result.game_win_rate:.1%} | "
            f"{result.average_net_bb_per_game:.2f} | "
            f"[{interval.lower:.2f}, {interval.upper:.2f}] | "
            f"{result.aggregate_bb_per_100:.2f} | "
            f"{result.hands_1_10_bb_per_100:.2f} | {late} | {delta} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def failing_scenarios(
    result: SuiteResult,
    *,
    minimum_late_bb_per_100: float,
    minimum_game_win_rate: float,
) -> List[str]:
    return [
        scenario.name
        for scenario in result.scenarios
        if not scenario.has_hand_50_window
        or scenario.late_bb_per_100 < minimum_late_bb_per_100
        or scenario.game_win_rate < minimum_game_win_rate
    ]
