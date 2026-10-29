# Early recognition: verified internal improvement

2026-10-26. Diagnosis after failed macro transfer: a matching successor could
remain queued while unrelated expansions consumed the remaining budget. Search
then returned exhausted despite having already evaluated a successful candidate.
The opt-in `eager=True` path returns immediately when a successor matches public
examples. Default behavior remains unchanged for reproducibility. No macro is
used in this comparison; this is a developer-written correction, not invention.

## Fresh evaluation

72 functions: multipliers -128, -64, 128 with offsets -12..11. These are disjoint
from both prior composition sweeps and training. Budget is 10,000 primitive
evaluations per task per arm. Three repetitions alternate arm order. Every
returned program passes independent symbolic affine-coefficient certification.

| Arm | Solved | Primitive evaluations |
| --- | ---: | ---: |
| Frozen behavior | 40/72 | 561,816 |
| Early recognition | 61/72 | 404,373 |

All repetitions agree: 21 additional successes, no baseline successes lost,
28.02% fewer primitive evaluations. Baseline search times: 177.44, 173.97,
162.86 ms; corrected: 129.34, 130.11, 117.04 ms. Timing excludes certificates
and report generation; short same-process measurements are not portable speed
guarantees. No training/compression overhead applies to either arm here.

Nine search unit tests pass, including exact-budget success and a 105-condition
development comparison across tasks and budgets. Raw per-task programs, costs,
timings and implementation digest are in `eager_validation_results.json`.

Acceptance required strictly higher coverage, lower evaluation cost and no lost
baseline tasks in all repetitions; it passed. This remains internally controlled
evaluation in a supplied finite DSL, not independent replication, open-world
learning or autonomous invention. Production defaults and prior failed evidence
are preserved. Eleven tasks still exceed the budget; no blanket completion claim.

Until the first public match, traversal and charged evaluation work are identical
with or without early recognition. Thus this change cannot spend more primitive
evaluations to recognize a public match; that does not prove public matches
generalize outside this affine language. Protected evaluation remains necessary.
