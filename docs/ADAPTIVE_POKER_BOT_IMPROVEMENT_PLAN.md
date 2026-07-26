# Adaptive Poker Bot Improvement Plan

## 1. Objective

Build an adaptive no-limit Texas Hold'em agent that identifies exploitable opponent
tendencies quickly and achieves positive expected value against representative
average players and poker bots by the time it has observed 50 hands at a table.

Poker variance makes it impossible to guarantee that the agent will be profitable
in every individual 50-hand session. Therefore, "consistently earn money by hand
50" will mean that, in controlled evaluation:

- the agent's decisions during hands 41-50 have positive expected value;
- its cumulative win rate trends positive by hand 50 across repeated matches;
- its result is statistically significant over a large evaluation sample;
- it improves measurably between hands 1-10 and hands 41-50;
- it succeeds against held-out opponents that were not used for training; and
- it does not depend on seeing opponents' hidden cards or other privileged state.

The initial target environment is the poker variant implemented by this repository.
Real-money deployment is outside the scope of this plan and must not occur without
separate legal, platform-policy, security, bankroll, and responsible-gambling
reviews.

## 2. Definition of Success

### 2.1 Primary metrics

Evaluate in big blinds rather than raw chips so results remain comparable across
blind and stack configurations.

The release candidate must satisfy all of the following:

1. **Positive post-adaptation win rate:** the lower bound of a 95% confidence
   interval for win rate during hands 41-50 is greater than 0 bb/100 against the
   aggregate held-out average-opponent suite.
2. **Positive 50-hand trajectory:** mean cumulative profit at hand 50 is greater
   than zero with a 95% confidence interval that excludes zero.
3. **Demonstrated adaptation:** performance during hands 41-50 is significantly
   better than performance during hands 1-10 against adaptive-test opponents.
4. **Generalization:** the agent is profitable separately against at least 80% of
   the opponent families in the held-out suite, rather than obtaining all profit
   from one weak opponent.
5. **Baseline improvement:** the adaptive agent outperforms the same policy with
   opponent-profile features disabled.
6. **Legality and integrity:** zero illegal actions, chip-conservation failures,
   hidden-information leaks, or betting-engine inconsistencies in the evaluation
   run.
7. **Causal validity:** on preregistered simulator benchmarks, the world model
   estimates the value of legal action interventions within defined error and
   calibration bounds and outperforms a correlational hand-strength/win
   predictor.

### 2.2 Secondary metrics

- bb/100 overall and by hands 1-10, 11-20, 21-30, 31-40, and 41-50
- probability of being ahead at hand 50
- expected value per decision
- showdown and non-showdown winnings
- performance by position, street, stack depth, and player count
- exploitability/regret against stronger benchmark agents
- calibration error for equity and opponent-action predictions
- inference time at p50, p95, and p99
- opponent-profile convergence speed and uncertainty

### 2.3 Evaluation scale

Fifty hands is the adaptation horizon, not an adequate sample size for proving a
win rate. Final evaluation should use many independent 50-hand matches, paired
seeds, rotated seats, and duplicate deals. A preliminary goal is at least 100,000
evaluation hands per major opponent family, followed by a power analysis to set
the final required sample size.

Training seeds, tuning seeds, and final evaluation seeds must be disjoint. The
final test suite must remain frozen and unavailable to training.

## 3. Current-State Gaps

The existing project provides a playable engine, a DQN agent, action histories,
model persistence, and baseline tests. The following gaps prevent it from meeting
the objective:

1. Opponent behavior is aggregated only over the current street.
2. No persistent profile exists for each opponent across hands.
3. Inference-mode agents do not adapt their policy or profile online.
4. Only the last action in a hand is written to replay memory.
5. Bet and raise sizing is mostly hard-coded.
6. The DQN chooses from unmasked actions and may fall back to randomness.
7. Hand strength is represented by coarse deterministic features instead of
   range-aware equity.
8. Training opponents are too narrow and do not represent average-player styles.
9. There is no held-out adaptation benchmark or statistical profitability test.
10. Model checkpoints lack complete schema, configuration, and evaluation
    metadata.
11. There is no causal world model separating card chance, player actions,
    opponent responses, folds, showdown outcomes, and payouts. The current model
    can learn correlations between features such as hand strength and winning,
    but it cannot answer the decision question: "What would happen if this same
    player chose a different legal action or bet size in this state?"

## 4. Target Architecture

Use a layered design so that opponent learning, poker-state estimation, decision
making, and evaluation can be tested independently.

```text
Game events
    |
    v
Observation validator ----> immutable hand/action history
    |                                  |
    v                                  v
Poker state encoder              Opponent profiler
    |                                  |
    +----------> causal world state <--+
                         |
                         v
              interventional simulator
             do(fold/check/call/bet/raise)
                         |
                         v
       counterfactual outcome distributions
       (responses, next street, fold, showdown,
                  payout and utility)
                         |
                         v
               legal-action generator
                         |
                         v
             strategy / exploitation policy
                         |
                         v
                  validated action
```

### 4.1 Observation and history layer

Create canonical, typed records for:

- hand ID, table ID, player ID, seat, dealer, blinds, and stack depth;
- street, board, pot, effective stack, and amount to call;
- every action, target amount, increment, and pot-relative size;
- legal actions and legal sizing bounds at every decision;
- showdown cards when legitimately revealed; and
- terminal payouts and net chip changes.

Histories must persist for the table session and must be view-safe: the bot may
consume only information a real player would have observed at that moment.

### 4.2 Per-opponent profile

Maintain an `OpponentProfile` keyed by stable player identity, with global priors
and uncertainty. At minimum track:

- voluntary put money in pot (VPIP);
- preflop raise, limp, three-bet, four-bet, and fold-to-three-bet rates;
- steal and fold-to-steal rates by position;
- continuation-bet and fold-to-continuation-bet rates by street;
- check-raise, donk-bet, probe-bet, and delayed-c-bet rates;
- aggression frequency and aggression factor by street;
- fold/call/raise response conditioned on facing bet-size bucket;
- bet and raise size distributions as fractions of the pot;
- river bluff indicators when showdowns reveal enough information;
- showdown frequency, showdown win rate, and muck/reveal observations;
- timing information only if it is reliable, consented to, and available equally;
- number of opportunities behind every rate; and
- recency-weighted and session-wide estimates.

Use beta-binomial or Dirichlet posteriors for categorical tendencies and
distributional models for bet sizes. Begin from population priors so estimates
remain stable with few observations. Include confidence/observation counts in the
policy input so the bot does not overreact to small samples.

### 4.3 Population style inference

In addition to raw statistics, infer a soft mixture over player styles, such as:

- tight-passive;
- loose-passive;
- tight-aggressive;
- loose-aggressive;
- balanced/reg-like;
- over-bluffing;
- under-bluffing/calling-station; and
- scripted or anomalous.

Do not force an opponent into one label. Maintain probabilities and update them
after every action. The policy should be able to exploit both the style posterior
and the underlying statistics.

### 4.4 Range and equity model

Replace coarse hand-strength proxies with decision-relevant estimates:

- initialize opponent ranges using position and preflop action;
- update ranges after every action using action likelihood and sizing;
- remove known hole and community cards;
- estimate showdown equity using exact enumeration where practical and Monte
  Carlo simulation otherwise;
- estimate equity versus each opponent and versus the joint multiway field;
- compute pot odds, implied-odds proxies, stack-to-pot ratio, and fold equity; and
- cache repeated calculations to meet latency targets.

Range updates must never condition on unrevealed opponent cards.

### 4.5 Causal poker world model

Implement an explicit structural causal model of how a poker hand progresses and
how decisions can produce a round win or loss. The world model must represent
mechanisms rather than treating final wins as labels correlated with visible hand
strength.

The model should distinguish:

- **Exogenous chance variables:** shuffled deck, private cards, future community
  cards, seat assignment, and any randomized opponent-policy noise;
- **Observed pre-action state:** legal public history, hero cards, board, pot,
  stacks, position, street, and action order;
- **Latent opponent state:** private cards/range, strategy type, beliefs, and
  session-specific tendencies;
- **Interventions:** the hero's legal action and chosen size, represented as
  `do(action = a, size = s)` rather than as another observed feature;
- **Mediators:** each opponent's fold/call/raise response, resulting pot and
  stacks, future action sequence, and whether the hand reaches showdown; and
- **Outcomes:** probability of winning without showdown, showdown equity, gross
  payout, net chip change, and bankroll utility.

A first structural graph should encode the following relationships:

```text
Deck seed ──> private cards ──> ranges/equity ───────────────┐
     └──────> board runout ──────────────────────────────────┤
Position/stacks/history ──> legal actions                    │
Opponent latent style ────> opponent response <──────────┐   │
Opponent private range ───> opponent response            │   │
Hero intervention do(action, size) ──────────────────────┘   │
Hero intervention ──> pot/stacks ──> later decisions ───────┤
Opponent response ───> fold/showdown path ──────────────────┤
Fold/showdown path + equity + pot/stacks ──> net chip payout ◄
```

This graph must be versioned and documented with assumptions about which
variables are observed, latent, exogenous, mediators, outcomes, and possible
confounders. Seat, stack depth, prior actions, player count, opponent identity,
and selection into showdown are especially important. Showdown-only card data
must not be treated as an unbiased sample of all opponent holdings.

#### 4.5.1 Hybrid simulator and learned mechanisms

Use known poker rules as the deterministic causal backbone:

- card removal, dealing, legal-action transitions, betting, pot construction,
  side pots, showdown ranking, and payouts come from the game engine;
- chance nodes are sampled from valid conditional deck distributions; and
- learned components model opponent ranges, action responses, and future policy
  behavior with calibrated uncertainty.

This hybrid approach is preferred over a single opaque network predicting
`win/loss`, because most transition and payout mechanisms are already known
exactly. Learned models should be limited to mechanisms that are genuinely
unknown, primarily opponent behavior and latent ranges.

#### 4.5.2 Interventional action evaluation

At each decision, enumerate legal actions and sizes. For every candidate:

1. hold the current observed history fixed;
2. intervene on the hero action with `do(action = candidate)`;
3. sample latent opponent holdings from legal posterior ranges;
4. sample opponent responses from per-opponent causal response models;
5. progress the hand through folds, calls, raises, future boards, and later
   decisions;
6. calculate payouts with the authoritative engine; and
7. estimate expected net big blinds, uncertainty, and downside risk.

Action selection should be based on the estimated causal effect:

```text
EV(a) = E[net_bb | do(hero_action = a), current_information]
```

not on:

```text
P(win | hero_action = a, historical_data)
```

The latter is confounded by the policy that chose actions historically: strong
hands may have been more likely to raise, and raises may therefore correlate with
wins even when a particular raise is not the best intervention in the current
state.

#### 4.5.3 Counterfactual learning and off-policy correction

Logged gameplay reveals only the outcome of the chosen action. Unchosen-action
effects must be estimated using a combination of:

- randomized exploration in simulation;
- known engine rollouts;
- behavior-policy propensities stored with every training action;
- inverse-propensity weighting or doubly robust estimation where appropriate;
- matched/paired deal evaluation; and
- uncertainty penalties when counterfactual support is weak.

Never claim an identified causal effect when the logged policy gave an action
zero or near-zero probability. Flag these states as unsupported and acquire
simulation data with deliberate exploration.

#### 4.5.4 Temporal and multiplayer causality

The model must handle sequential interventions, because an early bet changes the
pot, ranges, later legal actions, and opponent beliefs. Use a causal Markov state
or sequential structural causal model rather than predicting terminal success
from the initial hand alone.

In multiplayer pots, model each opponent separately and preserve action order.
One player's fold can causally change another player's response, equity, side-pot
eligibility, and payoff. An aggregate "opponent aggression" variable is not an
adequate causal state.

#### 4.5.5 World-model outputs

For every legal candidate action, expose:

- opponent fold/call/raise probabilities by player;
- distribution over response sizes;
- probability of ending the hand immediately;
- probability of reaching each later street and showdown;
- showdown-equity distribution conditional on reaching showdown;
- expected gross pot share and expected net bb;
- value-at-risk/downside summaries;
- epistemic uncertainty and effective support; and
- the causal path components that contributed to the estimate.

These outputs support policy decisions, debugging, calibration, and causal
validation. They must not be presented as certainty.

### 4.6 Policy design

Implement a strong non-adaptive base strategy and a bounded exploitation layer.
This is safer and easier to validate than unrestricted online neural-network
updates.

Recommended progression:

1. rule/equity baseline with legal sizing;
2. offline-trained masked DQN or actor-critic baseline;
3. recurrent or transformer policy that consumes action sequences;
4. opponent-conditioned policy using profile and range features; and
5. bounded exploit adjustment based on posterior confidence.

The exploit layer should shift frequencies and sizes only when observations
support the adjustment. Add configurable exploit limits to prevent catastrophic
overreaction or counter-exploitation.

The policy should consume interventional EV distributions from the causal world
model, not use raw hand strength as a proxy for winning. A model-free policy may
remain as an ensemble member or fallback, but the causal-model ablation must show
whether it adds value.

### 4.7 Action space and legality

Use a parameterized or discretized sizing space including:

- fold, check, and call;
- 25%, 33%, 50%, 66%, 75%, 100%, and 150% pot;
- minimum legal raise;
- geometric sizes based on remaining streets and stack-to-pot ratio; and
- all-in.

Generate the legal-action mask before inference. Invalid actions must receive
negative infinity before action selection; they must never trigger random
fallback behavior. Convert size buckets to engine-valid amounts and validate the
result a second time before execution.

### 4.8 Online adaptation

Online adaptation should initially update opponent beliefs, not neural-network
weights. Profile updates are fast, interpretable, reversible, and far less likely
to destabilize the bot within 50 hands.

If online policy learning is later added:

- isolate it behind a feature flag;
- use a small, bounded learning rate;
- retain a frozen base-policy copy;
- reject updates that violate safety/KL-divergence limits;
- store full transitions and legal masks;
- support immediate rollback; and
- never train from hidden information unavailable at decision time.

Opponent adaptation must update the learned causal response mechanisms and their
uncertainty. For example, observing frequent folds after large turn bets should
update `P(fold | do(bet_size), context, opponent)` only to the extent supported
by comparable opportunities; it must not simply associate that opponent's folds
with all future large bets.

## 5. Reinforcement-Learning Corrections

### 5.1 Transition collection

Store every decision transition, not merely the final action:

```text
(observation, opponent_context, legal_mask, action, reward,
 next_observation, next_legal_mask, terminal)
```

Maintain the trajectory until hand completion, assign terminal chip utility, and
calculate Monte Carlo or n-step returns for every action. Include blinds in net
profit and verify that rewards sum consistently with chip movements.

### 5.2 Reward

Use net big blinds won as the primary objective. Avoid hand-crafted penalties that
can teach the agent to optimize the shaping rule instead of profit. If auxiliary
rewards are required for early training, anneal them away and prove through
ablation that they improve final chip EV.

Consider bankroll-sensitive utility only as a separately evaluated policy. Do not
confuse lower variance with higher expected profit.

### 5.3 Stable learning

Add:

- target network;
- Double DQN targets or a suitable actor-critic alternative;
- prioritized replay only after a correct uniform-replay baseline;
- gradient clipping;
- observation normalization frozen for evaluation;
- checkpointed optimizer and random-number-generator states;
- deterministic evaluation mode;
- training curves and divergence detection; and
- reproducible configuration files.

### 5.4 Model inputs

Version the feature schema. Inputs should include:

- cards and board representation;
- position and number of players;
- pot, effective stacks, commitments, and legal sizes;
- full current-hand action sequence;
- range/equity estimates;
- one profile per relevant opponent or learned opponent embeddings;
- profile uncertainty and observation count; and
- an explicit missing-data mask.

For multiplayer games, use permutation-aware opponent encoding or deterministic
seat-relative ordering.

## 6. Opponent and Training Population

Build scripted opponents with configurable noise:

- tight-passive;
- loose-passive/calling station;
- tight-aggressive;
- loose-aggressive;
- over-folder;
- over-bluffer;
- min-bet/min-raise bot;
- large-sizing bot;
- short-stack shove/fold bot;
- position-aware bot;
- opponent that changes style after 20-30 hands; and
- adversarial bot that reacts to the agent.

Train against randomized mixtures of these behaviors, stack depths, table sizes,
blind levels, seats, and bet-size preferences. Add past policy checkpoints to the
population so the agent cannot overfit the latest opponent.

Human-derived population priors should be used only from legally obtained,
consented, anonymized data with documented provenance.

## 7. Evaluation Harness

Create a headless tournament runner that:

- runs thousands of independent 50-hand matches in parallel;
- rotates every seat and dealer position;
- replays paired/duplicate deals for competing agents;
- supports controlled interventions that replay the same information state with
  different hero actions and common random numbers;
- records every decision and profile update;
- records behavior-policy action propensities and causal-world-model predictions;
- compares adaptive and non-adaptive ablations;
- compares causal world-model planning against correlational win prediction and
  model-free policy baselines;
- produces bb/100, confidence intervals, and learning-by-hand curves;
- breaks results down by opponent, table size, stack depth, and street;
- detects illegal actions, timeouts, leakage, and chip-creation errors; and
- exports machine-readable JSON/CSV plus a concise Markdown report.

Required evaluation splits:

1. known scripted styles with unseen random seeds;
2. held-out parameterizations of known styles;
3. entirely held-out opponent logic;
4. frozen historical policy checkpoints;
5. mixed multiplayer tables;
6. opponents that change strategy mid-session; and
7. adversarial stress tests.

Use bootstrap confidence intervals clustered by match/deal, not by individual
hand, because hands within a match are not independent.

The causal evaluation suite must additionally report:

- interventional EV error against exact or high-sample simulator rollouts;
- opponent-response calibration under controlled action interventions;
- average treatment-effect and conditional treatment-effect error for bet sizes;
- policy value estimated by direct simulation, inverse propensity scoring, and a
  doubly robust estimator;
- coverage and calibration of epistemic uncertainty;
- performance under distribution shifts in opponent strategy; and
- the incremental value of the causal world model in a preregistered ablation.

## 8. Testing Requirements

### 8.1 Engine and information integrity

- property-based chip and card conservation tests;
- legal-action and sizing-bound tests for every stack state;
- side-pot and split-pot tests with multiple all-ins;
- heads-up blind and action-order tests;
- deterministic replay tests;
- hidden-card leakage tests at every API/agent boundary; and
- consistency tests between direct-engine and room-manager execution paths.

### 8.2 Opponent profiler

- opportunity counts and posterior updates for every statistic;
- position/street/bet-size conditioning;
- prior behavior with zero and few observations;
- decay and style-change detection;
- serialization and restoration;
- multiplayer identity isolation; and
- no updates from unobserved or hidden events.

### 8.3 Learning and policy

- every action in a hand receives a transition;
- terminal returns and blinds are correct;
- illegal actions are fully masked;
- inference is deterministic when configured;
- checkpoint schema incompatibility fails clearly;
- policy input is invariant/equivariant where intended; and
- adaptation improves results in controlled toy environments.

### 8.4 Causal world model

- the declared causal graph passes schema and temporal-order validation;
- deterministic transition and payout mechanisms exactly match the game engine;
- interventions change only the assigned action node and its descendants;
- identical exogenous seeds produce paired counterfactual rollouts;
- impossible cards, actions, and action sequences have zero probability;
- latent range samples respect card removal and observed showdowns;
- fold, call, and raise response models are calibrated under randomized
  simulator interventions;
- causal EV estimates recover exact values in small enumerated poker scenarios;
- a synthetic confounding test demonstrates that the causal estimator rejects a
  misleading action/win correlation;
- showdown-selection tests prevent revealed hands from biasing all-hand ranges;
- propensity and doubly robust estimators recover known treatment effects in
  synthetic logged-policy data;
- unsupported interventions produce high uncertainty or an explicit
  out-of-support result;
- sequential and multiplayer mediator effects are preserved; and
- no descendant of the selected action leaks into the pre-action state.

### 8.5 Statistical tests

Avoid flaky assertions that a bot wins one short match. Test deterministic
components directly and run profitability benchmarks as longer scheduled jobs
with predefined statistical gates.

## 9. Data, Reproducibility, and Model Governance

Every checkpoint must include:

- source commit;
- causal-graph and mechanism-schema versions;
- feature-schema and action-schema versions;
- complete training configuration;
- opponent-population version;
- seeds and library versions;
- training duration and sample count;
- validation and held-out results;
- known limitations; and
- a checksum.

Keep a model card for each release candidate. Do not label a model profitable
based on training results or a single favorable run.

## 10. Observability

Add structured logs and dashboards for:

- action probabilities before and after exploit adjustment;
- selected action and legal alternatives;
- equity, pot odds, and fold-equity estimate;
- opponent-profile values, uncertainty, and evidence;
- predicted opponent response;
- realized chip result;
- inference latency and errors; and
- aggregate adaptation curves.

Provide a debug explanation mode for offline analysis. Explanations must be
derived from recorded inputs and must not expose hidden server state.

## 11. Security, Legal, and Operational Boundaries

Before any external or real-money use:

- confirm that automated play is legal in the relevant jurisdiction;
- obtain explicit permission from the poker platform;
- comply with terms of service and API/bot policies;
- prohibit screen scraping, input automation, collusion, multi-accounting, and
  access to hidden information;
- sandbox model loading and allow only trusted, versioned checkpoints;
- remove user-controlled arbitrary model paths;
- establish bankroll, loss, and automatic shutdown limits;
- require human review of anomalous behavior; and
- conduct a responsible-gambling and abuse review.

The development and evaluation environment should use play money or simulation.

## 12. Phased Implementation

### Phase 0: Benchmark contract and reproducibility

Deliverables:

- formal metric definitions;
- frozen training/validation/test split format;
- deterministic seed and replay support;
- baseline evaluation of random and current DQN agents;
- experiment configuration and result schema; and
- CI smoke benchmark.

Exit gate: a clean checkout can reproduce baseline results and confidence
intervals from a documented command.

### Phase 1: Engine correctness and canonical observations

Deliverables:

- typed observation/action/terminal records;
- unified state builder shared by engine and web room manager;
- complete legal sizing information;
- hidden-information audit;
- expanded property and integration tests; and
- versioned action and observation schemas.

Exit gate: no action-path discrepancies, leakage, or conservation failures across
the stress suite.

### Phase 2: Evaluation harness and opponent suite

Deliverables:

- headless parallel match runner;
- scripted opponent families;
- paired-deal and seat-rotation support;
- 50-hand adaptation reports; and
- adaptive-versus-static ablation framework.

Exit gate: the harness distinguishes known adaptive and non-adaptive reference
agents with statistically sensible results.

### Phase 3: Persistent opponent profiling

Deliverables:

- Bayesian `OpponentProfile`;
- session persistence;
- contextual statistics and uncertainty;
- style posterior;
- profiler unit tests; and
- profile inspection/debug report.

Exit gate: profiles converge toward known scripted parameters within documented
error bounds and react to a mid-session style change.

### Phase 4: Poker strength and range model

Deliverables:

- range representation and updates;
- heads-up and multiplayer equity calculation;
- pot odds, fold equity, and effective-stack features;
- caching and latency benchmarks; and
- correctness comparisons against enumerated small cases.

Exit gate: equity error and inference latency meet predefined thresholds.

### Phase 5: Causal world model and interventional simulator

Deliverables:

- documented, versioned structural causal graph;
- causal state and exogenous-noise schemas;
- engine-backed transition and payout mechanisms;
- learned per-opponent action-response mechanisms;
- range-conditioned latent-card sampler;
- legal-action intervention API;
- paired counterfactual rollout engine;
- interventional EV, uncertainty, and support estimates;
- behavior-propensity logging and off-policy estimators; and
- synthetic confounding and causal-recovery test suite.

Exit gate: the world model recovers known interventional action values in
enumerated and randomized simulator scenarios, remains calibrated on held-out
opponents, and demonstrably avoids at least one benchmark where a correlational
win predictor selects the wrong action.

### Phase 6: Correct baseline policy

Deliverables:

- full trajectory replay;
- legal-action masking;
- expanded bet sizing;
- causal-world-model rollouts available to the action selector;
- stable offline RL implementation;
- checkpoint metadata and schema validation; and
- current-agent migration or retraining.

Exit gate: the policy beats random and naive scripted baselines on held-out deals
without illegal actions.

### Phase 7: Opponent-conditioned causal adaptation

Deliverables:

- profile-conditioned policy input;
- online updates to opponent-specific causal response mechanisms;
- uncertainty-aware estimates of action effects;
- confidence-bounded exploitation layer;
- recurrent action-history encoder if supported by ablation;
- style-change handling; and
- static-policy and no-world-model comparisons.

Exit gate: statistically significant improvement from hands 1-10 to hands 41-50
against the adaptation suite, with improvement attributable to better
interventional value estimates rather than hand-strength/win correlation alone.

### Phase 8: Population training and robustness

Deliverables:

- randomized population curriculum;
- historical checkpoint league;
- held-out opponent families;
- multiplayer training;
- adversarial/counter-adaptation tests; and
- exploitability safeguards.

Exit gate: positive results generalize across the required opponent families
without a severe regression against stronger balanced agents.

### Phase 9: Release qualification

Deliverables:

- large-scale frozen evaluation;
- confidence intervals and power analysis;
- model card;
- security and leakage review;
- performance/load testing;
- rollback procedure; and
- documented limitations.

Exit gate: all primary success metrics pass on the untouched final test set.

## 13. Recommended Repository Changes

Suggested structure:

```text
server/app/engine/
  observations.py
  action_space.py
  history.py
server/app/engine/opponents/
  profile.py
  priors.py
  style_model.py
  range_model.py
server/app/engine/causal/
  graph.py
  state.py
  mechanisms.py
  interventions.py
  counterfactuals.py
  world_model.py
server/app/engine/agents/
  adaptive_agent.py
  policy.py
  exploit_layer.py
server/app/training/
  replay.py
  rewards.py
  population.py
  configs/
server/app/evaluation/
  runner.py
  metrics.py
  causal_metrics.py
  off_policy.py
  reports.py
  opponents/
server/tests/
  property/
  profiling/
  causal/
  learning/
  evaluation/
docs/model_cards/
experiments/
```

Avoid duplicating game-state construction between `Game` and `RoomManager`; both
must call the same observation builder.

## 14. Initial Work Items

Implement in this order:

1. define the metric and evaluation result schemas;
2. build deterministic replay and paired-deal evaluation;
3. create four representative scripted opponent styles;
4. benchmark the current checkpoints;
5. unify and validate observation construction;
6. implement full-trajectory transition storage;
7. implement legal-action masking;
8. implement the persistent Bayesian opponent profile;
9. add profile features with uncertainty;
10. implement range-aware equity;
11. formalize and version the structural causal graph;
12. implement engine-backed causal transition and payout mechanisms;
13. implement opponent-response mechanisms and range-conditioned latent sampling;
14. add legal-action interventions and paired counterfactual rollouts;
15. validate interventional EV against enumerated and randomized ground truth;
16. add behavior propensities and doubly robust off-policy evaluation;
17. expand the bet-sizing action space;
18. integrate causal EV and uncertainty into policy selection;
19. retrain against a population;
20. run adaptive/static/no-world-model/correlational-predictor ablations; and
21. freeze and run the final held-out evaluation.

## 15. Decision Gates

The project should stop and reassess rather than merely train longer if:

- the evaluation harness cannot reproduce paired results;
- hidden information reaches the agent;
- the non-adaptive base policy cannot beat simple baselines;
- the causal model cannot recover known intervention effects in synthetic and
  enumerated scenarios;
- action-value estimates rely on unsupported observational correlations or omit
  behavior-policy propensities;
- profile estimates do not converge within 50 hands for strongly expressed
  tendencies;
- adaptation helps against one style but causes larger aggregate losses;
- confidence intervals remain too wide after the powered evaluation; or
- the real-money use case would violate law or platform rules.

## 16. Completion Criteria

This plan is complete only when the fork contains:

- an adaptive agent implementation;
- persistent, uncertainty-aware per-opponent models;
- a validated causal world model that simulates legal action interventions,
  opponent responses, future streets, folds, showdowns, and payouts;
- counterfactual evaluation proving the policy does not merely associate strong
  hands or historically selected actions with wins;
- a correct full-trajectory learning pipeline;
- a legal, expressive bet-sizing policy;
- a reproducible opponent population and evaluation harness;
- passing correctness, leakage, and statistical gates;
- a held-out report demonstrating positive expected performance by the defined
  50-hand horizon; and
- clear documentation that profitability is an empirical expectation, not a
  guarantee for every short session.
