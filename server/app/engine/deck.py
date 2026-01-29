"""
Deck Module - Standard 52-card deck implementation
Provides functionality to create, shuffle, and deal cards from a standard deck.
"""

from .card import Card
import random
from typing import List


class Deck:
    """
    Represents a standard 52-card deck.
    """

    def __init__(self):
        suits = ["Hearts", "Diamonds", "Clubs", "Spades"]
        # Values: 2-10, Jack=11, Queen=12, King=13, Ace=14
        values = list(range(2, 15))
        self.cards = [Card(suit, value) for suit in suits for value in values]
        self._still_in_deck = self.cards.copy()

    def __len__(self):
        """Returns number of cards remaining in deck."""
        return len(self._still_in_deck)

    def shuffle(self):
        """Reset and shuffle the deck."""
        self._still_in_deck = self.cards.copy()
        random.shuffle(self._still_in_deck)

    def deal_card(self) -> Card:
        """
        Deal one card from the deck.
        
        Returns:
            Card: The dealt card
            
        Raises:
            ValueError: If no cards left in deck
        """
        if len(self._still_in_deck) == 0:
            raise ValueError("No cards left in the deck to deal.")
        return self._still_in_deck.pop()

    def get_remaining_count(self) -> int:
        """Get count of cards remaining in deck."""
        return len(self._still_in_deck)
    
    def peek_top(self) -> Card:
        """Peek at top card without removing it."""
        if len(self._still_in_deck) == 0:
            raise ValueError("No cards left in the deck.")
        return self._still_in_deck[-1]

    def to_dict(self) -> dict:
        """Convert deck to dictionary for serialization."""
        return {
            "cards": [card.to_dict() for card in self.cards],
            "remaining": [card.to_dict() for card in self._still_in_deck]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Deck':
        """Create deck from dictionary."""
        deck = cls.__new__(cls)
        deck.cards = [Card.from_dict(c) for c in data["cards"]]
        deck._still_in_deck = [Card.from_dict(c) for c in data["remaining"]]
        return deck

    def __repr__(self):
        """Developer-friendly representation."""
        return f"Deck(remaining={len(self._still_in_deck)}/52)"
