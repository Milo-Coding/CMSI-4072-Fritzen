"""
Player Manager - Player session and connection management

Handles:
- Player registration and authentication
- WebSocket connection tracking
- Disconnection handling
"""

import uuid
from typing import Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from fastapi import WebSocket

from ..engine import Player


@dataclass
class PlayerSession:
    """
    Represents a connected player's session.
    
    Tracks connection state and room membership.
    """
    id: str
    name: str
    websocket: Optional[WebSocket] = None
    current_room: Optional[str] = None
    player: Optional[Player] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    is_connected: bool = True
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API."""
        return {
            "id": self.id,
            "name": self.name,
            "current_room": self.current_room,
            "is_connected": self.is_connected,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now()


class PlayerManager:
    """
    Manages player sessions and WebSocket connections.
    
    Provides registration, lookup, and connection tracking.
    """
    
    def __init__(self):
        self._sessions: Dict[str, PlayerSession] = {}
        self._websockets: Dict[str, WebSocket] = {}  # player_id -> websocket
        self._ws_to_player: Dict[WebSocket, str] = {}  # websocket -> player_id
    
    def register_player(
        self, 
        name: str, 
        websocket: Optional[WebSocket] = None,
        starting_chips: int = 1000
    ) -> PlayerSession:
        """
        Register a new player.
        
        Args:
            name: Player display name
            websocket: WebSocket connection (if connecting via WS)
            starting_chips: Initial chip count
            
        Returns:
            New player session
        """
        player_id = str(uuid.uuid4())[:8]
        
        # Create Player object
        player = Player(
            name=name,
            chips=starting_chips,
            player_id=player_id
        )
        
        session = PlayerSession(
            id=player_id,
            name=name,
            websocket=websocket,
            player=player
        )
        
        self._sessions[player_id] = session
        
        if websocket:
            self._websockets[player_id] = websocket
            self._ws_to_player[websocket] = player_id
        
        return session
    
    def get_session(self, player_id: str) -> Optional[PlayerSession]:
        """Get a player session by ID."""
        return self._sessions.get(player_id)
    
    def get_session_by_websocket(self, websocket: WebSocket) -> Optional[PlayerSession]:
        """Get a player session by their WebSocket connection."""
        player_id = self._ws_to_player.get(websocket)
        if player_id:
            return self._sessions.get(player_id)
        return None
    
    def update_websocket(
        self, 
        player_id: str, 
        websocket: WebSocket
    ) -> Optional[PlayerSession]:
        """
        Update a player's WebSocket connection.
        
        Useful for reconnection handling.
        
        Args:
            player_id: Player to update
            websocket: New WebSocket connection
            
        Returns:
            Updated session or None if player not found
        """
        session = self.get_session(player_id)
        if not session:
            return None
        
        # Remove old mapping if exists
        if session.websocket and session.websocket in self._ws_to_player:
            del self._ws_to_player[session.websocket]
        
        # Update mappings
        session.websocket = websocket
        session.is_connected = True
        session.update_activity()
        
        self._websockets[player_id] = websocket
        self._ws_to_player[websocket] = player_id
        
        return session
    
    def disconnect_player(self, player_id: str):
        """
        Mark a player as disconnected.
        
        Does not remove the session (allows reconnection).
        
        Args:
            player_id: Player to disconnect
        """
        session = self.get_session(player_id)
        if not session:
            return
        
        session.is_connected = False
        
        if session.websocket and session.websocket in self._ws_to_player:
            del self._ws_to_player[session.websocket]
        
        if player_id in self._websockets:
            del self._websockets[player_id]
        
        session.websocket = None
    
    def disconnect_by_websocket(self, websocket: WebSocket):
        """Disconnect player by their WebSocket."""
        player_id = self._ws_to_player.get(websocket)
        if player_id:
            self.disconnect_player(player_id)
    
    def remove_player(self, player_id: str):
        """
        Completely remove a player session.
        
        Args:
            player_id: Player to remove
        """
        session = self.get_session(player_id)
        if not session:
            return
        
        # Clean up websocket mappings
        if session.websocket and session.websocket in self._ws_to_player:
            del self._ws_to_player[session.websocket]
        
        if player_id in self._websockets:
            del self._websockets[player_id]
        
        # Remove session
        del self._sessions[player_id]
    
    def set_player_room(self, player_id: str, room_id: Optional[str]):
        """Update which room a player is in."""
        session = self.get_session(player_id)
        if session:
            session.current_room = room_id
            session.update_activity()
    
    def get_players_in_room(self, room_id: str) -> list[PlayerSession]:
        """Get all player sessions in a room."""
        return [
            session for session in self._sessions.values()
            if session.current_room == room_id and session.is_connected
        ]
    
    def get_connected_websockets_in_room(self, room_id: str) -> list[WebSocket]:
        """Get WebSocket connections for all players in a room."""
        websockets = []
        for session in self.get_players_in_room(room_id):
            if session.websocket:
                websockets.append(session.websocket)
        return websockets
    
    def get_all_sessions(self) -> list[PlayerSession]:
        """Get all player sessions."""
        return list(self._sessions.values())
    
    def get_connected_count(self) -> int:
        """Get number of connected players."""
        return sum(1 for s in self._sessions.values() if s.is_connected)
    
    def cleanup_inactive(self, max_inactive_seconds: int = 3600):
        """
        Remove inactive disconnected sessions.
        
        Args:
            max_inactive_seconds: Remove sessions inactive longer than this
        """
        now = datetime.now()
        to_remove = []
        
        for player_id, session in self._sessions.items():
            if not session.is_connected:
                inactive_time = (now - session.last_activity).total_seconds()
                if inactive_time > max_inactive_seconds:
                    to_remove.append(player_id)
        
        for player_id in to_remove:
            self.remove_player(player_id)
        
        return len(to_remove)
