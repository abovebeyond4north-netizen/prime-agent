# Verified inverse task-family expansion

The search provider can now adapt a certified `lower_bound` scaffold into two previously unsupported numeric families: `integer_sqrt(n)` and `triangular_inverse(n)`. The AST adaptation rule is developer-authored. The system acquires and certifies the new skills through the existing sandbox controller; it does not autonomously invent this rule.

The adapter requires a recognized certified lower-bound scaffold, changes its arguments, upper bound, monotone predicate and result offset, then submits the candidate through all ten gates. Source ancestry is recorded across task families. The default six-family algorithms-toolkit contract is unchanged. Evaluator code changes invalidate older certificates through the suite digest, requiring re-certification.

## Reproduce

```bash
cd recursive-ai
docker build -t recursive-ai-runner:local sandbox/
python3 main.py autonomous --goal lower_bound --tier 1 --max-attempts 4 --max-model-calls 0
python3 main.py autonomous --goal "numeric inverses" --tier 1 --max-attempts 8 --max-model-calls 0
python3 main.py solve --skill integer_sqrt --arguments '[100]'
python3 main.py solve --skill triangular_inverse --arguments '[100]'
```

Outputs: 10 and 13. Invocation admits nonnegative integers of at most 256 bits. Generated code executes only in Docker.

## Executed evidence

[Docker study](https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38325409098) at 777815faddec79da2bd56bd57c719e7a0f06d2e3. Three fresh executions use shifted evaluation seeds 190013, 290021 and 390029. Both arms inherit the same trained, certified lower-bound checkpoint, trained in two attempts and 17 containers. Limits per continuation: eight attempts, 240 containers, five consecutive no-gain attempts, zero model calls.

| Continuation | New families certified | Attempts | Learning containers | Contract coverage |
| --- | ---: | ---: | ---: | ---: |
| Adaptation disabled | 0 | 5, then stagnation | 17 | 1/3 |
| Scaffold transfer | 2 | 2 | 32 | 3/3 |

Results match across all three executions. Costs are not equal: 32 containers acquire the two new capabilities, whereas the ablation stops after 17 with no gain. Equal budget limits do not mean equal consumed compute.

Both new skills passed all ten certification gates and a fresh 512-case shifted final audit, while the earlier list-search skill remained certified. A separate math.isqrt-based oracle checked 1,024 additional random/boundary cases per new skill per run: 6,144 additional cases total, up to 256-bit inputs. This audit uses 64-case batches under the original sandbox instruction limits. Its cost is 33 containers per transfer run; restart invocations add four and rollback/restore invocation adds two. Unacquired ablation skills are unavailable, not scored as incorrect outputs on unexecuted cases.

Fresh CLI processes invoked both skills successfully. Rolling back to the donor checkpoint blocked integer-sqrt invocation; restoring the promoted checkpoint recovered it. The complete evidence records checkpoint IDs, lineage, costs and reproduced source whose hashes match the observed parent/child ancestry.

The first single-batch large-input audit failed the sandbox execution limit. That failure is retained in the evidence; only batching was corrected. No gates, resource limits, oracle, test cases or acceptance thresholds were relaxed.

## Scope

This verifies expansion from list search into two numeric inverse task families and retained operational capability, rather than a verification-cost-only change. It remains a developer-defined finite laboratory. The oracle implementation is separate from the candidate algorithm, but not controlled by an independent party. The three executions share an operator and environment class; they are not three independent operators or external task distributions. No open-world, general intelligence, autonomous algorithm-invention or statistical-generalization claim is made.
