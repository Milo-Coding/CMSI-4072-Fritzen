from game import Game
from agent import Agent
from card import Card
import torch
import random

def train_agents(num_games=100, hands_per_game=20, initial_chips=1000, small_blind=10):
    """
    Train agents by playing full games with multiple hands.
    
    Args:
        num_games: Number of complete games to play
        hands_per_game: Number of hands per game (game ends early if a player runs out of chips)
        initial_chips: Starting chip stack for each player
        small_blind: Small blind amount (big blind will be 2x this)
    """
    # Create the initial state first
    initial_state = {
        'opponents_chips': [initial_chips],
        'current_table_bet': 0,
        'call_amount': 0,
        'pot': 0,
        'community_cards': [],
        'state_name': 'Pre-Flop',
        'available_actions': ['check', 'bet', 'fold'],
        'agent_index': 0,
        'dealer_index': 1,
        'players': [None, None],  # Placeholder for 2 players
        'history': []
    }
    
    # Create a temporary agent to determine the feature vector size
    temp_agent = Agent(chips=initial_chips, name="temp", initial_state=initial_state)
    
    # Get the actual feature size
    features = temp_agent.featurize_game_state(initial_state)
    input_size = len(features)
    
    # Update initial state with input size
    initial_state['input_size'] = input_size
    
    # Create the training agent (the one we'll save)
    training_agent = Agent(chips=initial_chips, name="TrainingAgent", is_training=True, initial_state=initial_state)
    
    # Create opponent agent (also trains but we won't save it)
    opponent_agent = Agent(chips=initial_chips, name="OpponentAgent", is_training=True, initial_state=initial_state)
    
    # Training statistics
    training_agent_game_wins = 0
    opponent_agent_game_wins = 0
    total_hands_played = 0
    
    print(f"Starting training: {num_games} games, up to {hands_per_game} hands per game")
    print(f"Initial chips: ${initial_chips}, Small blind: ${small_blind}, Big blind: ${small_blind * 2}")
    print("=" * 70)

    for game_num in range(num_games):
        # Alternate starting positions - training agent gets to experience both positions
        if game_num % 2 == 0:
            # Training agent is player 0 (acts first in heads-up after blinds)
            players = [training_agent, opponent_agent]
            training_agent_index = 0
        else:
            # Training agent is player 1 (acts second in heads-up after blinds)
            players = [opponent_agent, training_agent]
            training_agent_index = 1
        
        # Reset agents' chips for new game
        for player in players:
            player.chips = initial_chips
            player.hand = []
            player.is_playing_round = True
            player.current_bet_in_round = 0
            player.has_acted_this_round = False
            player.last_chips = initial_chips  # Reset for reward calculation
        
        # Create a new game with specific parameters
        game = Game(small_blind=small_blind, 
                   start_total=initial_chips, 
                   num_players=2,
                   debug_mode=False)
        
        # Replace the game's AI players with our training agents
        game.players = players
        
        # Track chips before the game for result calculation
        initial_training_chips = training_agent.chips
        
        # Play full game (multiple hands until one player runs out or max hands reached)
        hands_this_game = 0
        for hand_num in range(hands_per_game):
            # Check if both players can still play (have chips for at least the big blind)
            if not game.is_still_playable():
                break
            
            game.play_hand()
            hands_this_game += 1
            total_hands_played += 1
            
            # Advance dealer for next hand
            game.dealer_index = (game.dealer_index + 1) % len(game.players)
            
        # Determine game winner based on final chip counts
        final_training_chips = training_agent.chips
        final_opponent_chips = opponent_agent.chips
        
        if final_training_chips > final_opponent_chips:
            training_agent_game_wins += 1
            game_result = "WIN"
        elif final_training_chips < final_opponent_chips:
            opponent_agent_game_wins += 1
            game_result = "LOSS"
        else:
            game_result = "DRAW"
        
        # Calculate overall game reward for the training agent
        # This is the net chip change over the entire game
        game_reward = final_training_chips - initial_training_chips
        
        # Send final game result to training agent
        # Using a scaled reward based on total chip change
        final_result = 1 if game_reward > 0 else (-1 if game_reward < 0 else 0)
        training_agent.receive_round_result(final_result)
        
        # Print progress every 10 games
        if (game_num + 1) % 10 == 0:
            training_win_rate = training_agent_game_wins / (game_num + 1) * 100
            avg_hands_per_game = total_hands_played / (game_num + 1)
            
            print(f"\nGame {game_num + 1}/{num_games} - {game_result}")
            print(f"  Position: {'First' if training_agent_index == 0 else 'Second'} | Hands played: {hands_this_game}")
            print(f"  Final chips - Training: ${final_training_chips} | Opponent: ${final_opponent_chips}")
            print(f"  Training agent game wins: {training_agent_game_wins}/{game_num + 1} ({training_win_rate:.1f}%)")
            print(f"  Avg hands per game: {avg_hands_per_game:.1f}")
            print(f"  Epsilon: {training_agent.epsilon:.3f}")
            print(f"  Memory size: {len(training_agent.memory)}")
            print("-" * 70)
            
        # Save model periodically (every 50 games)
        if (game_num + 1) % 50 == 0:
            training_agent.save_model('./src/ai_model_base.pth')
            print(f"✓ Model checkpoint saved at game {game_num + 1}")

    # Final statistics
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE!")
    print("=" * 70)
    print(f"Total games played: {num_games}")
    print(f"Total hands played: {total_hands_played}")
    print(f"Average hands per game: {total_hands_played / num_games:.1f}")
    print(f"\nFinal Results:")
    print(f"  Training Agent game wins: {training_agent_game_wins} ({training_agent_game_wins/num_games*100:.1f}%)")
    print(f"  Opponent Agent game wins: {opponent_agent_game_wins} ({opponent_agent_game_wins/num_games*100:.1f}%)")
    print(f"\nTraining Agent Stats:")
    print(f"  Final epsilon: {training_agent.epsilon:.3f}")
    print(f"  Memory size: {len(training_agent.memory)}")
    print(f"  Total training episodes: {training_agent.training_episodes}")
    
    # Save the final trained model
    training_agent.save_model('./src/ai_model_base.pth')
    print(f"\n✓ Final model saved: ./src/ai_model_base.pth")
    print("=" * 70)
    
    return training_agent, opponent_agent

def main():
    # Disable graphics for headless training mode
    Card.disable_graphics()
    
    # Set random seeds for reproducibility (optional - uncomment for deterministic training)
    # random.seed(42)
    # torch.manual_seed(42)
    
    # Start training with full games
    # Each game consists of multiple hands, and the training agent experiences both positions
    train_agents(
        num_games=20000,           # Number of complete games
        hands_per_game=20,       # Maximum hands per game (may end early if someone busts)
        initial_chips=1000,      # Starting chips for each game
        small_blind=10           # Small blind amount
    )

if __name__ == "__main__":
    main()