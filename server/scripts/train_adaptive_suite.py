#!/usr/bin/env python3
"""Run the adaptive agent against heads-up, multiplayer, and mixed tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.evaluation.training_suite import (
    default_scenarios,
    failing_scenarios,
    run_suite,
    write_json_report,
    write_markdown_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train and evaluate the adaptive agent across opponent suites",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--hands", type=int, default=50)
    parser.add_argument("--rollouts", type=int, default=64)
    parser.add_argument("--seed", type=int, default=4072)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./reports/adaptive_training"),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero if any scenario misses the configured gates",
    )
    parser.add_argument("--minimum-late-bb100", type=float, default=0.0)
    parser.add_argument("--minimum-game-win-rate", type=float, default=0.0)
    args = parser.parse_args()

    server_root = Path(__file__).parent.parent
    scenarios = default_scenarios(
        server_root=server_root,
        games=args.games,
        hands_per_game=args.hands,
    )
    result = run_suite(
        scenarios,
        seed=args.seed,
        rollout_count=args.rollouts,
    )
    json_path = args.output_dir / "results.json"
    markdown_path = args.output_dir / "report.md"
    write_json_report(result, json_path)
    write_markdown_report(result, markdown_path)

    for scenario in result.scenarios:
        print(
            f"{scenario.name}: hands={scenario.hands}, "
            f"wins={scenario.game_wins}/{scenario.games}, "
            f"bb/100={scenario.bb_per_100:.2f}, "
            f"late={scenario.late_bb_per_100:.2f}, "
            f"adaptation_delta={scenario.adaptation_delta_bb_per_100:.2f}"
        )
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")

    failures = failing_scenarios(
        result,
        minimum_late_bb_per_100=args.minimum_late_bb100,
        minimum_game_win_rate=args.minimum_game_win_rate,
    )
    if args.strict and failures:
        print(f"Failed scenarios: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
