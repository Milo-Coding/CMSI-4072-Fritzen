"""
Poker Game Engine

Core poker game logic migrated from the original Python implementation.
"""

from .card import Card
from .deck import Deck
from .player import Player
from .game import Game, GameEventType, GamePhase
from .evaluator import (
    HandRank, 
    evaluate_best_five, 
    evaluate_five,
    compare_hands,
    get_hand_name,
    hand_to_string
)

# Import agents submodule
from . import agents

__all__ = [
    'Card', 
    'Deck', 
    'Player', 
    'Game',
    'GameEventType',
    'GamePhase',
    'HandRank',
    'evaluate_best_five',
    'evaluate_five',
    'compare_hands',
    'get_hand_name',
    'hand_to_string',
    'agents',
]
