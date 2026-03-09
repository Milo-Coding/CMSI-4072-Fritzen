"""
API Schemas - Pydantic models for API validation

Defines all request/response models and WebSocket message formats.
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict, ValidationInfo


# ============================================================
# Card and Player Models
# ============================================================

class CardModel(BaseModel):
    """Card representation for API."""
    suit: str = Field(..., description="Card suit: Hearts, Diamonds, Clubs, Spades")
    value: int = Field(..., ge=2, le=14, description="Card value 2-14 (11=J, 12=Q, 13=K, 14=A)")
    display: Optional[str] = Field(None, description="Human-readable display (e.g., 'K♥')")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {"suit": "Hearts", "value": 14, "display": "A♥"}
    })


class PlayerModel(BaseModel):
    """Full player information (includes hidden cards for owner)."""
    player_id: str
    name: str
    chips: int = Field(..., ge=0)
    hand: List[CardModel] = Field(default_factory=list)
    is_playing_round: bool = True
    current_bet_in_round: int = Field(0, ge=0)
    has_acted_this_round: bool = False
    is_agent: bool = False
    agent_type: Optional[str] = None
    is_all_in: bool = False


class PlayerPublicModel(BaseModel):
    """Public player information (hides cards from opponents)."""
    player_id: str
    name: str
    chips: int = Field(..., ge=0)
    hand_size: int = Field(0, ge=0, description="Number of cards (not the cards themselves)")
    is_playing_round: bool = True
    current_bet_in_round: int = Field(0, ge=0)
    has_acted_this_round: bool = False
    is_agent: bool = False
    is_all_in: bool = False


# ============================================================
# Game State Models
# ============================================================

class GameStateModel(BaseModel):
    """Complete game state (for admin/spectator view)."""
    hand_number: int = Field(0, ge=0)
    phase: str = Field(..., description="Current game phase")
    dealer_index: int = Field(0, ge=0)
    pot: int = Field(0, ge=0)
    current_bet: int = Field(0, ge=0)
    small_blind: int = Field(10, ge=1)
    big_blind: int = Field(20, ge=1)
    community_cards: List[CardModel] = Field(default_factory=list)
    players: List[PlayerModel] = Field(default_factory=list)
    active_player_count: int = Field(0, ge=0)


class PlayerViewStateModel(BaseModel):
    """Game state from a specific player's perspective."""
    hand_number: int = Field(0, ge=0)
    phase: str
    dealer_index: int = Field(0, ge=0)
    pot: int = Field(0, ge=0)
    current_bet: int = Field(0, ge=0)
    small_blind: int = Field(10, ge=1)
    big_blind: int = Field(20, ge=1)
    community_cards: List[CardModel] = Field(default_factory=list)
    players: List[PlayerPublicModel] = Field(default_factory=list)
    your_hand: List[CardModel] = Field(default_factory=list)
    your_index: int = Field(0, ge=0)
    active_player_count: int = Field(0, ge=0)
    available_actions: List[str] = Field(default_factory=list)
    call_amount: int = Field(0, ge=0)
    is_your_turn: bool = False


# ============================================================
# Action Models
# ============================================================

class ActionType(str, Enum):
    """Valid player actions."""
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


class PlayerAction(BaseModel):
    """Player action request."""
    action: ActionType
    amount: Optional[int] = Field(None, ge=0, description="Required for bet/raise actions")
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Optional[int], info: ValidationInfo) -> Optional[int]:
        action = info.data.get('action')
        if action in [ActionType.BET, ActionType.RAISE] and v is None:
            raise ValueError(f'{action.value} action requires an amount')
        return v

    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {"action": "fold"},
            {"action": "call"},
            {"action": "bet", "amount": 50}
        ]
    })


class PlayerActionResult(BaseModel):
    """Result of a player action."""
    success: bool
    action: str
    amount: Optional[int] = None
    player_id: str
    pot: int = Field(0, ge=0)
    error: Optional[str] = None


# ============================================================
# Room Models
# ============================================================

class RoomConfig(BaseModel):
    """Configuration for creating a new room."""
    name: Optional[str] = Field(None, description="Room display name")
    small_blind: int = Field(10, ge=1)
    big_blind: Optional[int] = Field(None, ge=1, description="Defaults to 2x small blind")
    min_players: int = Field(2, ge=2, le=12)
    max_players: int = Field(6, ge=2, le=12)
    starting_chips: int = Field(1000, ge=100)
    ai_players: int = Field(0, ge=0, le=11, description="Number of AI players to add")
    ai_type: str = Field("random", description="Type of AI agent: random, dqn")
    
    @field_validator('big_blind')
    @classmethod
    def set_big_blind(cls, v: Optional[int], info: ValidationInfo) -> int:
        if v is None:
            return info.data.get('small_blind', 10) * 2
        return v

    @field_validator('max_players')
    @classmethod
    def validate_max_players(cls, v: int, info: ValidationInfo) -> int:
        min_players = info.data.get('min_players', 2)
        if v < min_players:
            raise ValueError('max_players must be >= min_players')
        return v


class RoomModel(BaseModel):
    """Room information."""
    id: str
    name: str
    player_count: int = Field(0, ge=0)
    max_players: int = Field(6, ge=2)
    is_active: bool = False
    phase: str = "waiting"
    small_blind: int = Field(10, ge=1)
    big_blind: int = Field(20, ge=1)
    pot: int = Field(0, ge=0)


class RoomListResponse(BaseModel):
    """Response for listing rooms."""
    rooms: List[RoomModel]
    total: int = Field(0, ge=0)


# ============================================================
# WebSocket Message Models
# ============================================================

class WSMessageType(str, Enum):
    """WebSocket message types."""
    # Client -> Server
    JOIN_GAME = "join_game"
    LEAVE_GAME = "leave_game"
    PLAYER_ACTION = "player_action"
    START_GAME = "start_game"
    NEXT_HAND = "next_hand"
    RESET_ROOM = "reset_room"
    CHAT = "chat"
    ADD_AI = "add_ai"
    REMOVE_PLAYER = "remove_player"
    
    # Server -> Client
    GAME_STATE = "game_state"
    PLAYER_ACTION_REQUIRED = "player_action_required"
    PLAYER_ACTION_TAKEN = "player_action_taken"
    COMMUNITY_CARDS = "community_cards"
    POT_UPDATE = "pot_update"
    WINNER = "winner"
    HAND_STARTED = "hand_started"
    HAND_ENDED = "hand_ended"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    ERROR = "error"
    CONNECTED = "connected"


class WSMessage(BaseModel):
    """Base WebSocket message."""
    type: WSMessageType
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class WSJoinGame(BaseModel):
    """Join game message data."""
    room_id: str
    player_name: str


class WSPlayerAction(BaseModel):
    """Player action message data."""
    action: ActionType
    amount: Optional[int] = None


class WSGameState(BaseModel):
    """Game state broadcast message data."""
    phase: str
    pot: int
    current_bet: int
    community_cards: List[CardModel]
    players: List[PlayerPublicModel]
    dealer_index: int
    active_player_id: Optional[str] = None


class WSPlayerActionRequired(BaseModel):
    """Action required notification data."""
    player_id: str
    available_actions: List[str]
    call_amount: int
    current_bet: int
    pot: int
    phase: str
    time_limit: Optional[int] = Field(None, description="Seconds to act (optional)")


class WSError(BaseModel):
    """Error message data."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


# ============================================================
# Event Models (for game engine events)
# ============================================================

class GameEvent(BaseModel):
    """Game event for broadcasting."""
    event_type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    hand_number: Optional[int] = None


class BlindsPostedEvent(BaseModel):
    """Blinds posted event data."""
    small_blind: Dict[str, Any]
    big_blind: Dict[str, Any]
    pot: int


class ShowdownEvent(BaseModel):
    """Showdown event data."""
    hands: List[Dict[str, Any]]


class PotAwardedEvent(BaseModel):
    """Pot awarded event data."""
    winners: List[str]
    amount_each: int
    total_pot: Optional[int] = None
    reason: str
