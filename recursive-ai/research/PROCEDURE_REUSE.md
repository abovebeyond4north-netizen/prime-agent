# Persistent procedure memory: matched ablation

Executed October 13, 2026. Code commit: 0acf20b178fdb9274f10e6845e159eef3e48737e.
Docker study: https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38394197159

## Measured result

All three CI runs (shifted seeds 910022, 910033, 910044) passed.

| Measure | Retained model reuse | Forced rediscovery |
| --- | ---: | ---: |
| Shared tier-1 training containers | 65 | 65 |
| Tier-2 continuation containers | 54 | 88 |
| Continuation attempts | 3 | 3 |
| Training + continuation containers | 119 | 153 |
| Certified task/tier contracts after uncapped continuation | 6 | 6 |
| Certified contracts with 54-container continuation limit | 6 | 5 |
| Status at 54-container limit | goal_reached | container_budget |

Savings: 34 continuation containers per run, 38.6%; 22.2% including shared training. Both uncapped arms produced identical final source hashes and passed fresh audits. Across those arms, 18,432 shifted final-audit cases passed, plus 3,072 extra seeded cases checked against the task oracle and exact integer boundary inequalities. Extra seeded validation uses 17 containers per arm and is reported separately from continuation cost.

## Causal boundary

The control starts from an exact copy of the same trained state, including certified sources, procedure models, operator history and archived candidates. Only model lookup at proposal time is suppressed; models remain in the checkpoint and no evaluator or certification gate is changed. It screens all 16 configurations for each of two inverse continuations. Reuse reconstructs a currently certified source, reuses its configuration and reinduces the predicate from public labels. All receiving candidates are certified afresh.

Arm order is reversed for even seeds. Shifted seeds are excluded from selection. Default regression reuse is disabled in both arms. The fixed cap is measured in the first uncapped reuse arm, then replayed from the frozen training checkpoint; it is not a preregistered arbitrary threshold. Full training, summaries, source hashes and procedure traces are preserved in procedure_reuse_results.json; raw checkpoints and logs are Actions artifacts for 30 days.

## Scope and limits

This verifies a benefit of retaining learned procedures compared with repeatedly rediscovering them. It does not compare against the supplied correct scaffold, demonstrate new task families, or establish open-world intelligence. Tier 2 changes the evaluation difficulty within the same bounded families. Three CI runs share an operator and environment class; they are not three independent external evaluators. Container launches are a deterministic work proxy, not total CPU, dollar cost or statistically proven wall-time savings.

Production behavior and protected evaluator files are unchanged. Local full suite: 153 tests, 145 passed, eight Docker-dependent skips. Project checks passed without warnings.

## Research connection

Agent Plasticity (submitted October 6, 2026): https://arxiv.org/abs/2610.08902. Its empirical protocol measures persistent artifact learning on held-out interactions and acquisition cost; artifact reuse can be a bottleneck. This study applies that measurement principle to a bounded symbolic controller, not a reproduction of its model or game results.

EvalResearchBench (submitted October 3, 2026): https://arxiv.org/abs/2610.04184; implementation https://github.com/Mercury7353/self-evaluation-bench. Learned evaluator design achieved about 75% pairwise agreement with targets; development winners did not necessarily win on sealed targets. Future proxy-screening experiments must compare against a simple public-task baseline and evaluate a frozen proxy on sealed faults; promotion still requires the protected verifier.

## Next acceptance tests

1. Compare reuse with the existing supplied-scaffold adapter at predeclared equal budgets and withheld task rules; require a positive held-out capability/cost effect in three replications and no retention regression.
2. If introducing cheap evaluation screening, freeze its decision rule before sealed evaluation. Require lower end-to-end cost, no missed designated incorrect programs, and unchanged full certification for promotions.
