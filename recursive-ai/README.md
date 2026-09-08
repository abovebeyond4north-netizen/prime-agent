# Recursive AI laboratory

An executable, bounded program-search laboratory with autonomous goal-driven curricula across six primitive algorithm families and generated compound arithmetic tasks. The original `run` command retains the single-task prototype. This is not AGI or autonomous model training. The default demo searches supplied algorithms; the optional API mode requests new source from a local or remote chat-completions-compatible service.

## Autonomous goal completion

```sh
cd recursive-ai
docker build -t recursive-ai-runner:local sandbox/
python3 main.py plan --goal "algorithms toolkit" --tier 2
python3 main.py autonomous --goal "algorithms toolkit" --tier 2 --max-attempts 64 --max-seconds 900
python3 main.py research-status
python3 main.py solve --skill gcd --arguments '[-12,18]'
python3 main.py solve --skill count_occurrences --arguments '[[1,2,2,3],2]'
```

This creates and solves prerequisite tasks without further input, archives unsuccessful stepping stones, repairs their source, composes verified helper functions, learns per-family operator preferences, and raises difficulty. The six families are `lower_bound`, `upper_bound`, `binary_search`, `count_occurrences`, `gcd`, and `fibonacci`. There are three supported difficulty tiers; the default goal has 12 certificates across six families and two tiers. Other supported goals are `sorted search`, `number theory`, and explicit function names. Unknown goals fail as unverifiable instead of receiving an invented success score.

A successful session ends with `goal_reached` only after all required gates and an independent shifted-distribution final audit. Exit code 2 means the goal was not established. Inspect the final summary for `attempt_budget`, `wall_budget`, `container_budget`, `model_call_budget`, `stagnation`, `operator_stop`, `audit_failed`, or execution errors. The default target is full weighted coverage, with an audit lower-bound requirement of 0.98 at simultaneous 95% confidence on the defined audit distribution.

Attempt and model-call reservations persist across restarts for the same goal. Wall time and container limits apply per session; Docker cleanup can add up to 15 seconds after the execution deadline. `--max-stagnation`, `--max-model-calls`, and `--max-containers` set additional limits. Create `.lab-state/STOP` to stop at the next broker check (or immediately terminate an active candidate); remove it before restarting. An already successful goal returns its recorded result if its active checkpoint is unchanged. A failed final audit is not retried on the same checkpoint. The goal and certificates include a fingerprint of trusted evaluator, task, AST policy, and harness source; changed evaluation code requires fresh certification.

The default offline `search` provider operates over supplied algorithm sketches. It includes imperfect candidate variants so verification and archive-based repair are exercised. This is a reproducible bounded baseline, not evidence of discovering unknown algorithms. For model-generated new programs, configure the environment described below and add `--provider api`. API call reservations bound request counts, and returned usage is logged when the provider supplies it; no live model calls were needed for CI.

Learning changes both archived program source and the operator policy's generated source. The policy executes only in Docker. Its UCB update rule remains fixed: this is evidence-based adaptation, not unrestricted rewriting of the learning algorithm. Read [research/RESEARCH.md](research/RESEARCH.md) for current research, design mappings, statistical assumptions, and limits.

## Automatically generated compound tasks

```sh
python3 main.py plan --goal "compound arithmetic" --task-seed 73 --task-count 3 --tier 2
python3 main.py autonomous --goal "compound arithmetic" --task-seed 73 --task-count 3 --tier 2 --max-model-calls 0
python3 main.py research-status
```

This goal generates integer expressions from a bounded grammar of addition, subtraction, multiplication, GCD, absolute value, minimum, and maximum. The current sampler combines GCD with arithmetic and min/max. Admission rejects duplicate output fingerprints on a fixed probe grid and expressions without observable dependence on both inputs. This measures finite behavioral diversity, not mathematical novelty or research breakthroughs.

The seed and task count freeze the curriculum before search. Three expressions at two tiers plus the GCD prerequisite produce seven equally weighted targets. Additional tasks outside that contract earn no credit. Changing the seed creates a different goal, not extra progress on the old goal. The default is six expressions; up to twelve are supported.

Offline synthesis compiles the declarative expression into Python AST and reuses a certified GCD implementation. The host oracle interprets the expression separately using Python's trusted integer arithmetic and `math.gcd`; it never executes proposed source. Every compound program still passes all ten gates and the independent final audit inside the existing resource limits. This is compositional synthesis within a fixed grammar, not autonomous creation of arbitrary evaluators or training of model weights.

Task keys contain the complete canonical specification, so checkpoint recovery and regression verification do not depend on an in-memory registry. `research-status` exposes each acquired `compound_<hash>` family name; invoke it with `python3 main.py solve --skill <family> --arguments '[-12,18]'`. Inputs are two integers of at most 512 bits. Grammar, sampling and oracle changes invalidate prior certificates through the evaluator fingerprint.

## Original single-task run

Requires Linux, Python 3.12+, Git, and a Docker daemon with working cgroup v2 limits and its default seccomp profile. Docker Desktop's Linux VM is also suitable for evaluation, but the controller uses POSIX file locking. Colab without Docker cannot run candidates: there is deliberately no host-execution fallback.

From the repository root:

```sh
cd recursive-ai
docker build -t recursive-ai-runner:local sandbox/
python3 main.py run --iterations 8
python3 main.py status
python3 -m unittest tests.test_lab -v
```

Capture each run's JSON lines if you want a separate telemetry file. Persistent telemetry, exact-source Beta evidence, bandit statistics, and the atomic active checkpoint pointer are in `.lab-state/memory.sqlite3`. Git checkpoints are in `.lab-state/checkpoints.git`. `main.py status` reports the current SHA. To restore a previously promoted checkpoint, pass that SHA to `python3 main.py rollback --checkpoint`. Rollback changes only the active pointer and appends an event; it preserves all historical evidence and never resets the parent repository.

The first promotion gains the single benchmark capability. Later replacements require objective improvement greater than 0.001; merely passing again is not capability growth. Runtime measurements are noisy, so this threshold is a prototype heuristic, not statistical proof of optimization.

## Optional model synthesis

Set `LAB_MODEL_URL` to the full chat-completions endpoint, `LAB_MODEL_NAME` to an installed or available model, and optionally `LAB_MODEL_KEY` in the environment. Run `python3 main.py run --provider api --iterations 8`. HTTPS is required except for loopback HTTP. No credentials are written to memory. API mode can incur provider charges and is only used when explicitly selected. The client requests at most 2048 output tokens per direct/repair proposal and uses a 60-second request timeout. Actual billed token usage is not currently tracked. Mutation and crossover run locally on source ASTs; they never execute candidate code.

## Boundaries and gates

The host controller, evaluator, source-generation adapters, SQLite store, Git store, Docker daemon, and image are trusted. The generator receives only public specification/examples, active source, and aggregate failed gate names. Candidate containers receive source and the current inputs, but never expected answers, repository files, evaluator code, credentials, or the Docker socket. Fresh holdout samples are withheld from the generator, not secret from the function processing its own inputs. The sampling distribution is public. Repeated adaptive selection can still overfit that distribution.

Every promotion requires these gates, in order:

1. Syntax and source/AST size limits.
2. Conservative pure-function AST policy (no imports, attributes, reflection, private names, decorators, defaults, or arbitrary calls).
3. Container boot: verify non-root UID, read-only root, seccomp filter, no-new-privileges, zero effective capabilities, and actual cgroup CPU/memory/swap/PID limits.
4. Public tests with host-computed expected answers.
5. Current candidate regression tests plus rechecks of every active skill (one supported task in the legacy `run` command).
6. 128 fresh holdout cases.
7. Translation, positive scaling, sign reversal with re-sorting, duplicates, empty inputs, and large integer cases.
8. CPU time and traced Python heap thresholds; autonomous mode also measures line-event work budgets; broker wall timeout and container memory ceiling. These are not hardware CPU-cycle measurements or total RSS measurements.
9. 1000 new randomized comparisons with a linear reference.
10. Three fresh-container runs on identical inputs, requiring byte-identical serialized outputs and oracle correctness.

Candidate inputs must remain unchanged. All output validation occurs on the host. A failing or unavailable gate ends evaluation, and unavailable isolation stops the run. Exceptions from candidates and private values are not fed into synthesis. AST filtering is defense in depth, not a proof that arbitrary Python is safe. Docker shares a kernel: use a dedicated disposable VM for hostile source.

The image contains only the trusted harness. The runner sets a read-only root, non-root UID, no network, one CPU, 512 MiB memory with no additional swap, 64 PIDs, no capabilities, no new privileges, and a 16 MiB noexec tmpfs. It retains Docker's maintained default seccomp profile instead of shipping an unverified custom syscall list. Configuration reference: https://docs.docker.com/reference/cli/docker/container/run/

There is no autonomous agent process with host write access. The requested OS-enforced read-only generator workspace and full mutable synthesizer subsystem are not implemented; only candidate execution is isolated. Editing trusted controller files is an operator action. Do not give a model host tools or run this controller from a model-writable checkout.

## Metrics

For binary skill indicators `p_i`, normalized nonnegative weights `w_i`, and wall time `E_k`:

- `C_k = sum(w_i * p_i)`.
- `delta_k = C_k - C_(k-1)`.
- `R_k = delta_k / E_k`; the implementation reports `R_k - R_(k-1)` as rate change, not physical acceleration.
- `J = 1 - 0.001 * AST_depth - source_bytes / 1e6 - peak_heap_bytes / 1e9 - CPU_seconds / 10`, compared only after all gates pass.
- Each exact source hash has a Beta(1,1) prior: posterior mean `(1 + successes) / (2 + successes + failures)`. Repeated related test suites are correlated evidence, not calibrated correctness probabilities.
- UCB1 selects an untried strategy first, then maximizes `mean_gain + sqrt(2 * log(total_attempts) / strategy_attempts)`. Rewards are capability gains in [0,1]; objective-only changes are not rewarded as new capabilities.

Git snapshot objects are written before SQLite activation. A crash before activation can leave an inactive checkpoint object; it cannot partially replace active state. A process lock serializes controller mutations. SQLite transactions atomically record activation, evidence, strategy reward, and episode. Events are append-only by controller convention, not tamper-proof against the host owner.

## Scope and verification

Implemented search strategies: direct synthesis, integer AST mutation, scope-preserving whole-function crossover, and regeneration using failure-gate context. The demo is deliberately finite; it does not discover an unlimited curriculum. Semantic embeddings, trained model updates, arbitrary new semantic task-family registration, and hardware cycle counters are not provided. Autonomous mode adds versioned multi-task contracts and records model usage when returned by the provider.

`tests.test_lab` and `tests.test_autonomy` verify controller gates using a fake runner, static rejection, actual Git checkpoints, SQLite rollback, and fail-closed behavior. It does not execute untrusted Python on the host. `tests.test_docker` contains real Docker integration checks and must be run separately on a Docker host after building the image:

```sh
python3 -m unittest tests.test_lab tests.test_autonomy tests.test_expressions tests.test_docker -v
```

A green controller test suite is not evidence that the container image has run successfully. See `VERIFICATION.md` for the actual verification results for this change.
