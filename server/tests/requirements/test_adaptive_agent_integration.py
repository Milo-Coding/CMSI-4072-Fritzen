"""Integration tests for the first functional adaptive-agent vertical slice."""

from __future__ import annotations

from app.engine import Game
from app.engine.agents import AdaptiveAgent, AgentRegistry
from app.models.schemas import AddAIRequest


def test_adaptive_agent_is_registered() -> None:
    assert "adaptive" in AgentRegistry.list_agents()
    agent = AgentRegistry.create(
        "adaptive",
        name="Adaptive",
        chips=1000,
        player_id="adaptive",
    )
    assert isinstance(agent, AdaptiveAgent)


def test_add_ai_schema_accepts_adaptive_without_checkpoint() -> None:
    request = AddAIRequest(ai_type="adaptive")
    assert request.ai_type == "adaptive"
    assert request.dqn_model_path is None


def test_adaptive_agent_completes_hands_and_collects_all_transitions() -> None:
    adaptive = AdaptiveAgent(
        name="Adaptive",
        chips=1000,
        player_id="adaptive",
        rollout_count=16,
    )
    opponent = AgentRegistry.create(
        "random",
        name="Opponent",
        chips=1000,
        player_id="opponent",
    )
    game = Game([adaptive, opponent], small_blind=10, big_blind=20)

    decisions_before = len(adaptive.completed_transitions)
    game.play_hand()

    assert adaptive.hands_played == 1
    assert len(adaptive.completed_transitions) >= decisions_before
    assert all(
        transition.behavior_probability == 1.0
        for transition in adaptive.completed_transitions
    )
    assert all(
        transition.action
        in {
            action
            for action, legal in transition.legal_action_mask.items()
            if legal
        }
        for transition in adaptive.completed_transitions
    )


def test_adaptive_agent_updates_only_opponent_profile() -> None:
    adaptive = AdaptiveAgent(
        name="Adaptive",
        chips=1000,
        player_id="adaptive",
        rollout_count=8,
    )
    state = {
        "state_name": "Flop",
        "available_actions": ["check"],
        "call_amount": 0,
        "current_table_bet": 0,
        "pot": 100,
        "community_cards": [],
        "dealer_index": 0,
        "agent_index": 0,
        "players": [
            {
                "player_id": "adaptive",
                "chips": 1000,
                "is_playing_round": True,
                "current_bet_in_round": 0,
            },
            {
                "player_id": "opponent",
                "chips": 1000,
                "is_playing_round": True,
                "current_bet_in_round": 0,
            },
        ],
        "action_history": [
            {
                "player_id": "opponent",
                "action": "raise",
                "amount": 75,
                "pot": 100,
                "street": "Flop",
            }
        ],
    }

    adaptive.decide_action(state)

    assert set(adaptive.opponent_profiles) == {"opponent"}
    aggression = adaptive.opponent_profiles["opponent"].estimate(
        "aggressive_action", {"street": "Flop"}
    )
    assert aggression.opportunities == 1
    assert aggression.successes == 1


def test_adaptive_agent_counts_fold_and_non_fold_responses() -> None:
    adaptive = AdaptiveAgent(
        name="Adaptive",
        chips=1000,
        player_id="adaptive",
        rollout_count=2,
    )
    base_state = {
        "state_name": "Flop",
        "available_actions": ["check"],
        "call_amount": 0,
        "current_table_bet": 0,
        "pot": 100,
        "community_cards": [],
        "dealer_index": 0,
        "agent_index": 0,
        "players": [
            {
                "player_id": "adaptive",
                "chips": 1000,
                "is_playing_round": True,
                "current_bet_in_round": 0,
            },
            {
                "player_id": "opponent",
                "chips": 1000,
                "is_playing_round": True,
                "current_bet_in_round": 0,
            },
        ],
    }
    state = {
        **base_state,
        "action_history": [
            {
                "player_id": "adaptive",
                "action": "bet",
                "amount": 50,
                "pot": 100,
                "street": "Flop",
            },
            {
                "player_id": "opponent",
                "action": "call",
                "amount": 50,
                "pot": 150,
                "street": "Flop",
            },
        ],
    }

    adaptive.decide_action(state)

    estimate = adaptive.opponent_profiles["opponent"].estimate(
        "fold_to_bet",
        {"street": "Flop", "size_bucket": 0.5},
    )
    assert estimate.opportunities == 1
    assert estimate.successes == 0
