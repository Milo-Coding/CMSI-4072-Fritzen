#!/usr/bin/env python3
"""
Interactive Poker Script

Play heads-up poker against an agent in the terminal.

Usage:
    python -m scripts.play_poker
    python -m scripts.play_poker --opponent dqn --model ./models/train_vs_random.pth
    python -m scripts.play_poker --chips 2000 --blind 20
    python -m scripts.play_poker --players 4 --opponent random
    python -m scripts.play_poker --players 6 --opponent dqn --chips 5000
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any, Union, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engine import Game, Player
from app.engine.game import GameEventType
from app.engine.agents import AgentRegistry


class HumanPlayer(Player):
    """Player controlled by human input from terminal."""
    
    def __init__(self, chips: int = 1000, name: str = "You", player_id: str = "human"):
        super().__init__(hand=[], chips=chips, name=name, player_id=player_id)
    
    def decide_action(self, game_state: Dict[str, Any]) -> Union[str, Tuple[str, int]]:
        """Get decision from human player via terminal input."""
        available_actions = game_state.get("available_actions", [])
        call_amount = game_state.get("call_amount", 0)
        current_bet = game_state.get("current_table_bet", 0)
        pot = game_state.get("pot", 0)
        
        # Display game state
        print("\n" + "=" * 60)
        print(f"💰 Pot: ${pot} | Current Bet: ${current_bet}")
        print(f"💵 Your Chips: ${self.chips} | Bet This Round: ${self.current_bet_in_round}")
        if call_amount > 0:
            print(f"📢 Call Amount: ${call_amount}")
        
        # Display your hand
        print(f"\n🎴 Your Hand: {self._format_hand()}")
        
        # Display community cards
        community_cards = game_state.get("community_cards", [])
        if community_cards:
            # Community cards come as dicts from game state
            cards_str = ", ".join([f"{c['display']}" for c in community_cards])
            print(f"🃏 Community: {cards_str}")
        
        # Display available actions
        print(f"\n🎯 Available Actions: {', '.join(available_actions)}")
        
        # Get input
        while True:
            action_input = input("\nYour action: ").strip().lower()
            
            # Parse action
            if action_input == "fold" and "fold" in available_actions:
                return "fold"
            
            elif action_input == "check" and "check" in available_actions:
                return "check"
            
            elif action_input == "call" and "call" in available_actions:
                return "call"
            
            elif action_input.startswith("bet") and "bet" in available_actions:
                # Try to parse bet amount
                parts = action_input.split()
                if len(parts) == 2:
                    try:
                        amount = int(parts[1])
                        if amount > 0 and amount <= self.chips:
                            return ("bet", amount)
                        else:
                            print(f"❌ Invalid bet amount. Must be between 1 and {self.chips}")
                    except ValueError:
                        print("❌ Invalid bet amount. Use: bet <amount>")
                else:
                    # Default bet
                    default_bet = min(self.chips, max(20, call_amount))
                    return ("bet", default_bet)
            
            elif action_input.startswith("raise") and "raise" in available_actions:
                # Try to parse raise amount
                parts = action_input.split()
                if len(parts) == 2:
                    try:
                        amount = int(parts[1])
                        min_raise = current_bet + 20
                        max_raise = self.chips + self.current_bet_in_round
                        if amount >= min_raise and amount <= max_raise:
                            return ("raise", amount)
                        else:
                            print(f"❌ Invalid raise. Must be between ${min_raise} and ${max_raise}")
                    except ValueError:
                        print("❌ Invalid raise amount. Use: raise <amount>")
                else:
                    # Default raise
                    min_raise = current_bet + 20
                    max_raise = self.chips + self.current_bet_in_round
                    default_raise = max(min_raise, min(max_raise, current_bet * 2))
                    return ("raise", default_raise)
            
            elif action_input == "help" or action_input == "?":
                self._print_help()
            
            else:
                print(f"❌ Invalid action. Type 'help' for instructions.")
    
    def _format_hand(self) -> str:
        """Format hand cards for display."""
        if not self.hand:
            return "No cards"
        return ", ".join([card.get_display_name() for card in self.hand])
    
    def _print_help(self):
        """Print help message."""
        print("\n" + "=" * 60)
        print("📖 HOW TO PLAY")
        print("=" * 60)
        print("Actions:")
        print("  fold          - Give up your hand")
        print("  check         - Pass (when no bet to call)")
        print("  call          - Match the current bet")
        print("  bet <amount>  - Make a bet (e.g., 'bet 50')")
        print("  raise <amount> - Raise to a total amount (e.g., 'raise 100')")
        print("  help or ?     - Show this help message")
        print("\nNotes:")
        print("  - If you just type 'bet' or 'raise', a default amount will be used")
        print("  - Raise amount is your TOTAL wager, not additional chips")
        print("=" * 60)


def create_opponent(opponent_type: str, chips: int, model_path: str = None) -> Player:
    """Create an opponent agent."""
    if opponent_type == "random":
        return AgentRegistry.create("random", name="RandomBot", chips=chips, player_id="opponent")
    elif opponent_type == "dqn":
        agent = AgentRegistry.create(
            "dqn", 
            name="DQN_Bot", 
            chips=chips, 
            player_id="opponent",
            is_training=False
        )
        if model_path and Path(model_path).exists():
            agent._load_model(model_path)
            print(f"✅ Loaded trained model from {model_path}")
        elif model_path:
            print(f"⚠️  Model not found at {model_path}, using untrained agent")
        return agent
    else:
        return AgentRegistry.create("random", name="RandomBot", chips=chips, player_id="opponent")


def display_hand_result(game: Game, human: HumanPlayer, opponents: list, hand_end_type: str = "unknown", winner_info: dict = None):
    """Display the result of a hand."""
    print("\n" + "=" * 60)
    if hand_end_type == "showdown":
        print("🏁 HAND COMPLETE - SHOWDOWN")
    elif hand_end_type == "fold":
        print("🏁 HAND COMPLETE - OPPONENT FOLDED" if human.is_playing_round else "🏁 HAND COMPLETE - YOU FOLDED")
    else:
        print("🏁 HAND COMPLETE")
    print("=" * 60)
    
    # Show final community cards
    if game.community_cards:
        cards_str = ", ".join([c.get_display_name() for c in game.community_cards])
        print(f"🃏 Community Cards: {cards_str}")
    
    # Show hands at showdown
    if hand_end_type == "showdown":
        print(f"\n{'─' * 60}")
        print("🎴 SHOWDOWN - All Hands Revealed:")
        print(f"{'─' * 60}")
        
        # Show human's hand
        if human.is_playing_round:
            print(f"{human.name}: {human._format_hand()}")
        
        # Show all opponents' hands who made it to showdown
        for opponent in opponents:
            if opponent.is_playing_round:
                print(f"{opponent.name}: {', '.join([c.get_display_name() for c in opponent.hand])}")
        print(f"{'─' * 60}")
    elif human.is_playing_round:
        # Not showdown but still want to show human's hand
        print(f"\n{human.name}'s Hand: {human._format_hand()}")
    
    # Show winner if available
    if winner_info:
        winners = winner_info.get("winners", [])
        amount = winner_info.get("amount_each", 0)
        
        if len(winners) == 1:
            winner_id = winners[0]
            if winner_id == human.player_id:
                print(f"\n🎉 YOU WIN ${amount}!")
            else:
                # Find the winning opponent
                winner = next((o for o in opponents if o.player_id == winner_id), None)
                if winner:
                    print(f"\n💔 {winner.name} wins ${amount}")
        elif len(winners) > 1:
            print(f"\n🤝 TIE - Pot split ${amount} each")
    
    # Show chip counts
    print(f"\n💵 {human.name}: ${human.chips}")
    for opponent in opponents:
        print(f"💵 {opponent.name}: ${opponent.chips}")
    print("=" * 60)


def play_game(
    initial_chips: int = 1000,
    small_blind: int = 10,
    opponent_type: str = "random",
    num_players: int = 2,
    model_path: str = None
):
    """Play an interactive poker game."""
    
    # Validate player count
    if num_players < 2 or num_players > 6:
        print("Error: Number of players must be between 2 and 6")
        return
    
    # Create players
    human = HumanPlayer(chips=initial_chips, name="You")
    
    # Create opponents (num_players - 1 opponents)
    opponents = []
    for i in range(num_players - 1):
        opponent = create_opponent(opponent_type, initial_chips, model_path)
        opponent.player_id = f"opponent_{i+1}"
        opponent.name = f"{opponent.name}_{i+1}" if num_players > 2 else opponent.name
        opponents.append(opponent)
    
    print("\n" + "=" * 60)
    print("♠️♥️  TEXAS HOLD'EM POKER  ♦️♣️")
    print("=" * 60)
    print(f"Players: {num_players}")
    print(f"Starting Chips: ${initial_chips}")
    print(f"Blinds: ${small_blind}/${small_blind * 2}")
    if num_players == 2:
        print(f"Opponent: {opponents[0].name}")
    else:
        print(f"Opponents: {', '.join([o.name for o in opponents])}")
    print("=" * 60)
    print("\nType 'help' or '?' at any time for instructions")
    print("Press Ctrl+C to quit\n")
    
    hand_number = 0
    
    try:
        while True:
            # Check if game is still playable
            if human.chips <= 0:
                print("\n💸 You're out of chips! Game over.")
                remaining = [o for o in opponents if o.chips > 0]
                if remaining:
                    print(f"🏆 {remaining[0].name} wins!" if len(remaining) == 1 else f"🏆 Winners: {', '.join([o.name for o in remaining])}")
                break
            
            # Check if all opponents are out
            active_opponents = [o for o in opponents if o.chips > 0]
            if not active_opponents:
                print(f"\n🎉 All opponents are out of chips! You win!")
                break
            
            hand_number += 1
            
            # Rotate human position each hand
            human_position = (hand_number - 1) % num_players
            players = []
            opponent_idx = 0
            for pos in range(num_players):
                if pos == human_position:
                    players.append(human)
                else:
                    if opponent_idx < len(active_opponents):
                        players.append(active_opponents[opponent_idx])
                        opponent_idx += 1
            
            print(f"\n{'─' * 60}")
            print(f"Hand #{hand_number}")
            print(f"{'─' * 60}")
            
            # Track hand outcome
            hand_end_type = "unknown"
            winner_info = None
            
            # Event handler for blinds posted
            def on_blinds_posted(data):
                sb_player_id = data.get("small_blind", {}).get("player_id")
                bb_player_id = data.get("big_blind", {}).get("player_id")
                sb_amount = data.get("small_blind", {}).get("amount")
                bb_amount = data.get("big_blind", {}).get("amount")
                
                # Find player names
                sb_name = "You" if sb_player_id == human.player_id else next((o.name for o in opponents if o.player_id == sb_player_id), "Unknown")
                bb_name = "You" if bb_player_id == human.player_id else next((o.name for o in opponents if o.player_id == bb_player_id), "Unknown")
                
                print(f"🎲 Small Blind (${sb_amount}): {sb_name}")
                print(f"🎲 Big Blind (${bb_amount}): {bb_name}")
            
            # Event handler for opponent actions
            def on_player_action(data):
                player_id = data.get("player_id")
                # Check if this is an opponent (not the human player)
                if player_id != human.player_id:
                    # Find the opponent by player_id
                    acting_opponent = next((o for o in opponents if o.player_id == player_id), None)
                    if acting_opponent:
                        action = data.get("action")
                        amount = data.get("amount", 0)
                        
                        if action == "fold":
                            print(f"\n🤖 {acting_opponent.name} folds")
                        elif action == "check":
                            print(f"\n🤖 {acting_opponent.name} checks")
                        elif action == "call":
                            print(f"\n🤖 {acting_opponent.name} calls ${amount}")
                        elif action == "bet":
                            print(f"\n🤖 {acting_opponent.name} bets ${amount}")
                        elif action == "raise":
                            print(f"\n🤖 {acting_opponent.name} raises to ${amount}")
            
            # Event handler for pot awarded
            def on_pot_awarded(data):
                nonlocal winner_info
                winner_info = data
            
            # Event handler for showdown
            def on_showdown(data):
                nonlocal hand_end_type
                hand_end_type = "showdown"
            
            # Event handler for betting round end (to detect folds)
            def on_hand_end(data):
                nonlocal hand_end_type
                if hand_end_type != "showdown":
                    # Check if anyone folded
                    active_in_hand = [p for p in players if p.is_playing_round]
                    if len(active_in_hand) <= 1:
                        hand_end_type = "fold"
            
            # Event handler for community cards dealt
            def on_community_cards_dealt(data):
                phase = data.get("phase")
                cards = data.get("cards", [])
                count = data.get("count", 0)
                
                # Format the cards
                cards_str = ", ".join([c['display'] for c in cards[-count:]])  # Only show new cards
                
                print(f"\n{'=' * 60}")
                print(f"📍 {phase.upper()}")
                print(f"🃏 Cards Dealt: {cards_str}")
                print(f"💰 Pot: ${data.get('pot', game.pot)}")
                print(f"{'=' * 60}")
            
            # Event handler for betting round started
            def on_betting_round_started(data):
                # Only show for rounds after hole cards (not pre-flop)
                phase = data.get("phase")
                if phase != "Pre-Flop":
                    pot = data.get("pot", 0)
                    print(f"\n💰 Current Pot: ${pot}")
            
            # Create and play hand
            game = Game(
                players=players,
                small_blind=small_blind,
                big_blind=small_blind * 2
            )
            
            # Register event handlers
            game.on_event(GameEventType.BLINDS_POSTED, on_blinds_posted)
            game.on_event(GameEventType.COMMUNITY_CARDS_DEALT, on_community_cards_dealt)
            game.on_event(GameEventType.BETTING_ROUND_STARTED, on_betting_round_started)
            game.on_event(GameEventType.PLAYER_ACTION_TAKEN, on_player_action)
            game.on_event(GameEventType.POT_AWARDED, on_pot_awarded)
            game.on_event(GameEventType.SHOWDOWN, on_showdown)
            game.on_event(GameEventType.HAND_ENDED, on_hand_end)
            
            game.play_hand()
            
            # Display result
            display_hand_result(game, human, opponents, hand_end_type, winner_info)
            
            # Ask to continue
            while True:
                continue_input = input("\nPlay another hand? (y/n): ").strip().lower()
                if continue_input in ['y', 'yes', '']:
                    break
                elif continue_input in ['n', 'no', 'q', 'quit']:
                    print("\n👋 Thanks for playing!")
                    return
                else:
                    print("Please enter 'y' or 'n'")
    
    except KeyboardInterrupt:
        print("\n\n👋 Game interrupted. Thanks for playing!")
    
    # Final statistics
    print("\n" + "=" * 60)
    print("📊 FINAL STATISTICS")
    print("=" * 60)
    print(f"{human.name}: ${human.chips}")
    for opponent in opponents:
        print(f"{opponent.name}: ${opponent.chips}")
    
    if human.chips > initial_chips:
        profit = human.chips - initial_chips
        print(f"\n🎉 You won ${profit}!")
    elif human.chips < initial_chips:
        loss = initial_chips - human.chips
        print(f"\n💸 You lost ${loss}")
    else:
        print(f"\n🤝 You broke even")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Play interactive poker against an agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--chips", "-c",
        type=int,
        default=1000,
        help="Starting chip stack"
    )
    
    parser.add_argument(
        "--blind", "-b",
        type=int,
        default=10,
        help="Small blind amount"
    )
    
    parser.add_argument(
        "--opponent", "-o",
        type=str,
        choices=["random", "dqn"],
        default="dqn",
        help="Opponent type"
    )
    
    parser.add_argument(
        "--players", "-p",
        type=int,
        default=2,
        choices=[2, 3, 4, 5, 6],
        help="Total number of players (2-6)"
    )
    
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="./models/train_vs_random.pth",
        help="Path to trained DQN model (for dqn opponent)"
    )
    
    args = parser.parse_args()
    
    play_game(
        initial_chips=args.chips,
        small_blind=args.blind,
        opponent_type=args.opponent,
        num_players=args.players,
        model_path=args.model if args.opponent == "dqn" else None
    )


if __name__ == "__main__":
    main()
