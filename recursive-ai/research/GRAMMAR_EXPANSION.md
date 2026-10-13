# Verified public-driven feature expansion

The learner starts with quadratic inverse hypotheses. If none fits its public examples, it composes another multiplication feature and retries. It selects a unique compatible predicate, refuses ambiguity, and stops after the bounded expansion budget. It receives only public (input,output) pairs; degree and coefficients are not supplied to selection.

The inherited search scaffold uses the induced predicate `p*k^degree + q*k <= d*n`. Candidate syntax contains repeated multiplication; emitted programs run only in Docker. The retained p+q>=d condition justifies the initial [0,n+1) interval for all admitted nonnegative inputs.

## Executed result

[Three fresh Docker executions](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38328669202) at 2a487155a16fe90c9b2328e3f8e223b74788cc2c, shifted seeds 190013, 290021 and 390029.

| Hidden task parameters (degree,p,q,d) | Expansion trace from public pairs | Frozen quadratic | Ten gates | Additional shifted cases, three runs |
| --- | --- | --- | --- | ---: |
| (3,1,0,1) | Quadratic: no fit; cubic: unique | No rule | Passed | 3,072 |
| (3,2,1,1) | Quadratic: no fit; cubic: unique | No rule | Passed | 3,072 |
| (4,1,1,2) | Quadratic/cubic: no fit; quartic: unique | No rule | Passed | 3,072 |

All nine expansion trials passed, including 9,216 additional cases with inputs up to 256 bits. Each trial used 12 certification containers and 17 additional-evaluation containers. Trusted inference considered 160 raw hypotheses for each cubic task and 240 for the quartic task; host candidate code was never executed. The separate oracle builds answers bit by bit, while candidates use interval bisection. Each shifted output also satisfies exact inequalities P(k)<=d*n<P(k+1).

The same run reverifies the earlier three quadratic predicates, both production inverse families, fresh-process invocation, retained list-search certification and rollback/restoration. Local suite: 141 tests, 134 passed and seven Docker-dependent skips; project checks passed without warnings.

Complete reports, public examples, expansion traces, generated source and costs are in `grammar_expansion_results.json`. CLI reproduction after exporting a certified lower-bound source:

```bash
python3 -m research.grammar_expansion --parent-source parent.py --seed 190013 --output expansion.json
```

## Remaining developer-defined dependencies

| Dependency | Status |
| --- | --- |
| Predicate coefficient selection | Induced from public labels |
| Whether to add a power feature | Triggered by lack of fit in public data |
| Multiplication feature-production mechanism | Developer-defined |
| Degree-four / 240-raw-hypothesis ceiling | Developer-defined resource bound |
| Recognized binary-search scaffold | Developer-defined and previously certified |
| Trusted task contracts, oracle and admission policy | Developer-defined |
| Runtime, language, containment and verification gates | Developer-defined |

The new cubic/quartic contracts are research tasks, not registered production skills or promoted checkpoints. This verifies bounded, data-driven feature expansion. It does not establish unrestricted grammar/scaffold invention or independent external generalization. All three executions share an operator and environment class.
