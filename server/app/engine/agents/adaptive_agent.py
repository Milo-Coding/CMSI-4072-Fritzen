"""Opponent-adaptive agent using causal action interventions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from ..card import Card
from ..causal.state import CausalPokerState
from ..causal.world_model import InterventionEstimate, PokerWorldModel
from ..opponents.profile import OpponentProfile
from ...training.replay import HandTrajectory, TrainingTransition
from .base_agent import AgentRegistry, BaseAgent


Decision = Union[str, Tuple[str, int]]


@AgentRegistry.register("adaptive")
class AdaptiveAgent(BaseAgent):
    """Plan legal actions with a causal world model and online opponent beliefs.

    The model updates interpretable opponent posteriors online. Neural weights are
    deliberately not modified during play; learned response mechanisms can be
    plugged into ``PokerWorldModel`` after suitable training data is available.
    """

    def __init__(
        self,
        *args,
        deterministic: bool = True,
        rollout_count: int = 128,
        uncertainty_penalty: float = 0.10,
        big_blind: int = 20,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if rollout_count <= 0:
            raise ValueError("rollout_count must be positive")
        self.deterministic = bool(deterministic)
        self.rollout_count = int(rollout_count)
        self.uncertainty_penalty = float(uncertainty_penalty)
        self.big_blind = max(1, int(big_blind))
        self.opponent_profiles: Dict[str, OpponentProfile] = {}
        self.world_model = PokerWorldModel(profiles=self.opponent_profiles)
        self.current_trajectory: Optional[HandTrajectory] = None
        self.completed_transitions: List[TrainingTransition] = []
        self.last_action_estimates: List[InterventionEstimate] = []
        self._observed_action_count = 0

    def on_hand_start(self, game_state: Dict[str, Any]) -> None:
        super().on_hand_start(game_state)
        hand_number = game_state.get("hand_number", self.hands_played)
        self.current_trajectory = HandTrajectory(
            hand_id=f"{self.player_id}:{hand_number}",
            starting_stack=self.chips,
        )
        self._observed_action_count = 0

    def on_hand_end(self, result: Dict[str, Any]) -> None:
        super().on_hand_end(result)
        if self.current_trajectory is not None:
            self.completed_transitions.extend(
                self.current_trajectory.finish(
                    ending_stack=self.chips,
                    big_blind=self.big_blind,
                )
            )
            self.current_trajectory = None

    def _profile_for(self, player_id: str) -> OpponentProfile:
        player_id = str(player_id)
        if player_id not in self.opponent_profiles:
            self.opponent_profiles[player_id] = OpponentProfile(player_id)
        return self.opponent_profiles[player_id]

    def _update_profiles(self, game_state: Mapping[str, Any]) -> None:
        history = list(game_state.get("action_history", []))
        new_actions = history[self._observed_action_count :]
        for action in new_actions:
            player_id = action.get("player_id")
            if player_id is None or str(player_id) == str(self.player_id):
                continue
            profile = self._profile_for(str(player_id))
            action_name = str(action.get("action", ""))
            street = str(action.get("street", game_state.get("state_name", "")))
            pot = max(1.0, float(action.get("pot", game_state.get("pot", 0))))
            amount = float(action.get("amount", 0))
            context = {
                "street": street,
                "size_bucket": round(amount / pot, 1),
            }
            profile.observe(
                "aggressive_action",
                action_name in {"bet", "raise", "all_in"},
                True,
                {"street": street},
            )
            if action_name == "fold":
                profile.observe("fold_to_bet", True, True, context)
        self._observed_action_count = len(history)

    def _hero_cards(self, game_state: Mapping[str, Any]) -> List[Any]:
        if self.hand:
            return list(self.hand)
        players = list(game_state.get("players", []))
        agent_index = int(game_state.get("agent_index", 0))
        if 0 <= agent_index < len(players):
            return list(players[agent_index].get("hand", []))
        return []

    def _candidate_actions(self, game_state: Mapping[str, Any]) -> List[Dict[str, Any]]:
        available = list(game_state.get("available_actions", []))
        pot = max(self.big_blind, int(game_state.get("pot", 0)))
        current_bet = int(game_state.get("current_table_bet", 0))
        players = list(game_state.get("players", []))
        agent_index = int(game_state.get("agent_index", 0))
        hero_current_bet = self.current_bet_in_round
        if 0 <= agent_index < len(players):
            hero_current_bet = int(
                players[agent_index].get("current_bet_in_round", hero_current_bet)
            )
        maximum_target = hero_current_bet + self.chips
        candidates: List[Dict[str, Any]] = []
        for action in available:
            if action == "bet":
                for amount in {
                    min(self.chips, max(self.big_blind, int(pot * fraction)))
                    for fraction in (0.33, 0.50, 0.75, 1.0)
                }:
                    if amount > 0:
                        candidates.append({"action": "bet", "amount": amount})
            elif action == "raise":
                minimum = current_bet + self.big_blind
                for target in {
                    minimum,
                    min(maximum_target, max(minimum, current_bet + int(pot * 0.5))),
                    min(maximum_target, max(minimum, current_bet + pot)),
                }:
                    if minimum <= target <= maximum_target:
                        candidates.append({"action": "raise", "amount": target})
            elif action == "all_in":
                candidates.append({"action": "all_in"})
            else:
                candidates.append({"action": action})
        return candidates

    def _causal_state(
        self,
        game_state: Mapping[str, Any],
        candidates: List[Dict[str, Any]],
    ) -> CausalPokerState:
        players = list(game_state.get("players", []))
        agent_index = int(game_state.get("agent_index", 0))
        opponents = []
        for index, player in enumerate(players):
            if index == agent_index or not player.get("is_playing_round", False):
                continue
            player_id = str(player.get("player_id"))
            self._profile_for(player_id)
            opponents.append(
                {
                    "player_id": player_id,
                    "stack": int(player.get("chips", 0)),
                    "is_playing_round": True,
                    "range": "all_legal_combinations",
                }
            )
        return CausalPokerState.from_dict(
            {
                "street": game_state.get("state_name", "Pre-Flop"),
                "hero_cards": self._hero_cards(game_state),
                "board": game_state.get("community_cards", []),
                "pot": game_state.get("pot", 0),
                "hero_stack": self.chips,
                "opponents": opponents,
                "amount_to_call": game_state.get("call_amount", 0),
                "legal_actions": candidates,
                "big_blind": game_state.get("big_blind", self.big_blind),
                "current_table_bet": game_state.get("current_table_bet", 0),
                "hero_current_bet": self.current_bet_in_round,
            }
        )

    @staticmethod
    def _decision(candidate: Mapping[str, Any]) -> Decision:
        action = str(candidate["action"])
        if action in {"bet", "raise"}:
            return action, int(candidate["amount"])
        return action

    def decide_action(self, game_state: Dict[str, Any]) -> Decision:
        available = list(game_state.get("available_actions", []))
        if not available:
            return "fold"
        self._update_profiles(game_state)
        candidates = self._candidate_actions(game_state)
        if not candidates:
            return "fold"

        state = self._causal_state(game_state, candidates)
        estimates = [
            self.world_model.evaluate_intervention(
                state,
                action=candidate,
                rollouts=self.rollout_count,
                exogenous_seed=0 if self.deterministic else None,
            )
            for candidate in candidates
        ]
        self.last_action_estimates = estimates
        selected_index = max(
            range(len(estimates)),
            key=lambda index: (
                estimates[index].expected_net_bb
                - self.uncertainty_penalty * estimates[index].epistemic_uncertainty,
                -index,
            ),
        )
        selected = candidates[selected_index]
        decision = self._decision(selected)

        if self.current_trajectory is not None:
            self.current_trajectory.record_decision(
                observation=deepcopy(game_state),
                opponent_context={
                    player_id: profile.to_dict()
                    for player_id, profile in self.opponent_profiles.items()
                },
                legal_actions=available,
                action=decision,
                # The current deterministic planner assigns all mass to its
                # selected action. Stochastic exploration must log its actual
                # propensity when added.
                behavior_probability=1.0,
            )
        return decision
