class Player:
    """Represents a poker player.

    Notes:
        - A player's contributed bet for the CURRENT betting round
          is tracked with `current_bet_in_round` (resets each betting round).
        - `is_playing_round` becomes False if the player folds or has
          no chips left (all-in still counts as playing until showdown).
    """

    def __init__(self, hand=None, chips=0, name: str | None = None):
        if chips < 0:
            raise ValueError("Initialized players cannot have negative chips.")
        # Avoid mutable default
        self.hand = hand if hand is not None else []
        self.chips = chips
        self.name = name or "Player"

        self.is_playing_round = True
        self.current_bet_in_round = 0  # amount invested in current betting street
        self.has_acted_this_round = False

    # --- Chip management (internal) ---
    def _add_chips(self, amount: int):
        self.chips += amount

    def _remove_chips(self, amount: int) -> int:
        if amount < 0:
            raise ValueError("Cannot remove a negative chip amount.")

        if amount > self.chips:
            # Player goes all-in instead of raising an exception in gameplay context
            amount = self.chips
        self.chips -= amount
        return amount

    # --- Actions ---
    def do_check(self, current_table_bet: int) -> bool:
        """Attempt to check.

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
        """Call the current table bet. Returns the amount contributed (could be 0)."""
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
        """Place an opening bet in a round where current_table_bet is 0.

        Returns the amount actually placed (may be reduced if player is all-in).
        """
        contributed = self._remove_chips(amount)
        self.current_bet_in_round += contributed
        self.has_acted_this_round = True
        return contributed


    def do_raise(self, current_wager: int, new_wager: int) -> tuple[int, int]:
        """Raise the current wager to a higher amount.

        Returns a tuple of (new_wager, amount_paid) if successful; (-1, -1) if invalid.
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
            Player throws all of their chips they have into
            the pool, regardless of the current wager.

            Returns:
                int 
                    The total amount of chips the player had before
                    going all in.     
        """
        self.current_subround_wager = self.chips
        self._remove_chips(self.chips)
        return self.current_subround_wager


    def do_fold(self) -> None:
        """Player folds and is out for the rest of the hand."""
        self.is_playing_round = False

    # --- State management ---
    def reset_for_new_hand(self):
        self.hand = []
        self.is_playing_round = self.chips > 0
        self.current_bet_in_round = 0
        self.has_acted_this_round = False

    def reset_for_new_betting_round(self):
        self.current_bet_in_round = 0
        self.has_acted_this_round = False
        if self.chips == 0 and self.is_playing_round:
            # Player is all-in; they won't act but remain for showdown
            self.has_acted_this_round = True

    def __str__(self):
        return f"Player({self.name}, Chips: {self.chips}, Hand: {[f'{c.value} of {c.suit}' for c in self.hand]})"