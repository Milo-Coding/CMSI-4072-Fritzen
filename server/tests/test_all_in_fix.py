"""Regression tests for all-in/fold action availability and betting-round termination."""

import time

from app.engine import Player, Game
from app.engine.agents import BaseAgent


class ScriptedAgent(BaseAgent):
    """Deterministic test agent with optional scripted actions."""

    def __init__(self, *args, scripted_actions=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.scripted_actions = list(scripted_actions or [])
        self.decision_calls = 0

    def decide_action(self, game_state):
        self.decision_calls += 1
        available_actions = game_state["available_actions"]

        if self.scripted_actions:
            action = self.scripted_actions.pop(0)
            # If scripted action is illegal in current state, use safe fallback.
            if isinstance(action, tuple):
                if action[0] in available_actions:
                    return action
            elif action in available_actions:
                return action

        # Safe deterministic fallback policy
        if "check" in available_actions:
            return "check"
        if "call" in available_actions:
            return "call"
        if "all_in" in available_actions:
            return "all_in"
        return "fold"


def test_all_in_no_actions():
    """All-in players must have no further available actions."""
    players = [
        Player(chips=100, name="Player1", player_id="p1"),
        ScriptedAgent(chips=100, name="Bot", player_id="bot")
    ]

    game = Game(players, small_blind=10, big_blind=20)
    game._prepare_new_hand()

    bot = players[1]
    bot.do_all_in()

    actions = game._get_available_actions(bot, call_amount=0)
    assert actions == []


def test_folded_no_actions():
    """Folded players must have no available actions."""
    players = [
        Player(chips=100, name="Player1", player_id="p1"),
        ScriptedAgent(chips=100, name="Bot", player_id="bot")
    ]

    game = Game(players, small_blind=10, big_blind=20)
    game._prepare_new_hand()

    bot = players[1]
    bot.do_fold()

    actions = game._get_available_actions(bot, call_amount=0)
    assert actions == []


def test_preflop_all_in_aggressor_round_completes_without_stall():
    """
    Regression for training stalls:
    if last aggressor goes all-in, betting round must still terminate.
    """
    players = [
        ScriptedAgent(chips=200, name="Dealer", player_id="p0", scripted_actions=["call"]),
        ScriptedAgent(chips=200, name="SB", player_id="p1", scripted_actions=["call"]),
        ScriptedAgent(chips=200, name="BB", player_id="p2", scripted_actions=["call"]),
        ScriptedAgent(chips=25, name="Short", player_id="p3", scripted_actions=["all_in"]),
    ]

    game = Game(players, small_blind=10, big_blind=20)
    game._prepare_new_hand()
    game._post_blinds()
    game._deal_hole_cards()

    started = time.perf_counter()
    game._betting_round("Pre-Flop")
    elapsed = time.perf_counter() - started

    # Must complete quickly (no pathological loop)
    assert elapsed < 0.5

    # Everyone should end pre-flop with 25 invested (short stack set the all-in raise)
    assert all(p.current_bet_in_round == 25 for p in players)
    assert game.current_table_bet == 25
    assert game.pot == 100


def test_all_in_player_not_asked_to_act_again_after_shove():
    """A player that is all-in pre-flop should not be prompted on later streets."""
    all_in_agent = ScriptedAgent(
        chips=25,
        name="Short",
        player_id="short",
        scripted_actions=["all_in"]
    )
    caller_1 = ScriptedAgent(chips=300, name="Caller1", player_id="c1")
    caller_2 = ScriptedAgent(chips=300, name="Caller2", player_id="c2")

    players = [caller_1, caller_2, all_in_agent]
    game = Game(players, small_blind=10, big_blind=20)

    game.play_hand()

    # Exactly one decision call for the all-in agent (the shove itself).
    assert all_in_agent.decision_calls == 1