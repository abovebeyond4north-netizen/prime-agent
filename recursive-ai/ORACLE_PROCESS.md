# Public selector process interface — October 16, 2026

The fallback selector now runs in a fresh Python subprocess. The parent retains the public label callback and all task/evaluator objects; only integer queries, public integer labels and the final acquisition report cross JSONL pipes. The child starts in a temporary working directory with an explicit source path and no inherited environment variables. This is an opt-in research harness change; the production controller, registry and promotion policy are unchanged.

The parent independently validates nonnegative inputs of at most 256 bits and integer labels in `0..n`, enforces 128 calls, bounds message size to 64 KiB, and matches the reported examples/query count against its actual transcript. Unknown message shapes, invalid labels, budget exhaustion, malformed results, worker failure and selector deadlines terminate acquisition. The default selector deadline is 30 seconds. The label callback remains trusted and must return promptly; the deadline does not interrupt a blocked callback.

The worker is trusted repository code, **not an OS sandbox**. It retains the user's filesystem permissions and could read files or make network calls if modified. This change prevents direct evaluator-object sharing and accidental inherited environment secrets; it does not prove adversarial isolation or independent evaluation. Candidate code still executes only in the existing Docker sandbox, and only the unchanged ten gates can certify it. A query result alone is never a certificate.

## Acceptance

Local validation passed: 176 tests, 168 passed and eight Docker-dependent skips; npm 11.10.1 repository checks passed without warnings. Six new tests verify full-report parity with in-process acquisition on the frozen 24-rule sample plus two out-of-grammar controls, both policies, and seed 920022; independent parent query limits; invalid requests; false transcripts; failure/deadline cleanup; and environment-secret stripping. The parity sample is an integration regression, not a new capability holdout.

Code `565959d2afc541de30c73912209d18207e36e7d5` passed all twelve [Docker study shards](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38926392393) and the [full laboratory regression](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38926402597). New raw evidence is in `oracle_process_results.json`. The earlier `fallback_results.json` and `QUERY_FALLBACK.md` remain historical evidence for the earlier in-process code.

| Seed | Original-stage certifications | Fixed-extra certifications | Fallback certifications | Fixed-extra labels including controls | Fallback labels including controls |
| --- | --- | --- | --- | --- | --- |
| 920022 | 15/24 | 22/24 | 24/24 | 2,408 | 2,174 |
| 920023 | 15/24 | 22/24 | 24/24 | 2,408 | 2,129 |
| 920024 | 15/24 | 22/24 | 24/24 | 2,408 | 2,152 |

All 192 acquisition reports, including public transcripts and hypotheses, exactly match the prior in-process results at `61043aa7126b3021597c255f3cbd70a67bcc72b4`. Certification outcomes, receiving-container counts and all restart/rollback/restoration output digests also match. Every emitted candidate passes ten gates and 128 additional 256-bit checks: 17,664 additional cases total. All controls abstain, both retained skills re-certify, all baseline-preservation assertions pass, and 26,880 replay outputs match. Original-stage counts reuse actual certification of identical preserved programs in both arms; no third baseline arm was executed.

The subprocess interface preserves the earlier bounded coverage improvement; this rerun is not a fresh sample or a new capability gain. Container and label costs are unchanged: 1,352 containers per replication, including shared training, both comparison arms, retention and replay. Each acquisition additionally starts one Python subprocess; its wall-time/CPU overhead has not been separately benchmarked. No paid model calls were used. The full laboratory run also passed promotion, autonomous completion, transfer, both evolution smoke tests and compound-skill reuse after restart.

## Remaining acceptance

Before running a modifiable or untrusted selector, use a separate container or principal with no evaluator-state mounts, credentials or network access, retain the parent-owned label budget, and demonstrate denied attempts to access protected files. Before production integration, define a supported task/skill contract and verify real controller acquisition, restart, invocation and rollback. Broader task capability, independent replication and external transfer remain unverified.
