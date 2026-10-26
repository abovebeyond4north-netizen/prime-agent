# Frozen one-bit to word-transfer experiment — October 26, 2026

This protocol is committed before Docker holdout outcomes are inspected. The new domain is bitwise operations over bounded integer words, rather than inverse-polynomial arithmetic. A trusted public-only learner receives four `(a,b,width,output)` observations with width=1, not a task ID, truth-table identifier, oracle callable or protected cases. It infers coefficients of the algebraic normal form `constant XOR a XOR b XOR (a AND b)` and emits a masked integer program. The Boolean basis, compiler, word-homogeneity assumption and width ceiling are developer-supplied. No pretrained model or paid API is used.

Development uses truth tables 6 (XOR) and 8 (AND); the other 14 of the 16 possible two-input truth tables form a complete disjoint rule holdout. This is rule holdout inside an explicitly new but finite internal domain, not external transfer or evidence of arbitrary-function identification. All arms receive the same four public observations. All proposals are frozen before protected evaluation. The current inverse-polynomial learner is not a baseline for this domain: its contract does not support it. The baseline is a new four-example lookup control; the mechanistic ablation omits the interaction term and abstains when the public table requires one.

Every emitted program faces the unchanged ten-gate Docker verifier, including fresh unseeded 2–32-bit holdouts, differential checks and 256-bit performance/boundary checks. Passing programs receive another 128 seeded shifted cases across widths 2–256. The evaluator computes answers one bit at a time via the hidden truth table, independently of the learner's normal-form construction. Ceiling: four training labels and 20 containers per arm/task. Ablation abstentions count as unsolved, not cheap successes. No retries, source revisions, promotions or protected-feedback updates are allowed. The two shards rotate execution order; they are not independent replications.

Each shard also runs a negative control that matches every one-bit public example of XOR but complements outputs for wider words. Protected checks must reject it; public agreement alone must not certify the word-homogeneity assumption. Its cost is reported separately.

Accept bounded transfer only if the compositional learner certifies all 14 holdout rules, loses no baseline/ablation success, rejects no required safety boundary and passes every additional audit. Report exact paired discordances against both controls, all container costs and the limitations. At 14 paired rules, predeclare a one-sided exact sign test on discordant pairs, Holm-corrected across the two comparisons at familywise 0.05. No accuracy claim beyond the enumerated rule family or statistical latency claim is allowed. Persistent deployment/rollback of these new skills remains a subsequent milestone; existing production behavior is untouched.

## Verified Docker outcome

Code `d9c4f78889ee2eedf3e2b0aed0f24ad6164bc0cb` passed both [Docker shards](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/40270360658). The compositional learner certified 14/14 held-out truth tables; the no-interaction ablation certified 7/14, abstaining on the other seven; the lookup control certified 1/14 (the constant-zero rule). No baseline or ablation success was lost. Every compositional candidate passed all ten gates and 128 additional 2–256-bit audit cases, totaling 1,792 additional checks. Both repeated width-dependent negative controls passed their public examples but were rejected at gate 5.

| Arm | Certified rules | Actual containers | Additional audit cases |
| --- | --- | --- | --- |
| Compositional | 14/14 | 224 | 1,792 |
| No interaction | 7/14 | 112 | 896 |
| Lookup only | 1/14 | 55 | 128 |

The two negative controls added six containers, for 397 total study containers, excluding image builds and unit-test infrastructure. Each rule supplies four public labels shared across the three arms: 56 holdout labels plus eight for the two repeated negative controls. Higher capability consumes more actual verification work than controls that fail or abstain early; there is no total-cost efficiency win claim.

Paired discordances are 13 wins / 0 losses versus lookup and 7 wins / 0 losses versus no interaction. Predeclared one-sided exact sign-test values are 0.0001220703125 and 0.0078125; Holm-adjusted values are 0.000244140625 and 0.0078125. These calculations are conditional on exchangeable discordance signs, not a warrant for extrapolation beyond this complete finite truth-table family. The exact rule counts and independently implemented bit-by-bit checks are the main evidence.

Full proposals, reports, costs, image IDs, learner digest and artifact hashes are committed in `boolean_transfer_results.json`. All 205 local tests completed: 192 passed and 13 Docker-dependent tests skipped. Repository checks passed without warnings under npm 11.10.1.

This is a new bounded research-domain capability supplied by a developer-added learner/compiler, not autonomous invention of Boolean algebra, self-generated primitives, persistent production deployment or open-world intelligence. Four one-bit observations encode the entire two-input truth table; transfer to words is conditional on the supplied bitwise-homogeneity hypothesis, which protected evaluation can falsify but finite testing cannot universally prove. The old inverse-polynomial control is unchanged and is not counted as a competing baseline here.

The [full laboratory regression on the same code commit](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/40270364367) passed, including real sandbox/controller checks, promotion, autonomous goals, transfer/evolution smoke tests and compound-skill reuse after restart. PR #81 remains draft, with the frozen control branch and production defaults unchanged.
