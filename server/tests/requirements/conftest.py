"""Shared fixtures and assertions for plan-level acceptance tests."""

from __future__ import annotations

import gc
import statistics
import time
from typing import Callable, Iterable, List

import pytest

from app.engine import Card
from app.engine.agents import AgentRegistry


@pytest.fixture
def heads_up_state() -> dict:
    """Return a realistic, public, heads-up flop decision state."""
    return {
        "state_name": "Flop",
        "available_actions": ["fold", "call", "raise"],
        "call_amount": 40,
        "current_table_bet": 80,
        "pot": 180,
        "community_cards": [
            Card("Hearts", 14).to_dict(),
            Card("Clubs", 9).to_dict(),
            Card("Diamonds", 4).to_dict(),
        ],
        "opponents_chips": [920],
        "dealer_index": 0,
        "agent_index": 1,
        "players": [
            {
                "player_id": "villain",
                "name": "Villain",
                "chips": 920,
                "is_playing_round": True,
                "current_bet_in_round": 80,
                "total_bet_in_hand": 80,
                "has_acted_this_round": True,
                "hand": [],
            },
            {
                "player_id": "hero",
                "name": "Hero",
                "chips": 960,
                "is_playing_round": True,
                "current_bet_in_round": 40,
                "total_bet_in_hand": 40,
                "has_acted_this_round": False,
                "hand": [
                    Card("Spades", 14).to_dict(),
                    Card("Spades", 13).to_dict(),
                ],
            },
        ],
        "street_actions": [
            {
                "player_id": "villain",
                "action": "bet",
                "amount": 80,
                "street": "Flop",
                "pot": 180,
                "current_table_bet": 80,
            }
        ],
        "street_action_history": {
            "Pre-Flop": [],
            "Flop": [],
            "Turn": [],
            "River": [],
        },
        "action_history": [],
    }


@pytest.fixture
def dqn_agent():
    """Create a deterministic inference-mode DQN agent."""
    pytest.importorskip("torch", reason="PyTorch is required for DQN tests")
    agent = AgentRegistry.create(
        "dqn",
        name="RequirementDQN",
        chips=960,
        player_id="hero",
        is_training=False,
    )
    agent.hand = [Card("Spades", 14), Card("Spades", 13)]
    return agent


def measured_latencies(
    operation: Callable[[], object],
    *,
    warmup: int,
    samples: int,
) -> List[float]:
    """Measure an operation with warmup and GC disabled during sampling."""
    for _ in range(warmup):
        operation()

    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        durations = []
        for _ in range(samples):
            started = time.perf_counter()
            operation()
            durations.append(time.perf_counter() - started)
        return durations
    finally:
        if gc_was_enabled:
            gc.enable()


def percentile(values: Iterable[float], quantile: float) -> float:
    """Return a nearest-rank percentile without a third-party dependency."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("At least one value is required")
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * quantile)))
    return ordered[index]


def assert_latency_budget(
    values: List[float],
    *,
    median_seconds: float,
    p95_seconds: float,
) -> None:
    """Assert stable median and tail-latency budgets with useful diagnostics."""
    observed_median = statistics.median(values)
    observed_p95 = percentile(values, 0.95)
    assert observed_median < median_seconds, (
        f"median latency {observed_median:.6f}s exceeded {median_seconds:.6f}s"
    )
    assert observed_p95 < p95_seconds, (
        f"p95 latency {observed_p95:.6f}s exceeded {p95_seconds:.6f}s"
    )
