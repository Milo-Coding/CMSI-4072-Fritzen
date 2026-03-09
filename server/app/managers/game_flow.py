"""
Game Flow Manager - Manual game progression for WebSocket games

Since the game engine's play_hand() is synchronous and blocks for human input,
this module provides manual step-by-step game progression for async WebSocket games.
"""

from typing import Optional, Dict, Any
from ..engine import Game, Player
from ..engine.game import GamePhase, GameEventType
from ..engine.agents import BaseAgent
from ..engine.evaluator import evaluate_best_five, get_hand_name


class GameFlowManager:
    """Manages manual progression of a poker game for WebSocket play."""
    
    @staticmethod
    def get_next_player_to_act(game: Game, current_player_index: int) -> Optional[int]:
        """
        Determine the next player who needs to act.
        
        Returns:
            Player index, or None if betting round is complete
        """
        active_players = [p for p in game.players if p.is_playing_round]
        if len(active_players) <= 1:
            return None
        
        # Check if everyone has acted and matched the current bet (or is all-in)
        all_matched = all(
            p.current_bet_in_round == game.current_table_bet or not p.is_playing_round or p.chips == 0
            for p in game.players
        )
        all_acted = all(
            p.has_acted_this_round or not p.is_playing_round
            for p in game.players
        )
        
        if all_matched and all_acted:
            return None  # Betting round complete
        
        # Find next active player
        next_index = (current_player_index + 1) % len(game.players)
        attempts = 0
        while attempts < len(game.players):
            if game.players[next_index].is_playing_round:
                # Check if this player still needs to act
                player = game.players[next_index]
                # All-in players don't need to act (even if their bet is less than table bet)
                if player.chips == 0:
                    # Skip all-in players
                    next_index = (next_index + 1) % len(game.players)
                    attempts += 1
                    continue
                # Check if player needs to act
                if not player.has_acted_this_round or player.current_bet_in_round < game.current_table_bet:
                    return next_index
            next_index = (next_index + 1) % len(game.players)
            attempts += 1
        
        return None
    
    @staticmethod
    def advance_to_next_phase(game: Game) -> bool:
        """
        Advance the game to the next phase after a betting round completes.
        
        Returns:
            True if game continues, False if hand is over
        """
        # Reset betting round state
        for player in game.players:
            player.reset_for_new_betting_round()
        game.current_table_bet = 0
        
        # Check if hand is over (only one player left)
        active = [p for p in game.players if p.is_playing_round]
        if len(active) <= 1:
            GameFlowManager._award_pot(game)
            return False
        
        # Advance to next phase
        if game.current_phase == GamePhase.PRE_FLOP:
            game.current_phase = GamePhase.FLOP
            game._deal_community(3)
            game.emit_event(GameEventType.COMMUNITY_CARDS_DEALT, {
                "phase": "Flop",
                "cards": [c.to_dict() for c in game.community_cards],
                "count": 3
            })
            return True
            
        elif game.current_phase == GamePhase.FLOP:
            game.current_phase = GamePhase.TURN
            game._deal_community(1)
            game.emit_event(GameEventType.COMMUNITY_CARDS_DEALT, {
                "phase": "Turn",
                "cards": [c.to_dict() for c in game.community_cards],
                "count": 1
            })
            return True
            
        elif game.current_phase == GamePhase.TURN:
            game.current_phase = GamePhase.RIVER
            game._deal_community(1)
            game.emit_event(GameEventType.COMMUNITY_CARDS_DEALT, {
                "phase": "River",
                "cards": [c.to_dict() for c in game.community_cards],
                "count": 1
            })
            return True
            
        elif game.current_phase == GamePhase.RIVER:
            game.current_phase = GamePhase.SHOWDOWN
            GameFlowManager._showdown(game)
            return False
        
        return False
    
    @staticmethod
    def _showdown(game: Game):
        """Execute showdown with proper side pot distribution."""
        active = [p for p in game.players if p.is_playing_round]
        
        # Evaluate hands
        results = []
        for player in active:
            if len(player.hand) == 2 and len(game.community_cards) >= 3:
                all_cards = player.hand + game.community_cards
                rank = evaluate_best_five(all_cards)
                results.append({
                    "player": player,
                    "rank": rank
                })
        
        # Store showdown hands for UI display
        game.showdown_hands = [
            {
                "player_id": r["player"].player_id,
                "player_name": r["player"].name,
                "hand": [c.to_dict() for c in r["player"].hand],
                "hand_rank": get_hand_name(r["rank"][0]),
                "rank_value": r["rank"][0].value
            }
            for r in results
        ]
        
        # Emit showdown event
        game.emit_event(GameEventType.SHOWDOWN, {
            "results": [{
                "player_id": r["player"].player_id,
                "hand": [c.to_dict() for c in r["player"].hand],
                "rank": r["rank"][0]  # Just the HandRank enum value
            } for r in results]
        })
        
        # Calculate and award pots using side pot system
        game._calculate_side_pots()
        game._award_pots()
    
    @staticmethod
    def _award_pot(game: Game):
        """Award pot to last remaining player."""
        active = [p for p in game.players if p.is_playing_round]
        if len(active) == 1:
            active[0]._add_chips(game.pot)
            game.emit_event(GameEventType.POT_AWARDED, {
                "winners": [active[0].player_id],
                "amount": game.pot,
                "reason": "all_others_folded"
            })
    
    @staticmethod
    def get_starting_player_index(game: Game) -> int:
        """Get the index of first player to act in current phase."""
        if game.current_phase == GamePhase.PRE_FLOP:
            # After blinds, first to act is left of big blind (UTG)
            start = (game.dealer_index + 3) % len(game.players)
            # Skip players who have no chips / are not in this hand
            index = start
            for _ in range(len(game.players)):
                p = game.players[index]
                if p.is_playing_round and p.chips > 0:
                    return index
                index = (index + 1) % len(game.players)
            return start  # fallback (no active players)
        else:
            # Post-flop, first to act is left of dealer
            index = (game.dealer_index + 1) % len(game.players)
            # Find first active player
            attempts = 0
            while attempts < len(game.players):
                if game.players[index].is_playing_round:
                    return index
                index = (index + 1) % len(game.players)
                attempts += 1
            return 0
