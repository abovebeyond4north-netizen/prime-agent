# Frozen controller-interface experiment — October 26, 2026

This protocol and its implementation are committed before the first Docker outcome is inspected. Sampling seed 1030026 fixes six unfiltered rules from the existing mixed-polynomial universe, excluding the two earlier six-rule studies, both 24-rule studies, mixed-feature/lifecycle fixtures and skill-contract fixtures. Two disjoint three-rule shards each include the same degree-5 negative control. This is a disjoint-rule internal holdout, not a domain holdout.

## Arms and acceptance

Each task starts from an empty dedicated state. Direct calls use the unchanged `research.skill_contract` service; controller calls use its opt-in API. The no-reuse ablation uses the controller but reacquires into a fresh state on the second request. No checkpoints are deleted. The same frozen construction configuration, task seed, selector, verifier and ceilings (128 labels, 128 containers, 180 seconds per acquisition) apply to all arms. Failed certification cannot trigger a retry. Only already-certified tasks receive a repeat request.

Primary acceptance is exact direct/controller parity in certification status, complete public transcripts/hypotheses, ten gates, reconstructed-source digest, labels and container counts. Every certified skill must also pass fresh-process invocation before and after the repeat request, checked with exact floor inequalities at a 255-bit input. Degree-5 controls must not certify. All service certifications retain their existing 128-case 256-bit audit.

The ablation asks only whether persistent reuse avoids repeated acquisition work without changing exact output. Acceptance requires cached repeats to consume zero labels/containers and cold repeats to reproduce initial semantics. Initial acquisition, repeated acquisition and invocation costs are reported separately; per-task empty state intentionally excludes cross-task retention from this experiment. Existing lifecycle tests cover retention and rollback.

No wrapper capability improvement is expected or claimed. A tie is a valid result. Total observed host wall time is descriptive; no speed significance is asserted. Generalization remains limited to this finite internal grammar. Future capability-gain experiments require a genuinely changed learner, preregistered new domain, unchanged-harness baseline, method ablation, all costs and supported paired holdout effects without correctness or retention regression.

## Executed outcome

Code `24bb90b184155d351d037f40cbfc49a48073daaa` passed both Docker shards in [run 40267709797](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/40267709797). Each arm certified 6/6 new in-grammar rules and abstained on the repeated degree-5 control. Direct/controller signatures matched exactly, including all public query traces, hypotheses, gates, source digests and label/container costs. Initial labels per accepted task ranged from 64 to 73, below the 128 ceiling; each cost 17 containers.

On six repeat requests, direct and controller arms each used zero labels and zero acquisition containers; the no-reuse arm consumed another 410 labels and 102 containers. All 36 fresh-process invocation checks passed exact-integer inequalities with unchanged repeated outputs. There were 3,072 executed 256-bit audit checks across 24 successful acquisitions; these reuse the same 128 seeded cases per rule in the matched arms and are not 3,072 independent test instances. Total study cost was 2,024 labels and 486 containers including invocations, excluding image builds and unit-test infrastructure. Full raw reports and Git/SQLite state, including hidden Git objects, are in the two 30-day workflow artifacts. The committed summary is `contract_comparison_results.json`.

Result: interface parity and measured repeated-request savings from persistent caching, not a capability gain attributable to the wrapper. Local verification: 199 tests, 186 passed and 13 Docker-dependent skips; repository checks passed without warnings using npm 11.10.1. The control branch and production defaults remain unchanged.

The [full laboratory regression at the same code commit](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/40267714744) also passed, including actual sandbox tests, promotion, autonomous goals/invocation, transfer and evolution smoke tests, and compound-skill reuse after restart. This does not turn the internal holdout into independently operated replication.
