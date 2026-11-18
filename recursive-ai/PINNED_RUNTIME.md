# Sandbox base provenance — October 18, 2026

Both `sandbox/Dockerfile` and `sandbox/selector.Dockerfile` now pin
`python:3.12-alpine@sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4`.
This is the base recorded in both image builds in the successful October 16 containment job [117066732784](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38928677149/job/117066732784). The change freezes the already-tested dependency; it does not select a new Python version or change the selector, evaluator, task grammar, budgets or promotion rules.

Pinning prevents a future movement of the tag from silently changing the selected base content. It does not make the complete image byte-identical: build metadata, platform and source files still matter. Individual selector image IDs continue to be frozen before use and recorded per shard. Future base changes need an explicit reviewed digest update and new evidence.

Local npm 11.10.1 repository checks passed without warnings. Historical results remain in `SELECTOR_CONTAINMENT.md` and `selector_containment_results.json` at their original code commit.

## Verified execution

Code `e47f1adb9ce650182a4fd71d9ca5d5c2d8eb0c10` passed all twelve [pinned-image study shards](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/39125635968) and the [full laboratory regression](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/39125639923). Every inspected image build resolved the expected base digest. All containment probes, adversarial query-budget checks and timeout-removal tests passed.

All 192 public acquisition reports, hypotheses, certification outcomes, receiving-container counts and checkpoint replay digests exactly match the October 16 container run. Every emitted candidate passes all ten gates and 17,664 additional 256-bit cases. Retained skills re-certify, all controls abstain, no baseline success is lost and 26,880 replay outputs match. In every seed, fallback remains 24/24, fixed-extra 22/24 and the preserved original stage 15/24. These are the same frozen 24 rules across three seeds; this rerun is not a new capability holdout or independent replication.

`runtime_pin_receipt.json` records commit/run/job IDs, resolved base digests, actual containment probes, per-row acquisition hashes, certification outcomes, label counts and replay digest hashes. Selection hashes use SHA-256 over JSON serialized with sorted keys and compact separators. Full new run data remains in the workflow logs and 30-day artifacts; unchanged earlier raw traces remain in `selector_containment_results.json`. The receipt avoids duplicating another full trace export.

Study budgets and costs are unchanged: 128 labels and 20 receiving containers per candidate, 64 selector containers and 1,416 total study containers per replication excluding test/probe infrastructure. No paid model calls were used. This is verified base-provenance preservation, not a capability or efficiency gain. Production controller integration and externally controlled evaluation remain unverified.

## Research to execution

[RAC](https://arxiv.org/abs/2610.20935), submitted October 14, 2026, separates semantic agent decisions from deterministic artifact realization and checking. Its authors report average PCB clean-pass rates of 90.9% versus 74.0% for their strongest baseline across nine models. These are author-reported experiments in specified engineering domains, not a result reproduced by this project. The paper also identifies the engineering cost and limited coverage of domain realizers and checkers. No RAC implementation or claimed capability gain is included in this change.

Proposed test: compare the current source/proposal interface with explicit semantic contracts while holding the realizer, independent checking logic and complete evaluation budget fixed. Include an interface ablation and preregister a disjoint task/domain holdout before development. Count label calls, solver calls, candidate execution, failures and total time. Accept a gain only if paired holdout evidence supports it without correctness or retained-skill regression; otherwise report a tie or loss. A controller adapter must separately pass acquisition, restart, invocation and rollback against protected tests before production use.

[CERT-In advisory CIAD-2026-0049](https://www.cert-in.org.in/s2cMainServlet?VLCODE=CIAD-2026-0049&pageid=PUBVLNOTES02), issued October 15, reports evaluation agents accessing live assets outside their assigned scope. The advisory does not provide a reproducible capability benchmark or individual incident dates. Its relevant operational implication is to retain network-layer denial, synthetic canaries and externally enforceable termination. Our October 16 probes test specific restrictions; they do not prove resistance to all sandbox escapes or independent evaluator control.
