"""Off-policy estimators for logged poker decisions."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def doubly_robust_action_value(
    rows: Sequence[Mapping[str, Any]],
    *,
    action: str,
) -> float:
    if not rows:
        raise ValueError("At least one logged decision is required")
    prediction_key = f"predicted_{action}_outcome"
    values = []
    for row in rows:
        propensity = float(row["behavior_probability"])
        if not 0.0 < propensity <= 1.0:
            raise ValueError("Behavior probabilities must be in (0, 1]")
        prediction = float(row[prediction_key])
        correction = 0.0
        if row["action"] == action:
            correction = (float(row["outcome"]) - prediction) / propensity
        values.append(prediction + correction)
    return sum(values) / len(values)


def doubly_robust_action_effect(
    rows: Sequence[Mapping[str, Any]],
    *,
    treatment: str,
    control: str,
) -> float:
    return doubly_robust_action_value(
        rows, action=treatment
    ) - doubly_robust_action_value(rows, action=control)
