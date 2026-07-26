"""Latency budgets that keep AI decisions from disrupting live play."""

from __future__ import annotations

import time

import pytest

from app.engine import Game
from app.engine.agents import AgentRegistry

from .conftest import assert_latency_budget, measured_latencies


@pytest.mark.performance
def test_dqn_action_selection_latency(dqn_agent, heads_up_state) -> None:
    """A local DQN decision should be effectively instantaneous for the UI."""
    latencies = measured_latencies(
        lambda: dqn_agent.decide_action(heads_up_state),
        warmup=20,
        samples=200,
    )

    # These are intentionally much lower than a human-visible delay while still
    # leaving headroom for shared CI machines.
    assert_latency_budget(
        latencies,
        median_seconds=0.010,
        p95_seconds=0.030,
    )


@pytest.mark.performance
def test_random_action_selection_latency(heads_up_state) -> None:
    """The lightweight baseline must not introduce measurable game-flow delay."""
    agent = AgentRegistry.create(
        "random",
        name="FastRandom",
        chips=960,
        player_id="hero",
    )
    latencies = measured_latencies(
        lambda: agent.decide_action(heads_up_state),
        warmup=20,
        samples=500,
    )

    assert_latency_budget(
        latencies,
        median_seconds=0.001,
        p95_seconds=0.005,
    )


@pytest.mark.performance
def test_complete_heads_up_hand_finishes_without_agent_stall() -> None:
    """Two bots must complete a hand well inside a live-play turn budget."""
    players = [
        AgentRegistry.create("random", name="A", chips=1000, player_id="a"),
        AgentRegistry.create("random", name="B", chips=1000, player_id="b"),
    ]
    game = Game(players, small_blind=10, big_blind=20)

    started = time.perf_counter()
    game.play_hand()
    elapsed = time.perf_counter() - started

    assert elapsed < 0.250, f"one simulated heads-up hand took {elapsed:.3f}s"


@pytest.mark.performance
@pytest.mark.future_requirement
def test_causal_planner_action_selection_latency(heads_up_state) -> None:
    """The future causal planner must keep p95 decisions below 500 ms."""
    causal_agents = pytest.importorskip(
        "app.engine.agents.adaptive_agent",
        reason="Adaptive causal agent has not been implemented",
    )
    agent = causal_agents.AdaptiveAgent(
        name="CausalBot",
        chips=960,
        player_id="hero",
        deterministic=True,
        rollout_count=128,
    )

    latencies = measured_latencies(
        lambda: agent.decide_action(heads_up_state),
        warmup=3,
        samples=30,
    )
    assert_latency_budget(
        latencies,
        median_seconds=0.250,
        p95_seconds=0.500,
    )
