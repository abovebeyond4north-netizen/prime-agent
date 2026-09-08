# Research basis and implementation decisions

Reviewed 8 September 2026. This is a focused review of primary sources, not an exhaustive systematic review or a claim to have established a universal SOTA ranking. Preprint results remain the authors' reported results. Different datasets, model sizes, compute budgets, and evaluation protocols prevent a direct ranking.

| Primary source and date | Relevant result or method | What this laboratory implements |
| --- | --- | --- |
| [Darwin Gödel Machine](https://arxiv.org/abs/2505.22954), May 2025, revised March 2026 | Empirically evaluated code changes and a branching archive allow useful stepping stones to survive. | Per-family archives with source hashes, parent lineage, test quality, and reuse in repair/crossover. No claim to reproduce SWE-bench results. |
| [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/), May 2025 | Evolutionary program proposals are selected using executable evaluators. | Cascaded gates, sandboxed candidates, performance budgets, and exact oracles. No Gemini integration or industrial optimization claims. |
| [Absolute Zero](https://arxiv.org/abs/2505.03335), May 2025, revised October 2025 | A proposer/solver setup generates code reasoning tasks and uses execution rewards for reinforcement learning. | Goal-derived task instances and increasing difficulty with executable truth. No model weight training or zero-prior-knowledge claim. |
| [Self-Challenging Language Model Agents](https://arxiv.org/abs/2506.01716), June 2025 | Code-as-Task couples instructions, verification, and quality filters for self-generated training tasks. | Generated task descriptors tied to immutable trusted families, public examples, private samples, and prerequisites. Arbitrary generated evaluators cannot authorize promotion. |
| [Hyperagents](https://arxiv.org/abs/2603.19461), March 2026 | Makes the meta-level improvement program editable, as well as the task agent. | A limited analogue: learned operator evidence is compiled into changing policy source, which is executed in Docker and checked against an action contract. The UCB learning rule itself is fixed. This is not a reproduction of DGM-H's open-ended meta-agent evolution. |
| [Continual Harness](https://arxiv.org/abs/2605.09998), May 2026 | Studies online harness adaptation for foundation agents. | Persistent operator outcomes, archive retrieval, and cross-session continuation; no foundation-model parameter updates. |
| [On the Fragility of Self-Improving Agents](https://arxiv.org/abs/2608.18066), August 2026 | Finds sensitivity to run variance, task order, and underspecified environments in memory-based methods. | Explicit function contracts, deterministic instruction-count budgets, repeated performance trials, and an independent final audit. A single CI run is not a statistical comparison against research baselines. |
| [CAFE](https://arxiv.org/abs/2608.24794), August 2026 | Couples search-agent and corrective-feedback learning, reporting gains beyond one-sided updates. | Feedback retains the failed gate and archive lineage, and changes subsequent operator selection. Its RL and critic training procedures are not implemented. |

## Algorithm and operational definition

The implemented autonomy is a closed loop within a declared computable task domain:

1. Turn a supported goal description into a fixed set of family/difficulty contracts and weights.
2. Select an unsatisfied task whose prerequisites have passed. Create its instruction without an operator prompt.
3. Retrieve useful source programs from the archive. Use learned per-family operator evidence to select direct generation, repair, mutation, or crossover.
4. Compile the selected policy's scores into a new pure Python program. Run that program only in Docker, verify its selected action, and retain its source/evidence snapshot.
5. Generate or modify candidate source. Reuse prerequisite functions when possible. Run all ten independent promotion gates.
6. Commit certified source to the private Git checkpoint store and atomically update activation, archive evidence, and telemetry.
7. Escalate task difficulty and repeat until the fixed capability target is met, a resource limit is reached, or progress stalls.
8. Run fresh shifted-distribution samples once for the selected checkpoint. A failed audit is terminal for that checkpoint. Report incomplete goals explicitly.

This is recursive program improvement in a bounded search space: earlier source and outcomes influence later source and policy parameters. It does not demonstrate unlimited recursive self-improvement, AGI, scientific discovery, or improvement of model weights.

## Quantitative contract

For a goal with fixed task set T and normalized weights, coverage is `C = sum(w_t * certified_t)`. Certification requires all ten gates, the supported evaluator version, and the task contract. Generated easy tasks outside T cannot change C. A new difficulty certificate measures additional coverage, not a new algorithm family.

Operator selection uses an optimistic bandit score `reward_sum / attempts + sqrt(2 * log(total_attempts) / attempts)`, with each untried operator selected before reuse. Reward is successful task certification; transfer between difficulty levels is recorded separately. Its usual stationary-bandit regret interpretation does not carry over automatically to this nonstationary search environment.

The default final audit runs 512 fresh cases per certified task. If all pass, its per-task one-sided lower bound is `(0.05 / |T|) ** (1 / 512)`, using a Bonferroni adjustment for simultaneous 95% coverage across the fixed task set. Completion requires a lower bound of at least 0.98 and the requested weighted coverage. This confidence statement is conditional on independent sampling from the declared audit distribution. It is not a guarantee on arbitrary inputs or across an unlimited sequence of manually restarted experiments.

Performance uses median CPU time across three trials, maximum traced heap, and deterministic Python line-event counts. Sorted-search programs must stay below 250 line events per performance case; this rejects linear scanning on the 10,000-element workload. This is a workload-specific complexity check, not a proof of asymptotic complexity.

## Research limits and next experiments

The offline `search` provider explores supplied program sketches, including imperfect variants, and repairs archived source. This makes the pipeline reproducible without paid calls but bounds novelty. `api` accepts genuinely new model proposals within the same pure-function domain; it requires a configured external or local endpoint. Neither provider gets evaluation authority.

To assess scientific improvement, compare fixed operator scheduling against the learned policy over multiple independently seeded runs, report attempts-to-certification and compute costs, and evaluate unseen task families without changing success criteria. The current tests establish execution and control correctness, not a statistically significant SOTA improvement. Fully editable meta-learning rules and automatic registration of wholly new semantic task families would require additional independent verification; they are intentionally not represented as implemented features.
