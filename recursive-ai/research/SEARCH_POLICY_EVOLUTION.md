# Search-policy evolution research layer

This layer evolves the **search procedure** used by the recursive-AI laboratory while
keeping correctness evaluation outside the evolvable surface.

## Motivation and current research mapping

The implementation is informed by several recent directions in automated algorithm and
agent design:

- **AlphaEvolve (Google DeepMind, 2025–2026)** combines LLM proposals, automated
  evaluators, and a program database implementing evolutionary selection.
  https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
- **Darwin Gödel Machine (Sakana AI / UBC, 2025)** shows that preserving a branching
  archive of diverse self-modified agents can outperform single-lineage hill climbing.
  https://sakana.ai/dgm/
- **ShinkaEvolve (2025)** emphasizes sample efficiency through exploration/exploitation
  parent sampling, novelty rejection, and bandit allocation.
  https://arxiv.org/abs/2509.19349
- **ALE-Agent (2025–2026)** demonstrates large-scale iterative algorithm engineering and
  reuse of insights from trial-and-error trajectories.
  https://sakana.ai/ahc058/
- **AB-MCTS (2025)** adaptively balances breadth and depth during inference-time search.
  https://sakana.ai/ab-mcts/
- **Digital Red Queen (2026)** demonstrates that evolving against a changing objective
  can promote robustness beyond a static benchmark.
  https://pub.sakana.ai/drq/
- **Agent0 (2025)** co-evolves a curriculum generator and executor, illustrating the
  value of task-generation pressure rather than a permanently fixed curriculum.
  https://arxiv.org/abs/2511.16043
- **Automated Design of Agentic Systems / Meta Agent Search** treats agent architecture
  itself as a searchable artifact and tests transfer across domains/models.
  https://arxiv.org/abs/2408.08435

The present change does **not** attempt unrestricted self-modification. It selects a
small, auditable search-policy surface whose effects can be measured independently.

## Evolvable search-policy surface

A policy genome contains only:

- `ucb_exploration`: exploration pressure for choosing direct / repair / mutation /
  crossover operators;
- `parent_quality_weight`: archive preference for verified quality;
- `parent_novelty_weight`: archive preference for structurally different programs;
- `parent_size_weight`: archive preference for smaller programs;
- `parent_limit`: bounded breadth of archive candidates available to synthesis.

The default genome exactly reproduces the previous search configuration:

```text
ucb_exploration        = 2.0
parent_quality_weight  = 0.70
parent_novelty_weight  = 0.25
parent_size_weight     = 0.05
parent_limit           = 8
```

## Sample-efficient racing

A naive evolutionary study evaluates every policy on every development replicate. This
layer instead uses successive-halving style racing:

1. evaluate every policy on the first development curriculum;
2. rank with correctness-first fitness plus a small diversity term;
3. eliminate roughly half;
4. spend the next replicate only on survivors;
5. continue until the development budget is exhausted;
6. branch the next generation from the surviving archive.

The report records the exact number of evaluations avoided relative to full evaluation.

## Novelty rejection

New offspring are rejected when their normalized policy distance is below a fixed
novelty floor relative to the archive. This prevents spending trials on numerically
different but behaviorally near-identical parameter configurations.

## Cross-family holdout

Development and final evaluation use disjoint task families by default:

```text
development: compound arithmetic
holdout:     sorted search
```

The final evolved policy is compared with the immutable default policy on the held-out
family. Automatic promotion is disabled. A policy is merely marked **eligible** when:

- both finalist and baseline achieve 100% goal completion;
- both pass their independent audits;
- the finalist does not regress verified coverage;
- the finalist does not use more attempts;
- the finalist does not use more container executions;
- and at least one measured efficiency dimension improves.

Adoption must occur in a later reviewed change.

## Run

```sh
cd recursive-ai
docker build -t recursive-ai-runner:local sandbox/

python3 main.py evolve-search-policy \
  --train-goal "compound arithmetic" \
  --holdout-goal "sorted search" \
  --tier 1 \
  --task-count 4 \
  --population 4 \
  --generations 2 \
  --replicates 2 \
  --holdout-replicates 2 \
  --base-seed 2000 \
  --max-model-calls 0
```

## Immutable boundary

The search genome cannot alter:

- host task oracles or expected answers;
- task-family definitions;
- AST safety policy;
- Docker isolation;
- the ten candidate verification gates;
- audit construction;
- development or holdout labels;
- study fitness ordering;
- policy-promotion logic;
- controller or evaluator source.

The protocol is source-fingerprinted. Changes to the trusted search-policy experiment
invalidate cached studies.
