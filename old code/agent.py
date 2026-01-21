from player import Player
from card import Card
import random
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

# Neural network for the poker agent
class PokerNet(nn.Module):
    def __init__(self, input_size, hidden_size=128, num_actions=5):  # 5 actions: fold, check, call, bet, raise
        super(PokerNet, self).__init__()
        self.num_actions = num_actions  # Store num_actions as instance variable
        self.network = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, num_actions)
        )
    
    def forward(self, x):
        return self.network(x)

# the agent is a player
class Agent(Player):
    def __init__(self, hand=[], chips=0, name="AI", is_training=False, initial_state=None, model_load_path='./src/ai_model_base.pth', model_save_path='./src/ai_model_most_recent_player.pth'):
        super().__init__(hand, chips, name)
        self.is_training = is_training
        
        # Initialize neural network and training components
        if initial_state is None:
            initial_state = {
                'opponents_chips': [chips],
                'current_table_bet': 0,
                'call_amount': 0,
                'pot': 0,
                'community_cards': [],
                'state_name': 'Pre-Flop'
            }
        # Get input size from initial_state if provided, otherwise calculate it
        self.input_size = initial_state.get('input_size', len(self.featurize_game_state(initial_state)))
        self.model = PokerNet(self.input_size)
        self.optimizer = optim.Adam(self.model.parameters())
        self.memory = []  # For experience replay
        self.batch_size = 32
        self.gamma = 0.99  # Discount factor
        self.epsilon = 1.0  # Exploration rate
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.model_save_path = model_save_path
        self.model_load_path = model_load_path
        
        # Training stats
        self.training_episodes = 0
        self.wins = 0
        self.losses = 0

        # Track change in chips for reward calculation
        self.last_chips = chips
        
        # Load existing model if available
        try:
            self.load_model(self.model_load_path)
            print(f"{self.name}: Loaded existing model")
        except:
            print(f"{self.name}: No existing model found, starting fresh")
   
        
    def decide_action_randomly(self, game_state):
        # Randomly choose an action from the available actions
        actions = game_state['available_actions']
        chosen_action = random.choice(actions)

        # Return the chosen action (don't execute it - the game will do that)
        if chosen_action == 'check':
            return 'check'
        elif chosen_action == 'call':
            return 'call'
        elif chosen_action == 'raise':
            # Raise by a minimum amount (we'll use call_amount as a guide for the minimum raise)
            min_raise = game_state['current_table_bet'] + game_state['call_amount']
            raise_amount = min(self.chips + self.current_bet_in_round, min_raise)
            return ('raise', raise_amount)
        elif chosen_action == 'fold':
            return 'fold'
        elif chosen_action == 'bet':
            # Simple bet of the call amount or remaining chips
            bet_amount = min(self.chips, game_state['call_amount'] if game_state['call_amount'] > 0 else 20)
            return ('bet', bet_amount)
        elif chosen_action == 'allin':
            return ('raise', self.chips + self.current_bet_in_round)

    def decide_action(self, game_state):
        """Decide action using epsilon-greedy policy during training"""
        features = self.featurize_game_state(game_state)
        feature_list = []
        
        # Ensure features are in a consistent order and pad if necessary
        expected_features = [
            "pot_size_ratio", "call_amount_ratio", "table_bet_ratio",
            "relative_position", "betting_freedom", "can_raise",
            "stage", "num_opponents", "pair_in_hand", "high_card",
            "suited", "connected", "hand_strength"
        ]
        
        # Create feature list with consistent ordering and handle missing features
        for feature in expected_features:
            feature_list.append(features.get(feature, 0.0))
        
        # Store the current state for training
        self.current_state = feature_list
        
        if self.is_training:
            # Use epsilon-greedy during training
            if random.random() < self.epsilon:
                # Explore: random action
                action = self.decide_action_randomly(game_state)
            else:
                # Exploit: use neural network
                action_idx = self.get_action(feature_list)
                action = self._map_action_index_to_action(action_idx, game_state)
            
            # Store the last state and action for training
            self.last_state = self.current_state
            self.last_action = self._action_to_index(action)
            
            return action
        else:
            # Always use network during gameplay
            action_idx = self.get_action(feature_list)
            action = self._map_action_index_to_action(action_idx, game_state)
            
            # Store the last state and action even during gameplay
            self.last_state = self.current_state
            self.last_action = self._action_to_index(action)
            
            return action
    
    def _action_to_index(self, action):
        """Convert a game action back to the corresponding network output index"""
        if isinstance(action, tuple):
            action_type = action[0]
        else:
            action_type = action

        if action_type == 'fold':
            return 0
        elif action_type == 'check':
            return 1
        elif action_type == 'call':
            return 2
        elif action_type == 'bet':
            return 3
        elif action_type == 'raise':
            return 4
        return 0  # Default to fold for unknown actions

    def _map_action_index_to_action(self, action_idx, game_state):
        """Map neural network output to game action"""
        available_actions = game_state['available_actions']
        
        # Define action mapping
        self.action_mapping = {
            0: 'fold',
            1: 'check' if 'check' in available_actions else 'call',
            2: 'call' if 'call' in available_actions else 'check',
            3: 'bet' if 'bet' in available_actions else 'raise',
            4: 'raise'
        }
        
        # Get the intended action
        intended_action = self.action_mapping.get(action_idx, 'fold')
        
        # Ensure the action is available, fallback to random if not
        if intended_action in available_actions:
            if intended_action == 'raise':
                min_raise = game_state['current_table_bet'] + game_state['call_amount']
                raise_amount = min(self.chips + self.current_bet_in_round, max(min_raise, min_raise * 2))
                return ('raise', raise_amount)
            elif intended_action == 'bet':
                bet_amount = min(self.chips, game_state['call_amount'] if game_state['call_amount'] > 0 else 20)
                return ('bet', bet_amount)
            else:
                return intended_action
        else:
            # Fallback to random action if neural network output is invalid
            return self.decide_action_randomly(game_state)
        
    def receive_round_result(self, result):
        """Process the round result and update the agent's strategy"""
        if self.is_training:
            self.training_episodes += 1
            # Calculate and store reward
            reward = self._calculate_reward()
            
            # Store the experience with the calculated reward
            if hasattr(self, 'last_state') and hasattr(self, 'last_action'):
                self.store_experience(self.last_state, self.last_action, reward, self.current_state, True)
                
            # Update the model if we have enough experiences
            if len(self.memory) >= self.batch_size:
                self.update_model()
            
            # Update epsilon
            if len(self.memory) > self.batch_size:
                self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
            
            # Update training stats
            if result > 0:
                self.wins += 1
            elif result < 0:
                self.losses += 1
                
            # Save model periodically
            if self.training_episodes % 100 == 0:
                self.save_model(self.model_save_path)
    
    def _calculate_reward(self):
        """Calculate reward based on game outcome"""
        # The reward should be equivalent to the chips won or lost this round
        reward = self.chips - self.last_chips
        self.last_chips = self.chips  # Update last_chips for next calculation
        return reward
        
            
    def start_training(self):
        """Enable training mode"""
        self.is_training = True
        
    def stop_training(self):
        """Disable training mode"""
        self.is_training = False
        
    def save_model(self, filepath):
        """Save the trained model"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict()
        }, filepath)
        
    def load_model(self, filepath):
        """Load a trained model"""
        checkpoint = torch.load(filepath)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        
    def store_experience(self, state, action, reward, next_state, done):
        """Store a transition in the replay memory"""
        self.memory.append((state, action, reward, next_state, done))
        
    def sample_batch(self):
        """Sample a batch of experiences from memory"""
        if len(self.memory) < self.batch_size:
            return None
        return random.sample(self.memory, self.batch_size)
    
    def update_model(self):
        """Update the model using a batch of experiences"""
        batch = self.sample_batch()
        if batch is None:
            return
            
        states, actions, rewards, next_states, dones = zip(*batch)
        
        # Convert to tensors
        states = torch.FloatTensor(states)
        actions = torch.LongTensor(actions)
        rewards = torch.FloatTensor(rewards)
        next_states = torch.FloatTensor(next_states)
        dones = torch.FloatTensor(dones)
        
        # Get current Q values
        current_q_values = self.model(states)
        
        # Get next Q values
        next_q_values = self.model(next_states).detach()
        
        # Compute target Q values
        target_q_values = rewards + (1 - dones) * self.gamma * next_q_values.max(1)[0]
        
        # Compute loss
        loss = nn.MSELoss()(current_q_values.gather(1, actions.unsqueeze(1)), target_q_values.unsqueeze(1))
        
        # Optimize the model
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
    def reset_training_stats(self):
        """Reset training statistics"""
        self.wins = 0
        self.losses = 0
        self.training_episodes = 0
        self.epsilon = 1.0
        self.memory = []
        
    def reset_model(self):
        """Reset the neural network to initial state"""
        self.model = PokerNet(self.input_size)
        self.optimizer = optim.Adam(self.model.parameters())
        self.reset_training_stats()
        print(f"{self.name}: Model reset")
    
    def get_action(self, state, epsilon=0.1):
        """Get action using epsilon-greedy policy"""
        if random.random() < epsilon and self.is_training:
            return random.randint(0, self.model.num_actions - 1)
        
        with torch.no_grad():
            # Ensure state is a 1D tensor of correct size
            if isinstance(state, list):
                state_tensor = torch.FloatTensor(state).unsqueeze(0)
            else:
                state_tensor = torch.FloatTensor([state])
                
            # Ensure input size matches model's expected input size
            if state_tensor.size(1) != self.input_size:
                raise ValueError(f"Input size mismatch. Expected {self.input_size}, got {state_tensor.size(1)}")
                
            q_values = self.model(state_tensor)
            return q_values.argmax().item()

    def featurize_game_state(self, game_state):
        """
        Convert a game_state dict into a fixed-length numeric feature vector.

        Keys in game_state:
        - 'current_table_bet': int              # Current highest bet on the table
        - 'call_amount': int                    # Amount needed to call
        - 'available_actions': list[str]        # e.g. ['check', 'call', 'raise', 'fold']
        - 'state_name': str                     # e.g. "Pre-Flop", "Flop", "Turn", "River"
        - 'opponents_chips': list[int]          # Chips of other players
        - 'pot': int                            # Current pot size
        - 'community_cards': list[Card]         # Community cards on the table
        - 'players': list[Player]               # All players in the game
        - 'dealer_index': int                   # Index of dealer in players list
        - 'agent_index': int                    # Index of this agent in players list
        - 'history': list[]                     # Placeholder for action history tracking

        Returns: dict[str, float]  Feature dictionary
        """
        features = {}
        
        # Basic game state features
        total_chips = sum(game_state["opponents_chips"] + [self.chips])
        features["pot_size_ratio"] = game_state["pot"] / total_chips if total_chips > 0 else 0.0
        features["call_amount_ratio"] = game_state["call_amount"] / self.chips if self.chips > 0 else 1.0
        features["table_bet_ratio"] = game_state["current_table_bet"] / self.chips if self.chips > 0 else 1.0
        
        # Position and betting ability features
        features["relative_position"] = (game_state["agent_index"] - game_state["dealer_index"]) % len(game_state["players"]) / len(game_state["players"])
        features["betting_freedom"] = len(game_state["available_actions"]) / 4.0  # Normalize by max possible actions
        features["can_raise"] = 1.0 if "raise" in game_state["available_actions"] else 0.0
        
        # Stage features with more granular state tracking
        stage_values = {"Pre-Flop": 0.25, "Flop": 0.5, "Turn": 0.75, "River": 1.0}
        features["stage"] = stage_values[game_state["state_name"]]
        features["num_opponents"] = len(game_state["opponents_chips"]) / (self.num_players - 1) if hasattr(self, 'num_players') else len(game_state["opponents_chips"]) / 5.0
        
        # Hand strength features
        if len(self.hand) == 2:  # Make sure we have a valid hand
            # Pair in hand
            features["pair_in_hand"] = 1.0 if self.hand[0].value == self.hand[1].value else 0.0
            # High card value normalized
            features["high_card"] = max(card.value for card in self.hand) / 14.0
            # Suited cards
            features["suited"] = 1.0 if Card.is_same_suit(self.hand[0], self.hand[1]) else 0.0
            # Connected cards (consecutive values)
            features["connected"] = 1.0 if abs(self.hand[0].value - self.hand[1].value) == 1 else 0.0
            # Hand strength value (higher cards = stronger starting hand)
            features["hand_strength"] = sum(card.value for card in self.hand) / 28.0  # Normalize by max possible (13 + 14)
        
        # Community card features
        if game_state["community_cards"]:
            # Count suits and values for flush and pair possibilities
            suit_count = {}
            value_count = {}
            all_cards = game_state["community_cards"] + self.hand
            
            for card in all_cards:
                suit_count[card.suit] = suit_count.get(card.suit, 0) + 1
                value_count[card.value] = value_count.get(card.value, 0) + 1
            
            # Flush draw feature
            features["flush_potential"] = max(suit_count.values()) / 5.0
            
            # Pair/Three of a kind/Four of a kind features
            features["highest_value_count"] = max(value_count.values()) / 4.0
            
            # Straight potential (more detailed)
            values = sorted([card.value for card in all_cards])
            # Handle Ace for low straight potential
            if 14 in values:  # Ace
                values.append(1)
            max_consecutive = 1
            current_consecutive = 1
            for i in range(1, len(values)):
                if values[i] == values[i-1] + 1:
                    current_consecutive += 1
                    max_consecutive = max(max_consecutive, current_consecutive)
                elif values[i] > values[i-1] + 1:  # Gap found
                    current_consecutive = 1
            features["straight_potential"] = max_consecutive / 5.0
            
            # Board texture features
            features["board_paired"] = 1.0 if max(value_count.values()) > 1 else 0.0
            features["board_suited"] = 1.0 if max(suit_count.values()) > 2 else 0.0

        # Opponent modeling features
        features["avg_opponent_chips"] = (sum(game_state["opponents_chips"]) / 
                                        len(game_state["opponents_chips"]) if game_state["opponents_chips"] else 0)
        features["chips_ratio"] = self.chips / features["avg_opponent_chips"] if features["avg_opponent_chips"] > 0 else 1.0
        features["stack_pressure"] = min(1.0, game_state["current_table_bet"] / features["avg_opponent_chips"]) if features["avg_opponent_chips"] > 0 else 0.0

        # Pot odds and implied odds features
        features["pot_odds"] = game_state["call_amount"] / (game_state["pot"] + game_state["call_amount"]) if (game_state["pot"] + game_state["call_amount"]) > 0 else 0.0
        total_chips_in_play = sum(game_state["opponents_chips"] + [self.chips])
        features["implied_odds"] = (total_chips_in_play - game_state["pot"]) / total_chips_in_play if total_chips_in_play > 0 else 0.0
        
        return features