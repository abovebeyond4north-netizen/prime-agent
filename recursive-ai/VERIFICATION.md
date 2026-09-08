# Verification record

Local checks on 2026-09-08:

- `python3 -m unittest tests.test_lab tests.test_docker -v`: 16 controller tests passed; 3 Docker integration tests skipped because Docker is unavailable.
- `npm run check`: passed (Biome, TypeScript, installer rendering, browser smoke checks). Used npm 11.10.0 to support the repository minimum-release-age configuration; dependencies were installed from the existing lockfile without changing it.
- Static policy rejection, each gate failing closed, invalid protocol outputs, actual isolation-probe limits, Git checkpoint preservation, SQLite activation atomicity, and zero gain for repeated success are covered by controller tests.
- No generated candidate code was executed on the host. Controller tests use an explicitly fake runner; their synthetic promotion telemetry is not evidence of real candidate success.
- The optional model API adapter has not been exercised against a live model.

The branch includes `.github/workflows/recursive-ai.yml` to build the Docker image, run all integration tests, and verify an actual ten-gate promotion. Remote execution results must be checked separately; adding the workflow does not establish that it ran or passed.

## Autonomous curriculum extension

Local verification of the extension on 2026-09-08:

- 36 controller/model-adapter tests passed; 6 real Docker tests were skipped locally because Docker is unavailable.
- The adapter tests use mocked responses and make no live model calls.
- `npm run check` passed without warnings, using npm 11.10.0.
- The expanded CI workflow tests six task families, learned policy execution, rejection of linear search under the deterministic work budget, a complete 12-certificate autonomous goal, independent auditing, and subsequent invocation of acquired skills.
- Local oracle-fake results are controller evidence only. The actual Docker and autonomous-goal outcome is recorded in the GitHub Actions run for the corresponding commit.

## Generated compound curriculum

Local controller verification on 2026-09-08:

- `python3 -m unittest tests.test_expressions tests.test_autonomy -v`: 24 tests passed; one compound Docker integration test skipped because Docker is unavailable locally.
- Tests cover bounded grammar rejection, canonical specification recovery, deterministic admission, fixed goal weights, prerequisite reuse, checkpoint resumption and acquired-skill invocation. Controller tests use an oracle fake and do not establish candidate correctness.
- CI additionally compares compiled compound programs against the independent interpreter, rejects constant-output candidates, completes a three-expression/two-tier goal in Docker, restarts the goal, and invokes every acquired family.
- Existing six-family CI result: [run 34284166234](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/34284166234). Compound execution must be verified in the run for the new commit.
- Repository `npm run check` passed without warnings for this extension.
