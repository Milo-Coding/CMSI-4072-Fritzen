"""
Poker Server Application

A multiplayer Texas Hold'em poker server with WebSocket support
and AI agent capabilities.

Modules:
    engine: Core poker game logic (Card, Deck, Player, Game, Evaluator)
    engine.agents: AI agent framework (BaseAgent, DQNAgent, RandomAgent)
    models: Pydantic schemas for API validation
    managers: Room and player session management
    api: REST and WebSocket endpoints
    main: FastAPI application entry point
"""

__version__ = "1.0.0"
