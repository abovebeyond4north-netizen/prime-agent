# Inverse-edge pruning: mixed result, not promoted

2026-10-26. An optional `prune_inverse` switch avoids evaluating a single negate
immediately after negate: it returns an already visited predecessor. Defaults
remain unchanged, and the original eager-recognition experiment remains reproducible.

On 48 new tasks (multipliers -256, 256, 512; offsets -8..7), eager search and
pruned eager search both solve 19/48 at 10,000 primitive evaluations per task.
Every solution passes the independent affine coefficient certificate. No baseline
success is lost. Evaluation cost falls from 408,687 to 397,023 (2.85%), but local
search time rises from 129.08 ms to 133.49 ms. A single short timing trial does not
establish a reliable runtime difference; importantly, no runtime gain is claimed.
The previously evaluated 72-task set remains 61/72, leaving eleven unresolved.

Eleven search unit tests pass, including 27 development-task pruning comparisons.
This supplied algebraic identity is not autonomous invention. The option is not
enabled by default or integrated into production. Do not equate reduced counted
operations with higher practical efficiency. Raw task outcomes are retained in
`pruning_results.json`; reproduce with `python -m research.pruning_validation`.

Remaining work: budget-limited search, adaptive reuse without coverage losses,
persistent composition lifecycle and independently controlled evaluation.
Any follow-up tuning must treat these task sets as seen development data.
