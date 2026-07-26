# Adaptive Training Suite Report

- Seed: `4072`
- Elapsed: `9.19s`

| Scenario | Players | Hands | Game wins | Win rate | bb/100 | Hands 1-10 bb/100 | Hands 41-50 bb/100 | Adaptation Δ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| heads_up_random | 2 | 472 | 15/20 | 75.0% | 83.91 | 15.00 | -147.50 | -162.50 |
| three_player_random | 3 | 463 | 8/20 | 40.0% | 18.81 | -1000.00 | 0.00 | 1000.00 |
| six_player_random | 6 | 487 | 7/20 | 35.0% | 203.13 | 54.00 | 0.00 | -54.00 |
| heads_up_simple_trained | 2 | 32 | 11/20 | 55.0% | 312.50 | 990.00 | N/A | N/A |
| heads_up_trained_vs_simple | 2 | 641 | 19/20 | 95.0% | 131.33 | 781.00 | 264.50 | -516.50 |
| four_player_mixed | 4 | 367 | 6/20 | 30.0% | 48.20 | 1047.50 | -1000.00 | -2047.50 |
| six_player_mixed | 6 | 421 | 4/20 | 20.0% | 47.51 | -500.00 | 0.00 | 500.00 |

Short runs are smoke tests, not evidence of profitability. Use many
independent matches and confidence intervals for release decisions.
