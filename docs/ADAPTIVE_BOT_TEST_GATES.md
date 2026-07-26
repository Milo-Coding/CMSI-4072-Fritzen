# Adaptive Bot Test Gates

This document maps the executable tests to
`docs/ADAPTIVE_POKER_BOT_IMPROVEMENT_PLAN.md`.

## Running the tests

From the repository root:

```bash
pytest -q
```

Run only action-latency gates:

```bash
pytest -q -m performance
```

Run the plan-derived acceptance directory:

```bash
pytest -q server/tests/requirements
```

Skipped requirement modules indicate that the corresponding planned production
module does not exist yet. They use `pytest.importorskip` at module load. As soon
as a production module is created at the documented path, its contract activates
automatically and becomes a pass/fail release gate.

## Current active gates

| Requirement | Tests |
|---|---|
| DQN action legality | `requirements/test_action_legality.py` |
| DQN and random-policy decision latency | `requirements/test_action_efficiency.py` |
| Full heads-up-hand latency | `requirements/test_action_efficiency.py` |
| Opponent hole-card isolation | `requirements/test_information_integrity.py` |
| Visible-card uniqueness | `requirements/test_information_integrity.py` |
| Public-only action histories | `requirements/test_information_integrity.py` |
| Hand evaluator correctness | `test_engine.py` |
| Betting-round termination and action order | `test_betting_round.py`, `test_all_in_fix.py` |
| Chip and pot conservation | `test_chip_conservation.py` |
| Side pots and all-ins | `test_chip_conservation.py`, `test_all_in_fix.py` |
| REST and WebSocket smoke behavior | `test_api_endpoints.py` |
| Core agent lifecycle | `test_agents.py` |

## Future contracts

### Opponent profile

`requirements/test_opponent_profile_contract.py` activates when
`app.engine.opponents.profile.OpponentProfile` exists. It requires:

- finite population priors;
- explicit opportunity counts;
- posterior learning and decreasing uncertainty;
- per-player isolation;
- contextual estimates; and
- lossless serialization.

### Causal world model

`requirements/test_causal_world_model_contract.py` activates when
`app.engine.causal.world_model` and `app.engine.causal.state` exist. It requires:

- immutable pre-intervention state;
- correct fold and showdown mechanisms;
- reproducible paired counterfactuals;
- rejection of illegal interventions;
- recovery from a synthetic action/outcome confounding example; and
- explicit uncertainty for out-of-support actions.

These tests intentionally evaluate:

```text
E[net_bb | do(action), current_information]
```

instead of observational `P(win | action)`.

### Full-trajectory learning

`requirements/test_learning_pipeline_contract.py` activates when
`app.training.replay.HandTrajectory` exists. It requires:

- one transition for every decision;
- behavior-policy propensities;
- blind-normalized terminal return; and
- legal-action masks stored in replay.

### Statistical evaluation

`requirements/test_evaluation_contract.py` activates when
`app.evaluation.metrics` exists. It requires:

- correct bb/100 normalization;
- reproducible match-clustered bootstrap intervals;
- exact early/late adaptation windows;
- profitability gates based on the lower confidence bound; and
- a doubly robust estimator that recovers a known synthetic effect.

### Causal planner latency

The causal planner performance contract activates when
`app.engine.agents.adaptive_agent.AdaptiveAgent` exists. With 128 configured
rollouts, its local action-selection budget is:

- median below 250 ms; and
- p95 below 500 ms.

These budgets cover local inference and planning. Network transport and UI
rendering should be measured separately in deployment load tests.

## Performance-test methodology

Microbenchmarks:

- warm up the policy before timing;
- disable garbage collection only during the measured loop;
- use `time.perf_counter`;
- assert both median and p95 rather than a single best run; and
- use generous CI-compatible limits rather than workstation-specific targets.

Long-running load and profitability benchmarks should not run in the ordinary
unit-test job. They belong in scheduled CI and must emit durable reports containing
the source commit, model checksum, seeds, opponent-suite version, sample count,
bb/100, clustered confidence intervals, and latency percentiles.

## Release rule

A candidate cannot be described as meeting the improvement plan when requirement
modules are skipped. Release qualification requires:

1. zero skipped requirement contracts;
2. all unit, integration, property, causal, statistical, and performance tests
   passing;
3. scheduled large-sample profitability evaluation passing its preregistered
   confidence-interval gates; and
4. no hidden-information, illegal-action, card-conservation, or chip-conservation
   failures.
