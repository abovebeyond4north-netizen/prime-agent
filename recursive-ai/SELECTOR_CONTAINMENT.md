# Containerized public-query selector — October 16, 2026

The research fallback now explicitly selects a Docker transport for public-query acquisition. The prior process transport remains available for trusted-code regression tests; missing Docker never silently switches a requested container run to the host.

## Authority boundary

`sandbox/selector.Dockerfile` copies exactly four public-only modules: `mixed_inference.py`, `public_queries.py`, `query_fallback.py` and `oracle_process.py`. Inference was moved out of the task/evaluator module without changing its interface or search logic. Neither the task implementations, protected evaluator, test fixtures, research results, skill memory nor checkpoint state is copied or mounted into the selector. The parent keeps the public label callback and certification authority. JSONL carries integer queries, public integer labels and an acquisition report; reports are proposals, never certificates.

The container uses no network or host mounts, a read-only root, UID/GID 65534, no Linux capabilities, no-new-privileges, Docker's default seccomp, one CPU, 128 MiB memory with no swap, 16 processes, 64 file descriptors and a 4 MiB temporary filesystem. The parent still validates inputs/labels, caps calls at 128, bounds messages and checks its transcript. A deadline or protocol failure kills the Docker client and forcibly removes the named container; uncertain cleanup is reported as a failure. The trusted label callback must return promptly because its execution is not interrupted by the selector deadline.

CI resolves the locally built selector image to its immutable image ID before testing or acquisition and records that identity per shard. The base Python image tag is not pinned to a registry digest, so future builds are not claimed to reproduce identical image bytes. This is standard Docker containment, not proof against kernel/container-runtime exploits or an independently operated evaluator.

## Acceptance protocol

Local suite: 182 tests, 170 passed and 12 Docker-dependent skips; npm 11.10.1 repository checks passed without warnings. Six added tests cover admission/command validation plus actual Docker containment, exact policy parity, adversarial query exhaustion and timeout cleanup. Docker-specific outcomes require CI execution.

The access probe creates a real host-side protected-file canary, attempts to read that exact path from the selector, tries external networking, checks for the inherited-secret canary and Docker socket, and inspects the actual root mount, UID, network interfaces, Linux process restrictions and cgroup limits. A separate malicious worker requests 129 labels; only 128 may reach the parent callback. A stalled worker must be removed after the deadline. The tests also compare complete acquisition reports for unique and ambiguous cases against the existing in-process policy.

The unchanged 12-shard study reruns both policies over the same 24 frozen rules and repeated out-of-grammar controls across three seeds. Acceptance requires exact public-transcript, hypothesis, certification and replay parity with the prior run, all ten certification gates, retained skills and all baseline-preservation checks. This is an integration and containment experiment, not a fresh capability holdout.

## Verified execution

Code `09dc6826c7a95b78cb7ab1cf9d8c6d6de9295770` passed all twelve [container study shards](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38928677149), the [full laboratory regression](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38928686843), the earlier [mixed-feature study](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38928677244) and [public-query study](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38928677293). Raw study results, per-shard image IDs and all twelve actual containment probe reports are in `selector_containment_results.json`.

Every access probe passed: protected-file access and external connection attempts failed, only loopback networking was present, inherited-secret and Docker-socket canaries were absent, and actual UID, read-only mount, seccomp, capabilities, no-new-privileges and cgroup limits matched the contract. The adversarial 129-query worker reached the label callback exactly 128 times. The stalled worker was terminated and its named container was confirmed absent. All six selector admission/containment tests passed in each shard.

| Seed | Original-stage certifications | Fixed-extra certifications | Fallback certifications | Fixed-extra labels including controls | Fallback labels including controls |
| --- | --- | --- | --- | --- | --- |
| 920022 | 15/24 | 22/24 | 24/24 | 2,408 | 2,174 |
| 920023 | 15/24 | 22/24 | 24/24 | 2,408 | 2,129 |
| 920024 | 15/24 | 22/24 | 24/24 | 2,408 | 2,152 |

All 192 acquisition reports, public transcripts, hypotheses, certification outcomes, receiving-container counts and checkpoint replay output digests exactly match the prior process run at `565959d2afc541de30c73912209d18207e36e7d5`. All ten gates, 17,664 additional 256-bit cases, 26,880 replay outputs, retained-skill certifications and baseline-preservation assertions pass. Out-of-grammar controls abstain in every arm and shard. Original-stage counts reuse certification of identical preserved programs in both arms; no third baseline execution was introduced.

This establishes tested Docker containment and preservation of the existing bounded capability gain. It does not establish broader task capability, independent verification or resistance to every possible sandbox escape.

## Cost and remaining scope

Each of the 16 acquisition sessions per shard now uses one additional selector container. Across four shards this adds 64 containers to the earlier 1,352 per replication: 1,416 study containers, excluding test/probe infrastructure. Query and candidate-certification budgets remain unchanged. Selector wall-time/CPU overhead is not separately benchmarked; no lower-total-cost claim is made.

Production integration remains separate: define a supported task/skill contract, then verify real controller acquisition, invocation, restart and rollback. Independent evaluation, external transfer, autonomous grammar invention and real-world recovery remain unverified.
