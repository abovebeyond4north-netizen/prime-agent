# Selective saved-composition reuse: frozen protocol

2026-10-26. `research.selective_reuse` adds a bounded backward planner over saved
affine macro certificates. For each public example set it derives the affine
target, reverses candidate suffix transformations, and checks any resulting
primitive program. It falls back to unchanged eager forward search if planning
fails or the expanded program exceeds the primitive-evaluation budget. No old
implementation, saved-state binding, production defaults or control branch change.

The primitive-evaluation allowance remains intact on fallback. Routing is not
free: symbolic states/edges and end-to-end wall time are reported separately.
This is not a guarantee of no wall-time regression at an equal wall deadline.
The batch holds a shared frozen library under its exclusive state lock, rechecks
all saved certificates once, and checks STOP between problems and before return.
Rollback/restoration changes the next batch's active library. This is a trusted
finite data interpreter, not arbitrary source generation.

## Pre-execution acceptance and ablations

The study is committed before the first evaluation run; local tests use only
development fixtures. Three same-process timing repetitions rotate four arms:

1. Eager primitive-only forward search.
2. Backward planning with primitives alone, then forward fallback (memory ablation).
3. Unconditional forward priority for the first saved macro (old policy control).
4. Selective backward planning over saved macros, then forward fallback.

Every task has caps of 10,000 primitive evaluations and 128 symbolic planner
states. Unused planner allowance is not traded for extra primitive evaluations.
Verification of a selected plan pays its expanded primitive count on every public
input. Setup/load/routing have wall cost, even when no primitive is evaluated.
All arms share public prevalidation. Memory arms are each charged the full cost
of training, compression and Git/SQLite storage, plus their own load/search time.
Generation and post-result correctness auditing are common excluded costs.

The fresh internal evaluation contains 30 explicitly composition-favoring tasks
(multipliers 1024, 2048, 4096 with ten near-all-ones offsets), 60 distinct random
primitive-program functions with absolute slope at least 1024, and three
unrepresentable affine controls. Random generation uses fixed seed 261026171.
These functions are disjoint from previous evaluations, but the environment and
generator are developer controlled, not an independently protected distribution.
Each returned program must pass the separate affine coefficient checker and five
large signed-integer audits; all per-task outcomes are retained in the artifact.

Primary acceptance: more solved tasks, no lost forward-baseline successes in all
three repetitions, and at least 10% lower median end-to-end wall time including
setup. Attribute a benefit to memory only if selective reuse also solves more
than primitive backward planning in every repetition and has lower median time.
Report cohort-specific results and negative findings even if acceptance fails.
Do not tune this policy using these evaluation outcomes; subsequent tuning needs
a new evaluation set. Three timing repetitions are not independent replications.

The affine model, inversion rules and planner are developer supplied. Any observed
gain is bounded compositional reuse, not autonomous invention or broad intelligence.

## Verified results, 2026-10-26

Frozen code `889015e2e9be39abb88e405a3315ddf53fed1041` passed the
[four-arm workflow](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/40283316654)
(35 lifecycle/routing/search tests plus the comparison) and the
[full Docker laboratory regression](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/40283323666)
(108 core tests plus promotion, autonomous goals, transfer, evolution and restart
smoke checks). Local full-suite verification before publication had 235 passes
and 13 Docker-dependent skips; repository checks passed with npm 11.10.1.

| Arm | Solved / 93 | Median end-to-end batch time |
| --- | ---: | ---: |
| Eager forward baseline | 0 | 421.67 ms |
| Primitive backward ablation | 0 | 430.64 ms |
| Unconditional macro priority | 0 | 395.00 ms |
| Selective saved-macro planning | 35 | 307.11 ms |

All three repetitions have identical coverage. Selective reuse solves 30/30
composition-favoring tasks, 5/60 random-program tasks and 0/3 unsupported controls.
All returned programs pass symbolic certification and five large signed-integer
audits each (525 repeated audit executions across the three repetitions). Median
batch time is 27.17% lower than forward search including training, compression,
storage, loading and routing. These are short, same-runner timing measurements,
not a portable speed guarantee or equal-wall-deadline comparison.

Selective search consumes 582,228 primitive evaluations, 1,066 planner states and
2,100 symbolic edges per repetition; library training adds 2,637 primitive
evaluations. The forward baseline consumes 929,907 primitive evaluations. These
different work types must not be treated as interchangeable unit costs.

The fresh set had zero baseline successes, so its no-lost-success condition alone
is vacuous. A separately labeled, post-hoc regression check used 244 previously
seen tasks without changing the policy: both arms solve 204, with no losses.
The task list, outcome, and exact runnable reproduction script are retained in
`selective_reuse_results.json`. This is retention evidence, not a fresh holdout.

The receipt also preserves the CI summary and artifact metadata. Full task-level
programs, timing rows and saved state are in the 70,500-byte artifact, expiring
2026-11-25. Its reported SHA-256 is
`08328c8a1a81293552bf0aab3385b7e9f54b0bf3e640e1d6aa9623249c8bb77b`;
the archive itself was not independently downloaded and hashed. The published
policy was not tuned after evaluation. PR #81 remains draft, production defaults
are unchanged, and the control branch remains at
`3466d1a7dc88262cb0f4f1c250d795ec43f33e55`.

Next gate: a new mixed-difficulty distribution with positive baseline successes,
matched end-to-end wall budgets, primitive-planning and no-memory ablations, and
an evaluator operated independently of development. Require no lost correctness,
count setup costs, and preserve per-cohort failures before proposing promotion.
