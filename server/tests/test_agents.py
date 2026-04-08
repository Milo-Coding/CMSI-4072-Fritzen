"""
Test Agent System

Tests for the extensible AI agent framework.
"""

import pytest
from app.engine import Player, Game
from app.engine.agents import BaseAgent, AgentRegistry, RandomAgent


class TestAgentRegistry:
    """Test the agent registration and creation system."""
    
    def test_list_agents(self):
        """Test listing available agents."""
        agents = AgentRegistry.list_agents()
        assert "random" in agents
        assert "dqn" in agents
    
    def test_create_random_agent(self):
        """Test creating a random agent."""
        agent = AgentRegistry.create("random", name="TestBot", chips=500)
        assert agent is not None
        assert agent.name == "TestBot"
        assert agent.chips == 500
        assert isinstance(agent, BaseAgent)
    
    def test_create_unknown_agent(self):
        """Test that unknown agent types raise ValueError."""
        with pytest.raises(ValueError, match="Unknown agent type"):
            AgentRegistry.create("nonexistent", name="Test", chips=100)
    
    def test_agent_is_player(self):
        """Test that agents are also Players."""
        agent = AgentRegistry.create("random", name="Bot", chips=1000)
        assert isinstance(agent, Player)


class TestRandomAgent:
    """Test the RandomAgent implementation."""
    
    def test_decide_action(self):
        """Test that random agent can make decisions."""
        agent = RandomAgent(name="TestBot", chips=1000, player_id="test-1")
        
        # Mock game state
        game_state = {
            "current_table_bet": 20,
            "call_amount": 20,
            "available_actions": ["fold", "call", "raise"],
            "state_name": "Pre-Flop",
            "opponents_chips": [1000],
            "pot": 30,
            "community_cards": [],
            "players": [],
            "dealer_index": 0,
            "agent_index": 1,
            "big_blind": 20
        }
        
        action = agent.decide_action(game_state)
        
        # Action should be valid
        assert action is not None
        if isinstance(action, tuple):
            assert action[0] in ["bet", "raise"]
            assert action[1] > 0
        else:
            assert action in ["fold", "check", "call"]
    
    def test_decide_action_with_check(self):
        """Test that agent can check when available."""
        agent = RandomAgent(name="CheckBot", chips=1000, player_id="test-2")
        
        game_state = {
            "current_table_bet": 0,
            "call_amount": 0,
            "available_actions": ["check", "bet"],
            "state_name": "Flop",
            "opponents_chips": [1000],
            "pot": 40,
            "community_cards": [],
            "players": [],
            "dealer_index": 0,
            "agent_index": 1,
            "big_blind": 20
        }
        
        # Make multiple decisions to test randomness
        decisions = [agent.decide_action(game_state) for _ in range(10)]
        
        # Should have at least some variety
        assert len(decisions) == 10


class TestAgentInGame:
    """Test agents working within a game."""
    
    def test_game_with_agents(self):
        """Test that a game can run with AI agents."""
        agent1 = AgentRegistry.create("random", name="Bot1", chips=1000, player_id="bot1")
        agent2 = AgentRegistry.create("random", name="Bot2", chips=1000, player_id="bot2")
        
        game = Game(
            players=[agent1, agent2],
            small_blind=10,
            big_blind=20
        )
        
        assert game.num_players == 2
        assert game.pot == 0
    
    def test_agent_stats(self):
        """Test agent statistics tracking."""
        agent = RandomAgent(name="StatsBot", chips=1000, player_id="stats-1")
        
        stats = agent.get_stats()
        
        assert "name" in stats
        assert "chips" in stats
        assert "hands_played" in stats
        assert "win_rate" in stats
        assert stats["name"] == "StatsBot"
        assert stats["chips"] == 1000
    
    def test_agent_to_dict(self):
        """Test agent serialization."""
        agent = RandomAgent(name="SerializeBot", chips=500, player_id="ser-1")
        
        data = agent.to_dict()
        
        assert data["name"] == "SerializeBot"
        assert data["chips"] == 500
        assert data["player_id"] == "ser-1"
        assert data["is_agent"] is True
        assert data["agent_type"] == "RandomAgent"


class TestDQNAgentImport:
    """Test DQN agent can be imported (requires PyTorch)."""
    
    def test_dqn_in_registry(self):
        """Test that DQN agent is registered."""
        assert "dqn" in AgentRegistry.list_agents()
    
    @pytest.mark.skipif(
        not pytest.importorskip("torch", reason="PyTorch not installed"),
        reason="PyTorch required for DQN agent"
    )
    def test_create_dqn_agent(self):
        """Test creating a DQN agent (if PyTorch available)."""
        try:
            agent = AgentRegistry.create("dqn", name="DQNBot", chips=1000)
            assert agent is not None
            assert agent.name == "DQNBot"
        except RuntimeError as e:
            if "PyTorch" in str(e):
                pytest.skip("PyTorch not installed")
            raise

    @pytest.mark.skipif(
        not pytest.importorskip("torch", reason="PyTorch not installed"),
        reason="PyTorch required for DQN agent"
    )
    def test_dqn_traces_all_actions_in_hand(self):
        """DQN should record each decision taken during a hand in its action trace."""
        agent = AgentRegistry.create("dqn", name="TraceBot", chips=1000, is_training=False)
        agent.on_hand_start({})

        game_state = {
            "state_name": "Flop",
            "available_actions": ["call"],
            "call_amount": 20,
            "current_table_bet": 40,
            "pot": 120,
            "community_cards": [],
            "opponents_chips": [980],
            "dealer_index": 0,
            "agent_index": 1,
            "players": [
                {
                    "player_id": "opp",
                    "name": "Opp",
                    "chips": 980,
                    "is_playing_round": True,
                    "current_bet_in_round": 40,
                    "total_bet_in_hand": 20,
                    "has_acted_this_round": True,
                },
                {
                    "player_id": "trace",
                    "name": "TraceBot",
                    "chips": 1000,
                    "is_playing_round": True,
                    "current_bet_in_round": 20,
                    "total_bet_in_hand": 20,
                    "has_acted_this_round": False,
                },
            ],
        }

        agent.decide_action(game_state)
        agent.decide_action(game_state)
        agent.decide_action(game_state)

        assert len(agent.hand_action_trace) == 3
        assert all(entry["action"] == "call" for entry in agent.hand_action_trace)

    @pytest.mark.skipif(
        not pytest.importorskip("torch", reason="PyTorch not installed"),
        reason="PyTorch required for DQN agent"
    )
    def test_dqn_reward_penalizes_larger_committed_loss(self):
        """Chip losses with higher commitment/action volume should receive lower reward."""
        agent = AgentRegistry.create("dqn", name="RewardBot", chips=1000, is_training=True)

        agent.hand_start_chips = 1000
        agent.chips = 900
        agent.total_bet_in_hand = 120
        agent.hand_action_trace = [
            {"commitment_estimate": 60.0},
            {"commitment_estimate": 60.0},
        ]
        lower_commitment_reward = agent._calculate_reward({"chip_change": -100})

        agent.hand_start_chips = 1000
        agent.chips = 900
        agent.total_bet_in_hand = 400
        agent.hand_action_trace = [
            {"commitment_estimate": 100.0},
            {"commitment_estimate": 100.0},
            {"commitment_estimate": 100.0},
            {"commitment_estimate": 100.0},
        ]
        higher_commitment_reward = agent._calculate_reward({"chip_change": -100})

        assert higher_commitment_reward < lower_commitment_reward
