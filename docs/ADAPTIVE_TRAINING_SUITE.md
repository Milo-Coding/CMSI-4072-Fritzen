# Adaptive Agent Training Suite

## Purpose

The training suite repeatedly runs the adaptive agent against every agent family
currently available in this repository. It supports:

- heads-up matches;
- homogeneous three-player and six-player tables;
- heads-up matches against each bundled DQN checkpoint;
- four-player mixed tables; and
- six-player mixed tables.

For the adaptive agent, "training" currently means updating persistent Bayesian
opponent profiles and collecting full-hand trajectories. It does not yet update
neural-network weights.

## Default suite

Run from `server/`:

```bash
python -m scripts.train_adaptive_suite
```

The default workload runs 20 games of up to 50 hands for every available
scenario. Bundled DQN checkpoints are detected under `server/models`.

For a quicker local experiment:

```bash
python -m scripts.train_adaptive_suite \
  --games 5 \
  --hands 50 \
  --rollouts 32 \
  --seed 4072 \
  --output-dir ./reports/adaptive_training_quick
```

For a larger run:

```bash
python -m scripts.train_adaptive_suite \
  --games 200 \
  --hands 50 \
  --rollouts 128 \
  --seed 4072 \
  --output-dir ./reports/adaptive_training_large
```

## Strict validation

Strict mode exits with status 1 when a scenario lacks 50 observed hands or misses
either configured threshold:

```bash
python -m scripts.train_adaptive_suite \
  --games 200 \
  --hands 50 \
  --rollouts 128 \
  --strict \
  --minimum-late-bb100 0 \
  --minimum-game-win-rate 0.25
```

Thresholds should be preregistered before a final run. A threshold of zero does
not establish statistical significance.

## Outputs

The output directory contains:

- `results.json`: complete machine-readable metrics, opponent profiles, and
  per-hand big-blind results;
- `report.md`: concise scenario comparison.

Each scenario reports:

- table size and opponent composition;
- games and hands completed;
- outright game wins and ties;
- total net chips and bb/100;
- bb/100 during hands 1-10;
- bb/100 during hands 41-50;
- the hand-50 adaptation delta;
- hands per second; and
- serialized per-opponent profiles.

If fewer than 50 hands complete, the report marks the hand 41-50 window as
`N/A` and strict validation fails. A nominal 50-hand game can end early when too
few players retain chips, so use multiple games per scenario.

## Independent-game Monte Carlo suite

The Monte Carlo command starts a fresh adaptive agent and fresh opponent profiles
for every game. This is different from the sequential training command, where
profiles persist across games in a scenario.

Run 100 independent games for every default scenario:

```bash
python -m scripts.monte_carlo_adaptive_suite \
  --games 100 \
  --hands 50 \
  --rollouts 64 \
  --bootstrap-samples 2000 \
  --seed 4072
```

Run selected scenarios:

```bash
python -m scripts.monte_carlo_adaptive_suite \
  --games 500 \
  --hands 50 \
  --scenario heads_up_random \
  --scenario four_player_mixed \
  --output-dir ./reports/selected_monte_carlo
```

Every trial receives a distinct deterministic seed, and the adaptive seat rotates
across trials. The report includes:

- average hands completed per game;
- number of games that actually reached hand 50;
- average net big blinds per game;
- game win and tie rates;
- aggregate bb/100;
- a match-clustered bootstrap confidence interval for net bb per game;
- average results for hands 1-10 and hands 41-50; and
- the average chip result at every hand index.

Because each trial starts with fresh profiles, the hand 1 versus hand 50
comparison measures within-table adaptation rather than knowledge carried over
from earlier games.

## Scenario API

Custom mixed tables can be defined in Python:

```python
from app.evaluation.training_suite import (
    OpponentSpec,
    TrainingScenario,
    run_scenario,
)

scenario = TrainingScenario(
    name="custom_mixed",
    opponents=[
        OpponentSpec("random"),
        OpponentSpec("dqn", "./models/simple_trained.pth"),
        OpponentSpec("random"),
    ],
    games=100,
    hands_per_game=50,
)

result = run_scenario(scenario, seed=4072, rollout_count=128)
```

The adaptive trainee's seat rotates between games. Opponent IDs remain stable
within a scenario so learned profiles persist across the run.

## Interpreting results

A short suite validates execution and data collection, not profitability.
Poker outcomes are high variance, and the current summary does not replace the
plan's match-clustered confidence-interval evaluation.

Before claiming the agent can win:

1. use independent seeds and many matches;
2. keep final opponent configurations held out from tuning;
3. compare against the same agent with profile adaptation disabled;
4. calculate match-clustered confidence intervals;
5. require the lower interval bound to exceed zero; and
6. verify improvement is present across opponent families, not only one weak bot.
