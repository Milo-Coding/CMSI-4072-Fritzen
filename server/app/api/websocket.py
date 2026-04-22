"""
WebSocket API - Real-time game communication

Handles WebSocket connections for live poker gameplay:
- Player connection/disconnection
- Game state broadcasting
- Action handling
"""

import json
from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import ValidationError

from ..managers import RoomManager, PlayerManager
from ..models.schemas import (
    AddAIRequest,
    RenameAIRequest,
    WSMessageType,
    WSMessage,
    WSPlayerAction,
    ActionType,
)


router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections for a room.
    
    Handles broadcasting game events to all connected players.
    """
    
    def __init__(self):
        self.room_manager: RoomManager = None
        self.player_manager: PlayerManager = None
    
    def setup(self, room_manager: RoomManager, player_manager: PlayerManager):
        """Initialize with manager instances."""
        self.room_manager = room_manager
        self.player_manager = player_manager

    async def _require_host(
        self,
        websocket: WebSocket,
        room_id: str,
        player_id: str,
    ) -> bool:
        """Ensure the player is the host for host-only lobby actions."""
        room = self.room_manager.get_room(room_id)
        if not room:
            await self.send_error(websocket, "ROOM_NOT_FOUND", "Room not found")
            return False
        if room.host_player_id != player_id:
            await self.send_error(
                websocket,
                "FORBIDDEN",
                "Only the room host can perform this action",
            )
            return False
        return True
    
    async def connect(self, websocket: WebSocket, player_name: str) -> str:
        """
        Accept a new WebSocket connection and register player.
        
        Returns:
            Player ID
        """
        await websocket.accept()
        
        session = self.player_manager.register_player(
            name=player_name,
            websocket=websocket
        )
        
        # Send connection confirmation
        await self.send_message(websocket, {
            "type": WSMessageType.CONNECTED.value,
            "data": {
                "player_id": session.id,
                "name": session.name
            }
        })
        
        return session.id
    
    async def disconnect(self, websocket: WebSocket):
        """Handle player disconnection."""
        session = self.player_manager.get_session_by_websocket(websocket)
        if session:
            # Leave room if in one
            if session.current_room:
                room = self.room_manager.leave_room(session.id)
                if room:
                    await self.broadcast_to_room(room.id, {
                        "type": WSMessageType.PLAYER_LEFT.value,
                        "data": {
                            "player_id": session.id,
                            "name": session.name
                        }
                    })
            
            self.player_manager.disconnect_player(session.id)
    
    async def send_message(self, websocket: WebSocket, message: dict):
        """Send a message to a single client."""
        message["timestamp"] = datetime.now().isoformat()
        await websocket.send_json(message)
    
    async def send_error(self, websocket: WebSocket, code: str, message: str):
        """Send an error message to a client."""
        await self.send_message(websocket, {
            "type": WSMessageType.ERROR.value,
            "data": {
                "code": code,
                "message": message
            }
        })
    
    async def broadcast_to_room(self, room_id: str, message: dict, exclude_player: str = None):
        """Broadcast a message to all players in a room."""
        websockets = self.player_manager.get_connected_websockets_in_room(room_id)
        message["timestamp"] = datetime.now().isoformat()
        
        for ws in websockets:
            session = self.player_manager.get_session_by_websocket(ws)
            if session and (exclude_player is None or session.id != exclude_player):
                try:
                    await ws.send_json(message)
                except Exception as e:
                    print(f"Error broadcasting to {session.id}: {e}")
    
    async def handle_join_game(self, websocket: WebSocket, player_id: str, data: dict) -> bool:
        """Handle a player joining a room."""
        room_id = data.get("room_id")
        if not room_id:
            await self.send_error(websocket, "INVALID_REQUEST", "room_id is required")
            return False
        
        session = self.player_manager.get_session(player_id)
        if not session or not session.player:
            await self.send_error(websocket, "PLAYER_NOT_FOUND", "Player session not found")
            return False
        
        room, join_error = self.room_manager.try_join_room(room_id, session.player)
        if not room:
            error_by_reason = {
                "room_not_found": ("ROOM_NOT_FOUND", "Room not found"),
                "room_full": ("ROOM_FULL", "Room is full"),
                "room_active": ("ROOM_ACTIVE", "Game already started in this room"),
            }
            code, message = error_by_reason.get(
                join_error,
                ("JOIN_FAILED", "Could not join room"),
            )
            await self.send_error(websocket, code, message)
            return False
        
        self.player_manager.set_player_room(player_id, room_id)
        
        # Notify others in room
        await self.broadcast_to_room(room_id, {
            "type": WSMessageType.PLAYER_JOINED.value,
            "data": {
                "player_id": player_id,
                "name": session.name,
                "player_count": room.player_count
            }
        }, exclude_player=player_id)
        
        # Send current game state to joining player
        await self.send_game_state(websocket, room_id, player_id)
        return True
    
    async def handle_leave_game(self, websocket: WebSocket, player_id: str):
        """Handle a player leaving a room."""
        session = self.player_manager.get_session(player_id)
        if not session or not session.current_room:
            return
        
        room_id = session.current_room
        room = self.room_manager.leave_room(player_id)
        self.player_manager.set_player_room(player_id, None)
        
        if room:
            await self.broadcast_to_room(room_id, {
                "type": WSMessageType.PLAYER_LEFT.value,
                "data": {
                    "player_id": player_id,
                    "name": session.name
                }
            })
    
    async def handle_player_action(self, websocket: WebSocket, player_id: str, data: dict):
        """Handle a player action (fold, check, call, bet, raise)."""
        session = self.player_manager.get_session(player_id)
        if not session or not session.current_room:
            await self.send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return
        
        action = data.get("action")
        amount = data.get("amount")
        
        if not action:
            await self.send_error(websocket, "INVALID_ACTION", "Action is required")
            return
        
        result = self.room_manager.execute_action(
            room_id=session.current_room,
            player_id=player_id,
            action=action,
            amount=amount
        )
        
        if not result.get("success"):
            await self.send_error(websocket, "ACTION_FAILED", result.get("error", "Unknown error"))
            return
        
        # Broadcast action to room
        await self.broadcast_to_room(session.current_room, {
            "type": WSMessageType.PLAYER_ACTION_TAKEN.value,
            "data": result
        })
        
        # Broadcast updated game state to all players
        await self.broadcast_game_state(session.current_room)
    
    async def handle_start_game(self, websocket: WebSocket, player_id: str):
        """Handle request to start the game."""
        session = self.player_manager.get_session(player_id)
        if not session or not session.current_room:
            await self.send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return

        if not await self._require_host(websocket, session.current_room, player_id):
            return
        
        if not self.room_manager.start_game(session.current_room):
            await self.send_error(websocket, "START_FAILED", "Cannot start game")
            return
        
        # Broadcast the initial state
        await self.broadcast_game_state(session.current_room)
    
    async def handle_next_hand(self, websocket: WebSocket, player_id: str):
        """Handle request to deal the next hand."""
        session = self.player_manager.get_session(player_id)
        if not session or not session.current_room:
            await self.send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return
        
        if not self.room_manager.deal_next_hand(session.current_room):
            await self.send_error(websocket, "NEXT_HAND_FAILED", "Cannot deal next hand")
            return
        
        # Broadcast the updated state
        await self.broadcast_game_state(session.current_room)
    
    async def handle_reset_room(self, websocket: WebSocket, player_id: str):
        """Handle request to reset the room."""
        session = self.player_manager.get_session(player_id)
        if not session or not session.current_room:
            await self.send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return
        
        if not self.room_manager.reset_room(session.current_room):
            await self.send_error(websocket, "RESET_FAILED", "Cannot reset room")
            return
        
        # Broadcast the updated state
        await self.broadcast_game_state(session.current_room)

    async def handle_add_ai(self, websocket: WebSocket, player_id: str, data: dict):
        """Handle request to add an AI player to the lobby."""
        session = self.player_manager.get_session(player_id)
        if not session or not session.current_room:
            await self.send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return

        if not await self._require_host(websocket, session.current_room, player_id):
            return

        try:
            add_ai_request = AddAIRequest(**(data or {}))
        except ValidationError as e:
            await self.send_error(websocket, "INVALID_REQUEST", str(e))
            return

        try:
            room = self.room_manager.add_ai_player(
                session.current_room,
                ai_type=add_ai_request.ai_type,
                dqn_model_path=add_ai_request.dqn_model_path,
            )
        except ValueError as e:
            await self.send_error(websocket, "ADD_AI_FAILED", str(e))
            return

        if not room:
            await self.send_error(websocket, "ADD_AI_FAILED", "Cannot add AI player (room may be full or game already started)")
            return

        await self.broadcast_game_state(session.current_room)

    async def handle_rename_ai(self, websocket: WebSocket, player_id: str, data: dict):
        """Handle request to rename an AI player in the lobby."""
        session = self.player_manager.get_session(player_id)
        if not session or not session.current_room:
            await self.send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return

        if not await self._require_host(websocket, session.current_room, player_id):
            return

        try:
            rename_request = RenameAIRequest(**(data or {}))
        except ValidationError as e:
            await self.send_error(websocket, "INVALID_REQUEST", str(e))
            return

        try:
            room = self.room_manager.rename_ai_player(
                session.current_room,
                target_player_id=rename_request.player_id,
                new_name=rename_request.new_name,
            )
        except ValueError as e:
            await self.send_error(websocket, "RENAME_AI_FAILED", str(e))
            return

        if not room:
            await self.send_error(
                websocket,
                "RENAME_AI_FAILED",
                "Cannot rename AI player (game may already be started)",
            )
            return

        await self.broadcast_game_state(session.current_room)

    async def handle_remove_player(self, websocket: WebSocket, player_id: str, data: dict):
        """Handle request to remove a player (human or AI) from the lobby."""
        session = self.player_manager.get_session(player_id)
        if not session or not session.current_room:
            await self.send_error(websocket, "NOT_IN_ROOM", "Not in a room")
            return

        target_id = data.get("player_id")
        if not target_id:
            await self.send_error(websocket, "INVALID_REQUEST", "player_id is required")
            return

        room = self.room_manager.remove_player_from_lobby(session.current_room, target_id)
        if not room:
            await self.send_error(websocket, "REMOVE_FAILED", "Cannot remove player (game may already be started)")
            return

        await self.broadcast_game_state(session.current_room)
    
    async def send_game_state(self, websocket: WebSocket, room_id: str, player_id: str):
        """Send game state to a specific player."""
        state = self.room_manager.get_game_state(room_id, player_id)
        room = self.room_manager.get_room(room_id)
        
        if not room:
            return
        
        await self.send_message(websocket, {
            "type": WSMessageType.GAME_STATE.value,
            "data": {
                "room": room.to_dict(),
                "game_state": state,
                "player_count": room.player_count
            }
        })
    
    async def broadcast_game_state(self, room_id: str):
        """Broadcast game state to all players in a room."""
        room = self.room_manager.get_room(room_id)
        if not room:
            return
        
        for session in self.player_manager.get_players_in_room(room_id):
            if session.websocket:
                state = self.room_manager.get_game_state(room_id, session.id)
                await self.send_message(session.websocket, {
                    "type": WSMessageType.GAME_STATE.value,
                    "data": {
                        "room": room.to_dict(),
                        "game_state": state
                    }
                })


# Global connection manager instance
connection_manager = ConnectionManager()


def get_connection_manager():
    """Dependency for getting connection manager."""
    return connection_manager


@router.websocket("/ws/game")
async def game_websocket(
    websocket: WebSocket,
    player_name: str = "Player",
    manager: ConnectionManager = Depends(get_connection_manager)
):
    """
    Main WebSocket endpoint for poker gameplay.
    
    Query Parameters:
        player_name: Display name for the player
        
    Message Types (Client -> Server):
        - join_game: Join a room
        - leave_game: Leave current room
        - player_action: Take an action (fold, check, call, bet, raise)
        - start_game: Start the game (if enough players)
        
    Message Types (Server -> Client):
        - connected: Connection confirmed
        - game_state: Current game state
        - player_joined: Another player joined
        - player_left: Another player left
        - player_action_taken: Action was taken
        - player_action_required: It's your turn
        - error: Error occurred
    """
    player_id = await manager.connect(websocket, player_name)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            message_type = data.get("type", "")
            message_data = data.get("data", {})
            
            # Route message to handler
            if message_type == WSMessageType.JOIN_GAME.value:
                await manager.handle_join_game(websocket, player_id, message_data)
            
            elif message_type == WSMessageType.LEAVE_GAME.value:
                await manager.handle_leave_game(websocket, player_id)
            
            elif message_type == WSMessageType.PLAYER_ACTION.value:
                await manager.handle_player_action(websocket, player_id, message_data)
            
            elif message_type == WSMessageType.START_GAME.value:
                await manager.handle_start_game(websocket, player_id)
            
            elif message_type == WSMessageType.NEXT_HAND.value:
                await manager.handle_next_hand(websocket, player_id)
            
            elif message_type == WSMessageType.RESET_ROOM.value:
                await manager.handle_reset_room(websocket, player_id)

            elif message_type == WSMessageType.ADD_AI.value:
                await manager.handle_add_ai(websocket, player_id, message_data)

            elif message_type == WSMessageType.RENAME_AI.value:
                await manager.handle_rename_ai(websocket, player_id, message_data)

            elif message_type == WSMessageType.REMOVE_PLAYER.value:
                await manager.handle_remove_player(websocket, player_id, message_data)
            
            else:
                await manager.send_error(
                    websocket, 
                    "UNKNOWN_MESSAGE", 
                    f"Unknown message type: {message_type}"
                )
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        await manager.disconnect(websocket)


@router.websocket("/ws/game/{room_id}")
async def game_room_websocket(
    websocket: WebSocket,
    room_id: str,
    player_name: str = "Player",
    manager: ConnectionManager = Depends(get_connection_manager)
):
    """
    WebSocket endpoint for connecting directly to a specific room.
    
    Path Parameters:
        room_id: Room to join
        
    Query Parameters:
        player_name: Display name for the player
    """
    player_id = await manager.connect(websocket, player_name)
    
    try:
        # Auto-join the specified room
        joined_room = await manager.handle_join_game(
            websocket,
            player_id,
            {"room_id": room_id},
        )
        if not joined_room:
            await websocket.close(code=1008, reason="join-failed")
            return
        
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type", "")
            message_data = data.get("data", {})
            
            if message_type == WSMessageType.PLAYER_ACTION.value:
                await manager.handle_player_action(websocket, player_id, message_data)
            
            elif message_type == WSMessageType.START_GAME.value:
                await manager.handle_start_game(websocket, player_id)
            
            elif message_type == WSMessageType.NEXT_HAND.value:
                await manager.handle_next_hand(websocket, player_id)
            
            elif message_type == WSMessageType.RESET_ROOM.value:
                await manager.handle_reset_room(websocket, player_id)

            elif message_type == WSMessageType.ADD_AI.value:
                await manager.handle_add_ai(websocket, player_id, message_data)

            elif message_type == WSMessageType.RENAME_AI.value:
                await manager.handle_rename_ai(websocket, player_id, message_data)

            elif message_type == WSMessageType.REMOVE_PLAYER.value:
                await manager.handle_remove_player(websocket, player_id, message_data)
            
            elif message_type == WSMessageType.LEAVE_GAME.value:
                await manager.handle_leave_game(websocket, player_id)
                break
            
            else:
                await manager.send_error(
                    websocket, 
                    "UNKNOWN_MESSAGE", 
                    f"Unknown message type: {message_type}"
                )
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        await manager.disconnect(websocket)
