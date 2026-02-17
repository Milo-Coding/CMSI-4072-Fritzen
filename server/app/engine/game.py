"""
Game Module - Texas Hold'em Poker Game Engine
Core poker game logic for Texas Hold'em, including game lifecycle,
betting rounds, hand evaluation, and event handling.
"""

from enum import Enum
from typing import List, Dict, Callable, Optional, Tuple, Any
import random
from .card import Card
from .deck import Deck
from .player import Player
from .evaluator import evaluate_best_five, compare_hands, get_hand_name


class GameEventType(Enum):
    """
    Event types emitted by the game engine.
    """
    GAME_STARTED = "game_started"
    HAND_STARTED = "hand_started"
    BLINDS_POSTED = "blinds_posted"
    HOLE_CARDS_DEALT = "hole_cards_dealt"
    BETTING_ROUND_STARTED = "betting_round_started"
    PLAYER_ACTION_REQUIRED = "player_action_required"
    PLAYER_ACTION_TAKEN = "player_action_taken"
    COMMUNITY_CARDS_DEALT = "community_cards_dealt"
    BETTING_ROUND_ENDED = "betting_round_ended"
    SHOWDOWN = "showdown"
    POT_AWARDED = "pot_awarded"
    HAND_ENDED = "hand_ended"
    GAME_ENDED = "game_ended"


class GamePhase(Enum):
    """Game phases for state tracking."""
    WAITING = "waiting"
    PRE_FLOP = "pre_flop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    ENDED = "ended"


class Game:
    """
    Texas Hold'em poker game engine.
    Manages game state, player actions, betting rounds, and hand evaluation.
    Emits events for game state changes.
    """

    def __init__(
        self, 
        players: List[Player],
        small_blind: int = 10, 
        big_blind: Optional[int] = None,
        debug_mode: bool = False
    ):
        """
        Initialize a poker game.
        
        Args:
            players: List of Player objects (must be 2-12 players)
            small_blind: Small blind amount
            big_blind: Big blind amount (defaults to 2x small blind)
            debug_mode: Enable debug features
        """
        self.small_blind = small_blind
        self.big_blind = big_blind if big_blind else small_blind * 2
        self.players = players
        self.num_players = len(players)
        
        self.deck = Deck()
        self.community_cards: List[Card] = []
        self.dealer_index = 0
        self.pot = 0
        self.current_table_bet = 0  # highest bet in current betting round
        self.side_pots: List[Dict[str, Any]] = []  # List of side pots {amount, eligible_players}
        
        self.debug_mode = debug_mode
        self.debug_community: List[Card] = []
        
        self._debug_checks()
        
        self.event_handlers: Dict[GameEventType, List[Callable]] = {}
        self.current_phase = GamePhase.WAITING
        self.hand_number = 0
        self.action_history: List[Dict] = []

    def on_event(self, event_type: GameEventType, callback: Callable):
        """
        Register an event handler.
        
        Args:
            event_type: Type of event to listen for
            callback: Function to call when event occurs
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(callback)
    
    def emit_event(self, event_type: GameEventType, data: Optional[Dict] = None):
        """
        Emit an event to all registered handlers.
        
        Args:
            event_type: Type of event being emitted
            data: Event data dictionary
        """
        if event_type in self.event_handlers:
            event_data = data or {}
            event_data['event_type'] = event_type.value
            for handler in self.event_handlers[event_type]:
                handler(event_data)

    def play_hand(self):
        """
        Play one complete hand of poker.
        
        ORIGINAL: game.play_hand() from old code/game.py
        MODIFIED: Replaced print() with emit_event()
        """
        self.hand_number += 1
        self.current_phase = GamePhase.PRE_FLOP
        
        self.emit_event(GameEventType.HAND_STARTED, {
            "hand_number": self.hand_number,
            "dealer_index": self.dealer_index
        })
        
        # Preparation
        self._prepare_new_hand()
        self._post_blinds()
        self._deal_hole_cards()
        
        self.emit_event(GameEventType.HOLE_CARDS_DEALT, {
            "players": [p.to_dict(hide_cards=True) for p in self.players]
        })
        
        # Pre-flop betting
        if self._can_continue_betting():
            self._betting_round("Pre-Flop")
        if self._hand_over():
            return self._award_pot_if_single()

        # Flop
        self.current_phase = GamePhase.FLOP
        self._deal_community(3)
        self.emit_event(GameEventType.COMMUNITY_CARDS_DEALT, {
            "phase": "Flop",
            "cards": [c.to_dict() for c in self.community_cards],
            "count": 3
        })
        
        if self._can_continue_betting():
            self._betting_round("Flop")
        if self._hand_over():
            return self._award_pot_if_single()

        # Turn
        self.current_phase = GamePhase.TURN
        self._deal_community(1)
        self.emit_event(GameEventType.COMMUNITY_CARDS_DEALT, {
            "phase": "Turn",
            "cards": [c.to_dict() for c in self.community_cards],
            "count": 1
        })
        
        if self._can_continue_betting():
            self._betting_round("Turn")
        if self._hand_over():
            return self._award_pot_if_single()

        # River
        self.current_phase = GamePhase.RIVER
        self._deal_community(1)
        self.emit_event(GameEventType.COMMUNITY_CARDS_DEALT, {
            "phase": "River",
            "cards": [c.to_dict() for c in self.community_cards],
            "count": 1
        })
        
        if self._can_continue_betting():
            self._betting_round("River")

        # Showdown
        self.current_phase = GamePhase.SHOWDOWN
        self._showdown()
        
        # Notify agents of hand end
        self._notify_hand_end()
        
        # End hand
        self.emit_event(GameEventType.HAND_ENDED, {
            "hand_number": self.hand_number
        })
        
        # Advance dealer
        self.dealer_index = (self.dealer_index + 1) % self.num_players
    
    def _notify_hand_end(self):
        """Notify all agents that the hand has ended for learning updates."""
        for player in self.players:
            if hasattr(player, 'on_hand_end') and callable(player.on_hand_end):
                # Calculate result for this player
                result = {
                    "won": hasattr(player, 'last_chips') and player.chips > player.last_chips,
                    "chip_change": player.chips - (player.last_chips if hasattr(player, 'last_chips') else player.chips)
                }
                player.on_hand_end(result)

    def _prepare_new_hand(self):
        """Reset game state for new hand."""
        if not self.debug_mode:
            for p in self.players:
                p.reset_for_new_hand()
        self.pot = 0
        self.community_cards = []
        self.deck.shuffle()
        self.current_table_bet = 0
        self.side_pots = []
        self.action_history = []
        
        # Notify agents that a new hand is starting
        game_state = {
            "hand_number": self.hand_number + 1,
            "dealer_index": self.dealer_index,
            "players": [p.to_dict(hide_cards=True) for p in self.players]
        }
        for p in self.players:
            if hasattr(p, 'on_hand_start') and callable(p.on_hand_start):
                p.on_hand_start(game_state)

    def _post_blinds(self):
        """Post small and big blinds."""
        if len(self.players) < 2:
            return
        
        # Find players with chips for blinds
        players_with_chips = [i for i, p in enumerate(self.players) if p.chips > 0]
        if len(players_with_chips) < 2:
            return  # Not enough players with chips
        
        # Find SB position (next player with chips after dealer)
        sb_index = self._find_next_player_with_chips(self.dealer_index)
        if sb_index is None:
            return
        
        # Find BB position (next player with chips after SB)
        bb_index = self._find_next_player_with_chips(sb_index)
        if bb_index is None:
            return
        
        small_blind_player = self.players[sb_index]
        big_blind_player = self.players[bb_index]
        
        sb_paid = small_blind_player._remove_chips(self.small_blind)
        bb_paid = big_blind_player._remove_chips(self.big_blind)
        
        small_blind_player.current_bet_in_round = sb_paid
        big_blind_player.current_bet_in_round = bb_paid
        self.current_table_bet = bb_paid
        self.pot += sb_paid + bb_paid
        
        self.emit_event(GameEventType.BLINDS_POSTED, {
            "small_blind": {
                "player_id": small_blind_player.player_id,
                "amount": sb_paid
            },
            "big_blind": {
                "player_id": big_blind_player.player_id,
                "amount": bb_paid
            },
            "pot": self.pot
        })
    
    def _find_next_player_with_chips(self, start_index: int) -> Optional[int]:
        """Find the next player after start_index who has chips.
        
        Args:
            start_index: Index to start searching from
            
        Returns:
            Index of next player with chips, or None if none found
        """
        next_index = (start_index + 1) % len(self.players)
        attempts = 0
        while attempts < len(self.players):
            if self.players[next_index].chips > 0:
                return next_index
            next_index = (next_index + 1) % len(self.players)
            attempts += 1
        return None

    def _deal_hole_cards(self):
        """Deal hole cards to players."""
        if not self.debug_mode:
            for p in self.players:
                if p.current_bet_in_round > 0 or p.chips > 0:
                    p.hand = [self.deck.deal_card(), self.deck.deal_card()]

    def _deal_community(self, n: int):
        """Deal community cards."""
        if self.debug_mode:
            self.community_cards += self.debug_community[:n]
            self.debug_community = self.debug_community[n:]
        else:
            for _ in range(n):
                self.community_cards.append(self.deck.deal_card())

    def set_cards(self, community_cards: List[Card], *hands: List[List[Card]]):
        """
        DEBUG ONLY: Set predetermined cards.
        """
        if len(community_cards) != 5:
            raise ValueError("Parameter community_cards requires a list size of 5.")
        if len(hands) != self.num_players:
            raise ValueError(f"The total hands cannot be held by {len(self.players)} players.") 
        self.debug_community = community_cards
        for i in range(len(hands)):
            self.players[i].hand = hands[i]

    def _betting_round(self, state_name: str):
        """
        Execute one betting round.
        
        ORIGINAL: Game._betting_round() from old code/game.py
        MODIFIED: Added event emissions, removed prints
        FIXED: Betting round now correctly allows all players to respond to raises
        """
        self.emit_event(GameEventType.BETTING_ROUND_STARTED, {
            "phase": state_name,
            "pot": self.pot,
            "current_bet": self.current_table_bet
        })
        
        self._setup_new_betting_round(state_name)
        active_players = self._get_active_players()
        if len(active_players) <= 1:
            return

        # Determine starting player
        if state_name == "Pre-Flop":
            action_index = (self.dealer_index + 3) % len(self.players)
        else:
            action_index = (self.dealer_index + 1) % len(self.players)

        # Track who was the last aggressor (raiser/bettor)
        last_aggressor_index = None
        
        # Pre-flop, the BB is the initial aggressor
        if state_name == "Pre-Flop":
            last_aggressor_index = (self.dealer_index + 2) % len(self.players)
        
        # Track if BB has had their option (pre-flop only)
        bb_had_option = False
        bb_index = (self.dealer_index + 2) % len(self.players)

        while True:
            # Find the next active player
            attempts = 0
            while self.players[action_index] not in self._get_active_players():
                action_index = (action_index + 1) % len(self.players)
                attempts += 1
                if attempts > len(self.players):
                    # No active players found
                    break
            
            if attempts > len(self.players):
                break

            player = self.players[action_index]
            
            # Check if betting round is complete
            # Round ends when action returns to the last aggressor (unless BB gets option)
            if last_aggressor_index is not None and action_index == last_aggressor_index:
                # Special case: Pre-flop BB gets option when everyone just called to BB
                # Only give BB option if:
                # 1. It's pre-flop
                # 2. Current bet is still just the big blind (no raises)
                # 3. BB hasn't had their option yet
                # 4. We're at the BB position
                if (state_name == "Pre-Flop" and 
                    self.current_table_bet == self.big_blind and 
                    not bb_had_option and 
                    action_index == bb_index):
                    # BB gets their option to raise or check
                    bb_had_option = True
                    # Let BB act below
                else:
                    # Action returned to aggressor - round complete
                    break
            
            # Also check if everyone has matched the bet and acted
            # (handles case where there's no aggressor yet, like start of post-flop)
            if last_aggressor_index is None:
                all_matched = all(
                    p.current_bet_in_round == self.current_table_bet or not p.is_playing_round
                    for p in self.players
                )
                all_acted = all(
                    p.has_acted_this_round or not p.is_playing_round
                    for p in self.players
                )
                if all_matched and all_acted:
                    break

            decision = self._get_player_decision(player, state_name)
            self._execute_player_decision(player, decision)

            if self._hand_over():
                return

            # If there was a bet or raise, update the aggressor
            if isinstance(decision, tuple) and decision[0] in ("bet", "raise"):
                last_aggressor_index = action_index
                # Reset has_acted for players who now need to respond to the raise
                for p in self.players:
                    if p != player and p.is_playing_round:
                        p.has_acted_this_round = False
            
            # If BB just exercised their option with a check, end the round
            if (state_name == "Pre-Flop" and 
                bb_had_option and 
                action_index == bb_index and 
                decision == "check"):
                break

            action_index = (action_index + 1) % len(self.players)
        
        self.emit_event(GameEventType.BETTING_ROUND_ENDED, {
            "phase": state_name,
            "pot": self.pot
        })

    def _setup_new_betting_round(self, state_name: str):
        """Reset betting state for new round."""
        if state_name != "Pre-Flop":
            for player in self.players:
                player.reset_for_new_betting_round()
            self.current_table_bet = 0

    def _get_active_players(self) -> List[Player]:
        """Get list of players still in the hand."""
        return [p for p in self.players if p.is_playing_round]

    def _get_player_decision(self, player: Player, state_name: str):
        """
        Get decision from player.
        
        ORIGINAL: Game._get_player_decision() from old code/game.py
        MODIFIED: Simplified to work with base Player class (no Agent/Human distinction)
        NOTE: In web version, this will be overridden or extended
        """
        call_amount = self.current_table_bet - player.current_bet_in_round
        available_actions = self._get_available_actions(player, call_amount)
        
        # Build game state for agents
        game_state = {
            "state_name": state_name,
            "available_actions": available_actions,
            "call_amount": call_amount,
            "current_table_bet": self.current_table_bet,
            "pot": self.pot,
            "community_cards": [c.to_dict() for c in self.community_cards],
            "opponents_chips": [p.chips for p in self.players if p != player and p.is_playing_round],
            "dealer_index": self.dealer_index,
            "agent_index": self.players.index(player),
            "players": [p.to_dict(hide_cards=(p != player)) for p in self.players]
        }
        
        # Emit event requesting action
        self.emit_event(GameEventType.PLAYER_ACTION_REQUIRED, {
            "player_id": player.player_id,
            "available_actions": available_actions,
            "call_amount": call_amount,
            "current_bet": self.current_table_bet,
            "pot": self.pot,
            "phase": state_name
        })
        
        # Check if player has a decide_action method (is an agent)
        if hasattr(player, 'decide_action') and callable(player.decide_action):
            return player.decide_action(game_state)
        
        # Default simple decision (to be overridden by game manager)
        return self._get_simple_decision(player, available_actions, call_amount, state_name)

    def _get_available_actions(self, player: Player, call_amount: int) -> List[str]:
        """Determine what actions the player can take."""
        actions = []
        
        actions.append("fold")
        
        # Check if player can cover the call amount
        if call_amount == 0:
            actions.append("check")
        elif player.chips >= call_amount:
            actions.append("call")
        
        # Can only bet/raise if they have chips beyond the call
        if player.chips > 0:
            if self.current_table_bet == 0:
                # Can bet any amount
                actions.append("bet")
            else:
                min_raise = self.current_table_bet + self.big_blind
                total_after_call = player.current_bet_in_round + call_amount
                can_raise = player.current_bet_in_round + player.chips >= min_raise
                if can_raise:
                    actions.append("raise")
            
            # Add all-in if player has chips but can't cover full call or raise
            if call_amount > 0 and player.chips < call_amount:
                actions.append("all_in")
            elif "raise" not in actions and player.chips > 0 and self.current_table_bet > 0:
                # Can't raise but has chips - can go all-in
                actions.append("all_in")
        
        return actions

    def _get_simple_decision(self, player: Player, available_actions: List[str], 
                            call_amount: int, state_name: str):
        """Simple decision logic for regular players."""
        import random
        
        # Simple random strategy
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

    def _execute_player_decision(self, player: Player, decision):
        """Execute the player's chosen action."""
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
        """Handle fold action."""
        player.do_fold()
        self.emit_event(GameEventType.PLAYER_ACTION_TAKEN, {
            "player_id": player.player_id,
            "action": "fold"
        })

    def _handle_check(self, player: Player):
        """Handle check action."""
        if player.do_check(self.current_table_bet):
            self.emit_event(GameEventType.PLAYER_ACTION_TAKEN, {
                "player_id": player.player_id,
                "action": "check"
            })
        else:
            # Check failed, convert to call
            self._handle_call(player)

    def _handle_call(self, player: Player):
        """Handle call action."""
        contributed = player.do_call(self.current_table_bet)
        self.pot += contributed
        self.emit_event(GameEventType.PLAYER_ACTION_TAKEN, {
            "player_id": player.player_id,
            "action": "call",
            "amount": contributed,
            "pot": self.pot
        })

    def _handle_bet(self, player: Player, amount: int):
        """Handle bet action."""
        contributed = player.do_bet(amount)
        self.current_table_bet = contributed
        self.pot += contributed
        self.emit_event(GameEventType.PLAYER_ACTION_TAKEN, {
            "player_id": player.player_id,
            "action": "bet",
            "amount": contributed,
            "pot": self.pot
        })

    def _handle_raise(self, player: Player, amount: int):
        """Handle raise action."""
        new_wager, amount_added = player.do_raise(self.current_table_bet, amount)
        if new_wager != -1 and new_wager > self.current_table_bet:
            self.current_table_bet = new_wager
            self.pot += amount_added
            self.emit_event(GameEventType.PLAYER_ACTION_TAKEN, {
                "player_id": player.player_id,
                "action": "raise",
                "amount": new_wager,
                "pot": self.pot
            })
        else:
            # Raise failed, convert to call
            self._handle_call(player)

    def _calculate_side_pots(self):
        """
        Calculate main pot and side pots based on all-in players.
        
        This is called at the end of each betting round to properly distribute
        chips into pots that each player is eligible to win.
        """
        # Get all players and their contributions
        contributions = [(p, p.current_bet_in_round) for p in self.players]
        # Sort by contribution amount
        contributions.sort(key=lambda x: x[1])
        
        self.side_pots = []
        remaining_players = [p for p in self.players if p.is_playing_round]
        
        if len(remaining_players) <= 1:
            return
        
        previous_level = 0
        
        for player, bet_amount in contributions:
            if bet_amount <= previous_level or bet_amount == 0:
                continue
            
            # Calculate pot for this level
            pot_size = 0
            eligible_players = []
            
            for p in self.players:
                if p.current_bet_in_round >= bet_amount and p.is_playing_round:
                    eligible_players.append(p.player_id)
                    # This player contributes (bet_amount - previous_level) to this pot
                    contribution = min(p.current_bet_in_round, bet_amount) - previous_level
                    pot_size += contribution
            
            if pot_size > 0 and len(eligible_players) > 0:
                self.side_pots.append({
                    "amount": pot_size,
                    "eligible_players": eligible_players,
                    "cap": bet_amount
                })
            
            previous_level = bet_amount
    
    def _award_pots(self):
        """Award main pot and side pots at showdown."""
        if not self.side_pots:
            # No side pots calculated, use simple pot award
            self._showdown_simple()
            return
        
        # Award each pot from smallest to largest
        for pot_idx, pot_info in enumerate(self.side_pots):
            eligible_player_ids = pot_info["eligible_players"]
            pot_amount = pot_info["amount"]
            
            # Get eligible players still in the round
            eligible = [
                p for p in self.players
                if p.player_id in eligible_player_ids and p.is_playing_round
            ]
            
            if len(eligible) == 0:
                continue
            elif len(eligible) == 1:
                # Only one eligible player
                eligible[0]._add_chips(pot_amount)
                self.emit_event(GameEventType.POT_AWARDED, {
                    "pot_type": "side" if pot_idx > 0 else "main",
                    "pot_index": pot_idx,
                    "winners": [eligible[0].player_id],
                    "amount": pot_amount,
                    "reason": "only_eligible"
                })
            else:
                # Multiple eligible players - evaluate hands
                ranked = []
                for p in eligible:
                    if len(p.hand) == 2 and len(self.community_cards) >= 3:
                        rank = evaluate_best_five(p.hand + self.community_cards)
                        ranked.append((rank, p))
                
                if ranked:
                    ranked.sort(key=lambda x: x[0], reverse=True)
                    best_rank = ranked[0][0]
                    winners = [p for r, p in ranked if r == best_rank]
                    
                    share = pot_amount // len(winners)
                    for winner in winners:
                        winner._add_chips(share)
                    
                    self.emit_event(GameEventType.POT_AWARDED, {
                        "pot_type": "side" if pot_idx > 0 else "main",
                        "pot_index": pot_idx,
                        "winners": [w.player_id for w in winners],
                        "amount": share,
                        "total_pot": pot_amount,
                        "reason": "showdown"
                    })
    
    def _showdown_simple(self):
        """Simple showdown without side pots (original logic)."""
        contenders = [p for p in self.players if p.is_playing_round]
        if len(contenders) == 1:
            winner = contenders[0]
            winner._add_chips(self.pot)
            self.emit_event(GameEventType.POT_AWARDED, {
                "winners": [winner.player_id],
                "amount_each": self.pot,
                "reason": "uncontested"
            })
            return

        # Evaluate all hands
        ranked = []
        for p in contenders:
            rank = evaluate_best_five(p.hand + self.community_cards)
            ranked.append((rank, p))
            
        self.emit_event(GameEventType.SHOWDOWN, {
            "hands": [
                {
                    "player_id": p.player_id,
                    "hand": [c.to_dict() for c in p.hand],
                    "rank": get_hand_name(r[0])
                }
                for r, p in ranked
            ]
        })

        # Sort by rank (best first)
        ranked.sort(key=lambda x: x[0], reverse=True)
        best_rank = ranked[0][0]
        winners = [p for r, p in ranked if r == best_rank]
        share = self.pot // len(winners)
        
        for w in winners:
            w._add_chips(share)
        
        self.emit_event(GameEventType.POT_AWARDED, {
            "winners": [w.player_id for w in winners],
            "amount_each": share,
            "total_pot": self.pot,
            "reason": "showdown"
        })
    
    def _showdown(self):
        """
        Determine winner(s) and award pot.
        
        ORIGINAL: Game._showdown() from old code/game.py
        MODIFIED: Added side pot support
        """
        # Calculate side pots before awarding
        self._calculate_side_pots()
        
        contenders = [p for p in self.players if p.is_playing_round]
        if len(contenders) == 1:
            # Award all pots to the only remaining player
            winner = contenders[0]
            winner._add_chips(self.pot)
            self.emit_event(GameEventType.POT_AWARDED, {
                "winners": [winner.player_id],
                "amount_each": self.pot,
                "reason": "uncontested"
            })
            return
        
        # Show hands first
        ranked = []
        for p in contenders:
            rank = evaluate_best_five(p.hand + self.community_cards)
            ranked.append((rank, p))
            
        self.emit_event(GameEventType.SHOWDOWN, {
            "hands": [
                {
                    "player_id": p.player_id,
                    "hand": [c.to_dict() for c in p.hand],
                    "rank": get_hand_name(r[0])
                }
                for r, p in ranked
            ]
        })
        
        # Award pots (main pot and side pots)
        self._award_pots()

    def _award_pot_if_single(self):
        """Award pot if only one player remains."""
        contenders = [p for p in self.players if p.is_playing_round]
        if len(contenders) == 1:
            winner = contenders[0]
            winner._add_chips(self.pot)
            self.emit_event(GameEventType.POT_AWARDED, {
                "winners": [winner.player_id],
                "amount_each": self.pot,
                "reason": "others_folded"
            })
            
            # Notify agents of hand end (early finish due to folds)
            self._notify_hand_end()
            
            # Emit hand ended event
            self.emit_event(GameEventType.HAND_ENDED, {
                "hand_number": self.hand_number
            })
            
            # Advance dealer
            self.dealer_index = (self.dealer_index + 1) % self.num_players

    def _hand_over(self) -> bool:
        """Check if hand is over (only one player remains)."""
        active = [p for p in self.players if p.is_playing_round]
        return len(active) <= 1
    
    def _can_continue_betting(self) -> bool:
        """Check if betting can continue (at least 2 players can act)."""
        # Players who can act have chips and are still in the round
        can_act = [p for p in self.players if p.is_playing_round and p.chips > 0]
        return len(can_act) >= 2

    def is_still_playable(self) -> bool:
        """Returns true if at least 2 players have chips."""
        counter = 0
        for p in self.players:
            if p.chips > 0:
                counter += 1
        return counter > 1

    def _debug_checks(self):
        """Validate game configuration."""
        if self.num_players < 2:
            raise Exception("Error: Game cannot have less than 2 players.")
        elif self.num_players > 12:
            raise Exception("Error: Game cannot have more than 12 players.")

    def get_state(self) -> dict:
        """
        Get complete game state for serialization.
        
        Returns:
            dict: Complete game state
        """
        return {
            "hand_number": self.hand_number,
            "phase": self.current_phase.value,
            "dealer_index": self.dealer_index,
            "pot": self.pot,
            "current_bet": self.current_table_bet,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "community_cards": [c.to_dict() for c in self.community_cards],
            "players": [p.to_dict() for p in self.players],
            "active_player_count": len(self._get_active_players()),
            "side_pots": self.side_pots
        }
    
    def get_player_view(self, player_id: str) -> dict:
        """
        Get game state from a specific player's perspective.
        Hides other players' hole cards.
        
        Args:
            player_id: ID of the player requesting the view
            
        Returns:
            dict: Game state with hidden opponent cards
        """
        return {
            "hand_number": self.hand_number,
            "phase": self.current_phase.value,
            "dealer_index": self.dealer_index,
            "pot": self.pot,
            "current_bet": self.current_table_bet,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "community_cards": [c.to_dict() for c in self.community_cards],
            "players": [p.to_dict(hide_cards=(p.player_id != player_id)) for p in self.players],
            "active_player_count": len(self._get_active_players()),
            "side_pots": self.side_pots
        }
