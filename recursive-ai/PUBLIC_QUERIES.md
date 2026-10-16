# Public boundary queries — October 16, 2026

Code: `72c5cdafce9f3402769886233127b5434ee27fa4`.
Three real Docker replications passed in [run 38915268147](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38915268147), seeds 720016, 720017 and 720018. Raw public-query traces, gate reports, checkpoint identities, output digests and costs are in `public_query_results.json`. Git/SQLite checkpoint artifacts are retained by the workflow for 30 days.

## Verified gain and ablation

| Policy | Certified sampled in-grammar rules, each run | Out-of-grammar controls | Prediction scoring lookups, each run |
| --- | --- | --- | --- |
| Original fixed examples | 3 / 6 | Both rejected | 0 |
| Random boundary queries | 6 / 6 | Both rejected | 0 |
| Scored boundary queries | 6 / 6 | Both rejected | 463,478 |

The fixed policy abstains on three ambiguous rules. Both boundary policies resolve them and all emitted candidates pass the ten unchanged certification gates plus 128 additional fresh 256-bit cases each. Across policies and runs, 5,760 additional cases pass, with exact floor inequalities also checked. No rejected/ambiguous target is removed from the result denominator.

This is a bounded coverage gain from better public example acquisition. The evidence supports the simpler random-boundary method in this study: scoring adds no certified coverage. Zero scoring lookups does not mean zero computation; both boundary methods enumerate possible rules, construct boundary pools and filter hypotheses.

## Frozen design and information boundary

- The developer-defined grammar is unchanged: `p*k**degree + r*k*k + q*k <= d*n`, degree 3/4 and bounded normalized coefficients. A public oracle returns only labels at learner-requested inputs. Neither protected examples nor target coefficients enter query selection.
- Public-only development used sampling seed 620016. A coarse query pool failed to resolve two development ambiguities. The final selector includes exact thresholds of surviving hypotheses at roots 1..16. No protected tests were used for that revision.
- Before Docker execution, the code froze a separate sampling seed, 620017, for six unfiltered in-grammar rules. Two declared out-of-grammar controls are also included. This small sampled test set differs from the development set; it is not an external task distribution.
- Fixed uses the existing 64-example sequence, including its repeated inputs. Random and scored methods share the first 16 inputs and the same dynamic boundary pool. Random chooses uniformly; scoring chooses the most balanced predicted output partition. All policies request exactly 64 labels per target.
- The prediction ceiling is 200,000 lookups per target. Each emitted candidate has a predeclared 20-container ceiling; actual certification plus additional audit uses 18. Shared donor/procedure acquisition costs 42 containers per replication. The procedure configuration and emitted-program grammar are unchanged.

## Cost, retention and lifecycle

Per replication, fixed uses 54 receiving containers; random and scored each use 108 because they certify three additional rules. Equal resource ceilings do not mean equal consumed work. This is not a claim of lower CPU, wall time, total containers or cost than fixed examples or a supplied correct solution.

Every arm also re-certifies the two earlier acquired skills through all ten gates (24 containers). Separate processes reconstruct persisted mixed programs without query acquisition or inference, execute fresh audits, switch the active Git/SQLite checkpoint back to the original two skills, then restore the extended checkpoint and reproduce all output digests. Lifecycle checks cost 15 containers for fixed and 21 for each boundary arm. Across arms/runs, 9,216 replay outputs pass. Total study consumption is 441 containers per replication. No paid model calls were used.

Local validation: 164 tests, 156 pass and eight Docker-dependent skips. Both new tests pass; npm 11.10.1 project checks pass without warnings. Broader laboratory regression is separately tracked at [run 38915275300](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38915275300); do not infer its conclusion from the study result.

## Limits and next work

These are three seeded replications on the same six test rules, with one operator/environment class and an internal evaluator. They do not establish population-wide significance, independent replication, new grammar invention or open-world intelligence. Boundary access and random choice change together relative to the fixed sequence; the scored-versus-random comparison isolates scoring within the shared dynamic pool, not all effects of active acquisition.

Random boundary querying is the preferred research mode on current evidence. No production defaults, controller, public-oracle contract or evaluator changed; nothing was automatically promoted. Next, test this frozen cheap policy on a larger separately sampled rule distribution, including no-fit/ambiguity outcomes and public-query cost, then expose it only through a bounded public-oracle interface with retained certification and checkpoint gates. Real distribution-shift rollback and independently controlled evaluation remain unmet.
