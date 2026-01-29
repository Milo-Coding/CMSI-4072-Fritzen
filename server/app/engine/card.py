"""
Card Module - Handles playing card representation and validation
"""


class Card:
    """
    Represents a playing card.
        
    Attributes:
        suit (str): "Hearts", "Diamonds", "Clubs", or "Spades"
        value (int): 2-14 (where 11=Jack, 12=Queen, 13=King, 14=Ace)
    """

    def __init__(self, suit: str, value: int):
        if suit not in ("Hearts", "Diamonds", "Clubs", "Spades"):
            raise ValueError(
                f'Suit "{suit}" is not a valid suit. '
                'They must be "Hearts", "Diamonds", "Clubs", or "Spades".'
            )
        if value < 2 or value > 14:
            raise ValueError(f'Value "{value}" is not between 2 to 14.')
        
        self.suit: str = suit
        self.value: int = value

    def to_dict(self) -> dict:
        """Convert card to dictionary for JSON serialization for web APIs."""
        return {
            "suit": self.suit,
            "value": self.value,
            "display": self.get_display_name()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Card':
        """Create card from dictionary."""
        return cls(suit=data["suit"], value=data["value"])

    def __eq__(self, other):
        """Check if two cards are equal."""
        if not isinstance(other, Card):
            return False
        return self.suit == other.suit and self.value == other.value
    
    def __hash__(self):
        """Make cards hashable for use in sets/dicts."""
        return hash((self.suit, self.value))

    def get_display_name(self) -> str:
        """Get human-readable card name (e.g., 'K♥', 'A♠')."""
        suit_symbols = {
            "Hearts": "♥",
            "Diamonds": "♦",
            "Clubs": "♣",
            "Spades": "♠"
        }
        
        value_names = {
            11: "J",
            12: "Q",
            13: "K",
            14: "A"
        }
        
        value_str = value_names.get(self.value, str(self.value))
        return f"{value_str}{suit_symbols[self.suit]}"
    
    def __str__(self):
        """String representation of card."""
        return self.get_display_name()
    
    def __repr__(self):
        """Developer-friendly representation."""
        return f"Card(suit='{self.suit}', value={self.value})"
