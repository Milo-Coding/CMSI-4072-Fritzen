"""Action-selection contracts for legal tokens and wager bounds."""

from __future__ import annotations

from copy import deepcopy


def _action_type(decision):
    return decision[0] if isinstance(decision, tuple) else decision


def test_dqn_returns_only_an_available_action(dqn_agent, heads_up_state) -> None:
    """Inference must never emit an action outside the engine-provided mask."""
    for _ in range(100):
        decision = dqn_agent.decide_action(heads_up_state)
        assert _action_type(decision) in heads_up_state["available_actions"]


def test_dqn_raise_target_stays_within_stack(dqn_agent, heads_up_state) -> None:
    """Any emitted raise target must be reachable with the current stack."""
    state = deepcopy(heads_up_state)
    state["available_actions"] = ["raise"]
    hero = state["players"][state["agent_index"]]
    maximum_target = dqn_agent.chips + hero["current_bet_in_round"]

    for _ in range(25):
        decision = dqn_agent.decide_action(state)
        assert isinstance(decision, tuple)
        assert decision[0] == "raise"
        assert state["current_table_bet"] < decision[1] <= maximum_target


def test_dqn_single_legal_action_is_deterministic(dqn_agent, heads_up_state) -> None:
    """A legal mask with one action must not trigger a random fallback."""
    state = deepcopy(heads_up_state)
    state["available_actions"] = ["call"]

    decisions = [dqn_agent.decide_action(state) for _ in range(50)]

    assert decisions == ["call"] * 50
