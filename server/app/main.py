"""
Poker Server - Main FastAPI Application

This is the entry point for the poker server.
Run with: uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .managers import RoomManager, PlayerManager
from .api.websocket import router as websocket_router, connection_manager
from .api.rest import router as rest_router, set_managers


# Global manager instances
room_manager = RoomManager()
player_manager = PlayerManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    
    Sets up and tears down resources.
    """
    # Startup
    print("🃏 Poker Server starting up...")
    
    # Initialize managers
    set_managers(room_manager, player_manager)
    connection_manager.setup(room_manager, player_manager)
    
    # List available agents
    from .engine.agents import AgentRegistry
    print(f"  Available AI agents: {AgentRegistry.list_agents()}")
    
    print("✅ Server ready!")
    
    yield
    
    # Shutdown
    print("🛑 Poker Server shutting down...")
    # Cleanup could go here


# Create FastAPI application
app = FastAPI(
    title="Poker Server",
    description="""
    A real-time multiplayer Texas Hold'em poker server.
    
    ## Features
    
    - **Real-time gameplay** via WebSocket
    - **Multiple rooms** for concurrent games
    - **AI opponents** with pluggable agent system
    - **RESTful API** for room management
    
    ## Endpoints
    
    ### WebSocket
    - `ws://host/ws/game` - Main game connection
    - `ws://host/ws/game/{room_id}` - Direct room connection
    
    ### REST
    - `POST /api/rooms` - Create a room
    - `GET /api/rooms` - List rooms
    - `GET /api/rooms/{id}` - Get room info
    - `POST /api/rooms/{id}/start` - Start game
    - `POST /api/rooms/{id}/action` - Make an action
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for React client
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(websocket_router)
app.include_router(rest_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "name": "Poker Server",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "websocket": "/ws/game",
        "api": "/api"
    }


# For running directly with python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
