"""
Test to verify all-in players cannot take actions after going all-in
"""

from app.engine import Player, Game
from app.engine.agents import BaseAgent


class MockAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def decide_action(self, game_state):
        available_actions = game_state["available_actions"] 
        print(f"Agent {self.name} available actions: {available_actions}")
        if available_actions:
            return available_actions[0]  # Take first available action
        return None


def test_all_in_no_actions():
    """Test that all-in players have no available actions"""
    
    # Create test players
    players = [
        Player(chips=100, name="Player1", player_id="p1"),
        MockAgent(chips=100, name="Bot", player_id="bot")
    ]
    
    game = Game(players, small_blind=10, big_blind=20)
    game._prepare_new_hand()
    
    bot = players[1]
    
    print(f"Before all-in: Bot chips={bot.chips}")
    
    # Bot goes all-in
    bot.do_all_in()
    print(f"After all-in: Bot chips={bot.chips}")
    
    # Check available actions
    call_amount = 0
    actions = game._get_available_actions(bot, call_amount)
    print(f"Available actions for all-in bot: {actions}")
    
    # Should be empty list
    assert actions == [], f"All-in player should have no actions, got: {actions}"
    
    print("✓ All-in player correctly has no available actions")
    

def test_folded_no_actions():
    """Test that folded players have no available actions"""
    
    players = [
        Player(chips=100, name="Player1", player_id="p1"),
        MockAgent(chips=100, name="Bot", player_id="bot")
    ]
    
    game = Game(players, small_blind=10, big_blind=20)
    game._prepare_new_hand()
    
    bot = players[1]
    
    print(f"Before fold: Bot is_playing_round={bot.is_playing_round}")
    
    # Bot folds
    bot.do_fold()
    print(f"After fold: Bot is_playing_round={bot.is_playing_round}")
    
    # Check available actions
    call_amount = 0
    actions = game._get_available_actions(bot, call_amount)
    print(f"Available actions for folded bot: {actions}")
    
    # Should be empty list
    assert actions == [], f"Folded player should have no actions, got: {actions}"
    
    print("✓ Folded player correctly has no available actions")


if __name__ == "__main__":
    test_all_in_no_actions()
    print()
    test_folded_no_actions()
    print("\n✅ All tests passed! All-in and folded players will be properly skipped.")