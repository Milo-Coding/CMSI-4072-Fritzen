"""
Room Manager - Multi-room game management

Handles creating, joining, and managing multiple concurrent poker games.
"""

import uuid
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime

from ..engine import Game, Player, GameEventType
from ..engine.agents import AgentRegistry, BaseAgent
from ..models.schemas import RoomConfig


@dataclass
class Room:
    """
    Represents a poker room/table.
    
    Contains a game instance and tracks connected players.
    """
    id: str
    name: str
    config: RoomConfig
    game: Optional[Game] = None
    players: List[Player] = field(default_factory=list)
    is_active: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    # Event callbacks for broadcasting
    _event_callbacks: List[Callable] = field(default_factory=list)
    
    @property
    def player_count(self) -> int:
        return len(self.players)
    
    @property
    def is_full(self) -> bool:
        return self.player_count >= self.config.max_players
    
    @property
    def can_start(self) -> bool:
        return self.player_count >= self.config.min_players and not self.is_active
    
    @property
    def phase(self) -> str:
        if self.game:
            return self.game.current_phase.value
        return "waiting"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "name": self.name,
            "player_count": self.player_count,
            "max_players": self.config.max_players,
            "is_active": self.is_active,
            "phase": self.phase,
            "small_blind": self.config.small_blind,
            "big_blind": self.config.big_blind or self.config.small_blind * 2,
            "pot": self.game.pot if self.game else 0
        }
    
    def add_event_callback(self, callback: Callable[[str, dict], None]):
        """Add a callback for game events."""
        self._event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable):
        """Remove an event callback."""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)
    
    def _broadcast_event(self, event_data: dict):
        """Broadcast event to all callbacks."""
        for callback in self._event_callbacks:
            try:
                callback(self.id, event_data)
            except Exception as e:
                print(f"Error in event callback: {e}")


class RoomManager:
    """
    Manages multiple poker rooms.
    
    Provides room creation, player joining/leaving, and game lifecycle.
    """
    
    def __init__(self):
        self._rooms: Dict[str, Room] = {}
        self._player_rooms: Dict[str, str] = {}  # player_id -> room_id
    
    def create_room(self, config: RoomConfig) -> Room:
        """
        Create a new poker room.
        
        Args:
            config: Room configuration
            
        Returns:
            The created room
        """
        room_id = str(uuid.uuid4())[:8]
        room_name = config.name or f"Table-{room_id}"
        
        room = Room(
            id=room_id,
            name=room_name,
            config=config
        )
        
        # Add AI players if requested
        for i in range(config.ai_players):
            try:
                ai_player = AgentRegistry.create(
                    config.ai_type,
                    name=f"Bot-{i+1}",
                    chips=config.starting_chips,
                    player_id=f"ai-{room_id}-{i}"
                )
                room.players.append(ai_player)
            except ValueError as e:
                print(f"Warning: Could not create AI player: {e}")
        
        self._rooms[room_id] = room
        return room
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """Get a room by ID."""
        return self._rooms.get(room_id)
    
    def list_rooms(self, include_full: bool = True) -> List[Room]:
        """
        List all rooms.
        
        Args:
            include_full: Include rooms that are full
        """
        rooms = list(self._rooms.values())
        if not include_full:
            rooms = [r for r in rooms if not r.is_full]
        return rooms
    
    def delete_room(self, room_id: str) -> bool:
        """Delete a room."""
        if room_id in self._rooms:
            room = self._rooms[room_id]
            # Remove player mappings
            for player in room.players:
                if player.player_id in self._player_rooms:
                    del self._player_rooms[player.player_id]
            del self._rooms[room_id]
            return True
        return False
    
    def join_room(
        self, 
        room_id: str, 
        player: Player
    ) -> Optional[Room]:
        """
        Add a player to a room.
        
        Args:
            room_id: Room to join
            player: Player to add
            
        Returns:
            The room if successful, None if failed
        """
        room = self.get_room(room_id)
        if not room:
            return None
        
        if room.is_full:
            return None
        
        if room.is_active:
            # Could allow joining active games in the future
            return None
        
        # Check if player already in a room
        if player.player_id in self._player_rooms:
            # Leave current room first
            self.leave_room(player.player_id)
        
        room.players.append(player)
        self._player_rooms[player.player_id] = room_id
        
        return room
    
    def leave_room(self, player_id: str) -> Optional[Room]:
        """
        Remove a player from their current room.
        
        Args:
            player_id: Player to remove
            
        Returns:
            The room they left, or None
        """
        room_id = self._player_rooms.get(player_id)
        if not room_id:
            return None
        
        room = self.get_room(room_id)
        if not room:
            del self._player_rooms[player_id]
            return None
        
        # Find and remove player
        room.players = [p for p in room.players if p.player_id != player_id]
        del self._player_rooms[player_id]
        
        # Delete room if empty (except AI players)
        human_players = [p for p in room.players if not isinstance(p, BaseAgent)]
        if not human_players:
            self.delete_room(room_id)
        
        return room
    
    def get_player_room(self, player_id: str) -> Optional[Room]:
        """Get the room a player is in."""
        room_id = self._player_rooms.get(player_id)
        if room_id:
            return self.get_room(room_id)
        return None
    
    def start_game(self, room_id: str) -> bool:
        """
        Start the game in a room.
        
        Args:
            room_id: Room to start
            
        Returns:
            True if game started, False otherwise
        """
        room = self.get_room(room_id)
        if not room:
            return False
        
        if not room.can_start:
            return False
        
        # Create game instance
        room.game = Game(
            players=room.players,
            small_blind=room.config.small_blind,
            big_blind=room.config.big_blind
        )
        
        # Register event handler for broadcasting
        for event_type in GameEventType:
            room.game.on_event(event_type, lambda data: room._broadcast_event(data))
        
        room.is_active = True
        
        return True
    
    def play_hand(self, room_id: str) -> bool:
        """
        Play a hand in a room.
        
        Args:
            room_id: Room ID
            
        Returns:
            True if hand played, False otherwise
        """
        room = self.get_room(room_id)
        if not room or not room.game or not room.is_active:
            return False
        
        room.game.play_hand()
        return True
    
    def get_game_state(self, room_id: str, player_id: Optional[str] = None) -> Optional[dict]:
        """
        Get game state for a room.
        
        Args:
            room_id: Room ID
            player_id: If provided, get player-specific view
            
        Returns:
            Game state dictionary
        """
        room = self.get_room(room_id)
        if not room or not room.game:
            return None
        
        if player_id:
            return room.game.get_player_view(player_id)
        return room.game.get_state()
    
    def execute_action(
        self, 
        room_id: str, 
        player_id: str, 
        action: str, 
        amount: Optional[int] = None
    ) -> dict:
        """
        Execute a player action in a room.
        
        Args:
            room_id: Room ID
            player_id: Player making action
            action: Action type
            amount: Amount for bet/raise
            
        Returns:
            Result of the action
        """
        room = self.get_room(room_id)
        if not room or not room.game:
            return {"success": False, "error": "Room or game not found"}
        
        # Find player
        player = None
        for p in room.players:
            if p.player_id == player_id:
                player = p
                break
        
        if not player:
            return {"success": False, "error": "Player not found in room"}
        
        # Execute action based on type
        try:
            if action == "fold":
                player.do_fold()
            elif action == "check":
                if not player.do_check(room.game.current_table_bet):
                    return {"success": False, "error": "Cannot check"}
            elif action == "call":
                contributed = player.do_call(room.game.current_table_bet)
                room.game.pot += contributed
            elif action == "bet":
                if amount is None:
                    return {"success": False, "error": "Bet requires amount"}
                contributed = player.do_bet(amount)
                room.game.current_table_bet = contributed
                room.game.pot += contributed
            elif action == "raise":
                if amount is None:
                    return {"success": False, "error": "Raise requires amount"}
                new_wager, added = player.do_raise(room.game.current_table_bet, amount)
                if new_wager != -1:
                    room.game.current_table_bet = new_wager
                    room.game.pot += added
                else:
                    return {"success": False, "error": "Invalid raise"}
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
            
            return {
                "success": True,
                "action": action,
                "amount": amount,
                "player_id": player_id,
                "pot": room.game.pot
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
