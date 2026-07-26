"""Blind-normalized, match-clustered evaluation metrics."""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence


@dataclass(frozen=True)
class ProfitabilityResult:
    mean: float
    lower: float
    upper: float


def bb_per_100(*, net_chips: float, big_blind: float, hands: int) -> float:
    if big_blind <= 0:
        raise ValueError("big_blind must be positive")
    if hands <= 0:
        raise ValueError("hands must be positive")
    return (float(net_chips) / float(big_blind)) * (100.0 / hands)


def _percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot calculate a percentile of no values")
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def cluster_bootstrap_ci(
    rows: Sequence[Mapping[str, Any]],
    *,
    cluster_key: str,
    value_key: str,
    confidence: float = 0.95,
    samples: int = 2000,
    seed: int = 0,
) -> ProfitabilityResult:
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between zero and one")
    if samples <= 0:
        raise ValueError("samples must be positive")
    clusters: Dict[Any, List[float]] = {}
    for row in rows:
        clusters.setdefault(row[cluster_key], []).append(float(row[value_key]))
    if not clusters:
        raise ValueError("At least one cluster is required")
    cluster_values = [sum(values) for values in clusters.values()]
    observed = statistics.mean(cluster_values)
    rng = random.Random(seed)
    bootstrap_means = [
        statistics.mean(rng.choices(cluster_values, k=len(cluster_values)))
        for _ in range(samples)
    ]
    tail = (1.0 - confidence) / 2.0
    return ProfitabilityResult(
        mean=observed,
        lower=_percentile(bootstrap_means, tail),
        upper=_percentile(bootstrap_means, 1.0 - tail),
    )


def adaptation_windows(
    hands: Iterable[Mapping[str, Any]],
) -> Dict[str, List[Mapping[str, Any]]]:
    ordered = sorted(hands, key=lambda row: int(row["hand_number"]))
    return {
        "early": [row for row in ordered if 1 <= int(row["hand_number"]) <= 10],
        "late": [row for row in ordered if 41 <= int(row["hand_number"]) <= 50],
    }


def passes_positive_ev_gate(result: ProfitabilityResult) -> bool:
    return result.lower > 0.0
