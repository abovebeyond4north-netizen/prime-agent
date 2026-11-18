# Larger frozen boundary-query replication — October 16, 2026

Code: `8ac3cb8ac286b5ca565a73b25e7aecbf407a95c3`.
All 12 real Docker shards passed in [run 38918601781](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38918601781). The [full laboratory regression](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38918607611) also passed at that code commit. Raw query traces, gate reports, checkpoint identities, output digests and costs are in `query_scale_results.json`. The workflow uploads checkpoint stores and SQLite state for 30 days.

## Result: larger coverage gain, but one per-rule loss

| Seed | Fixed examples certified | Random boundary certified | Boundary-only successes | Fixed-only successes |
| --- | --- | --- | --- | --- |
| 820019 | 13 / 24 | 23 / 24 | 10 | 0 |
| 820020 | 13 / 24 | 23 / 24 | 11 | 1 |
| 820021 | 13 / 24 | 23 / 24 | 10 | 0 |

Every emitted candidate passed all ten unchanged gates and its additional 128 seeded 256-bit checks, including exact floor inequalities. Across the study, 13,824 additional cases passed. Both out-of-grammar controls were rejected by every policy, shard and seed. No ambiguous or failed task was filtered out.

One target remains ambiguous for the boundary policy in each run:

- Seed 820019: `(degree,p,r,q,d)=(4,4,4,0,3)`; fixed also abstains.
- Seed 820020: `(3,4,3,1,2)`; fixed succeeds. **This is a per-rule coverage loss despite the aggregate gain.**
- Seed 820021: `(4,3,1,4,4)`; fixed also abstains.

No method changes or targeted retries were made after these outcomes. This supports better aggregate coverage on this finite sample, not unconditional replacement of fixed examples. The earlier six-rule result does not establish that random boundary selection always dominates.

## Frozen sample and budgets

The query policy and grammar are unchanged from the preceding experiment. Sampling seed 620018 draws 24 rules uniformly without replacement after excluding both earlier six-rule query-study sets. Four disjoint shards each contain six sampled rules and repeat the same two declared out-of-grammar controls. The sample was not pre-screened for identifiability or success. Three new seeds vary random acquisition and shifted audits; they reuse the same 24 rules and are not 72 independent task draws.

Each policy requests exactly 64 public labels per target and has the same 20-container candidate ceiling. Public labels alone determine the inferred hypothesis; protected verification follows selection. Random mode makes zero scoring-prediction lookups but still constructs boundary pools and filters hypotheses. Successful candidates consume 18 containers each, including the additional audit. A supplied/frozen procedure configuration and existing generator are shared; the study does not measure autonomous grammar invention.

Each replication consumes 1,152 containers: receiving trials 648, repeated shared acquisition across four shards 168, retention 192, and lifecycle replay 144. Fixed receiving work is 234 containers versus 414 for boundary selection because more candidates are certified. These are equal ceilings, not equal consumed computation or a total-cost reduction. No paid model calls were used.

## Retention, persistence and regression

Every arm re-certifies its two earlier acquired skills through all ten gates. Fresh processes reconstruct persisted mixed models without rediscovery, replay the extended checkpoint, switch to the earlier two-skill checkpoint, restore the extension and reproduce all output digests. This yields 23,040 passing replay outputs across shards/seeds. It is an internal explicit checkpoint test, not autonomous recovery from real-world distribution shift.

Local validation: 166 tests, 158 passed and eight Docker-dependent skips; new partition/early-rejection tests passed; npm 11.10.1 repository checks passed without warnings. The full laboratory run separately passed promotion, autonomous completion, transfer, both evolution smoke tests and compound-skill reuse after restart.

## Decision and remaining gap

Keep the fixed policy available. Do not replace it unconditionally or enable this research path by default. The next candidate should preserve a successful fixed-example result and use boundary acquisition only after ambiguity, with any additional query allowance explicitly budgeted. Freeze that policy before evaluating a new disjoint sample; require no losses of fixed-policy successes, higher certified coverage, correct no-fit behavior, retained prior contracts and checkpoint replay. No such complementary policy is implemented or verified by this experiment.

The evaluator, grammar and operator remain internally controlled. These are same-environment-class replications; independent evaluation, external transfer, population-wide claims and real distribution-shift rollback remain unverified. No production controller, evaluator, defaults or promotion policy changed; no merge or automatic promotion was performed.
