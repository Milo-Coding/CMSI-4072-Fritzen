import os

try:
    import pygame
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False


class Card:

    card_back_img = None
    _load_graphics = True

    def __init__(self, suit: str, value: int):
        # For simplicity, the Ace (A) will be 14, NOT 1.
        # Suits Values: "Hearts", "Diamonds", "Clubs", "Spades"
        if suit not in ("Hearts", "Diamonds", "Clubs", "Spades"):
            raise ValueError(f'Suit "{suit}" is not a valid suit. They must be "Hearts", "Diamonds", "Clubs", or "Spades".')
        if value < 2 or value > 14:
            raise ValueError(f'Value "{value}" is not between 2 to 14.')
        self.suit: str = suit
        self.value: int = value

        # Graphics
        self.flipped = False
        self.card_img = None
        
        # Only load graphics if needed and pygame is available
        if Card._load_graphics and HAS_PYGAME:
            ref_path: list[str] = ["img", "cards"]
            match value:
                case 11:
                    ref_path.append(f"J{suit[0]}.jpg")
                case 12:
                    ref_path.append(f"Q{suit[0]}.jpg")
                case 13:
                    ref_path.append(f"K{suit[0]}.jpg")
                case 14:
                    ref_path.append(f"A{suit[0]}.jpg")
                case _:
                    ref_path.append(f"{value}{suit[0]}.jpg")
            self.card_img = pygame.image.load(os.path.join(*ref_path)).convert()

    @staticmethod
    def initialize_card_back() -> None:
        if Card._load_graphics and HAS_PYGAME:
            Card.card_back_img = pygame.image.load(os.path.join(*["img", "cards", "Back.jpg"])).convert()

    @staticmethod
    def disable_graphics() -> None:
        """Disable graphics loading for headless/training mode."""
        Card._load_graphics = False

    @staticmethod
    def is_same_suit(card_ref, *cards) -> bool:
        """
            A function that checks if the cards are in the same suit.

            Parameters:
                card_ref (Card)
                    The card used as reference.
                *cards (Card[])
                    The cards that are being compared to the first card.

            Returns:
                bool - True if the cards' suits match. Otherwise, false.
        """
        for card in cards:
            if card_ref.suit != card.suit:
                return False
        return True


    def __lt__(self, other) -> bool:
        """
            Compares the value between two cards,
            disregarding suit.
        """
        return self.value > other.value
    
    
    def __eq__(self, other) -> bool:
        """
            Compares the value between two cards,
            disregarding suit.
        """
        return self.value == other.value

    def __gt__(self, other) -> bool:
        """
            Compares the value between two cards,
            disregarding suit.
        """
        return self.value < other.value