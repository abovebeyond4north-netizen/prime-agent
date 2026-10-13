# Verified public-example rule induction

The inverse adapter now infers its predicate from public input-output examples instead of selecting it by task name. The bounded hypothesis grammar is `p*k*k + q*k <= d*n`, with integer p=1..4, q=0..4, d=1..4. Equivalent coefficient scalings are normalized. The grammar also requires p+q>=d so the inherited search interval [0,n+1) is valid. Only a unique compatible rule is emitted; ambiguous or unsupported observations do not select a rule.

The learner receives at most 64 public pairs. It tests the trusted arithmetic constraints `P(k)<=d*n<P(k+1)`; it never executes candidate source on the host. The selected rule is inserted into a previously certified lower-bound scaffold. All candidate code then runs under the existing Docker gates. Grammar and scaffold are developer-defined; the coefficients are inferred, not supplied by a task-name lookup.

## Executed evidence

[Docker run](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38326814775) at 7631ad477dd0c30e99dca416dbb909977116d134. Three fresh executions use shifted seeds 190013, 290021 and 390029.

| Held-out predicate (p,q,d) | Recovered from 64 public pairs | Ten gates | Frozen square predicate | Additional shifted cases, all three runs |
| --- | --- | --- | --- | ---: |
| (2,3,2) | Exact | Passed | Rejected | 3,072 |
| (3,1,2) | Exact | Passed | Rejected | 3,072 |
| (4,0,3) | Exact | Passed | Rejected | 3,072 |

All nine held-out trials passed all ten gates and 9,216 additional large-input cases, up to 256 bits, against a separate closed-form math.isqrt oracle. Each rule trial used 12 certification containers, two frozen-control containers and 17 shifted-evaluation containers. Protected and shifted cases never enter induction. Ambiguous labels were refused.

The production integer-square-root and triangular-inverse goals were also rerun with the example-induced predicates: all three sessions certified both new skills, preserved the earlier search skill, passed 6,144 additional cases, invoked both skills in fresh processes, and verified rollback/restoration. Complete reports and generated source are in `inverse_induction_results.json`.

Local checks: 138 tests, 131 passed and seven Docker-dependent skips; project checks passed without warnings.

## Scope

This verifies supervised induction of previously unused predicates within a finite grammar, followed by generalization checks. It does not infer the grammar, the search scaffold or an unrestricted learning algorithm. The three held-out predicates are research-only trusted task contracts; they are not registered production skills or promoted checkpoints. The two production inverse families are available through the autonomous controller. One operator and environment class execute all replications; the evaluator is not externally controlled.

## Reproduce

After training `lower_bound`, export its certified source from the checkpoint as a file, then run:

```bash
python3 -m research.inverse_induction --parent-source parent.py --seed 190013 --output induction.json
```

Candidate execution requires the built `recursive-ai-runner:local` Docker image. The script evaluates all three held-out predicates and the frozen-predicate ablation, preserving measured costs and emitted source. It never promotes research tasks.
