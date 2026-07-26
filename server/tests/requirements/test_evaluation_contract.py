"""Statistical contracts for the future 50-hand evaluation harness."""

from __future__ import annotations

import math

import pytest

metrics_module = pytest.importorskip(
    "app.evaluation.metrics",
    reason="Evaluation metrics have not been implemented",
)

pytestmark = pytest.mark.future_requirement


def test_bb_per_100_is_blind_normalized() -> None:
    assert metrics_module.bb_per_100(
        net_chips=200,
        big_blind=20,
        hands=100,
    ) == pytest.approx(10.0)


def test_match_cluster_bootstrap_is_reproducible() -> None:
    matches = [
        {"match_id": f"m{i}", "net_bb": float((i % 5) - 1)}
        for i in range(100)
    ]

    first = metrics_module.cluster_bootstrap_ci(
        matches,
        cluster_key="match_id",
        value_key="net_bb",
        confidence=0.95,
        samples=1000,
        seed=42,
    )
    second = metrics_module.cluster_bootstrap_ci(
        matches,
        cluster_key="match_id",
        value_key="net_bb",
        confidence=0.95,
        samples=1000,
        seed=42,
    )

    assert first == second
    assert first.lower <= first.mean <= first.upper


def test_adaptation_windows_are_disjoint() -> None:
    hands = [{"hand_number": i, "net_bb": i / 100} for i in range(1, 51)]

    windows = metrics_module.adaptation_windows(hands)

    assert [row["hand_number"] for row in windows["early"]] == list(range(1, 11))
    assert [row["hand_number"] for row in windows["late"]] == list(range(41, 51))


def test_profitability_gate_requires_confidence_interval_above_zero() -> None:
    passing = metrics_module.ProfitabilityResult(mean=1.5, lower=0.1, upper=2.9)
    inconclusive = metrics_module.ProfitabilityResult(
        mean=1.5, lower=-0.1, upper=3.1
    )

    assert metrics_module.passes_positive_ev_gate(passing)
    assert not metrics_module.passes_positive_ev_gate(inconclusive)


def test_doubly_robust_estimator_recovers_simple_known_effect() -> None:
    off_policy = pytest.importorskip(
        "app.evaluation.off_policy",
        reason="Off-policy evaluation has not been implemented",
    )
    rows = []
    for index in range(2000):
        action = "bet" if index % 2 == 0 else "check"
        outcome = 2.0 if action == "bet" else 0.0
        rows.append(
            {
                "action": action,
                "outcome": outcome,
                "behavior_probability": 0.5,
                "predicted_bet_outcome": 2.0,
                "predicted_check_outcome": 0.0,
            }
        )

    estimate = off_policy.doubly_robust_action_effect(
        rows,
        treatment="bet",
        control="check",
    )

    assert math.isfinite(estimate)
    assert estimate == pytest.approx(2.0, abs=0.05)
