"""
REST API - HTTP endpoints for room and game management

Provides endpoints for:
- Room creation and listing
- Room information and management
- Game state queries (for polling-based clients)
"""

from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from ..managers import RoomManager, PlayerManager
from ..models.schemas import (
    RoomConfig,
    RoomModel,
    RoomListResponse,
    GameStateModel,
    PlayerAction,
    PlayerActionResult,
)


router = APIRouter(prefix="/api", tags=["poker"])


# These will be set by the main app
_room_manager: RoomManager = None
_player_manager: PlayerManager = None


def set_managers(room_manager: RoomManager, player_manager: PlayerManager):
    """Set the manager instances (called from main.py)."""
    global _room_manager, _player_manager
    _room_manager = room_manager
    _player_manager = player_manager


def get_room_manager() -> RoomManager:
    """Get the room manager instance."""
    if _room_manager is None:
        raise HTTPException(status_code=500, detail="Server not properly initialized")
    return _room_manager


def get_player_manager() -> PlayerManager:
    """Get the player manager instance."""
    if _player_manager is None:
        raise HTTPException(status_code=500, detail="Server not properly initialized")
    return _player_manager


# ============================================================
# Room Endpoints
# ============================================================

@router.post("/rooms", response_model=RoomModel, status_code=201)
async def create_room(config: RoomConfig):
    """
    Create a new poker room.
    
    Args:
        config: Room configuration
        
    Returns:
        Created room information
    """
    room_manager = get_room_manager()
    room = room_manager.create_room(config)
    return RoomModel(**room.to_dict())


@router.get("/rooms", response_model=RoomListResponse)
async def list_rooms(
    include_full: bool = Query(True, description="Include rooms that are full")
):
    """
    List all available rooms.
    
    Args:
        include_full: Whether to include full rooms
        
    Returns:
        List of rooms
    """
    room_manager = get_room_manager()
    rooms = room_manager.list_rooms(include_full=include_full)
    
    return RoomListResponse(
        rooms=[RoomModel(**r.to_dict()) for r in rooms],
        total=len(rooms)
    )


@router.get("/rooms/{room_id}", response_model=RoomModel)
async def get_room(room_id: str):
    """
    Get information about a specific room.
    
    Args:
        room_id: Room ID
        
    Returns:
        Room information
    """
    room_manager = get_room_manager()
    room = room_manager.get_room(room_id)
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    return RoomModel(**room.to_dict())


@router.delete("/rooms/{room_id}")
async def delete_room(room_id: str):
    """
    Delete a room.
    
    Args:
        room_id: Room ID
        
    Returns:
        Success message
    """
    room_manager = get_room_manager()
    
    if not room_manager.delete_room(room_id):
        raise HTTPException(status_code=404, detail="Room not found")
    
    return {"message": "Room deleted", "room_id": room_id}


# ============================================================
# Game State Endpoints
# ============================================================

@router.get("/rooms/{room_id}/state")
async def get_game_state(
    room_id: str,
    player_id: Optional[str] = Query(None, description="Get player-specific view")
):
    """
    Get the current game state.
    
    Args:
        room_id: Room ID
        player_id: Optional player ID for player-specific view
        
    Returns:
        Game state
    """
    room_manager = get_room_manager()
    room = room_manager.get_room(room_id)
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if not room.game:
        return {
            "room": room.to_dict(),
            "game_state": None,
            "message": "Game not started"
        }
    
    state = room_manager.get_game_state(room_id, player_id)
    
    return {
        "room": room.to_dict(),
        "game_state": state
    }


@router.post("/rooms/{room_id}/start")
async def start_game(room_id: str):
    """
    Start the game in a room.
    
    Args:
        room_id: Room ID
        
    Returns:
        Success message and game state
    """
    room_manager = get_room_manager()
    
    if not room_manager.start_game(room_id):
        room = room_manager.get_room(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        if not room.can_start:
            raise HTTPException(
                status_code=400, 
                detail=f"Need at least {room.config.min_players} players to start"
            )
        raise HTTPException(status_code=400, detail="Cannot start game")
    
    # Play first hand
    room_manager.play_hand(room_id)
    
    state = room_manager.get_game_state(room_id)
    
    return {
        "message": "Game started",
        "game_state": state
    }


@router.post("/rooms/{room_id}/hand")
async def play_hand(room_id: str):
    """
    Play the next hand in a room.
    
    Args:
        room_id: Room ID
        
    Returns:
        Game state after hand
    """
    room_manager = get_room_manager()
    
    if not room_manager.play_hand(room_id):
        room = room_manager.get_room(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        if not room.is_active:
            raise HTTPException(status_code=400, detail="Game not started")
        raise HTTPException(status_code=400, detail="Cannot play hand")
    
    state = room_manager.get_game_state(room_id)
    
    return {
        "message": "Hand played",
        "game_state": state
    }


# ============================================================
# Player Action Endpoints
# ============================================================

@router.post("/rooms/{room_id}/action", response_model=PlayerActionResult)
async def player_action(
    room_id: str,
    player_id: str,
    action: PlayerAction
):
    """
    Execute a player action.
    
    Args:
        room_id: Room ID
        player_id: Player making the action
        action: Action to take
        
    Returns:
        Action result
    """
    room_manager = get_room_manager()
    
    result = room_manager.execute_action(
        room_id=room_id,
        player_id=player_id,
        action=action.action.value,
        amount=action.amount
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Action failed"))
    
    return PlayerActionResult(**result)


# ============================================================
# Health and Info Endpoints
# ============================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/info")
async def server_info():
    """Get server information."""
    room_manager = get_room_manager()
    player_manager = get_player_manager()
    
    return {
        "name": "Poker Server",
        "version": "1.0.0",
        "rooms": len(room_manager.list_rooms()),
        "connected_players": player_manager.get_connected_count(),
        "agent_types": ["random", "dqn"]
    }


# ============================================================
# Agent Info Endpoints
# ============================================================

@router.get("/agents")
async def list_agents():
    """List available AI agent types."""
    from ..engine.agents import AgentRegistry
    
    return {
        "agents": AgentRegistry.list_agents(),
        "default": "random"
    }


@router.get("/models")
async def list_models():
    """
    List available .pth model files for DQN agents.
    
    Returns:
        List of model filenames and their paths
    """
    server_root = Path(__file__).resolve().parents[2]
    cwd = Path.cwd()

    candidate_dirs = [
        server_root / "models",
        cwd / "server" / "models",
        cwd / "models",
    ]

    seen_paths = set()
    pth_files = []
    for models_dir in candidate_dirs:
        if not models_dir.exists() or not models_dir.is_dir():
            continue
        for model_path in sorted(models_dir.glob("*.pth")):
            resolved = str(model_path.resolve())
            if resolved not in seen_paths:
                seen_paths.add(resolved)
                pth_files.append(model_path.resolve())

    pth_files.sort(key=lambda p: p.name)
    return {
        "models": [
            {"name": f.name, "path": str(f)}
            for f in pth_files
        ]
    }
