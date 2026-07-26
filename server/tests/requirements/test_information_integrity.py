"""Tests that enforce public-information boundaries and card integrity."""

from __future__ import annotations

from copy import deepcopy

from app.engine import Game
from app.engine.agents import BaseAgent


class StateCaptureAgent(BaseAgent):
    """Capture the state supplied by the engine and take a passive action."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.observed_states = []

    def decide_action(self, game_state):
        self.observed_states.append(deepcopy(game_state))
        available = game_state["available_actions"]
        if "check" in available:
            return "check"
        if "call" in available:
            return "call"
        return "fold"


def test_agent_never_receives_opponent_hole_cards() -> None:
    """No decision state may contain another player's private cards."""
    hero = StateCaptureAgent(name="Hero", chips=1000, player_id="hero")
    villain = StateCaptureAgent(name="Villain", chips=1000, player_id="villain")
    game = Game([hero, villain], small_blind=10, big_blind=20)

    game.play_hand()

    assert hero.observed_states
    for state in hero.observed_states:
        opponent = next(p for p in state["players"] if p["player_id"] == "villain")
        assert opponent.get("hand", []) == []


def test_agent_state_contains_only_unique_visible_cards() -> None:
    """Hero cards and board cards must never contain duplicate physical cards."""
    hero = StateCaptureAgent(name="Hero", chips=1000, player_id="hero")
    villain = StateCaptureAgent(name="Villain", chips=1000, player_id="villain")
    game = Game([hero, villain], small_blind=10, big_blind=20)

    game.play_hand()

    for state in hero.observed_states:
        hero_state = next(p for p in state["players"] if p["player_id"] == "hero")
        visible = list(hero_state.get("hand", [])) + list(state["community_cards"])
        identities = [(card["suit"], card["value"]) for card in visible]
        assert len(identities) == len(set(identities))


def test_street_history_does_not_contain_private_cards() -> None:
    """Action logs used for opponent adaptation must remain public-only."""
    hero = StateCaptureAgent(name="Hero", chips=1000, player_id="hero")
    villain = StateCaptureAgent(name="Villain", chips=1000, player_id="villain")
    game = Game([hero, villain], small_blind=10, big_blind=20)

    game.play_hand()

    for state in hero.observed_states:
        for action in state["action_history"]:
            assert "hand" not in action
            assert "hole_cards" not in action
