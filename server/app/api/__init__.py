"""
API Module - REST and WebSocket endpoints

Provides the HTTP and WebSocket interfaces for the poker server.
"""

from .websocket import router as websocket_router
from .rest import router as rest_router

__all__ = [
    'websocket_router',
    'rest_router',
]
