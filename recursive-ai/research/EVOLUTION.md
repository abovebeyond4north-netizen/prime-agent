# Evolutionary curriculum laboratory

This layer adds two bounded mechanisms inspired by AlphaEvolve-style program evolution,
quality-diversity search, and branching self-improvement research:

1. **Candidate lineage + diversity selection.** Program candidates are archived with
   parent digests and operator/origin metadata. Parent selection keeps the strongest
   candidate first, then greedily balances verification quality, AST-structural novelty,
   and source-size efficiency. Candidate code is parsed for structure but never executed
   on the host.
2. **Curriculum genome evolution.** A genome contains exactly three bounded numeric
   parameters controlling the order of already-trusted tasks:
   `retry_weight`, `family_balance_weight`, and `unlock_weight`. It cannot create
   new evaluators, change expected answers, skip prerequisites, lower difficulty gates,
   alter the sandbox, or promote itself.

## Run a bounded study

```sh
cd recursive-ai
docker build -t recursive-ai-runner:local sandbox/
python3 main.py evolve-curriculum \
  --evolution-goal "compound arithmetic" \
  --tier 2 \
  --task-count 6 \
  --population 4 \
  --generations 2 \
  --replicates 2 \
  --holdout-replicates 2 \
  --base-seed 1000 \
  --max-model-calls 0
```

The development seeds and holdout seeds are disjoint. Every genome receives the same
development seeds. The archive remains available across generations, so later search can
return to an older branch rather than replacing the current best irreversibly.

Selection is correctness-first. A genome's lexicographic objective is:

1. goal-reached rate,
2. independent audit pass rate,
3. mean verified coverage,
4. fewer attempts,
5. fewer container runs,
6. lower wall time.

Survivor selection then mixes quality rank with normalized Euclidean distance in the
three-dimensional genome space. This is a small quality-diversity search, not an
unbounded genetic algorithm.

## Holdout rule

After development, exactly one finalist is compared with the immutable default curriculum
profile on fresh seeds. The study reports:

- `holdout_improved`: all finalist and baseline trials are correct/audited, and the
  finalist has no coverage regression and strictly fewer mean attempts (or higher coverage);
- `holdout_non_regression`: correctness and coverage are preserved with equal attempts;
- `holdout_regressed`: both are correct, but the finalist is less efficient;
- `holdout_incomplete`: one or more correctness/audit requirements failed.

A development winner is **not automatically promoted**. The report only marks whether the
profile is eligible for a later separately reviewed and verified adoption.

## Immutable boundary

The following remain outside the genome and outside candidate write access:

- task families and host oracles;
- AST safety policy;
- Docker isolation configuration;
- the ten verification gates;
- holdout seeds while development selection is running;
- controller code and promotion logic.

The evaluator fingerprint already invalidates stale certificates when trusted evaluation
code changes. The new curriculum-profile digest similarly prevents cached goal summaries
from being reused under a different evolved profile.

## What this adds relative to the previous lab

The previous autonomous loop already had direct synthesis, repair, AST mutation,
crossover, an archive, UCB operator learning, generated compound tasks, transfer studies,
and independent audits. The new layer adds:

- explicit program lineage edges;
- quality-diversity parent retrieval instead of only top-quality/shortest retrieval;
- a bounded evolvable curriculum policy;
- branching mutation/recombination of those policies;
- an archive across generations;
- a fresh-seed holdout comparison against the immutable baseline.

This is closer to an experimental recursive-improvement loop because a part of the
search strategy itself becomes an evaluated artifact, while the machinery deciding
whether that artifact is acceptable stays fixed.
