"""Acceptance contract for full-trajectory, legally masked learning."""

from __future__ import annotations

import pytest

replay_module = pytest.importorskip(
    "app.training.replay",
    reason="Plan-compliant trajectory replay has not been implemented",
)

HandTrajectory = replay_module.HandTrajectory

pytestmark = pytest.mark.future_requirement


def test_every_decision_becomes_a_training_transition() -> None:
    trajectory = HandTrajectory(hand_id="h1", starting_stack=1000)
    for index, action in enumerate(["call", "check", "bet"]):
        trajectory.record_decision(
            observation={"step": index},
            opponent_context={"villain": {"hands_seen": 12}},
            legal_actions=["fold", "check", "call", "bet"],
            action=action,
            behavior_probability=0.25,
        )

    transitions = trajectory.finish(ending_stack=1120)

    assert len(transitions) == 3
    assert all(t.done is (index == 2) for index, t in enumerate(transitions))
    assert all(t.return_bb > 0 for t in transitions)


def test_behavior_probability_is_required_for_off_policy_data() -> None:
    trajectory = HandTrajectory(hand_id="h2", starting_stack=1000)

    with pytest.raises(ValueError, match="probability"):
        trajectory.record_decision(
            observation={"step": 0},
            opponent_context={},
            legal_actions=["fold", "call"],
            action="call",
            behavior_probability=None,
        )


def test_terminal_return_includes_blind_loss() -> None:
    trajectory = HandTrajectory(hand_id="h3", starting_stack=1000)
    trajectory.record_decision(
        observation={"step": 0},
        opponent_context={},
        legal_actions=["fold", "call"],
        action="fold",
        behavior_probability=0.5,
    )

    [transition] = trajectory.finish(ending_stack=990, big_blind=20)

    assert transition.return_bb == pytest.approx(-0.5)


def test_unavailable_action_has_zero_mask_value() -> None:
    trajectory = HandTrajectory(hand_id="h4", starting_stack=1000)
    trajectory.record_decision(
        observation={"step": 0},
        opponent_context={},
        legal_actions=["fold", "call"],
        action="call",
        behavior_probability=0.5,
    )

    [transition] = trajectory.finish(ending_stack=1000)

    assert transition.legal_action_mask["fold"]
    assert transition.legal_action_mask["call"]
    assert not transition.legal_action_mask["raise"]
