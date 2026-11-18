# Empty-state procedure learning versus supplied adapter

Executed October 14, 2026 at 16e82059f36c8ab26f0a80dfbc19073467758695.
Docker run: https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38561139891

All three runs (seeds 230006, 230007, 230008) completed from separate empty states with predeclared equal budgets: 16 attempts, 160 container launches, 600 seconds and zero model calls.

| Per arm, per run | Learned procedure | Supplied adapter |
| --- | ---: | ---: |
| Acquisition containers, including final audit | 116 | 99 |
| Attempts | 7 | 7 |
| Certified task/tier contracts | 6 | 6 |
| Persisted procedure models | 4 | 0 |

The supplied adapter used 17 fewer containers. Both arms produced identical normalized candidate source maps and passed fresh final audits. Across the paired runs, 18,432 final-audit cases passed. Separate seeded checks passed 3,072 additional 64-bit cases with exact integer boundary postconditions. That additional validation used 17 containers per arm and is reported separately from acquisition cost.

Both arms start empty and use the same goal, budgets, default learned operator policy, protected verifier and disabled regression cache. Only learn_inverse_procedure differs. The final goal includes lower-bound search, integer square root and triangular inversion at tiers 1 and 2. Arms run in alternating order. Extra shifted seeds are not used for selection.

This closes the previously unmeasured cold-start comparator. The 38.6% continuation saving against forced rediscovery remains valid; it is not a saving over the existing supplied adapter. The earlier scaffold study tied continuation cost. Empty-state acquisition shows a 17-container disadvantage on these supported families.

Source mechanisms, default flags, evaluation gates and promotion/rollback implementation remain unchanged. This is new verification code and evidence, not a new production capability. Local full suite: 158 tests, 150 passed, eight Docker-dependent skips. Project checks passed without warnings.

Limitations: same designed task families and evaluator; three seeds share an operator/environment class. Normalized source equality concerns AST structure, not raw source text. Container count is a work proxy, not a CPU, wall-time or monetary comparison. No open-world or independent external evaluator claim.

## Consequential research reviewed

MASS: paper submitted October 8, official release October 12, 2026.
https://arxiv.org/abs/2610.12176
https://sakana.ai/mass/
https://github.com/SakanaAI/mass

MASS alternates workflow evolution and supervised fine-tuning on team trajectories using Qwen3.6-27B. Authors report 1.2–1.6x score per output token on four research benchmarks after two cycles, but coding pass rates declined in their table: Terminal-Bench 0.375→0.352 and SWE-bench Verified 0.626→0.611. The available implementation omits some reported benchmark adapters; actual search/training requires model serving and GPU allocation. We did not execute or adopt its full pipeline.

A possible no-training adaptation is to compare fixed and searched execution plans, with feedback-selection ablation, at equal total work budgets. Freeze plans before a sealed task panel; accept only replicated success/cost improvement with no retention regression and successful rollback. Self-judgment must not replace certification.
