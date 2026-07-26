"""Bayesian, context-aware opponent tendency tracking.

The profile stores opportunities and outcomes rather than bare rates. Beta priors
keep estimates finite during the first hands and expose uncertainty to policies.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, Optional, Tuple


DEFAULT_PRIORS: Dict[str, Tuple[float, float]] = {
    "vpip": (3.0, 7.0),
    "preflop_raise": (2.0, 8.0),
    "fold_to_bet": (4.0, 6.0),
    "fold_to_flop_bet": (4.0, 6.0),
    "river_bet": (3.0, 7.0),
    "aggressive_action": (3.0, 7.0),
}
FALLBACK_PRIOR = (2.0, 2.0)


@dataclass(frozen=True)
class OpponentEstimate:
    """Posterior summary suitable for policy features and diagnostics."""

    mean: float
    uncertainty: float
    opportunities: int
    successes: int
    alpha: float
    beta: float


@dataclass
class _BetaEvidence:
    alpha_prior: float
    beta_prior: float
    successes: int = 0
    failures: int = 0

    @property
    def opportunities(self) -> int:
        return self.successes + self.failures

    def estimate(self) -> OpponentEstimate:
        alpha = self.alpha_prior + self.successes
        beta = self.beta_prior + self.failures
        total = alpha + beta
        variance = alpha * beta / (total * total * (total + 1.0))
        return OpponentEstimate(
            mean=alpha / total,
            uncertainty=math.sqrt(variance),
            opportunities=self.opportunities,
            successes=self.successes,
            alpha=alpha,
            beta=beta,
        )


class OpponentProfile:
    """Persistent posterior beliefs for one opponent.

    Estimates are stored globally and for each supplied context. A contextual
    query falls back to the global posterior when that exact context has no
    evidence, which is useful during the first fifty hands.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        player_id: str,
        priors: Optional[Mapping[str, Tuple[float, float]]] = None,
    ):
        self.player_id = str(player_id)
        self._priors = dict(DEFAULT_PRIORS)
        if priors:
            self._priors.update(priors)
        self._evidence: Dict[str, _BetaEvidence] = {}

    @staticmethod
    def _context_key(context: Optional[Mapping[str, Any]]) -> str:
        if not context:
            return "*"
        return json.dumps(dict(context), sort_keys=True, separators=(",", ":"), default=str)

    def _prior_for(self, statistic: str) -> Tuple[float, float]:
        alpha, beta = self._priors.get(statistic, FALLBACK_PRIOR)
        if alpha <= 0 or beta <= 0:
            raise ValueError("Beta priors must be positive")
        return float(alpha), float(beta)

    def _key(self, statistic: str, context: Optional[Mapping[str, Any]]) -> str:
        return f"{statistic}|{self._context_key(context)}"

    def _bucket(
        self,
        statistic: str,
        context: Optional[Mapping[str, Any]],
    ) -> _BetaEvidence:
        key = self._key(statistic, context)
        if key not in self._evidence:
            alpha, beta = self._prior_for(statistic)
            self._evidence[key] = _BetaEvidence(alpha, beta)
        return self._evidence[key]

    def observe(
        self,
        statistic: str,
        occurred: bool,
        opportunity: bool = True,
        context: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Record one publicly observed opportunity and outcome."""
        if not opportunity:
            return
        for selected_context in (None, context):
            bucket = self._bucket(statistic, selected_context)
            if occurred:
                bucket.successes += 1
            else:
                bucket.failures += 1
            if context is None:
                break

    def estimate(
        self,
        statistic: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> OpponentEstimate:
        """Return a contextual posterior, falling back to global evidence."""
        contextual_key = self._key(statistic, context)
        if context and contextual_key not in self._evidence:
            return self._bucket(statistic, None).estimate()
        return self._bucket(statistic, context).estimate()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "player_id": self.player_id,
            "priors": {key: list(value) for key, value in self._priors.items()},
            "evidence": {
                key: asdict(value)
                for key, value in sorted(self._evidence.items())
            },
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OpponentProfile":
        if payload.get("schema_version") != cls.SCHEMA_VERSION:
            raise ValueError("Unsupported opponent-profile schema version")
        profile = cls(
            player_id=str(payload["player_id"]),
            priors={
                key: (float(value[0]), float(value[1]))
                for key, value in payload.get("priors", {}).items()
            },
        )
        profile._evidence = {
            key: _BetaEvidence(
                alpha_prior=float(value["alpha_prior"]),
                beta_prior=float(value["beta_prior"]),
                successes=int(value["successes"]),
                failures=int(value["failures"]),
            )
            for key, value in payload.get("evidence", {}).items()
        }
        return profile
