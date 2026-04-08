"""
DQN Agent Module - Deep Q-Network Reinforcement Learning Agent

This agent uses a neural network trained with Q-learning to make decisions.
Supports both training mode (with exploration) and inference mode.

Changes from original:
- Restructured to use BaseAgent interface
- Made PyTorch optional for environments without it
- Separated neural network into its own class
- Added proper type hints and documentation
- Made model paths configurable
"""

import random
import math
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path

from .base_agent import BaseAgent, AgentRegistry
from ..card import Card

# PyTorch import with graceful fallback
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    import numpy as np
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None
    nn = None
    optim = None
    np = None


class PokerNet(nn.Module if HAS_TORCH else object):
    """
    Neural network for Q-value estimation.
    
    Architecture:
    - Input: Feature vector from game state
    - Hidden: 2 fully connected layers with ReLU
    - Output: Q-values for each action
    """
    
    def __init__(self, input_size: int, hidden_size: int = 128, num_actions: int = 5):
        """
        Initialize the network.
        
        Args:
            input_size: Size of feature vector
            hidden_size: Size of hidden layers
            num_actions: Number of possible actions (fold, check, call, bet, raise)
        """
        if not HAS_TORCH:
            raise RuntimeError("PyTorch is required for DQN Agent")
        
        super(PokerNet, self).__init__()
        self.num_actions = num_actions
        self.network = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, num_actions)
        )
    
    def forward(self, x):
        """Forward pass through the network."""
        return self.network(x)


@AgentRegistry.register("dqn")
class DQNAgent(BaseAgent):
    """
    Deep Q-Network agent for poker.
    
    Uses a neural network to estimate action values (Q-values) and
    selects actions using epsilon-greedy policy during training.
    
    Features:
    - Experience replay for stable learning
    - Epsilon-greedy exploration
    - Configurable network architecture
    - Model save/load functionality
    """
    
    # Action index mapping
    ACTION_FOLD = 0
    ACTION_CHECK = 1
    ACTION_CALL = 2
    ACTION_BET = 3
    ACTION_RAISE = 4
    
    # Default feature names in order
    DEFAULT_FEATURES = [
        "pot_size_ratio", "call_amount_ratio", "table_bet_ratio",
        "relative_position", "betting_freedom", "can_raise",
        "stage", "num_active_opponents", "pair_in_hand", "high_card",
        "suited", "connected", "hand_strength", "pot_odds",
        "stack_to_pot_ratio", "relative_stack_size", "num_community_cards",
        "position_is_late", "position_is_early"
    ]
    
    def __init__(
        self,
        hand: Optional[List[Card]] = None,
        chips: int = 1000,
        name: str = "DQN_Bot",
        player_id: Optional[str] = None,
        is_training: bool = False,
        model_load_path: Optional[str] = None,
        model_save_path: Optional[str] = None,
        input_size: int = 19,
        hidden_size: int = 128,
        batch_size: int = 32,
        gamma: float = 0.9,
        epsilon: float = 1.0,
        epsilon_min: float = 0.01,
        epsilon_decay: float = 0.9999,
        **kwargs
    ):
        """
        Initialize the DQN agent.
        
        Args:
            is_training: Enable training mode with exploration
            model_load_path: Path to load pre-trained model
            model_save_path: Path to save model during training
            input_size: Size of feature vector
            hidden_size: Size of hidden layers
            batch_size: Batch size for training
            gamma: Discount factor for future rewards
            epsilon: Initial exploration rate
            epsilon_min: Minimum exploration rate
            epsilon_decay: Decay rate for exploration
        """
        super().__init__(
            hand=hand,
            chips=chips,
            name=name,
            player_id=player_id,
            **kwargs
        )
        
        if not HAS_TORCH:
            raise RuntimeError(
                "PyTorch is required for DQN Agent. "
                "Install with: pip install torch"
            )
        
        self.is_training = is_training
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.model_load_path = model_load_path
        self.model_save_path = model_save_path or "./models/dqn_agent.pth"
        
        # Initialize network
        self.model = PokerNet(input_size, hidden_size)
        self.optimizer = optim.Adam(self.model.parameters())
        
        # Training hyperparameters
        self.batch_size = batch_size
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        
        # Experience replay memory
        self.memory: List[Tuple] = []
        self.max_memory_size = 10000
        
        # Training statistics
        self.training_episodes = 0
        self.wins = 0
        self.losses = 0
        self.last_reward = 0.0
        self.cumulative_reward = 0.0
        self.cumulative_chip_delta = 0.0
        
        # State tracking for learning
        self.last_state: Optional[List[float]] = None
        self.last_action: Optional[int] = None
        self.current_state: Optional[List[float]] = None

        # Per-hand action trace so terminal rewards can reflect all actions taken
        self.hand_start_chips = chips
        self.hand_action_trace: List[Dict[str, Any]] = []
        
        # Load existing model if specified
        if model_load_path:
            self._load_model(model_load_path)
    
    def decide_action(self, game_state: Dict[str, Any]) -> Union[str, Tuple[str, int]]:
        """
        Decide action using epsilon-greedy policy.
        
        Args:
            game_state: Current game state
            
        Returns:
            Action to take
        """
        # Extract features
        features = self.featurize_game_state(game_state)
        feature_list = self._features_to_list(features)
        self.current_state = feature_list
        
        if self.is_training and random.random() < self.epsilon:
            # Explore: random action
            action = self._decide_randomly(game_state)
        else:
            # Exploit: use neural network
            action_idx = self._get_best_action(feature_list)
            action = self._map_action_index(action_idx, game_state)
        
        # Store for training
        self.last_state = self.current_state
        self.last_action = self._action_to_index(action)
        self._record_hand_action(game_state, action, features)
        
        return action

    def on_hand_start(self, game_state: Dict[str, Any]) -> None:
        """Reset per-hand trace and chip baseline at the start of a hand."""
        super().on_hand_start(game_state)
        self.hand_start_chips = self.chips
        self.hand_action_trace = []
    
    def _decide_randomly(self, game_state: Dict[str, Any]) -> Union[str, Tuple[str, int]]:
        """
        Make a random valid decision.
        """
        available = game_state.get("available_actions", ["fold"])
        if not available:
            return "fold"
        action = random.choice(available)
        
        if action == "check":
            return "check"
        elif action == "call":
            return "call"
        elif action == "fold":
            return "fold"
        elif action == "bet":
            bet_amount = min(self.chips, max(20, game_state.get("call_amount", 20)))
            return ("bet", bet_amount)
        elif action == "raise":
            current_bet = game_state.get("current_table_bet", 0)
            # Minimum raise is current bet plus a small increment (use big blind as increment, default 20)
            min_raise = current_bet + 20
            # Max we can raise to is our total chips plus what we've already bet this round
            max_raise = self.chips + self.current_bet_in_round
            # Ensure raise is at least min_raise, but not more than max_raise
            raise_amount = max(min_raise, min(max_raise, min_raise + random.randint(0, 40)))
            return ("raise", raise_amount)
        elif action == "all_in":
            return "all_in"
        
        return "fold"
    
    def _get_best_action(self, state: List[float]) -> int:
        """Get best action according to Q-network."""
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0)
            q_values = self.model(state_tensor)
            return q_values.argmax().item()
    
    def _map_action_index(self, action_idx: int, game_state: Dict[str, Any]) -> Union[str, Tuple[str, int]]:
        """
        Map network output to game action.
        """
        available = game_state.get("available_actions", [])
        current_bet = game_state.get("current_table_bet", 0)
        call_amount = game_state.get("call_amount", 0)
        
        # Map action index to action name
        action_mapping = {
            self.ACTION_FOLD: "fold",
            self.ACTION_CHECK: "check" if "check" in available else "call",
            self.ACTION_CALL: "call" if "call" in available else "check",
            self.ACTION_BET: "bet" if "bet" in available else "raise",
            self.ACTION_RAISE: "raise" if "raise" in available else ("all_in" if "all_in" in available else "call")
        }
        
        intended_action = action_mapping.get(action_idx, "fold")
        
        if intended_action in available:
            if intended_action == "raise":
                # Minimum raise is current bet plus a small increment (use big blind as increment, default 20)
                min_raise = current_bet + 20
                # Max we can raise to is our total chips plus what we've already bet this round
                max_raise = self.chips + self.current_bet_in_round
                # Try to raise to 2x the current bet, but ensure it's at least min_raise and at most max_raise
                raise_amount = max(min_raise, min(max_raise, current_bet * 2))
                return ("raise", raise_amount)
            elif intended_action == "bet":
                bet_amount = min(self.chips, max(20, call_amount))
                return ("bet", bet_amount)
            else:
                return intended_action
        
        # Fallback to random if action not available
        return self._decide_randomly(game_state)
    
    def _action_to_index(self, action: Union[str, Tuple[str, int]]) -> int:
        """Convert game action to network output index."""
        if isinstance(action, tuple):
            action_type = action[0]
        else:
            action_type = action
        
        mapping = {
            "fold": self.ACTION_FOLD,
            "check": self.ACTION_CHECK,
            "call": self.ACTION_CALL,
            "bet": self.ACTION_BET,
            "raise": self.ACTION_RAISE,
            "all_in": self.ACTION_RAISE  # Treat all-in as aggressive raise action
        }
        return mapping.get(action_type, self.ACTION_FOLD)

    def _normalize_action(self, action: Union[str, Tuple[str, int]]) -> Tuple[str, Optional[int]]:
        """Convert actions to a normalized (action_type, amount) tuple."""
        if isinstance(action, tuple):
            action_type = str(action[0])
            amount = int(action[1]) if len(action) > 1 else None
            return action_type, amount
        return str(action), None

    def _estimate_action_commitment(
        self,
        game_state: Dict[str, Any],
        action_type: str,
        amount: Optional[int]
    ) -> float:
        """Estimate chips committed by this action using available game-state context."""
        call_amount = float(game_state.get("call_amount", 0))
        agent_index = int(game_state.get("agent_index", 0))
        players = game_state.get("players", [])
        player_current_bet = 0.0
        if 0 <= agent_index < len(players):
            player_current_bet = float(players[agent_index].get("current_bet_in_round", 0))

        if action_type in {"check", "fold"}:
            return 0.0
        if action_type == "call":
            return max(0.0, call_amount)
        if action_type == "bet":
            return max(0.0, float(amount or 0))
        if action_type == "raise":
            target_wager = float(max(0, amount or 0))
            return max(0.0, target_wager - player_current_bet)
        if action_type == "all_in":
            return float(max(0, self.chips))

        return 0.0

    def _record_hand_action(
        self,
        game_state: Dict[str, Any],
        action: Union[str, Tuple[str, int]],
        features: Dict[str, float]
    ) -> None:
        """Append a compact action record for this hand's terminal reward shaping."""
        action_type, amount = self._normalize_action(action)
        commitment_estimate = self._estimate_action_commitment(game_state, action_type, amount)

        self.hand_action_trace.append({
            "stage": game_state.get("state_name", "Pre-Flop"),
            "action": action_type,
            "amount": amount,
            "call_amount": game_state.get("call_amount", 0),
            "pot": game_state.get("pot", 0),
            "current_table_bet": game_state.get("current_table_bet", 0),
            "commitment_estimate": commitment_estimate,
            "feature_snapshot": {
                "pot_size_ratio": features.get("pot_size_ratio", 0.0),
                "call_amount_ratio": features.get("call_amount_ratio", 0.0),
                "table_bet_ratio": features.get("table_bet_ratio", 0.0),
                "pot_odds": features.get("pot_odds", 0.0),
                "stage": features.get("stage", 0.0),
                "relative_position": features.get("relative_position", 0.0)
            }
        })
    
    def _features_to_list(self, features: Dict[str, float]) -> List[float]:
        """Convert feature dict to ordered list."""
        return [features.get(f, 0.0) for f in self.DEFAULT_FEATURES]
    
    def featurize_game_state(self, game_state: Dict[str, Any]) -> Dict[str, float]:
        """
        Convert game state to feature vector.
        Enhanced for multiplayer with better position, pot odds, and stack features.
        """
        features = {}
        
        # Get base game state info
        pot = game_state.get("pot", 0)
        call_amount = game_state.get("call_amount", 0)
        current_bet = game_state.get("current_table_bet", 0)
        
        # Get player info - players is a list of player dicts
        players = game_state.get("players", [])
        num_total_players = len(players) if players else 2
        agent_idx = game_state.get("agent_index", 0)
        dealer_idx = game_state.get("dealer_index", 0)
        
        # Count active opponents (still playing this round)
        active_opponents = [p for p in players if p.get("is_playing_round", False) 
                           and players.index(p) != agent_idx]
        num_active_opponents = len(active_opponents)
        
        # Calculate total chips in play (active players only)
        opponents_chips = [p.get("chips", 0) for p in active_opponents]
        total_chips = sum(opponents_chips) + self.chips
        avg_opponent_chips = sum(opponents_chips) / len(opponents_chips) if opponents_chips else self.chips
        
        # === Basic Ratio Features ===
        features["pot_size_ratio"] = pot / total_chips if total_chips > 0 else 0.0
        features["call_amount_ratio"] = call_amount / self.chips if self.chips > 0 else 1.0
        features["table_bet_ratio"] = current_bet / self.chips if self.chips > 0 else 1.0
        
        # === Position Features ===
        # Relative position (0.0 = dealer, higher = later position)
        features["relative_position"] = ((agent_idx - dealer_idx) % num_total_players) / max(num_total_players, 1)
        
        # Position categories (early/late)
        position_index = (agent_idx - dealer_idx) % num_total_players
        # Last 1/3 of positions are "late", first 1/3 are "early"
        features["position_is_late"] = 1.0 if position_index > (num_total_players * 2 / 3) else 0.0
        features["position_is_early"] = 1.0 if position_index < (num_total_players / 3) else 0.0
        
        # === Action Availability Features ===
        available = game_state.get("available_actions", [])
        features["betting_freedom"] = len(available) / 5.0  # fold, check, call, bet, raise
        features["can_raise"] = 1.0 if "raise" in available or "bet" in available else 0.0
        
        # === Game Stage ===
        stage_values = {"Pre-Flop": 0.25, "Flop": 0.5, "Turn": 0.75, "River": 1.0}
        features["stage"] = stage_values.get(game_state.get("state_name", "Pre-Flop"), 0.25)
        
        # === Opponent Count (normalized to max 5 opponents in 6-player game) ===
        features["num_active_opponents"] = min(num_active_opponents, 5) / 5.0
        
        # === Pot Odds Feature ===
        # Pot odds = call amount / (pot + call amount)
        if call_amount > 0:
            pot_odds = call_amount / (pot + call_amount)
            features["pot_odds"] = min(pot_odds, 1.0)  # Cap at 1.0
        else:
            features["pot_odds"] = 0.0  # No cost to continue
        
        # === Stack Features ===
        # Stack to pot ratio (higher = more room to maneuver)
        features["stack_to_pot_ratio"] = self.chips / pot if pot > 0 else 1.0
        features["stack_to_pot_ratio"] = min(features["stack_to_pot_ratio"], 10.0) / 10.0  # Normalize to 0-1
        
        # Relative stack size compared to average opponent
        if avg_opponent_chips > 0:
            features["relative_stack_size"] = self.chips / avg_opponent_chips
            features["relative_stack_size"] = min(features["relative_stack_size"], 3.0) / 3.0  # Normalize
        else:
            features["relative_stack_size"] = 1.0
        
        # === Community Cards ===
        community_cards = game_state.get("community_cards", [])
        features["num_community_cards"] = len(community_cards) / 5.0  # Normalize to 0-1
        
        # === Hand Features ===
        if len(self.hand) >= 2:
            card1, card2 = self.hand[0], self.hand[1]
            features["pair_in_hand"] = 1.0 if card1.value == card2.value else 0.0
            features["high_card"] = max(c.value for c in self.hand) / 14.0
            features["suited"] = 1.0 if card1.suit == card2.suit else 0.0
            gap = abs(card1.value - card2.value)
            features["connected"] = 1.0 if gap == 1 else 0.0
            features["hand_strength"] = sum(c.value for c in self.hand) / 28.0
        else:
            features["pair_in_hand"] = 0.0
            features["high_card"] = 0.0
            features["suited"] = 0.0
            features["connected"] = 0.0
            features["hand_strength"] = 0.0
        
        return features
    
    # =========== Training Methods ===========
    
    def on_hand_end(self, result: Dict[str, Any]) -> None:
        """Process hand result for learning."""
        super().on_hand_end(result)
        
        if not self.is_training:
            return
        
        self.training_episodes += 1
        
        # Calculate reward
        reward = self._calculate_reward(result)
        self.last_reward = reward
        self.cumulative_reward += reward
        self.cumulative_chip_delta += float(self.chips - self.hand_start_chips)
        
        # Store experience
        if self.last_state is not None and self.last_action is not None:
            self.store_experience(
                self.last_state,
                self.last_action,
                reward,
                self.current_state or self.last_state,
                done=True
            )
        
        # Train if we have enough experiences
        if len(self.memory) >= self.batch_size:
            self.update_model()
        
        # Decay epsilon
        if len(self.memory) > self.batch_size:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        
        # Track wins/losses
        if result.get("won", False) or (self.chips - self.last_chips > 0):
            self.wins += 1
        elif self.chips < self.last_chips:
            self.losses += 1
    
    def _calculate_reward(self, result: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate terminal hand reward from chip outcomes and full-hand action trace.

        This keeps one replay entry per hand while making the reward reflect all
        actions taken during that hand via aggregate commitment and action counts.
        """
        result = result or {}

        net_chip_delta = float(result.get("chip_change", self.chips - self.hand_start_chips))
        hand_start = max(1.0, float(self.hand_start_chips))
        total_bet_in_hand = float(getattr(self, "total_bet_in_hand", 0))
        trace_commitment = float(sum(a.get("commitment_estimate", 0.0) for a in self.hand_action_trace))
        effective_commitment = max(1.0, total_bet_in_hand, trace_commitment)
        action_count = max(1.0, float(len(self.hand_action_trace)))

        # Build a raw chip score directly from chip outcomes.
        raw_chip_reward = net_chip_delta

        # Extra downside pressure for large committed losses (chip-outcome only).
        if net_chip_delta < 0:
            commitment_penalty = 0.20 * effective_commitment
            action_penalty = 2.0 * max(0.0, action_count - 1.0)
            raw_chip_reward -= commitment_penalty + action_penalty

        # Use a centered sigmoid to keep reward bounded in [-1, 1] without hard clipping.
        # Temperature controls sensitivity and scales with stack size.
        temperature = max(20.0, hand_start * 0.1)
        logits = raw_chip_reward / temperature
        logits = max(-60.0, min(60.0, logits))
        return (2.0 / (1.0 + math.exp(-logits))) - 1.0
    
    def store_experience(self, state, action, reward, next_state, done):
        """Store experience in replay memory."""
        self.memory.append((state, action, reward, next_state, done))
        if len(self.memory) > self.max_memory_size:
            self.memory.pop(0)
    
    def update_model(self):
        """Update model using experience replay."""
        if len(self.memory) < self.batch_size:
            return
        
        batch = random.sample(self.memory, self.batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        
        # Convert to tensors
        states = torch.FloatTensor(states)
        actions = torch.LongTensor(actions)
        rewards = torch.FloatTensor(rewards)
        next_states = torch.FloatTensor(next_states)
        dones = torch.FloatTensor(dones)
        
        # Get current Q values
        current_q = self.model(states)
        current_q_values = current_q.gather(1, actions.unsqueeze(1))
        
        # Get next Q values
        with torch.no_grad():
            next_q = self.model(next_states)
            max_next_q = next_q.max(1)[0]
        
        # Compute target
        targets = rewards + (1 - dones) * self.gamma * max_next_q
        
        # Compute loss and update
        loss = nn.MSELoss()(current_q_values, targets.unsqueeze(1))
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
    
    # =========== Model Persistence ===========
    
    def save_model(self, filepath: str):
        """Save model to file."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'epsilon': self.epsilon,
            'training_episodes': self.training_episodes,
            'wins': self.wins,
            'losses': self.losses,
        }, filepath)
    
    def _load_model(self, filepath: str):
        """Load model from file."""
        if not Path(filepath).exists():
            print(f"{self.name}: No model found at {filepath}, starting fresh")
            return
        
        try:
            checkpoint = torch.load(filepath, map_location='cpu')
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            self.epsilon = checkpoint.get('epsilon', self.epsilon)
            self.training_episodes = checkpoint.get('training_episodes', 0)
            self.wins = checkpoint.get('wins', 0)
            self.losses = checkpoint.get('losses', 0)
            print(f"{self.name}: Loaded model from {filepath}")
        except Exception as e:
            print(f"{self.name}: Error loading model: {e}")
    
    # =========== Training Control ===========
    
    def start_training(self):
        """Enable training mode."""
        self.is_training = True
    
    def stop_training(self):
        """Disable training mode."""
        self.is_training = False
    
    def reset_training(self):
        """Reset training state."""
        self.memory = []
        self.epsilon = 1.0
        self.training_episodes = 0
        self.wins = 0
        self.losses = 0
        self.last_reward = 0.0
        self.cumulative_reward = 0.0
        self.cumulative_chip_delta = 0.0
        self.hand_action_trace = []
        self.hand_start_chips = self.chips
        self.model = PokerNet(self.input_size, self.hidden_size)
        self.optimizer = optim.Adam(self.model.parameters())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics including training info."""
        stats = super().get_stats()
        avg_reward = self.cumulative_reward / self.training_episodes if self.training_episodes > 0 else 0.0
        avg_chip_delta = self.cumulative_chip_delta / self.training_episodes if self.training_episodes > 0 else 0.0
        stats.update({
            "is_training": self.is_training,
            "epsilon": self.epsilon,
            "training_episodes": self.training_episodes,
            "memory_size": len(self.memory),
            "train_wins": self.wins,
            "train_losses": self.losses,
            "last_reward": self.last_reward,
            "avg_reward": avg_reward,
            "avg_chip_delta": avg_chip_delta
        })
        return stats
