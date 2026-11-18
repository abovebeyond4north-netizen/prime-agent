# Mixed-feature matched scaffold and lifecycle — October 16, 2026

Code: `891103b7551cabf223a2442ad83e39766d0f9197`.
All three real Docker replications passed in [run 38897511989](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38897511989), seeds 430013, 430014 and 430015. Raw gate reports, checkpoint identities and output digests are in `mixed_lifecycle_results.json`. The workflow also uploads Git checkpoint stores and SQLite state for 30 days.

## Fixed comparison

New diagnostic rules `(degree,p,r,q,d)` are `(3,2,1,0,1)`, `(3,2,1,0,2)` and `(4,2,1,4,3)`, for `p*k**degree + r*k*k + q*k <= d*n`. They were selected for unique public identifiability before sandbox execution. Hypothesis selection sees only public input/output pairs. The previously learned procedure configuration is frozen before these rules. The supplied arm uses a correct developer-supplied configuration and does not need procedure acquisition. Arm order alternates by seed parity. The old grammar emits no fit on every rule; this is a representation ablation, not an equally consuming sandbox arm.

| Measurement | Learned configuration | Supplied configuration |
| --- | --- | --- |
| Receiving containers, each rule | 30 / predeclared ceiling 40 | 30 / predeclared ceiling 40 |
| Certification | All ten unchanged gates pass | All ten unchanged gates pass |
| Extra seeded 256-bit cases, each rule | 512 pass | 512 pass |
| Fresh-process lifecycle containers, each replication | 15 | 15 |
| Two prior skills re-certified, each replication | 24 containers | 24 containers |

All nine paired trials tie with identical normalized sources. Across 18 candidate trials, 9,216 additional 256-bit cases pass, each also checked against the exact floor inequalities. Shared donor/procedure acquisition costs 42 containers per replication. Including both arms, retention and lifecycle checks, each replication consumes 300 containers. Container counts are a work proxy, not a claim about wall time, CPU or dollars. No model calls were used.

## Fresh-process persistence and rollback

The harness uses the existing `VersionController` Git objects and `MemoryEngine` SQLite active pointer, with research-only manifests:

1. Save the two certified acquired skills as a base checkpoint, then the three certified mixed skills plus their inferred models as a child checkpoint.
2. Launch a separate Python process. Reopen the selected checkpoint; reconstruct each mixed source from its persisted hypothesis/configuration; execute 64 fresh audit inputs for each of five skills in Docker.
3. Switch the SQLite pointer back to the base. A second fresh process verifies exactly the original two skills remain and reproduce their output digests.
4. Restore the extended checkpoint. A third fresh process reproduces every initial replay digest without running inference or discovery.

The lifecycle replay totals 4,608 checked outputs across arms/replications. It is an explicit checkpoint switch in an internal test, **not** autonomous recovery under real-world distribution shift. A unit test additionally rejects model/source mismatch before candidate execution. Existing donor and training skills each pass full ten-gate re-certification after the lifecycle test.

Local suite: 162 tests, 154 pass and eight Docker-dependent skips. Both new tests pass. Project checks pass without warnings using npm 11.10.1. Broader laboratory regression is tracked separately at [run 38897517161](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38897517161); check its conclusion rather than inferring success from this study.

## Limits and next acceptance test

No production controller, model schema, evaluator, defaults or promotion policy changed. The new research manifests do not establish production integration. Three seeds share an operator and environment class. Rules and grammar remain developer-defined and the evaluator is not independently controlled. These findings do not overturn the earlier cold-start disadvantage or establish open-world intelligence.

Next, evaluate bounded public counterexample acquisition against fixed examples and random-query controls on a preregistered rule distribution, including ambiguous/no-fit outcomes rather than filtering them. Freeze selection before untouched audits; accept only higher certified coverage at matched query/container budgets with retained prior contracts and passing checkpoint replay. Independent operator/evaluator replication and real distribution-shift rollback remain separate unmet requirements.

## Consequential external development reviewed

[Anthropic's October 15 announcement](https://www.anthropic.com/news/an-update-on-independent-evaluators) says six METR staff have been onboarded with employee-like access. METR can publish without a veto, subject to narrow predefined redactions and the right to characterize those redactions. This is a reported operational access arrangement, not a new published capability evaluation or proof of safety. Its practical implication for this project is to require evaluator access and publication rights alongside a frozen reproducible artifact. This project has not obtained such an independent evaluator.
