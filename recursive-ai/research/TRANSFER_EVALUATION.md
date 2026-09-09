# Held-out cross-family policy transfer

Reviewed 8 September 2026. This experiment asks a narrower and more falsifiable question than whether the laboratory can repeatedly solve a fixed curriculum:

> Does search experience from one set of algorithm families improve performance on fresh, disjoint task families when no candidate source, skill, checkpoint, archive, expected answer, or evaluator state is transferred?

This follows the direction of recent cross-task self-improvement research. **Training Language Agents to Learn from Experience** (Shalev, Ding, Jamnik, 2026; https://arxiv.org/abs/2605.20477) evaluates whether lessons extracted from prior trajectories improve future unseen task families. **MetaSkill-Evolve** (Wang et al., 2026; https://arxiv.org/abs/2607.05297) separates fast task-skill evolution from a slower meta-skill improvement process. This laboratory implements only a bounded analogue: a fixed UCB1 rule may receive a compressed prior over its four existing search operators. It does not rewrite the UCB rule or train model weights.

## Transfer boundary

The training state is never reused as the held-out state. Every held-out condition starts with a fresh directory, SQLite database, checkpoint repository and candidate archive.

The only transferable object is four numeric triples, one for each existing operator:

```text
(attempts, successful_certifications, wall_seconds)
```

The operator order is:

```text
direct
repair
mutation
crossover
```

`ResearchMemory.global_operators()` aggregates those values across training families. It exports no source code or task-specific identifiers. The held-out controller receives the aggregate through an in-memory argument; it does not copy the training database.

## Bounded prior compression

Raw training counts can become arbitrarily larger than the amount of evidence collected in a new held-out family. Directly adding those counts would allow a long training curriculum to overwhelm all future exploration. The implementation therefore compresses training evidence to a fixed pseudo-count mass `S`, configured with `--prior-strength` and restricted to `[0, 32]`.

For `K=4` operators, every operator receives the same pseudo-count:

```text
p = S / K
```

For an operator observed during training, its transferred reward rate is:

```text
q_i = successes_i / attempts_i
```

For an unobserved operator, `q_i` is the global training success rate rather than zero. This avoids converting lack of evidence into a false negative result. The transferred row is:

```text
(p, p*q_i, p*mean_seconds_i)
```

The held-out learned policy adds this bounded prior to family-local evidence before computing the existing UCB1 score. Local held-out outcomes continue accumulating normally and eventually dominate the fixed-size prior.

No prior is accepted by the fixed control. Passing one to `policy_mode="fixed"` fails closed.

## Three held-out conditions

Each replicate trains one learned policy on the training goal, extracts the aggregate operator evidence, then evaluates three fresh held-out states:

1. `fixed` — deterministic round-robin over the same four operators, no learned prior.
2. `learned_scratch` — UCB1 on the held-out families with no prior.
3. `learned_transfer` — the same UCB1 rule with the bounded cross-family prior.

The distinction between `learned_scratch` and `learned_transfer` is essential. If transfer beats only the fixed policy, the result could simply mean UCB1 is a better within-task scheduler. Transfer must also be compared with UCB1 starting from no prior to test whether earlier experience itself helps.

## Family separation

Before any execution, the experiment expands both goal contracts, including prerequisites, and computes their family sets. Any overlap aborts the study.

Useful built-in pairs include:

```text
train:   sorted search
holdout: number theory
```

and the smaller CI smoke pair:

```text
train:   binary_search  # expands to lower_bound + binary_search
holdout: gcd
```

The second pair is intentionally small enough for real Docker execution on every CI run.

## Running the study

Build the isolated candidate image first:

```sh
cd recursive-ai
docker build -t recursive-ai-runner:local sandbox/
```

Run a replicated offline study:

```sh
python3 main.py transfer-evaluate \
  --train-goal "sorted search" \
  --holdout-goal "number theory" \
  --tier 2 \
  --replicates 10 \
  --base-seed 100 \
  --prior-strength 4 \
  --max-attempts 64 \
  --max-seconds 900 \
  --max-model-calls 0
```

The study writes an atomic report under:

```text
<state>/transfer-evaluation/<study-id>/report.json
```

Every replicate has independent directories for training and each held-out condition.

## Reported measurements

Training cost is reported separately instead of being hidden inside the held-out result. Held-out summaries include:

- goal completion rate
- final shifted-distribution audit pass rate
- weighted capability coverage
- attempts to termination
- wall time
- container executions
- model calls
- paired attempt differences
- paired wall-time differences
- paired coverage differences
- exact two-sided sign tests on non-zero attempt differences

The most direct transfer statistic is:

```text
attempt_delta_transfer_minus_control
```

Negative values favor transfer.

Two paired comparisons are reported:

```text
learned_transfer vs learned_scratch
learned_transfer vs fixed
```

## What would count as evidence

A useful positive result requires more than one successful run. Stronger evidence would have all of the following:

1. Training and held-out family sets remain disjoint.
2. All three conditions use identical held-out contracts, evaluators, resource limits and candidate generators.
3. Transferred policy improves attempts or completion rate against `learned_scratch`, not merely against `fixed`.
4. Improvements persist over multiple independently seeded replicates.
5. Final shifted-distribution audits remain passing.
6. Reversing or changing the train/holdout split does not destroy the effect completely.
7. Increasing `prior-strength` does not monotonically improve results simply by suppressing exploration; prior-strength should be treated as an experimental variable.
8. Training cost is reported and the transfer advantage can plausibly amortize over multiple future tasks.

## What would falsify the hypothesis

The experiment should be treated as negative or inconclusive if:

- `learned_transfer` is no better than `learned_scratch` across sufficient replicates;
- transferred priors improve training-like families but hurt disjoint families;
- results are driven by one seed or one operator ordering;
- audits or coverage degrade while attempt counts improve;
- the prior only helps when its pseudo-count mass is so large that held-out exploration is effectively disabled.

A negative result is useful: it means the current operator statistics are not sufficiently general to serve as a reusable meta-skill.

## Current limits

The transferable meta-state is intentionally small. It does not yet condition operator priors on task descriptors, failure modes, algorithmic structure, difficulty or resource profile. It also does not evolve the update rule itself. Those are possible later experiments, but only after this simpler transfer hypothesis is measured cleanly.

This is evidence about bounded search-policy transfer within the declared program-search laboratory. It is not evidence of unrestricted recursive self-improvement, AGI, autonomous evaluator creation, or safe execution of arbitrary hostile Python on a shared host.
