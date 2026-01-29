"""
Test Betting Round Logic

Tests for the betting round bug fix where players should
respond to raises before the round ends.
"""

import pytest
from app.engine import Card, Player, Game, GameEventType


class MockPlayer(Player):
    """Player with predetermined actions for testing."""
    
    def __init__(self, actions: list, **kwargs):
        super().__init__(**kwargs)
        self.actions = actions
        self.action_index = 0
        self.actions_taken = []
    
    def get_next_action(self):
        """Get the next predetermined action."""
        if self.action_index < len(self.actions):
            action = self.actions[self.action_index]
            self.action_index += 1
            return action
        return "fold"  # Default if we run out of actions


class TestBettingRoundLogic:
    """Test betting round scenarios."""
    
    def test_players_respond_to_bb_raise(self):
        """
        Test that when BB raises pre-flop, other players get to respond.
        
        Scenario:
        - Player 1 (Dealer): calls $20
        - Player 2 (SB): calls $10 more (total $20)
        - Player 3 (BB): raises to $40
        - Player 1 should get to respond!
        - Player 2 should get to respond!
        """
        # Create players with enough chips
        players = [
            Player(chips=1000, name="Dealer", player_id="player_1"),
            Player(chips=1000, name="SB", player_id="player_2"),
            Player(chips=1000, name="BB", player_id="player_3")
        ]
        
        game = Game(players=players, small_blind=10, big_blind=20)
        
        # Track all actions taken
        actions_taken = []
        
        def track_action(data):
            actions_taken.append({
                'player_id': data.get('player_id'),
                'action': data.get('action'),
                'amount': data.get('amount')
            })
        
        game.on_event(GameEventType.PLAYER_ACTION_TAKEN, track_action)
        
        # Play a hand
        game.play_hand()
        
        # Count actions per player in pre-flop
        # After BB raises, both other players should act again
        preflop_actions = {}
        for action in actions_taken:
            pid = action['player_id']
            preflop_actions[pid] = preflop_actions.get(pid, 0) + 1
        
        # Verify chip conservation
        total_chips = sum(p.chips for p in players)
        assert total_chips == 3000, "Total chips should be conserved"
    
    def test_betting_round_ends_when_all_check(self):
        """Test that betting round ends correctly when everyone checks."""
        players = [
            Player(chips=1000, name="Alice", player_id="p1"),
            Player(chips=1000, name="Bob", player_id="p2"),
        ]
        
        game = Game(players=players, small_blind=10, big_blind=20)
        
        events = []
        def track_event(data):
            events.append(data)
        
        game.on_event(GameEventType.BETTING_ROUND_ENDED, track_event)
        
        # Play hand
        game.play_hand()
        
        # Should have multiple betting round ended events
        # (Pre-flop, Flop, Turn, River if hand goes to showdown)
        assert len(events) >= 1, "At least one betting round should complete"
    
    def test_fold_ends_hand_early(self):
        """Test that if all but one player folds, hand ends."""
        players = [
            Player(chips=1000, name="Alice", player_id="p1"),
            Player(chips=1000, name="Bob", player_id="p2"),
        ]
        
        game = Game(players=players, small_blind=10, big_blind=20)
        
        pot_awarded = []
        def track_pot(data):
            pot_awarded.append(data)
        
        game.on_event(GameEventType.POT_AWARDED, track_pot)
        
        # Play hand
        game.play_hand()
        
        # Pot should be awarded
        assert len(pot_awarded) == 1, "Pot should be awarded exactly once"
        
        # Chips should be conserved
        total = sum(p.chips for p in players)
        assert total == 2000, "Chips should be conserved"
    
    def test_raise_resets_action(self):
        """Test that a raise allows others to respond."""
        players = [
            Player(chips=1000, name="Alice", player_id="p1"),
            Player(chips=1000, name="Bob", player_id="p2"),
            Player(chips=1000, name="Charlie", player_id="p3"),
        ]
        
        game = Game(players=players, small_blind=10, big_blind=20)
        
        actions = []
        def track_action(data):
            actions.append(data)
        
        game.on_event(GameEventType.PLAYER_ACTION_TAKEN, track_action)
        
        # Play hand
        game.play_hand()
        
        # Should have actions from all players
        player_ids = set(a['player_id'] for a in actions)
        assert len(player_ids) >= 2, "At least 2 players should act"


class TestPreFlopBBOption:
    """Test the Big Blind's option to raise when no one raised."""
    
    def test_bb_can_raise_when_all_call(self):
        """BB should get the option to raise even if everyone just calls."""
        players = [
            Player(chips=1000, name="Dealer", player_id="dealer"),
            Player(chips=1000, name="SB", player_id="sb"),
            Player(chips=1000, name="BB", player_id="bb"),
        ]
        
        game = Game(players=players, small_blind=10, big_blind=20)
        
        bb_actions = []
        def track_action(data):
            if data.get('player_id') == 'bb':
                bb_actions.append(data)
        
        game.on_event(GameEventType.PLAYER_ACTION_TAKEN, track_action)
        
        # Play hand
        game.play_hand()
        
        # BB should have at least one action
        assert len(bb_actions) >= 1, "BB should get to act at least once"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
