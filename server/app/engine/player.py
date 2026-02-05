"""
Player Module - Poker player representation and actions
Handles player state, actions, and chip management.
"""

from typing import List, Optional
from .card import Card


class Player:
    """
    Represents a poker player.

    Handles player state, actions, and chip management.
    """

    def __init__(
        self, 
        hand: Optional[List[Card]] = None, 
        chips: int = 0, 
        name: Optional[str] = None,
        player_id: Optional[str] = None  # NEW: for tracking in multiplayer
    ):
        if chips < 0:
            raise ValueError("Initialized players cannot have negative chips.")
        # Avoid mutable default
        self.hand = hand if hand is not None else []
        self.chips = chips
        self.name = name or "Player"

        self.is_playing_round = True
        self.current_bet_in_round = 0  # amount invested in current betting street
        self.has_acted_this_round = False
        
        self.player_id = player_id or name or "unknown"

    def _add_chips(self, amount: int):
        """Add chips to player's stack."""
        self.chips += amount

    def _remove_chips(self, amount: int) -> int:
        """
        Remove chips from player's stack.
        If player doesn't have enough, they go all-in.
        
        Returns:
            int: Amount actually removed
        """
        if amount < 0:
            raise ValueError("Cannot remove a negative chip amount.")

        if amount > self.chips:
            # Player goes all-in instead of raising an exception in gameplay context
            amount = self.chips
        self.chips -= amount
        return amount

    def do_check(self, current_table_bet: int) -> bool:
        """
        Attempt to check.

        A check is only valid if the player has already matched the current table bet.
        Returns True if the check is legal, False otherwise.
        """
        if not self.is_playing_round:
            return False
        if current_table_bet == self.current_bet_in_round:
            self.has_acted_this_round = True
            return True
        return False

    def do_call(self, current_table_bet: int) -> int:
        """
        Call the current table bet. 
        
        Returns:
            int: The amount contributed (could be 0)
        """
        if not self.is_playing_round:
            return 0
        owed = current_table_bet - self.current_bet_in_round
        if owed <= 0:
            # Nothing to call
            self.has_acted_this_round = True
            return 0
        paid = self._remove_chips(owed)
        self.current_bet_in_round += paid
        self.has_acted_this_round = True
        if self.chips == 0:
            # Still in the hand but cannot take further betting actions (all-in)
            pass
        return paid

    def do_bet(self, amount: int) -> int:
        """
        Place an opening bet in a round where current_table_bet is 0.

        Returns:
            int: The amount actually placed (may be reduced if player is all-in)
        """
        contributed = self._remove_chips(amount)
        self.current_bet_in_round += contributed
        self.has_acted_this_round = True
        return contributed

    def do_raise(self, current_wager: int, new_wager: int) -> tuple[int, int]:
        """
        Raise the current wager to a higher amount.

        Returns:
            tuple[int, int]: (new_wager, amount_paid) if successful; (-1, -1) if invalid.
            If the player doesn't have enough chips for the full raise, they go all-in
            and the returned wager reflects their total contribution this round.
        """
        if not self.is_playing_round:
            return -1, -1
        if new_wager <= current_wager:
            return -1, -1

        # Amount the player needs to put in now (target - already contributed)
        to_put = new_wager - self.current_bet_in_round
        
        paid = self._remove_chips(to_put)
        self.current_bet_in_round += paid
        self.has_acted_this_round = True
        return self.current_bet_in_round, paid

    def do_all_in(self) -> int:
        """
        Player throws all of their chips they have into the pool,
        regardless of the current wager.

        Returns:
            int: The total amount of chips the player had before going all in
        """
        all_in_amount = self.chips
        self.current_bet_in_round += self._remove_chips(self.chips)
        self.has_acted_this_round = True
        return all_in_amount

    def do_fold(self) -> None:
        """Player folds and is out for the rest of the hand."""
        self.is_playing_round = False

    def reset_for_new_hand(self):
        """Reset player state for a new hand."""
        self.hand = []
        self.is_playing_round = self.chips > 0
        self.current_bet_in_round = 0
        self.has_acted_this_round = False

    def reset_for_new_betting_round(self):
        """Reset player state for a new betting round."""
        self.current_bet_in_round = 0
        self.has_acted_this_round = False
        if self.chips == 0 and self.is_playing_round:
            # Player is all-in; they won't act but remain for showdown
            self.has_acted_this_round = True

    def to_dict(self, hide_cards: bool = False) -> dict:
        """
        Convert player to dictionary for JSON serialization.
        
        Args:
            hide_cards: If True, don't include hand cards (for opponent view)
            
        Returns:
            dict: Player state as dictionary
        """
        return {
            "player_id": self.player_id,
            "name": self.name,
            "chips": self.chips,
            "hand": [] if hide_cards else [card.to_dict() for card in self.hand],
            "is_playing_round": self.is_playing_round,
            "current_bet_in_round": self.current_bet_in_round,
            "has_acted_this_round": self.has_acted_this_round
        }
    
    def get_public_info(self) -> dict:
        """
        Get public information about player (for opponents).
        Hides private information like hand cards.
        """
        return {
            "player_id": self.player_id,
            "name": self.name,
            "chips": self.chips,
            "hand_size": len(self.hand),  # Only show count, not cards
            "is_playing_round": self.is_playing_round,
            "current_bet_in_round": self.current_bet_in_round,
            "has_acted_this_round": self.has_acted_this_round
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Player':
        """Create player from dictionary."""
        player = cls(
            hand=[Card.from_dict(c) for c in data.get("hand", [])],
            chips=data["chips"],
            name=data["name"],
            player_id=data.get("player_id")
        )
        player.is_playing_round = data["is_playing_round"]
        player.current_bet_in_round = data["current_bet_in_round"]
        player.has_acted_this_round = data["has_acted_this_round"]
        return player

    def __str__(self):
        return f"Player({self.name}, Chips: {self.chips}, Hand: {[f'{c.value} of {c.suit}' for c in self.hand]})"

    def __repr__(self):
        return f"Player(id={self.player_id}, name={self.name}, chips={self.chips})"
