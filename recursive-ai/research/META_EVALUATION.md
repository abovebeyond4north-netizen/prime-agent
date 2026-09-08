# Meta-learning evaluation protocol

This experiment compares the adaptive UCB1 operator policy against a non-learning round-robin control while holding the operator action space, task contract, evaluator, sandbox, and promotion gates constant.

## Why this exists

A self-improvement system should not be credited for becoming better at improvement merely because one autonomous run succeeds. The relevant question is whether the adaptive search policy reaches the same independently audited capability with fewer attempts or resources, or reaches more capability under the same budget, across paired trials.

The control condition cycles through `direct`, `repair`, `mutation`, and `crossover` without reading reward. The learned condition uses the existing per-family UCB1 evidence. Both policies are compiled to pure Python and executed through the same sandbox action contract. Curriculum transfer remains available to both conditions because it is a capability of the system rather than a learned operator choice.

## Run a study

Build the runner first:

```sh
cd recursive-ai
docker build -t recursive-ai-runner:local sandbox/
```

Then run paired trials:

```sh
python3 main.py meta-evaluate \
  --goal "algorithms toolkit" \
  --tier 2 \
  --replicates 5 \
  --base-seed 100 \
  --max-attempts 64 \
  --max-seconds 900 \
  --max-model-calls 0
```

For generated compound curricula, the paired seed also fixes the generated task contract:

```sh
python3 main.py meta-evaluate \
  --goal "compound arithmetic" \
  --tier 2 \
  --task-count 6 \
  --replicates 5 \
  --base-seed 500 \
  --max-model-calls 0
```

Each learned/fixed trial receives a separate state directory under:

```text
.lab-state/meta-evaluation/<study-id>/seed-<n>-fixed/
.lab-state/meta-evaluation/<study-id>/seed-<n>-learned/
```

This prevents checkpoints, archives, operator evidence, and policy history from leaking between experimental conditions. Re-running the same study configuration resumes the same trial directories rather than silently creating a new dataset.

The aggregate report is written atomically to:

```text
.lab-state/meta-evaluation/<study-id>/report.json
```

## Recorded measurements

For each condition the report includes:

- goal completion rate,
- shifted-distribution final-audit pass rate,
- mean weighted capability coverage,
- mean and median attempts,
- mean wall-clock time,
- mean sandbox-container executions,
- mean model calls,
- paired learned-minus-fixed deltas for attempts, wall time, coverage, and completion,
- an exact two-sided sign test over nonzero paired attempt differences.

A negative `attempt_delta_learned_minus_fixed` favors the learned policy. A positive coverage or completion delta favors the learned policy.

## Interpretation rules

Do not call one successful run recursive self-improvement. Treat the report as descriptive experimental evidence unless the result is replicated across independently varied curricula, model sampling seeds or providers, and compute environments.

A stronger claim requires all of the following:

1. the learned condition does not reduce final-audit success or weighted coverage,
2. it improves attempts or resource use on paired trials,
3. the effect repeats across multiple seeds,
4. the result survives additional unseen task distributions,
5. the evaluator, sandbox, promotion rules, and hidden audit remain unchanged,
6. the adaptive condition does not receive information unavailable to the control.

The sign test is included because it makes few distributional assumptions, but small sample sizes have very low power. It is not a substitute for effect sizes, confidence intervals, repeated studies, or adversarial evaluation.

## Important limitation

For deterministic offline sketches, some supported task families are solved before adaptive operator selection has enough observations to differ materially from round-robin scheduling. A null result in that regime means the benchmark does not expose a benefit; it does not prove that adaptive search can never help. More demanding verified task families and stochastic/API-backed proposal distributions are needed to stress meta-learning meaningfully.
