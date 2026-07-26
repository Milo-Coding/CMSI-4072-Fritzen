"""Hybrid rules-based causal world model.

Known poker mechanisms are computed directly. Opponent response probabilities are
currently driven by Bayesian profiles or conservative population priors; learned
response-model checkpoints can replace that mechanism without changing the
intervention API.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from ..card import Card
from ..evaluator import HandRank, evaluate_best_five
from ..opponents.profile import OpponentProfile
from .state import CausalPokerState


@dataclass(frozen=True)
class InterventionEstimate:
    action: str
    amount: int
    expected_net_bb: float
    expected_gross_pot_share: float
    probability_fold_win: float
    probability_showdown: float
    showdown_equity: float
    epistemic_uncertainty: float
    out_of_support: bool = False


class PokerWorldModel:
    """Evaluate legal action interventions under the current public state."""

    def __init__(
        self,
        *,
        seed: int = 0,
        profiles: Optional[Mapping[str, OpponentProfile]] = None,
        synthetic_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    ):
        self.seed = int(seed)
        self.profiles = dict(profiles or {})
        self._synthetic_rows = list(synthetic_rows or [])

    @classmethod
    def deterministic_test_model(cls, seed: int = 0) -> "PokerWorldModel":
        return cls(seed=seed)

    @classmethod
    def synthetic_confounding_fixture(
        cls,
        observational_rows: Sequence[Mapping[str, Any]],
    ) -> "PokerWorldModel":
        return cls(synthetic_rows=observational_rows)

    @staticmethod
    def _normalize_action(action: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "action": str(action.get("action", "")),
            "amount": max(0, int(action.get("amount", 0))),
        }

    def _validate_action(
        self,
        state: CausalPokerState,
        action: Mapping[str, Any],
    ) -> Dict[str, Any]:
        candidate = self._normalize_action(action)
        for legal in state.legal_actions:
            normalized_legal = self._normalize_action(legal)
            if candidate["action"] != normalized_legal["action"]:
                continue
            if candidate["action"] not in {"bet", "raise"}:
                return candidate
            if candidate["amount"] == normalized_legal["amount"]:
                return candidate
        raise ValueError(f"Action intervention is not legal: {candidate}")

    @staticmethod
    def _cards(cards: Iterable[tuple[str, int]]) -> list[Card]:
        return [Card(suit, value) for suit, value in cards]

    def _showdown_equity(self, state: CausalPokerState) -> float:
        cards = self._cards(state.hero_cards + state.board)
        if len(cards) >= 5:
            rank, kickers = evaluate_best_five(cards)
            # A made royal/ace-high straight flush cannot lose.
            if rank == HandRank.STRAIGHT_FLUSH and kickers and kickers[0] == 14:
                return 1.0
            rank_component = (float(rank) - 1.0) / 8.0
            kicker_component = (kickers[0] / 14.0) if kickers else 0.0
            return min(0.99, max(0.01, 0.75 * rank_component + 0.25 * kicker_component))

        if len(state.hero_cards) == 2:
            values = sorted((card[1] for card in state.hero_cards), reverse=True)
            paired = values[0] == values[1]
            suited = state.hero_cards[0][0] == state.hero_cards[1][0]
            connected = abs(values[0] - values[1]) <= 2
            equity = (values[0] + values[1]) / 40.0
            equity += 0.18 if paired else 0.0
            equity += 0.04 if suited else 0.0
            equity += 0.03 if connected else 0.0
            return min(0.90, max(0.10, equity))
        return 0.5

    def _fold_probability(
        self,
        state: CausalPokerState,
        amount: int,
    ) -> tuple[float, float]:
        active = [opponent for opponent in state.opponents if opponent.get("is_playing_round", True)]
        if not active:
            return 1.0, 0.0
        pot_fraction = amount / max(1.0, float(state.pot))
        all_fold = 1.0
        uncertainty = 0.0
        for opponent in active:
            profile = self.profiles.get(str(opponent.get("player_id")))
            if profile:
                estimate = profile.estimate(
                    "fold_to_bet",
                    {"street": state.street, "size_bucket": round(pot_fraction, 1)},
                )
                fold = estimate.mean
                uncertainty += estimate.uncertainty
            else:
                # Conservative population prior with a monotonic sizing response.
                fold = min(0.70, max(0.15, 0.28 + 0.18 * pot_fraction))
                uncertainty += 0.20
            all_fold *= fold
        return all_fold, uncertainty / len(active)

    def evaluate_intervention(
        self,
        state: CausalPokerState,
        *,
        action: Mapping[str, Any],
        rollouts: int = 128,
        exogenous_seed: Optional[int] = None,
    ) -> InterventionEstimate:
        """Estimate net value under ``do(hero_action = action)``."""
        if rollouts <= 0:
            raise ValueError("rollouts must be positive")
        candidate = self._validate_action(state, action)
        action_name = candidate["action"]
        amount = candidate["amount"]
        big_blind = float(state.big_blind)
        equity = self._showdown_equity(state)

        if action_name == "fold":
            return InterventionEstimate(
                action=action_name,
                amount=0,
                expected_net_bb=0.0,
                expected_gross_pot_share=0.0,
                probability_fold_win=0.0,
                probability_showdown=0.0,
                showdown_equity=0.0,
                epistemic_uncertainty=0.0,
            )

        contribution = 0
        fold_win_probability = 0.0
        response_uncertainty = 0.0
        if action_name == "call":
            contribution = min(state.hero_stack, state.amount_to_call)
        elif action_name in {"bet", "raise", "all_in"}:
            if action_name == "all_in":
                amount = state.hero_current_bet + state.hero_stack
            contribution = min(
                state.hero_stack,
                max(0, amount - state.hero_current_bet),
            )
            fold_win_probability, response_uncertainty = self._fold_probability(
                state, contribution
            )

        showdown_probability = 1.0 - fold_win_probability
        called_pot = state.pot + contribution
        # Approximate one matching opponent contribution. The known engine is
        # authoritative once multi-street rollouts are implemented.
        if action_name in {"bet", "raise", "all_in"} and state.opponents:
            called_pot += contribution
        gross_share = (
            fold_win_probability * state.pot
            + showdown_probability * equity * called_pot
        )
        net_chips = gross_share - contribution

        # Seed is consumed to make paired counterfactual API semantics explicit.
        random.Random(self.seed if exogenous_seed is None else exogenous_seed).random()
        return InterventionEstimate(
            action=action_name,
            amount=amount,
            expected_net_bb=net_chips / big_blind,
            expected_gross_pot_share=gross_share,
            probability_fold_win=fold_win_probability,
            probability_showdown=showdown_probability,
            showdown_equity=equity,
            epistemic_uncertainty=response_uncertainty + 1.0 / math.sqrt(rollouts),
        )

    def estimate_action_effects(
        self,
        *,
        context: Mapping[str, Any],
    ) -> Dict[str, InterventionEstimate]:
        """Estimate stratified effects for synthetic/off-policy diagnostics."""
        strength = context.get("strength")
        rows = [row for row in self._synthetic_rows if row.get("strength") == strength]
        actions = {"fold", "check", "call", "bet", "raise"}
        actions.update(str(row.get("action")) for row in self._synthetic_rows)
        estimates: Dict[str, InterventionEstimate] = {}
        for action in actions:
            selected = [row for row in rows if row.get("action") == action]
            count = sum(int(row.get("count", 1)) for row in selected)
            if count:
                mean = sum(
                    float(row["net_bb"]) * int(row.get("count", 1))
                    for row in selected
                ) / count
                uncertainty = 1.0 / math.sqrt(count)
            else:
                mean = 0.0
                uncertainty = 1.0
            estimates[action] = InterventionEstimate(
                action=action,
                amount=0,
                expected_net_bb=mean,
                expected_gross_pot_share=0.0,
                probability_fold_win=0.0,
                probability_showdown=0.0,
                showdown_equity=0.0,
                epistemic_uncertainty=uncertainty,
                out_of_support=count == 0,
            )
        return estimates
