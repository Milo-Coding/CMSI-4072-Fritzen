"""Complete per-hand trajectory collection with legal masks and propensities."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence


ACTION_SCHEMA = ("fold", "check", "call", "bet", "raise", "all_in")


@dataclass(frozen=True)
class TrainingTransition:
    observation: Dict[str, Any]
    opponent_context: Dict[str, Any]
    legal_action_mask: Dict[str, bool]
    action: str
    behavior_probability: float
    return_bb: float
    next_observation: Optional[Dict[str, Any]]
    done: bool


@dataclass
class _Decision:
    observation: Dict[str, Any]
    opponent_context: Dict[str, Any]
    legal_action_mask: Dict[str, bool]
    action: str
    behavior_probability: float


class HandTrajectory:
    """Collect every decision and assign terminal chip utility to each one."""

    def __init__(self, hand_id: str, starting_stack: int):
        self.hand_id = str(hand_id)
        self.starting_stack = int(starting_stack)
        self._decisions: List[_Decision] = []
        self._finished = False

    def record_decision(
        self,
        *,
        observation: Mapping[str, Any],
        opponent_context: Mapping[str, Any],
        legal_actions: Sequence[str],
        action: str,
        behavior_probability: Optional[float],
    ) -> None:
        if self._finished:
            raise RuntimeError("Cannot append to a finished hand trajectory")
        if behavior_probability is None or not 0.0 < behavior_probability <= 1.0:
            raise ValueError("A behavior probability in (0, 1] is required")
        action_type = action[0] if isinstance(action, tuple) else str(action)
        legal = set(legal_actions)
        if action_type not in legal:
            raise ValueError("Recorded action must be legal")
        self._decisions.append(
            _Decision(
                observation=deepcopy(dict(observation)),
                opponent_context=deepcopy(dict(opponent_context)),
                legal_action_mask={
                    candidate: candidate in legal for candidate in ACTION_SCHEMA
                },
                action=action_type,
                behavior_probability=float(behavior_probability),
            )
        )

    def finish(
        self,
        *,
        ending_stack: int,
        big_blind: int = 20,
    ) -> List[TrainingTransition]:
        if self._finished:
            raise RuntimeError("Trajectory has already been finished")
        if big_blind <= 0:
            raise ValueError("big_blind must be positive")
        self._finished = True
        terminal_return = (int(ending_stack) - self.starting_stack) / float(big_blind)
        transitions = []
        for index, decision in enumerate(self._decisions):
            next_observation = (
                deepcopy(self._decisions[index + 1].observation)
                if index + 1 < len(self._decisions)
                else None
            )
            transitions.append(
                TrainingTransition(
                    observation=deepcopy(decision.observation),
                    opponent_context=deepcopy(decision.opponent_context),
                    legal_action_mask=dict(decision.legal_action_mask),
                    action=decision.action,
                    behavior_probability=decision.behavior_probability,
                    return_bb=terminal_return,
                    next_observation=next_observation,
                    done=index == len(self._decisions) - 1,
                )
            )
        return transitions
