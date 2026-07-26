#!/usr/bin/env python3
"""Run independent adaptive-agent games and average their outcomes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.evaluation.training_suite import (
    default_scenarios,
    run_monte_carlo,
    write_monte_carlo_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monte Carlo evaluation of within-game adaptive learning",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--hands", type=int, default=50)
    parser.add_argument("--rollouts", type=int, default=64)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=4072)
    parser.add_argument(
        "--scenario",
        action="append",
        help="Scenario name to run; repeat for several. Defaults to all.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./reports/adaptive_monte_carlo"),
    )
    args = parser.parse_args()

    server_root = Path(__file__).parent.parent
    scenarios = default_scenarios(
        server_root=server_root,
        games=1,
        hands_per_game=args.hands,
    )
    if args.scenario:
        requested = set(args.scenario)
        scenarios = [scenario for scenario in scenarios if scenario.name in requested]
        missing = requested - {scenario.name for scenario in scenarios}
        if missing:
            parser.error(f"Unknown scenario(s): {', '.join(sorted(missing))}")

    results = [
        run_monte_carlo(
            scenario,
            games=args.games,
            seed=args.seed + index * args.games,
            rollout_count=args.rollouts,
            confidence=args.confidence,
            bootstrap_samples=args.bootstrap_samples,
        )
        for index, scenario in enumerate(scenarios)
    ]
    write_monte_carlo_reports(
        results,
        json_path=args.output_dir / "results.json",
        markdown_path=args.output_dir / "report.md",
    )
    for result in results:
        interval = result.net_bb_confidence_interval
        print(
            f"{result.scenario_name}: games={result.games_completed}, "
            f"win_rate={result.game_win_rate:.1%}, "
            f"avg_net_bb={result.average_net_bb_per_game:.2f}, "
            f"CI=[{interval.lower:.2f}, {interval.upper:.2f}], "
            f"bb/100={result.aggregate_bb_per_100:.2f}, "
            f"adaptation_delta={result.adaptation_delta_bb_per_100}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
