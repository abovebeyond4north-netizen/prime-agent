# Opt-in contained skill contract — October 20, 2026

`research.skill_contract` is a bounded research service connecting public-query acquisition to certification, versioned persistence, invocation and explicit checkpoint activation. It is not wired into the production autonomous controller or its task registry; those defaults and the frozen control branch are unchanged.

## Supported contract and authority

The host supplies a data-only mixed-polynomial task descriptor, a trusted public-label callable and a frozen construction configuration. Only integer public queries/labels cross into the Docker selector; the task object, private evaluator, configuration, source construction, certification and persistence stay in the parent. The construction procedure is **caller supplied**, not learned by this adapter. This service does not invent a grammar or obtain an external task provider.

Task descriptors contain exactly `degree`, `p`, `r`, `q`, `d`; bounded degree-5/coefficient-5 cases are permitted as out-of-grammar diagnostics, but the existing selector still emits only its degree-3/4 bounded hypotheses. No arbitrary task code is accepted. Candidates execute only in the existing isolated runner.

State must use a dedicated directory. A format marker and versioned manifest envelope prevent accidental insertion of research keys into production state. Checkpoints bind the source/model reconstruction, source hash, current ten-gate certificate and a digest of adapter/evaluator/compiler/runtime dependencies. Stale or corrupted records fail closed before labels or candidate execution. This is integrity checking under a trusted host, not cryptographic authentication against a malicious host administrator.

## Lifecycle and budgets

`acquire()` uses one Docker selector with a 128-label ceiling. A unique hypothesis is constructed and must pass all ten existing gates within 20 receiving containers. Every existing skill then receives its own complete ten-gate retention check, avoiding the production registry's lack of research-key decoding. The new candidate also passes 128 additional seeded 256-bit cases before a Git checkpoint and SQLite activation transaction can be committed. Up to eight skills are supported; a call has at most 128 total containers including the selector and a bounded wall deadline. Operator-stop checks run during label service, candidate execution and before activation. The trusted callback must return promptly; its execution is not interrupted by the deadline.

A durable attempt reservation permits only one acquisition per task contract. Failed or ambiguous attempts cannot request a new batch after observing evaluator feedback. This is deliberately conservative: infrastructure failures also consume the reservation, and retry/migration requires a separately reviewed state/protocol decision. Successful repeat acquisition reconstructs and validates the persisted record without requesting labels or running containers.

`invoke()` honors the state's `STOP` file before opening state and during runner operations, reloads certified state, reconstructs its source, boots the isolated runner and checks the requested output against the trusted task oracle. `activate()` accepts only checkpoints registered by this state and validates their contents before switching the active pointer; explicit checkpoint recovery remains available while stopped. Rollback is an explicit internal checkpoint switch, not autonomous recovery under real-world distribution shift.

## API and CLI

After building the existing runner and public-only selector images:

```python
from research.skill_contract import acquire, task_contract

descriptor = {'degree': 4, 'p': 3, 'r': 3, 'q': 0, 'd': 1}
configuration = {'upper': 'n + 1', 'direction': 'forward', 'comparison': '<=', 'result': 'low - 1'}
task = task_contract(descriptor)
result = acquire('.contract-state', descriptor,
                 lambda n: task.expected([(n,)])[0], configuration, seed=920022)
print(result['checkpoint'])
```

This example deliberately uses an internal synthetic public provider; it is not external learning. `acquire()` takes a callable through the Python API, rather than loading provider code from an untrusted command-line path. Invocation is available in fresh processes:

```sh
python3 -m research.skill_contract invoke --state .contract-state --key research:mixed_inverse_4_3_3_0_1 --input 100
```

Explicit activation is also available through `activate(root, checkpoint)` and the module's `activate` CLI command. The checkpoint must already be registered in that state's checkpoint table; arbitrary Git objects cannot be activated through this interface.

## Verification scope

Local suite: 195 tests, 182 passed and 13 Docker-dependent skips. All twelve new non-Docker contract tests passed; npm 11.10.1 repository checks passed. Unit tests use an oracle fake and never execute candidate source on the host.

Code `d5c4b46fe33d07ee2e5870ac14e3469197d3a982` passed all three [Docker contract trials](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/39422368963) and the [full laboratory regression](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/39422376640). All nineteen selector/contract tests passed in each Docker trial, including the persisted-invocation STOP regression. Raw reports, exact large-integer invocation outputs, source image identities, checkpoint identities and containment probes are recorded in `skill_contract_results.json`; Git/SQLite state is also uploaded in 30-day workflow artifacts. The full laboratory run also passed its production controller, promotion, autonomous goal, transfer, evolution and compound-skill restart checks; these do not imply production integration of this separate adapter.

| Seed | Successful acquisitions | Labels including rejected provider | Service containers | Additional shifted cases | Fresh-process invocations |
| --- | --- | --- | --- | --- | --- |
| 920022 | 2 | 195 | 57 | 256 | 4 |
| 920023 | 2 | 194 | 57 | 256 | 4 |
| 920024 | 2 | 195 | 57 | 256 | 4 |

Every successful acquisition passed the ten unchanged gates and 128 additional 256-bit cases. The second acquisition re-certified the first skill through all ten gates. Repeated acquisition used zero labels and zero containers in every trial. Four fresh-process invocations per trial checked both skills, rollback removal of the second skill, retained access to the first, and restoration of the same output/checkpoint. The twelve original integer outputs at input `2**255-1` were locally rechecked against exact floor inequalities without lossy floating-point conversion.

A deliberately mismatched public provider failed real certification in every trial and returned the prior active checkpoint. A repeated attempt was rejected before calling its provider. Each Docker trial also set the real state's `STOP` file and verified that a fresh invocation process failed with an operator-stop error. Fault-injection unit tests separately cover retention/audit failure, activation rollback, stale adapters, source corruption, malformed gate lists, budgets and operator stop; these injected tests are not misreported as additional real-world failures.

Each trial's 57 service containers comprise 17 for the first acquisition, 29 for the second including retention, three for the rejected provider and eight for four invocations. Containment/adversarial probe tests use seven additional containers per trial. Neither figure is an efficiency comparison with the much larger earlier 24-rule study. No paid model calls were used.

The integration fixtures are two existing mixed-polynomial tasks and one deliberately mismatched public provider across three internal seeds. This is lifecycle/containment evidence, not a new capability distribution, equal-budget improvement comparison or independent replication. The supplied configuration, finite grammar, internal evaluator, eight-skill capacity and terminal-attempt policy remain limitations. Production controller integration, external transfer, independent operators and genuine distribution-shift recovery remain unverified.

## Research-to-execution note

On October 19, the authors of [Emerging Trends in AI Agent Evaluation](https://www.normaltech.ai/p/new-paper-emerging-trends-in-ai-agent) published a synthesis emphasizing full trajectories, component attribution and the limits of transferring lab results to deployment. It is methodological analysis, not a new measured capability result. This adapter is evaluated with state transitions and failure traces rather than a final success flag alone; no external evaluation toolkit or model judge was adopted.

Next experiment: compare this adapter with the unchanged paired harness on preregistered disjoint tasks at identical acquisition, construction and verification budgets. Include an interface ablation; count all label, retention, execution and failure costs. Accept a gain only with supported paired holdout improvement and no correctness/retention regression. Independently operated replication remains a separate requirement.
