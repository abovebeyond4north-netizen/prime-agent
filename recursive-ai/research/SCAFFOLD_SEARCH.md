# Verified procedure configuration discovery

This research experiment selects an inverse-search procedure using public execution, without accepting a donor program. Its developer-defined candidate grammar enumerates 16 choices of upper bound, branch direction, comparison and return offset. Candidate code executes only in Docker. A unique matching configuration is retained; ambiguity and exhausted budgets do not produce a selected model.

## Executed evidence

[Docker study](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38329695496) at 6b12b81d23feb45470bcb86a8eaefca7f3b74b13. Three fresh executions use seeds 490033, 590041 and 690047.

Each run screens 16 candidates on square-root public examples. Exactly one matches:

| Choice | Learned value |
| --- | --- |
| Upper bound | n + 1 |
| Branch direction | Forward: true increases low, false reduces high |
| Comparison | <= |
| Return offset | low - 1 |

The procedure configuration is frozen before exposure to three new cubic/quartic predicate tasks. Predicate coefficients/degrees are then inferred from those tasks' public labels using the existing expansion mechanism. All nine transferred procedures pass all ten gates and 9,216 additional large-input cases across three runs. The frozen first candidate fails each transferred task. Separate bitwise oracle checks and exact inequalities are applied on shifted inputs.

The selected model is saved as JSON and replayed in a fresh Python process. The replay reconstructs approved candidate syntax, executes it in Docker on a 255-bit square-root input and matches math.isqrt. No candidate source is executed on the host.

Costs per run: 17 screening containers, 12 training-certification containers, two fresh-process replay containers; each of three transfer tasks adds 12 certification, two frozen-control and 17 additional-audit containers. Total: 124 containers per run. This proves correct selection and transfer; it does not claim a compute advantage over a supplied verified scaffold.

Local checks: 145 tests, 138 passed and seven Docker-dependent skips; project checks passed without warnings. The experiment adds research code only and leaves production/controller behavior unchanged.

## Reproduce

```bash
cd recursive-ai
docker build -t recursive-ai-runner:local sandbox/
python3 -m research.scaffold_search --seed 490033 --output scaffold-result.json
python3 -m research.scaffold_search --replay-model scaffold-result.model.json --input 100
```

The replay output is 10. Complete reports and generated source are in `scaffold_search_results.json`. Model JSON is also retained in the workflow artifacts for 30 days.

## Scope and remaining dependencies

A specific donor source and preselected boundary/branch/comparison/result choices are unnecessary in this research experiment. The overall binary-search loop form, midpoint expression, allowed updates and the 16-option grammar remain developer-defined. The learned model is not integrated into production selection or promoted checkpoints. Task admission and evaluator remain trusted designed components. The three executions share one operator and environment class; no unrestricted program synthesis or independent external evaluation claim.
