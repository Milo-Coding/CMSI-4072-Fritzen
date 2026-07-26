# Adaptive Agent Implementation Status

## Implemented

The repository now contains a functional first vertical slice of the adaptive
agent described in the improvement plan.

### Adaptive agent

`app.engine.agents.adaptive_agent.AdaptiveAgent`:

- is registered as agent type `adaptive`;
- is available in the game-room UI;
- evaluates every generated legal action through a causal intervention API;
- selects actions by expected net big blinds with an uncertainty penalty;
- uses bounded, deterministic local planning by default;
- records every decision in a full-hand trajectory;
- logs the behavior-policy probability;
- retains completed training transitions; and
- updates per-opponent beliefs without modifying neural weights online.

### Bayesian opponent profiles

`app.engine.opponents.profile.OpponentProfile` provides:

- finite population priors;
- Beta-Binomial posterior updates;
- opportunity and success counts;
- contextual and global estimates;
- posterior uncertainty;
- strict per-player identity isolation;
- schema-versioned serialization; and
- round-trip restoration.

The included priors are conservative development defaults, not estimates learned
from a representative poker population.

### Causal world model

`app.engine.causal` provides:

- a validated causal poker-state schema;
- immutable action-intervention inputs;
- legal-intervention validation;
- explicit fold-win and showdown pathways;
- engine-backed made-hand evaluation;
- expected net-bb estimates;
- response and sampling uncertainty;
- reproducible exogenous seeds for paired comparisons;
- out-of-support reporting; and
- a synthetic-confounding diagnostic.

Known rules are calculated directly. Unknown opponent responses use live Bayesian
profiles when available and conservative population defaults otherwise.

### Training trajectory

`app.training.replay.HandTrajectory` provides:

- one transition for every decision;
- legal-action masks;
- behavior-policy propensities;
- next observations;
- terminal flags; and
- blind-normalized terminal returns.

### Evaluation

`app.evaluation` provides:

- bb/100 normalization;
- reproducible match-clustered bootstrap confidence intervals;
- hand 1-10 and hand 41-50 adaptation windows;
- lower-confidence-bound profitability gates; and
- doubly robust action-value/effect estimators.

## Deliberately data-dependent work

The following components should not be fabricated without representative training
or evaluation data:

1. **Population priors.** VPIP, aggression, folding, sizing, and style priors need
   legally obtained, representative data or a deliberately designed simulated
   population.
2. **Learned response mechanisms.** The current causal opponent-response
   mechanism is Bayesian/rules-based. Conditional response models require logged
   contexts, actions, behavior propensities, and outcomes.
3. **Calibrated range model.** The current vertical slice uses legal-card and
   hand-strength reasoning, not a learned position/action-conditioned range
   checkpoint.
4. **Population-trained base policy.** No claim of profitability should be made
   before population training and held-out evaluation.
5. **Final causal calibration thresholds.** Acceptable EV error, uncertainty
   coverage, and out-of-support thresholds must be selected using validation data
   before the final test set is opened.

## Important current limitations

- Non-river equity is a fast deterministic approximation, not full range-versus-
  range Monte Carlo equity.
- The initial opponent response mechanism models aggregate fold probability and a
  simplified called-pot path; it does not yet simulate recursive raises or all
  remaining streets.
- Online beliefs live for the lifetime of the agent object. Database persistence
  across server restarts is not implemented.
- The planner is causal in action semantics and pathway decomposition, but it is
  not yet a learned sequential structural causal model.
- The agent has not been shown to be profitable against humans or held-out bots.

## Verification

From the repository root:

```bash
pytest -q
pytest -q -m performance
```

The frontend can be checked with:

```bash
cd client
npm run build
npm run lint
```

Release qualification remains governed by
`docs/ADAPTIVE_BOT_TEST_GATES.md` and requires large-sample scheduled evaluation,
not just unit-test success.
