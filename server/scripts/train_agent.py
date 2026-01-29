#!/usr/bin/env python3
"""
Agent Training Script

Train DQN agents by playing against various opponents.

Usage:
    python -m scripts.train_agent --games 1000 --hands 20
    python -m scripts.train_agent --opponent random --save-path ./models/my_agent.pth
    python -m scripts.train_agent --load-path ./models/existing.pth --games 500
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engine import Game, Player
from app.engine.agents import AgentRegistry, DQNAgent


def create_opponent(opponent_type: str, chips: int, player_id: str) -> Player:
    """Create an opponent player/agent."""
    if opponent_type == "random":
        return AgentRegistry.create("random", name="RandomBot", chips=chips, player_id=player_id)
    elif opponent_type == "dqn":
        return AgentRegistry.create("dqn", name="DQN_Opponent", chips=chips, player_id=player_id, is_training=False)
    elif opponent_type == "dqn-train":
        return AgentRegistry.create("dqn", name="DQN_Opponent", chips=chips, player_id=player_id, is_training=True)
    else:
        # Default to random
        return AgentRegistry.create("random", name="RandomBot", chips=chips, player_id=player_id)


def reset_player(player: Player, chips: int):
    """Reset a player for a new game."""
    player.chips = chips
    player.hand = []
    player.is_playing_round = True
    player.current_bet_in_round = 0
    player.has_acted_this_round = False


def train(
    num_games: int = 1000,
    hands_per_game: int = 20,
    initial_chips: int = 1000,
    small_blind: int = 10,
    opponent_type: str = "random",
    model_load_path: str = None,
    model_save_path: str = "./models/trained_agent.pth",
    save_every: int = 100,
    verbose: bool = True
):
    """
    Train a DQN agent by playing poker games.
    
    Args:
        num_games: Number of complete games to play
        hands_per_game: Maximum hands per game
        initial_chips: Starting chip stack
        small_blind: Small blind amount
        opponent_type: Type of opponent (random, dqn, dqn-train)
        model_load_path: Path to load existing model
        model_save_path: Path to save trained model
        save_every: Save model every N games
        verbose: Print progress updates
    """
    # Ensure models directory exists
    Path(model_save_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Create training agent
    training_agent = AgentRegistry.create(
        "dqn",
        name="Trainee",
        chips=initial_chips,
        player_id="trainee",
        is_training=True,
        model_load_path=model_load_path,
        model_save_path=model_save_path
    )
    
    # Create opponent
    opponent = create_opponent(opponent_type, initial_chips, "opponent")
    
    # Statistics tracking
    stats = {
        "games_played": 0,
        "hands_played": 0,
        "trainee_game_wins": 0,
        "opponent_game_wins": 0,
        "ties": 0,
        "start_time": datetime.now()
    }
    
    if verbose:
        print("=" * 60)
        print("🎰 Poker Agent Training")
        print("=" * 60)
        print(f"Games: {num_games}")
        print(f"Hands per game: {hands_per_game}")
        print(f"Initial chips: ${initial_chips}")
        print(f"Blinds: ${small_blind}/${small_blind * 2}")
        print(f"Opponent: {opponent_type}")
        print(f"Save path: {model_save_path}")
        if model_load_path:
            print(f"Loaded from: {model_load_path}")
        print("=" * 60)
        print()
    
    try:
        for game_num in range(num_games):
            # Alternate positions each game
            if game_num % 2 == 0:
                players = [training_agent, opponent]
                trainee_idx = 0
            else:
                players = [opponent, training_agent]
                trainee_idx = 1
            
            # Reset chips for new game
            reset_player(training_agent, initial_chips)
            reset_player(opponent, initial_chips)
            
            # Track starting chips
            trainee_start_chips = training_agent.chips
            
            # Create game
            game = Game(
                players=players,
                small_blind=small_blind,
                big_blind=small_blind * 2
            )
            
            # Play hands until someone is broke or max hands reached
            hands_this_game = 0
            for hand_num in range(hands_per_game):
                if not game.is_still_playable():
                    break
                
                game.play_hand()
                hands_this_game += 1
                stats["hands_played"] += 1
            
            # Determine game winner
            stats["games_played"] += 1
            if training_agent.chips > opponent.chips:
                stats["trainee_game_wins"] += 1
            elif opponent.chips > training_agent.chips:
                stats["opponent_game_wins"] += 1
            else:
                stats["ties"] += 1
            
            # Progress update
            if verbose and (game_num + 1) % 50 == 0:
                win_rate = stats["trainee_game_wins"] / stats["games_played"] * 100
                epsilon = training_agent.epsilon if hasattr(training_agent, 'epsilon') else 0
                print(f"Game {game_num + 1}/{num_games} | "
                      f"Win Rate: {win_rate:.1f}% | "
                      f"Epsilon: {epsilon:.3f} | "
                      f"Hands: {stats['hands_played']}")
            
            # Periodic save
            if (game_num + 1) % save_every == 0:
                training_agent.save_model(model_save_path)
                if verbose:
                    print(f"  💾 Model saved to {model_save_path}")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Training interrupted by user")
    
    # Final save
    training_agent.save_model(model_save_path)
    
    # Print final statistics
    elapsed = (datetime.now() - stats["start_time"]).total_seconds()
    
    print()
    print("=" * 60)
    print("📊 Training Complete!")
    print("=" * 60)
    print(f"Total games:     {stats['games_played']}")
    print(f"Total hands:     {stats['hands_played']}")
    print(f"Trainee wins:    {stats['trainee_game_wins']} ({stats['trainee_game_wins']/max(1,stats['games_played'])*100:.1f}%)")
    print(f"Opponent wins:   {stats['opponent_game_wins']} ({stats['opponent_game_wins']/max(1,stats['games_played'])*100:.1f}%)")
    print(f"Ties:            {stats['ties']}")
    print(f"Time elapsed:    {elapsed:.1f}s ({stats['hands_played']/max(1,elapsed):.1f} hands/sec)")
    print(f"Final epsilon:   {training_agent.epsilon:.4f}")
    print(f"Memory size:     {len(training_agent.memory)}")
    print(f"Model saved to:  {model_save_path}")
    print("=" * 60)
    
    return training_agent, stats


def main():
    parser = argparse.ArgumentParser(
        description="Train a DQN poker agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--games", "-g",
        type=int,
        default=1000,
        help="Number of games to play"
    )
    
    parser.add_argument(
        "--hands", "-n",
        type=int,
        default=20,
        help="Maximum hands per game"
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
        choices=["random", "dqn", "dqn-train"],
        default="random",
        help="Opponent type"
    )
    
    parser.add_argument(
        "--load-path", "-l",
        type=str,
        default=None,
        help="Path to load existing model"
    )
    
    parser.add_argument(
        "--save-path", "-s",
        type=str,
        default="./models/trained_agent.pth",
        help="Path to save trained model"
    )
    
    parser.add_argument(
        "--save-every",
        type=int,
        default=100,
        help="Save model every N games"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )
    
    args = parser.parse_args()
    
    train(
        num_games=args.games,
        hands_per_game=args.hands,
        initial_chips=args.chips,
        small_blind=args.blind,
        opponent_type=args.opponent,
        model_load_path=args.load_path,
        model_save_path=args.save_path,
        save_every=args.save_every,
        verbose=not args.quiet
    )


if __name__ == "__main__":
    main()
