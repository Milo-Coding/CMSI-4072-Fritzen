"""
Base Agent Module - Abstract base class for all AI agents

Provides a plugin architecture for creating different AI agents.
New agents should subclass BaseAgent and implement the required methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Type, Union, Tuple
from ..player import Player
from ..card import Card


class AgentRegistry:
    """
    Registry for agent types.
    
    Allows dynamic registration and instantiation of different agent types.
    This makes it easy to add new AI strategies without modifying existing code.
    """
    
    _agents: Dict[str, Type['BaseAgent']] = {}
    
    @classmethod
    def register(cls, name: str):
        """
        Decorator to register an agent class.
        
        Usage:
            @AgentRegistry.register("my_agent")
            class MyAgent(BaseAgent):
                ...
        """
        def decorator(agent_class: Type['BaseAgent']):
            cls._agents[name.lower()] = agent_class
            return agent_class
        return decorator
    
    @classmethod
    def get(cls, agent_type: str) -> Optional[Type['BaseAgent']]:
        """Get an agent class by type name."""
        return cls._agents.get(agent_type.lower())
    
    @classmethod
    def list_agents(cls) -> List[str]:
        """List all registered agent names."""
        return list(cls._agents.keys())
    
    @classmethod
    def create(cls, agent_type: str, **kwargs) -> 'BaseAgent':
        """
        Create an agent instance by type name.
        
        Args:
            agent_type: Registered agent type name
            **kwargs: Arguments to pass to agent constructor
            
        Returns:
            BaseAgent: New agent instance
            
        Raises:
            ValueError: If agent type is not registered
        """
        agent_class = cls.get(agent_type)
        if agent_class is None:
            available = ", ".join(cls.list_agents())
            raise ValueError(
                f"Unknown agent type '{agent_type}'. Available: {available}"
            )
        return agent_class(**kwargs)


class BaseAgent(Player, ABC):
    """
    Abstract base class for AI poker agents.
    
    All AI agents must subclass this and implement:
    - decide_action(): Choose an action given game state
    
    Optional overrides:
    - on_hand_start(): Called at start of each hand
    - on_hand_end(): Called at end of each hand with result
    - featurize_game_state(): Convert game state to feature vector
    """
    
    def __init__(
        self,
        hand: Optional[List[Card]] = None,
        chips: int = 1000,
        name: str = "AI",
        player_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the base agent.
        
        Args:
            hand: Initial hand cards
            chips: Starting chip count
            name: Display name
            player_id: Unique identifier
            **kwargs: Additional agent-specific parameters
        """
        super().__init__(
            hand=hand,
            chips=chips,
            name=name,
            player_id=player_id
        )
        
        # Track chip changes for reward calculation
        self.last_chips = chips
        self.hands_played = 0
        self.hands_won = 0
    
    @abstractmethod
    def decide_action(self, game_state: Dict[str, Any]) -> Union[str, Tuple[str, int]]:
        """
        Decide what action to take given the current game state.
        
        This is the core method that defines agent behavior.
        
        Args:
            game_state: Dictionary containing:
                - current_table_bet: int - Highest bet on table
                - call_amount: int - Amount needed to call
                - available_actions: List[str] - Valid actions
                - state_name: str - "Pre-Flop", "Flop", "Turn", "River"
                - opponents_chips: List[int] - Other players' chips
                - pot: int - Current pot size
                - community_cards: List[Card] - Community cards
                - players: List[Player] - All players
                - dealer_index: int - Dealer position
                - agent_index: int - This agent's position
                
        Returns:
            Union[str, Tuple[str, int]]: Action to take.
                Simple actions: "fold", "check", "call"
                Actions with amounts: ("bet", amount), ("raise", amount)
        """
        pass
    
    def on_hand_start(self, game_state: Dict[str, Any]) -> None:
        """
        Called at the start of each hand.
        
        Override to perform setup or logging.
        
        Args:
            game_state: Initial game state for the hand
        """
        self.last_chips = self.chips
        self.hands_played += 1
    
    def on_hand_end(self, result: Dict[str, Any]) -> None:
        """
        Called at the end of each hand.
        
        Override to perform learning, logging, or cleanup.
        
        Args:
            result: Dictionary containing:
                - won: bool - Whether this agent won
                - pot_share: int - Amount won (if any)
                - chip_change: int - Net chip change
                - hand_rank: str - Final hand ranking (if showdown)
        """
        chip_change = self.chips - self.last_chips
        if chip_change > 0:
            self.hands_won += 1
    
    def featurize_game_state(self, game_state: Dict[str, Any]) -> Dict[str, float]:
        """
        Convert game state to a feature dictionary for decision making.
        
        Override to implement custom feature extraction.
        
        Args:
            game_state: Raw game state dictionary
            
        Returns:
            Dict[str, float]: Feature dictionary with normalized values
        """
        features = {}
        
        # Basic game state features
        total_chips = sum(game_state.get("opponents_chips", [0])) + self.chips
        pot = game_state.get("pot", 0)
        call_amount = game_state.get("call_amount", 0)
        current_bet = game_state.get("current_table_bet", 0)
        
        features["pot_size_ratio"] = pot / total_chips if total_chips > 0 else 0.0
        features["call_amount_ratio"] = call_amount / self.chips if self.chips > 0 else 1.0
        features["table_bet_ratio"] = current_bet / self.chips if self.chips > 0 else 1.0
        
        # Stage features
        stage_values = {"Pre-Flop": 0.25, "Flop": 0.5, "Turn": 0.75, "River": 1.0}
        features["stage"] = stage_values.get(game_state.get("state_name", "Pre-Flop"), 0.25)
        
        # Hand strength features (if we have cards)
        if len(self.hand) == 2:
            features["pair_in_hand"] = 1.0 if self.hand[0].value == self.hand[1].value else 0.0
            features["high_card"] = max(c.value for c in self.hand) / 14.0
            features["suited"] = 1.0 if self.hand[0].suit == self.hand[1].suit else 0.0
            gap = abs(self.hand[0].value - self.hand[1].value)
            features["connected"] = 1.0 if gap == 1 else (0.5 if gap == 2 else 0.0)
            features["hand_strength"] = sum(c.value for c in self.hand) / 28.0
        else:
            features["pair_in_hand"] = 0.0
            features["high_card"] = 0.0
            features["suited"] = 0.0
            features["connected"] = 0.0
            features["hand_strength"] = 0.0
        
        return features
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get agent performance statistics.
        
        Returns:
            Dict with agent stats
        """
        return {
            "name": self.name,
            "player_id": self.player_id,
            "chips": self.chips,
            "hands_played": self.hands_played,
            "hands_won": self.hands_won,
            "win_rate": self.hands_won / self.hands_played if self.hands_played > 0 else 0.0
        }
    
    def to_dict(self, hide_cards: bool = False) -> dict:
        """
        Convert agent to dictionary for serialization.
        
        Extends parent to_dict with agent-specific fields.
        """
        data = super().to_dict(hide_cards=hide_cards)
        data["is_agent"] = True
        data["agent_type"] = self.__class__.__name__
        return data
    
    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.player_id}, name={self.name}, chips={self.chips})"
