from card import Card
from deck import Deck
from player import Player
from agent import Agent
from human import Human
from itertools import combinations

HAND_RANKS = {
    'high_card': 1,
    'pair': 2,
    'two_pair': 3,
    'three_kind': 4,
    'straight': 5,
    'flush': 6,
    'full_house': 7,
    'four_kind': 8,
    'straight_flush': 9,
}


class Game:
    """Implements a simplified No-Limit Texas Hold'em style game flow.

    TODO:
        - No UI (console output only).
        - No side-pot handling for partial all-ins.
        - No Player input (assumes simple/random decisions for non-Agent players).
        - No checks for valid blinds (assumes players have enough chips).
        - Game only lasts a fixed number of hands, no continuous play.
        - No action history tracking for Agents.
    """

    def __init__(self, small_blind=10, start_total=1000, num_players=2, debug_mode=False, human_player_index=-1):
        self.small_blind = small_blind
        self.big_blind = small_blind * 2
        self.start_total = start_total
        self.num_players = num_players

        self.players = []
        self.training_mode = False
        
        # Create a minimal game state for agent initialization
        # First create empty players list that will be populated
        temp_players = [None] * num_players
        initial_game_state = {
            'opponents_chips': [start_total] * (num_players - 1),
            'current_table_bet': 0,
            'call_amount': 0,
            'pot': 0,
            'community_cards': [],
            'state_name': 'Pre-Flop',
            'dealer_index': 0,
            'players': temp_players,
            'available_actions': ['check', 'bet'],
            'history': []
        }

        # Now create the players
        for i in range(self.num_players):
            if i == human_player_index:
                player = Human(chips=self.start_total, name=f"Human")
            else:
                # Create a copy of the game state with the correct agent index
                agent_state = initial_game_state.copy()
                agent_state['agent_index'] = i
                player = Agent(chips=self.start_total, name=f"AI_{i+1}", initial_state=agent_state)
            self.players.append(player)
            initial_game_state['players'][i] = player  # Update the players list in the game state
                
        self.deck = Deck()
        self.community_cards = []
        self.dealer_index = 0
        self.pot = 0
        self.current_table_bet = 0  # highest bet in current betting round

        self.debug_mode = debug_mode
        self.debug_community = []

        self._debug_checks()

    # --- Game lifecycle ---
    def start(self, num_hands: int = 1):
        print(f"Starting game with {self.num_players} players, each with ${self.start_total}, small blind = ${self.small_blind}.")

        # TODO: transition from set hand range to continuous gameplay
        for h in range(num_hands):
            print(f"\n--- Hand {h+1} ---")
            self.play_hand()
            # Advance dealer
            self.dealer_index = (self.dealer_index + 1) % self.num_players

    def play_hand(self):
        # Preparation
        self._prepare_new_hand()
        self._post_blinds()
        self._deal_hole_cards()
        print("Hole cards dealt.")
        self._betting_round("Pre-Flop")
        if self._hand_over():
            return self._award_pot_if_single()

        # Flop
        self._deal_community(3)
        print("Flop:", self._cards_str(self.community_cards))
        self._betting_round("Flop")
        if self._hand_over():
            return self._award_pot_if_single()

        # Turn
        self._deal_community(1)
        print("Turn:", self._cards_str(self.community_cards))
        self._betting_round("Turn")
        if self._hand_over():
            return self._award_pot_if_single()

        # River
        self._deal_community(1)
        print("River:", self._cards_str(self.community_cards))
        self._betting_round("River")

        # Showdown
        self._showdown()

    # --- Preparation ---
    def _prepare_new_hand(self):
        if not self.debug_mode:
            for p in self.players:
                p.reset_for_new_hand()
        self.pot = 0
        self.community_cards = []
        self.deck.shuffle()
        self.current_table_bet = 0

    def _post_blinds(self):
        # TODO: check that players have enough chips to post blinds
        if len(self.players) < 2:
            return
        sb_index = (self.dealer_index + 1) % len(self.players)
        bb_index = (self.dealer_index + 2) % len(self.players)
        small_blind_player = self.players[sb_index]
        big_blind_player = self.players[bb_index]
        sb_paid = small_blind_player._remove_chips(self.small_blind)
        bb_paid = big_blind_player._remove_chips(self.big_blind)
        small_blind_player.current_bet_in_round = sb_paid
        big_blind_player.current_bet_in_round = bb_paid
        self.current_table_bet = bb_paid
        self.pot += sb_paid + bb_paid
        print(f"Blinds posted: {small_blind_player.name} (SB {sb_paid}), {big_blind_player.name} (BB {bb_paid}).")

    def set_cards(self, community_cards, *hands):
        """
            DEBUG ONLY PUBLIC METHOD
            Sets the cards such that the community cards and each players
            hands are pre-defined.

            Parameters:
                community_cards: list[Card]
                    A list that contains exactly five cards. The first three will
                    be revealed during Flop, then the next will be the Turn, 
                    and the final will be the River.
                *hands: list[list[Card]]
                    A list of tuples where each list hold a pair of cards the
                    players WILL be holding. Note that these cards in order
                    in how the Players are initialized when making a new game.
        """
        if len(community_cards) != 5:
            raise ValueError("Parameter community_cards requires a list size of 5.")
        if len(hands) != self.num_players:
            raise ValueError(f"The total hands cannot be held by {len(self.players)} players.") 
        self.debug_community = community_cards
        for i in range(len(hands)):
            self.players[i].hand = hands[i]

    def _deal_hole_cards(self):
        if not self.debug_mode:
            for p in self.players:
              # Deal cards to all players with chips or those who posted blinds, even if chips == 0 after posting
              if p.current_bet_in_round > 0 or p.chips > 0:
                  p.hand = [self.deck.deal_card(), self.deck.deal_card()]

    def _deal_community(self, n: int):
        if self.debug_mode:
            self.community_cards += self.debug_community[:n]
            self.debug_community = self.debug_community[n:]
        else:
            for _ in range(n):
                self.community_cards.append(self.deck.deal_card())

    # --- Betting ---
    def _betting_round(self, state_name: str):
        print(f"-- {state_name} betting round --")
        
        self._setup_new_betting_round(state_name)
        active_players = self._get_active_players()
        if len(active_players) <= 1:
            return

        # Determine starting player
        if state_name == "Pre-Flop":
            action_index = (self.dealer_index + 3) % len(self.players)
        else:
            action_index = (self.dealer_index + 1) % len(self.players)

        players_to_act = len(active_players)
        last_aggressor = None

        # Pre-flop, the BB is the initial aggressor
        if state_name == "Pre-Flop":
            bb_index = (self.dealer_index + 2) % len(self.players)
            last_aggressor = self.players[bb_index]

        while players_to_act > 0:
            # Find the next player who is actually in the hand
            while self.players[action_index] not in active_players:
                action_index = (action_index + 1) % len(self.players)

            player = self.players[action_index]

            # If action returns to the aggressor and no one has re-raised, the round can end.
            if player == last_aggressor:
                # Exception: Pre-flop, BB can act if no one raised.
                if state_name == "Pre-Flop" and self.current_table_bet == self.big_blind:
                    pass # Allow BB to act
                else:
                    break
            
            # If all players have acted and the bet is matched, end the round.
            if players_to_act == 1 and player.current_bet_in_round == self.current_table_bet and last_aggressor == self.players[(self.dealer_index + 2) % len(self.players)]:
                if state_name == "Pre-Flop" and self.current_table_bet == self.big_blind:
                     break

            decision = self._get_player_decision(player, state_name)
            self._execute_player_decision(player, decision)
            players_to_act -= 1

            if self._hand_over():
                return

            # If there was a bet or raise, reset the action
            if isinstance(decision, tuple) and (decision[0] == "bet" or decision[0] == "raise"):
                last_aggressor = player
                # Recalculate who needs to act. It's everyone still in the hand.
                players_to_act = len(self._get_active_players())

            action_index = (action_index + 1) % len(self.players)

        # Final check for the big blind pre-flop if there was no raise
        if state_name == "Pre-Flop" and self.current_table_bet == self.big_blind and not self._hand_over():
            bb_index = (self.dealer_index + 2) % len(self.players)
            bb_player = self.players[bb_index]
            if bb_player in active_players:
                # If BB hasn't had a chance to check/raise, give it
                if bb_player.current_bet_in_round == self.big_blind:
                    decision = self._get_player_decision(bb_player, state_name)
                    self._execute_player_decision(bb_player, decision)

    def _setup_new_betting_round(self, state_name: str):
        """Reset betting state for new round"""
        if state_name != "Pre-Flop":
            for player in self.players:
                player.reset_for_new_betting_round()
            self.current_table_bet = 0

    def _get_starting_player_index(self) -> int:
        """Determine who starts the betting"""
        return (self.dealer_index + 1) % len(self.players)

    def _should_skip_player(self, player: Player) -> bool:
        """Check if we should skip this player"""
        return not player.is_playing_round or player.chips == 0

    def _should_end_betting_round(self) -> bool:
        """Check if betting round should end"""
        active_players = self._get_active_players()
        
        # End if only one player remains
        if len(active_players) <= 1:
            return True
            
        return self._all_players_have_matched_and_acted()

    def _all_players_have_matched_and_acted(self) -> bool:
        """Check if all active players have matched the current bet AND had a chance to act"""
        for player in self.players:
            if player.is_playing_round and player.chips > 0:
                # Player hasn't matched the bet
                if player.current_bet_in_round != self.current_table_bet:
                    return False
                # Player hasn't acted this round (for the first cycle)
                if not player.has_acted_this_round:
                    return False
        return True

    def _get_active_players(self):
        """Get list of players still in the hand"""
        return [p for p in self.players if p.is_playing_round]

    # --- Player Decision Logic ---
    def _get_player_decision(self, player: Player, state_name: str):
        """Get decision from player based on their type"""
        call_amount = self.current_table_bet - player.current_bet_in_round
        available_actions = self._get_available_actions(player, call_amount)
        
        if isinstance(player, Agent):
            return self._get_agent_decision(player, available_actions, call_amount, state_name)
        elif isinstance(player, Human):
            return self._get_human_decision(player, available_actions, call_amount, state_name)
        else:
            # TODO: Replace with real player input mechanism
            return self._get_simple_decision(player, available_actions, call_amount, state_name)

    def _get_available_actions(self, player: Player, call_amount: int) -> list:
        """Determine what actions the player can take"""
        actions = []
        
        actions.append("fold")
        if call_amount == 0:
            actions.append("check")
        else:
            actions.append("call")
        
        # Can only bet/raise if they have chips
        if player.chips > 0:
            if self.current_table_bet == 0:
                actions.append("bet")
            else:
                min_raise = self.current_table_bet + self.big_blind
                max_bet = player.chips + player.current_bet_in_round
                if max_bet >= min_raise:
                    actions.append("raise")
        
        return actions

    def _get_agent_decision(self, player, available_actions, call_amount, state_name):
        """Let the Agent make a decision using their own logic"""
        game_state = {
            'current_table_bet': self.current_table_bet,
            'call_amount': call_amount,
            'available_actions': available_actions,
            'state_name': state_name,
            'opponents_chips': [p.chips for p in self.players if p != player],
            'pot': self.pot,
            'community_cards': self.community_cards,
            'players': self.players,
            'dealer_index': self.dealer_index,
            'agent_index': self.players.index(player),
            'history': []  # TODO Placeholder for action history tracking
        }
        
        # Agent decides and returns the action (doesn't execute it)
        return player.decide_action(game_state)
    
    def set_training_mode(self, enabled):
        """Enable or disable training mode for all AI players"""
        self.training_mode = enabled
        for player in self.players:
            if isinstance(player, Agent):
                player.is_training = enabled
                if enabled:
                    print(f"{player.name} training mode enabled")
                else:
                    print(f"{player.name} training mode disabled")
    
    def reset_ai_models(self):
        """Reset all AI models"""
        for player in self.players:
            if isinstance(player, Agent):
                player.reset_model()
        print("All AI models reset")

    def _interpret_agent_action(self, player, call_amount):
        """Figure out what action the agent took"""
        if not player.is_playing_round:
            return "fold"
        elif player.current_bet_in_round > self.current_table_bet:
            return ("raise", player.current_bet_in_round)
        elif player.current_bet_in_round == self.current_table_bet:
            return "call" if call_amount > 0 else "check"
        elif player.current_bet_in_round > 0 and self.current_table_bet == 0:
            return ("bet", player.current_bet_in_round)
        else:
            # Fallback for partial calls or other states
            return "call" if call_amount > 0 else "check"
        
    def _get_human_decision(self, player, available_actions, call_amount, state_name):
        """Get decision from human player via command line"""
        return player.get_human_decision(available_actions, call_amount, self.current_table_bet, self.pot)

    def _get_simple_decision(self, player, available_actions, call_amount, state_name):
        """Simple decision logic for regular players"""
        import random
    
        # Simple random strategy that works without hand evaluation
        if "check" in available_actions and random.random() < 0.8:
            return "check"
        elif "call" in available_actions and random.random() < 0.7:
            return "call"
        elif "bet" in available_actions and random.random() < 0.4:
            return ("bet", min(20, player.chips))
        elif "raise" in available_actions and random.random() < 0.3:
            raise_amount = self.current_table_bet + 20
            return ("raise", min(raise_amount, player.chips + player.current_bet_in_round))
        elif "fold" in available_actions and random.random() < 0.2:
            return "fold"
        else:
            # Default fallback
            if "check" in available_actions:
                return "check"
            elif "call" in available_actions:
                return "call"
            else:
                return "fold"

    # --- Execute Player Decisions ---
    def _execute_player_decision(self, player: Player, decision):
        """Execute the player's chosen action"""
        if decision == "fold":
            self._handle_fold(player)
        elif decision == "check":
            self._handle_check(player)
        elif decision == "call":
            self._handle_call(player)
        elif isinstance(decision, tuple):
            action_type, amount = decision
            if action_type == "bet":
                self._handle_bet(player, amount)
            elif action_type == "raise":
                self._handle_raise(player, amount)

    def _handle_fold(self, player: Player):
        """Handle fold action"""
        player.do_fold()
        print(f"{player.name} folds.")

    def _handle_check(self, player: Player):
        """Handle check action"""
        if player.do_check(self.current_table_bet):
            print(f"{player.name} checks.")
        else:
            # Check failed, convert to call
            self._handle_call(player, "check failed")

    def _handle_call(self, player: Player, reason=""):
        """Handle call action"""
        contributed = player.do_call(self.current_table_bet)
        self.pot += contributed
        if reason:
            print(f"{player.name} calls {contributed} ({reason}). (Pot={self.pot})")
        else:
            print(f"{player.name} calls {contributed}. (Pot={self.pot})")

    def _handle_bet(self, player: Player, amount: int):
        """Handle bet action"""
        contributed = player.do_bet(amount)
        self.current_table_bet = contributed
        self.pot += contributed
        print(f"{player.name} bets {contributed}. (Pot={self.pot})")

    def _handle_raise(self, player: Player, amount: int):
        """Handle raise action"""
        new_wager, amount_added = player.do_raise(self.current_table_bet, amount)
        if new_wager != -1 and new_wager > self.current_table_bet:
            self.current_table_bet = new_wager
            self.pot += amount_added
            print(f"{player.name} raises to {new_wager}. (Pot={self.pot})")
        else:
            # Raise failed, convert to call
            self._handle_call(player, "raise failed")

    # --- Showdown ---
    def _showdown(self):
        # Check if there is only one player still playing.
        contenders = [p for p in self.players if p.is_playing_round]
        if len(contenders) == 1:
            winner = contenders[0]
            winner._add_chips(self.pot)
            print(f"{winner.name} wins uncontested pot of {self.pot}.")
            return

        ranked = []
        for p in contenders:
            rank = self._evaluate_best_five(p.hand + self.community_cards)
            ranked.append((rank, p))
            print(f"{p.name} shows {self._cards_str(p.hand)} -> {rank}")

        ranked.sort(key=lambda x: x[0], reverse=True)
        best_rank = ranked[0][0]
        winners = [p for r, p in ranked if r == best_rank]
        share = self.pot // len(winners)    # TODO determine how to work with chip remainders.
        
        for player in self.players:
            if isinstance(player, Agent):
                if player in winners:
                    result = 1  # Win
                else:
                    result = -1  # Loss
                player.receive_round_result(result)
                player.training_episodes += 1
        
        for w in winners:
            w._add_chips(share)
        
        if len(winners) > 1:
            print(f"Winners: {', '.join(w.name for w in winners)} split pot {self.pot} (each {share}).")
        else:
            print(f"Winner: {', '.join(w.name for w in winners)} wins pot of {self.pot}.")

    def _award_pot_if_single(self):
        contenders = [p for p in self.players if p.is_playing_round]
        if len(contenders) == 1:
            winner = contenders[0]
            winner._add_chips(self.pot)
            print(f"{winner.name} wins pot of {self.pot}.")

    # --- Getters ---
    def is_still_playable(self) -> bool:
        """Returns true if at least 2 players have chips"""
        counter = 0
        for p in self.players:
            if p.chips > 0:
                counter += 1
        return counter > 1

    # --- Helpers ---
    def _hand_over(self) -> bool:
        active = [p for p in self.players if p.is_playing_round]
        return len(active) <= 1

    def _cards_str(self, cards):
        return [f"{c.value} {c.suit[0]}" for c in cards]

    # --- Hand evaluation ---
    def _evaluate_best_five(self, cards):
        # Evaluate all 5-card combos
        best = None
        for combo in combinations(cards, 5):
            rank = self._evaluate_five(combo)
            if best is None or rank > best:
                best = rank
        return best

    def _evaluate_five(self, five_cards):
        values = sorted([c.value for c in five_cards], reverse=True)
        suits = [c.suit for c in five_cards]
        counts = {v: values.count(v) for v in set(values)}
        is_flush = len(set(suits)) == 1
        unique_vals = sorted(set(values), reverse=True)

        # Straight detection including Ace-low (A-2-3-4-5)
        is_straight = False
        if len(unique_vals) == 5:
            if max(unique_vals) - min(unique_vals) == 4:
                is_straight = True
            elif set(unique_vals) == {14, 2, 3, 4, 5}:
                is_straight = True
                # For Ace-low straight, treat Ace as 1 for kicker ordering
                values = [5, 4, 3, 2, 1]

        # Frequency patterns
        freq_sorted = sorted(((cnt, val) for val, cnt in counts.items()), reverse=True)
        # Build kicker ordering by frequency then value
        ordered_vals = []
        for cnt, val in freq_sorted:
            ordered_vals.extend([val] * cnt)

        if is_flush and is_straight:
            return (HAND_RANKS['straight_flush'], ordered_vals)
        if 4 in counts.values():
            return (HAND_RANKS['four_kind'], ordered_vals)
        if sorted(counts.values()) == [2, 3]:
            return (HAND_RANKS['full_house'], ordered_vals)
        if is_flush:
            return (HAND_RANKS['flush'], values)
        if is_straight:
            return (HAND_RANKS['straight'], values)
        if 3 in counts.values():
            return (HAND_RANKS['three_kind'], ordered_vals)
        if list(counts.values()).count(2) == 2:
            return (HAND_RANKS['two_pair'], ordered_vals)
        if 2 in counts.values():
            return (HAND_RANKS['pair'], ordered_vals)
        return (HAND_RANKS['high_card'], values)


    def _debug_checks(self):
        if self.num_players < 2:
            raise Exception("Error: Game cannot have less than 2 players.")
        elif self.num_players > 12:
            raise Exception("Error: Game cannot have more than 12 players.")
        elif self.small_blind * 2 > self.start_total:
            raise Exception("Erorr: Small blind is too big! Raise the start total or lower the small blind cost!")
