"""
Agent System - Extensible AI player framework

This module provides a plugin-based architecture for AI poker agents.
New agents can be created by subclassing BaseAgent and implementing
the decide_action method.
"""

from .base_agent import BaseAgent, AgentRegistry
from .dqn_agent import DQNAgent
from .random_agent import RandomAgent

__all__ = [
    'BaseAgent',
    'AgentRegistry',
    'DQNAgent',
    'RandomAgent',
]
