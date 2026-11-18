# Baseline-preserving public-query fallback — October 16, 2026

Code: `61043aa7126b3021597c255f3cbd70a67bcc72b4`.
All twelve real Docker shards passed in [run 38920656555](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38920656555). The [full laboratory regression](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38920665162) also passed at that code commit. Raw public labels, acquisition traces, gate reports, checkpoint identities, output digests and costs are in `fallback_results.json`. Checkpoint and SQLite artifacts are uploaded for 30 days.

## Verified outcome

| Seed | Original 64-label stage | Fixed extra examples | Boundary fallback | Baseline successes lost |
| --- | --- | --- | --- | --- |
| 920022 | 15 / 24 | 22 / 24 | 24 / 24 | 0 |
| 920023 | 15 / 24 | 22 / 24 | 24 / 24 | 0 |
| 920024 | 15 / 24 | 22 / 24 | 24 / 24 | 0 |

All emitted candidates passed the ten unchanged certification gates and 128 additional seeded 256-bit cases each, including the exact floor inequalities: 17,664 additional cases across the study. Both declared out-of-grammar controls were rejected in every arm/shard/run. No ambiguity or failure was filtered away or retried after viewing protected outcomes.

The original baseline was not separately executed as a third arm. Its unique hypotheses and generated programs are returned unchanged by both comparison arms and receive their actual certification checks there. The 15/24 baseline count comes from those identical preserved programs. This is not an invented third benchmark run.

## What changed

Both policies first acquire the complete original 64 public examples. A unique hypothesis returns immediately, unchanged and without additional labels. A no-fit also returns immediately. Only ambiguity permits up to 64 more public labels:

- `extended_fixed` requests a fixed sequence of unused integers from 32 upward, up to 64 points, stopping on uniqueness.
- `boundary_fallback` randomly selects unused inputs from the existing pool plus exact thresholds of surviving hypotheses at roots 1..16, also stopping on uniqueness.

The comparison therefore controls for additional-label allowance. Both policies have a maximum of 128 labels and the same 20-container candidate ceiling. This is explicitly **not** the preceding 64-label-only comparison. All query choices finish before protected certification; failures cannot trigger further acquisition.

The new `PublicOracle` validates integer inputs/labels, restricts inputs to nonnegative 256-bit integers, counts requests and enforces the 128-call limit for this trusted research selector. It is a budgeted interface, not an independent evaluator or a new process-isolation boundary. The original inference API and protected gates are unchanged; supplemental hypotheses are filtered incrementally against all collected public labels.

A regression test covers the previously lost rule `(degree,p,r,q,d)=(3,4,3,1,2)`: both policies preserve the original unique hypothesis and use exactly 64 labels. Additional tests cover ambiguity budgets, invalid labels/inputs, hard query exhaustion and disjoint sample construction.

## Label and execution costs

| Seed | Fixed-extra target labels | Boundary-fallback target labels | Fixed-extra labels including repeated controls | Boundary labels including repeated controls |
| --- | --- | --- | --- | --- |
| 920022 | 1,896 | 1,662 | 2,408 | 2,174 |
| 920023 | 1,896 | 1,617 | 2,408 | 2,129 |
| 920024 | 1,896 | 1,640 | 2,408 | 2,152 |

The original 24-rule stage consumes 1,536 labels. Extra acquisition is therefore a real cost, not a free improvement. Across the three runs, boundary fallback consumes 4,919 in-grammar labels versus 5,688 for the fixed-extra control while certifying two additional rules per run. These are label counts, not CPU/time/dollar measurements.

Each emitted candidate consumes 18 receiving containers within its 20-container ceiling. Fixed-extra uses 396 receiving containers per replication; fallback uses 432 because it verifies two more programs. Four shared acquisition setups cost 168 containers, retention costs 192 and lifecycle replay costs 164, bringing total study consumption to 1,352 containers per replication. No paid model calls were used.

## Fresh sample, retained behavior and lifecycle

Sampling seed 620019 draws 24 unfiltered normalized rules after excluding all 36 earlier query-study development/test rules. Four disjoint shards each add the same two declared out-of-grammar controls. The policy was frozen before this sample's public outcomes or protected tests were inspected. Three new seeds vary random queries and shifted audits on the same 24 rules; they are not 72 independent rule samples.

The shared paired harness is reused through scoped substitutions of only its public rule supplier and acquisition function. Certification, retention, candidate generator and checkpoint replay are unchanged. Per-run assertions require every unique baseline to be preserved and every emitted candidate to pass. Each arm also re-certifies its two previously acquired skills.

Fresh processes reconstruct persisted models without rediscovery, replay the extension, switch back to the earlier checkpoint, then restore and reproduce all output digests: 26,880 replay outputs pass. This is explicit internal checkpoint switching, not autonomous recovery from real-world distribution shift.

Local validation: 170 tests, 162 passed and eight Docker-dependent skips; all four new tests passed; npm 11.10.1 repository checks passed without warnings. The full laboratory regression additionally passed promotion, autonomous completion, transfer, both evolution smoke tests and compound-skill reuse after restart.

## Scope and remaining work

This closes the observed per-rule-loss gap for the tested complementary policy while improving bounded coverage and label use relative to a fixed-extra control. It does not erase the earlier replacement policy's recorded loss. The method and finite grammar are developer-designed; the evaluator/operator remain internal. Independent replication, external transfer, general intelligence and genuine distribution-shift rollback remain unverified.

The fallback and budgeted oracle are research-only implementations. Production defaults, controller, task registry, evaluator and promotion policy are unchanged; no merge or automatic production promotion was performed. A production integration still needs an explicit public-oracle contract and authority separation. Any further optimization should retain this preservation guard and compare complete acquisition plus certification costs on new rules.
