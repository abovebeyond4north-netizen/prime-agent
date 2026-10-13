# Session regression reuse

An opt-in `execute_goal(..., reuse_regression_checks=True)` experiment avoids repeating successful public/property checks for unchanged earlier skills within one verifier session. The default remains false. The cache is bounded to 64 successes and discarded on restart. Its key includes exact source, task, cases, expected outputs, suite digest and runner image reference. Failed and interrupted checks are not cached. Gate reports disclose reused checks; session summaries report hits and executions.

Candidate checks, isolation probes, protected samples, differential checks, performance trials, determinism trials and final shifted audits still run fresh. This is for trusted finite pure-function tasks with a fixed runner image, not for mutable or nondeterministic environments. Certificates continue to be tied to the evaluator suite digest.

## Executed comparison

Code: 085794b376c34e3b95f9cc22db73eb6184a1360e. [Docker evidence](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38323538389).

| Goal, tier 2 | Certified tasks | Attempts, both modes | Control containers | Reuse containers | Saved |
| --- | ---: | ---: | ---: | ---: | ---: |
| Algorithms toolkit | 12 | 16 | 240 | 185 | 55 (22.9%) |
| Compound arithmetic, seed 7301 | 7 | 8 | 119 | 104 | 15 (12.6%) |

Both modes completed each goal with the same certifications and passing fresh shifted audits, with zero model calls. Savings exactly matched cache hits. Separate invalidation canaries cost five containers per suite and rejected modified source twice; final audits also rejected it. Local verification: 129 tests, 122 passed and seven Docker-dependent skips; project checks passed without warnings.

These are two developer-controlled conditions, one run per arm, with one operator and a fixed image. No statistical generalization, external independent evaluation, novel capability gain or default promotion is claimed. Raw traces are retained as Actions artifacts for 30 days; complete reports are in `regression_reuse_results.json`.
