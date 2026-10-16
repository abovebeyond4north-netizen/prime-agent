# Bounded mixed-feature extension — October 15, 2026

## Verified result

Code: `9f56c1e90e6608db1a70d8af365b80c501b21341`.
Three Docker replications passed in [run 38731949342](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38731949342), with seeds 330010, 330011 and 330012. Raw reports, emitted sources, public examples and inference counts are in `mixed_feature_results.json`.

The research grammar adds one quadratic term: `p*k**degree + r*k*k + q*k <= d*n`, with degree 3 or 4, normalized bounded integer coefficients, and positive leading/quadratic coefficients. It enumerates both degrees before deciding uniqueness. Ambiguous public evidence produces no candidate.

| Rule (degree, p, r, q, d) | Frozen grammar | Extended grammar, each seed |
| --- | --- | --- |
| (3, 1, 1, 0, 1) | No fit | Ten gates passed; 30 containers |
| (3, 1, 1, 1, 2) | No fit | Ten gates passed; 30 containers |
| (4, 1, 1, 2, 3) | No fit | Ten gates passed; 30 containers |

Each candidate also passed 512 seeded 256-bit input checks and exact floor-boundary inequalities: 4,608 additional checks across nine trials. The unchanged verifier uses a separate bit-construction oracle; candidate code uses bisection. Each receiving trial has a predeclared 40-container ceiling. Its 30 containers include the additional checks. Shared donor/model acquisition costs 42 containers per replication, excluded from the receiving-task count. No paid model calls were used.

## What this does not establish

- This is a developer-written feature expansion, not autonomous discovery of a grammar production. Selection of coefficients and degree uses public labels only; the search procedure configuration is frozen before target rules.
- Fixtures were selected for identifiability from the fixed public inputs. An earlier ambiguous fixture was rejected, not resolved using protected evidence. These are diagnostic fixtures, not a representative success-rate sample.
- The frozen grammar has the same resource ceiling but emits no candidate and consumes no sandbox containers. This is a representation ablation, not an equal-consumed-compute efficiency comparison.
- A supplied correct mixed-feature scaffold could solve these tasks too; no advantage over that comparator was measured. The prior cold-start cost disadvantage remains valid.
- The extended grammar is research-only. Production defaults, evaluator, promotion, persistent model schema and rollback are unchanged; no new skill was promoted. Evaluator, operator and environment remain internally controlled.

Local validation: 160 tests, 152 passed and eight Docker-dependent skips; `npm run check` passed without warnings using npm 11.10.1. CI separately executes the sandbox study.

## Highest-value next acceptance test

Before enabling this extension, test persistent acquisition and restart/reuse against a supplied mixed-feature scaffold and the frozen grammar at matched predeclared budgets. Use new identifiable rules, untouched seeded audits, all prior task regressions and a rollback-to-known-checkpoint replay. Require correct holdout results, retained prior contracts, verified restart/rollback and full cost accounting. Do not infer an efficiency win from greater representational coverage alone.

## Newly reviewed upstream release

[Prime Intellect shipped and published its Rust rewrite October 9](https://www.primeintellect.ai/blog/prime-agent-rust). Its validation separates terminal, transcript/provider-request and daemon-protocol parity; scripted runtime benchmarks exclude inference. The authors also report bugs outside exercised parity flows. This suggests a parity gate for any future runtime migration, not a reason to migrate this branch now. No Rust migration or independent reproduction of upstream performance was performed here.
