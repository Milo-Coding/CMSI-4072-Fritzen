"""Tests for adaptive heads-up, multiplayer, and mixed-table training."""

from __future__ import annotations

import json
from pathlib import Path

from app.evaluation.training_suite import (
    OpponentSpec,
    TrainingScenario,
    default_scenarios,
    failing_scenarios,
    run_monte_carlo,
    run_scenario,
    run_suite,
    write_json_report,
    write_markdown_report,
    write_monte_carlo_reports,
)


def test_heads_up_training_smoke() -> None:
    result = run_scenario(
        TrainingScenario(
            name="heads_up_smoke",
            opponents=[OpponentSpec("random")],
            games=2,
            hands_per_game=3,
        ),
        seed=11,
        rollout_count=4,
    )

    assert result.player_count == 2
    assert result.games == 2
    assert 1 <= result.hands <= 6
    assert len(result.hand_results_bb) == result.hands
    assert 0.0 <= result.game_win_rate <= 1.0
    assert result.hands_per_second > 0.0


def test_large_random_table_training_smoke() -> None:
    result = run_scenario(
        TrainingScenario(
            name="large_smoke",
            opponents=[OpponentSpec("random") for _ in range(5)],
            games=2,
            hands_per_game=2,
        ),
        seed=12,
        rollout_count=2,
    )

    assert result.player_count == 6
    assert result.opponent_types == ["random"] * 5
    assert len(result.profiles) == 5


def test_mixed_table_preserves_composition(tmp_path: Path) -> None:
    # An adaptive opponent exercises heterogeneous construction without requiring
    # a model checkpoint in this unit test.
    scenario = TrainingScenario(
        name="mixed_smoke",
        opponents=[
            OpponentSpec("random"),
            OpponentSpec("adaptive"),
            OpponentSpec("random"),
        ],
        games=1,
        hands_per_game=2,
    )

    result = run_scenario(scenario, seed=13, rollout_count=2)

    assert result.player_count == 4
    assert result.opponent_types == ["random", "adaptive", "random"]


def test_default_suite_contains_required_table_shapes() -> None:
    scenarios = default_scenarios(
        server_root=Path(__file__).parents[2],
        games=1,
        hands_per_game=1,
    )
    names = {scenario.name for scenario in scenarios}

    assert "heads_up_random" in names
    assert "three_player_random" in names
    assert "six_player_random" in names
    assert "four_player_mixed" in names
    assert "six_player_mixed" in names
    assert any(name.startswith("heads_up_simple_trained") for name in names)
    assert any(name.startswith("heads_up_trained_vs_simple") for name in names)


def test_reports_are_machine_and_human_readable(tmp_path: Path) -> None:
    suite = run_suite(
        [
            TrainingScenario(
                "report_smoke",
                [OpponentSpec("random")],
                games=1,
                hands_per_game=2,
            )
        ],
        seed=14,
        rollout_count=2,
    )
    json_path = tmp_path / "results.json"
    markdown_path = tmp_path / "report.md"

    write_json_report(suite, json_path)
    write_markdown_report(suite, markdown_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["scenarios"][0]["name"] == "report_smoke"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Hands 1-10 bb/100" in markdown
    assert "Hands 41-50 bb/100" in markdown
    assert "Adaptation" in markdown


def test_strict_gate_identifies_underperforming_scenario() -> None:
    suite = run_suite(
        [
            TrainingScenario(
                "gate_smoke",
                [OpponentSpec("random")],
                games=1,
                hands_per_game=1,
            )
        ],
        seed=15,
        rollout_count=2,
    )

    failures = failing_scenarios(
        suite,
        minimum_late_bb_per_100=1_000_000.0,
        minimum_game_win_rate=1.1,
    )

    assert failures == ["gate_smoke"]


def test_monte_carlo_averages_independent_games_and_rotates_seats() -> None:
    scenario = TrainingScenario(
        "monte_carlo_smoke",
        [OpponentSpec("random")],
        games=1,
        hands_per_game=3,
    )

    result = run_monte_carlo(
        scenario,
        games=4,
        seed=101,
        rollout_count=2,
        bootstrap_samples=100,
    )

    assert result.games_requested == 4
    assert result.games_completed == 4
    assert result.games_reaching_hand_50 == 0
    assert 0 < result.total_hands <= 12
    assert result.average_hands_per_game == result.total_hands / 4
    assert 0.0 <= result.game_win_rate <= 1.0
    assert result.net_bb_confidence_interval.lower <= (
        result.net_bb_confidence_interval.mean
    )
    assert result.net_bb_confidence_interval.mean <= (
        result.net_bb_confidence_interval.upper
    )
    assert set(result.hand_index_mean_bb).issubset({1, 2, 3})
    assert result.hands_41_50_bb_per_100 is None


def test_monte_carlo_is_reproducible_for_same_seed() -> None:
    scenario = TrainingScenario(
        "reproducible",
        [OpponentSpec("random")],
        games=1,
        hands_per_game=2,
    )
    first = run_monte_carlo(
        scenario,
        games=3,
        seed=202,
        rollout_count=2,
        bootstrap_samples=50,
    )
    second = run_monte_carlo(
        scenario,
        games=3,
        seed=202,
        rollout_count=2,
        bootstrap_samples=50,
    )

    assert first.game_win_rate == second.game_win_rate
    assert first.average_net_bb_per_game == second.average_net_bb_per_game
    assert first.hand_index_mean_bb == second.hand_index_mean_bb
    assert (
        first.net_bb_confidence_interval
        == second.net_bb_confidence_interval
    )


def test_monte_carlo_reports_include_average_and_confidence_interval(
    tmp_path: Path,
) -> None:
    result = run_monte_carlo(
        TrainingScenario(
            "report_monte_carlo",
            [OpponentSpec("random")],
            games=1,
            hands_per_game=2,
        ),
        games=2,
        seed=303,
        rollout_count=2,
        bootstrap_samples=50,
    )
    json_path = tmp_path / "mc.json"
    markdown_path = tmp_path / "mc.md"

    write_monte_carlo_reports(
        [result],
        json_path=json_path,
        markdown_path=markdown_path,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["results"][0]["games_completed"] == 2
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Avg net bb/game" in markdown
    assert "95% CI" in markdown
