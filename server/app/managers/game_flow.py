"""
Game Flow Manager - Manual game progression for WebSocket games

Since the game engine's play_hand() is synchronous and blocks for human input,
this module provides manual step-by-step game progression for async WebSocket games.
"""

from typing import Optional, Dict, Any
from ..engine import Game, Player
from ..engine.game import GamePhase, GameEventType
from ..engine.agents import BaseAgent
from ..engine.evaluator import evaluate_best_five


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
        
        # Check if everyone has acted and matched the current bet
        all_matched = all(
            p.current_bet_in_round == game.current_table_bet or not p.is_playing_round
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
        """Execute showdown."""
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
        
        # Find winner(s)
        if results:
            results.sort(key=lambda x: x["rank"], reverse=True)
            best_rank = results[0]["rank"]
            winners = [r for r in results if r["rank"] == best_rank]
            
            game.emit_event(GameEventType.SHOWDOWN, {
                "results": [{
                    "player_id": r["player"].player_id,
                    "hand": [c.to_dict() for c in r["player"].hand],
                    "rank": r["rank"][0]  # Just the HandRank enum value
                } for r in results]
            })
            
            # Award pot
            pot_share = game.pot // len(winners)
            for winner_data in winners:
                winner_data["player"]._add_chips(pot_share)
            
            game.emit_event(GameEventType.POT_AWARDED, {
                "winners": [w["player"].player_id for w in winners],
                "amount": pot_share
            })
    
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
            # After blinds, first to act is left of big blind
            return (game.dealer_index + 3) % len(game.players)
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
