"""Reproducible profitability and causal-policy evaluation utilities."""

from .metrics import (
    ProfitabilityResult,
    adaptation_windows,
    bb_per_100,
    cluster_bootstrap_ci,
    passes_positive_ev_gate,
)

__all__ = [
    "ProfitabilityResult",
    "adaptation_windows",
    "bb_per_100",
    "cluster_bootstrap_ci",
    "passes_positive_ev_gate",
]
