"""
Random Agent - Simple baseline agent for testing

Makes random valid decisions. Useful for:
- Testing game logic
- Baseline comparisons
- Filling empty seats
"""

import random
from typing import Dict, List, Any, Union, Tuple, Optional

from .base_agent import BaseAgent, AgentRegistry
from ..card import Card


@AgentRegistry.register("random")
class RandomAgent(BaseAgent):
    """
    Agent that makes random valid decisions.
    
    Useful as a baseline opponent or for testing.
    """
    
    def __init__(
        self,
        hand: Optional[List[Card]] = None,
        chips: int = 1000,
        name: str = "RandomBot",
        player_id: Optional[str] = None,
        fold_probability: float = 0.1,
        bet_probability: float = 0.3,
        raise_probability: float = 0.2,
        **kwargs
    ):
        """
        Initialize random agent.
        
        Args:
            fold_probability: Chance to fold when possible
            bet_probability: Chance to bet when possible
            raise_probability: Chance to raise when possible
        """
        super().__init__(
            hand=hand,
            chips=chips,
            name=name,
            player_id=player_id,
            **kwargs
        )
        self.fold_probability = fold_probability
        self.bet_probability = bet_probability
        self.raise_probability = raise_probability
    
    def decide_action(self, game_state: Dict[str, Any]) -> Union[str, Tuple[str, int]]:
        """
        Make a random valid decision.
        
        Args:
            game_state: Current game state
            
        Returns:
            Random valid action
        """
        available_actions = game_state.get("available_actions", ["fold"])
        call_amount = game_state.get("call_amount", 0)
        current_bet = game_state.get("current_table_bet", 0)
        
        # Weight actions based on probabilities
        r = random.random()
        
        if "fold" in available_actions and r < self.fold_probability:
            return "fold"
        
        if "check" in available_actions:
            # Usually check if we can
            if random.random() < 0.7:
                return "check"
        
        if "call" in available_actions:
            # Usually call if we need to act
            if random.random() < 0.6:
                return "call"
        
        if "bet" in available_actions and random.random() < self.bet_probability:
            # Random bet between minimum and half our stack
            min_bet = max(20, game_state.get("big_blind", 20))
            max_bet = min(self.chips // 2, self.chips)
            if max_bet >= min_bet:
                bet_amount = random.randint(min_bet, max_bet)
                return ("bet", bet_amount)
        
        if "raise" in available_actions and random.random() < self.raise_probability:
            # Random raise
            min_raise = current_bet + game_state.get("big_blind", 20)
            max_raise = min(self.chips + self.current_bet_in_round, self.chips * 2)
            if max_raise >= min_raise:
                raise_amount = random.randint(min_raise, max_raise)
                return ("raise", raise_amount)
        
        # Fallback: check > call > fold
        if "check" in available_actions:
            return "check"
        elif "call" in available_actions:
            return "call"
        else:
            return "fold"
