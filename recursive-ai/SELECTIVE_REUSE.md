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
