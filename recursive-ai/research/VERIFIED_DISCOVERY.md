# Verified Discovery Pipeline

The Verified Discovery Pipeline is the second stage of Frontier Discovery.

Frontier Discovery produces **candidates**. This module evaluates one candidate under a
preregistered computational protocol and records one of three outcomes:

- `verified_under_protocol`: both independent implementations reproduced every declared
  prediction and every adversarial/counterexample suite across all replicates.
- `rejected`: the two implementations agreed with each other but their consensus violated
  at least one preregistered prediction.
- `inconclusive`: isolation, determinism, resource bounds, or independent implementation
  agreement was insufficient to decide the candidate.

The word **verified** is deliberately scoped. It means reproducibly verified under the
exact protocol whose hash was committed before execution. It does not convert a
computational experiment into an unrestricted claim about external reality.

## Trust boundary

The verifier:

1. requires a candidate already anchored in `frontier-discovery/ledger.jsonl`;
2. requires the plan's `hypothesis` to exactly match the candidate statement;
3. statically validates two structurally distinct pure-function implementations;
4. writes a hash commitment of the complete protocol before running either implementation;
5. boots the existing Docker isolation boundary;
6. evaluates a primary prediction and at least one adversarial falsification suite;
7. repeats every suite at least three times for both implementations;
8. requires deterministic outputs and agreement between independent implementations;
9. separates scientific rejection from infrastructure/methodological inconclusiveness;
10. appends only successful outcomes to `verified_knowledge.jsonl`.

Neither this module nor `verified_knowledge.jsonl` can update the capability ledger.

## Why preregistration matters

Without preregistration, a system can accidentally overfit its hypothesis to results:
change expected outputs, modify counterexamples, or tune a verifier after observing the
experiment. The pipeline prevents that by appending a `verification_preregistered`
record before `SandboxRunner.boot()` is called.

The record commits to:

- candidate and study identifiers;
- exact candidate statement hash;
- prediction-case hash and expected-output hash;
- every falsification-suite hash;
- both verifier source hashes and structural AST hashes;
- replicate count;
- instruction, CPU, and memory budgets.

The later `verification_completed` record points back to that exact preregistration hash.

## Verification plan

A verification plan is JSON. The executable functions must satisfy
`core.ast_validator` and therefore cannot import modules, access attributes, perform I/O,
or call anything outside the approved pure-function subset.

A concrete example:

```json
{
  "study_id": "study-1",
  "candidate_id": "candidate-1",
  "hypothesis": "Investigate whether even inputs map to one.",
  "entrypoint": "experiment",
  "primary_source": "def experiment(x):\n    return 1 if x % 2 == 0 else 0\n",
  "independent_source": "def experiment(x):\n    if x % 2:\n        return 0\n    return 1\n",
  "prediction": {
    "name": "declared prediction",
    "cases": [[2], [3], [4], [5]],
    "expected_outputs": [1, 0, 1, 0]
  },
  "falsification_suites": [
    {
      "name": "boundary counterexamples",
      "cases": [[0], [-1], [-2], [101]],
      "expected_outputs": [1, 0, 1, 0]
    }
  ],
  "replicates": 3,
  "max_steps": 500000,
  "max_cpu_seconds": 0.5,
  "max_peak_bytes": 1000000
}
```

The `study_id`, `candidate_id`, and `hypothesis` must correspond to a real Frontier
Discovery report in the chosen state directory. The example above is illustrative; it
will fail closed unless such a report exists.

## Run

From `recursive-ai/`:

```bash
python3 -m research.verified_discovery \
  --state .lab-state \
  --plan verification-plan.json \
  --image recursive-ai-runner:local
```

Exit code is `0` only for `verified_under_protocol`; rejected and inconclusive runs exit
with code `2`.

## Persistence

For a verification attempt:

```text
.lab-state/
├── frontier-discovery/
│   ├── ledger.jsonl
│   └── <study-id>/report.json
└── verified-discovery/
    ├── ledger.jsonl
    ├── verified_knowledge.jsonl
    └── <verification-id>/
        ├── protocol.json
        └── report.json
```

`protocol.json` contains hashes and bounded metadata, not mutable result-derived
predictions. `report.json` records the completed gates and hashes of replicate outputs.

The verification ledger stores both starts and completions. A crash after preregistration
therefore leaves an auditable incomplete attempt rather than silently disappearing.

## Complexity and bounds

Let:

- `S` be the number of suites including the primary prediction,
- `R` be the replicate count,
- `C` be the total number of cases across suites.

The verifier performs exactly `2 * S * R` isolated implementation runs. Case-level work is
therefore proportional to `O(2 * R * C)` plus the cost of the pure experiment functions.

Hard bounds:

- at most 16 falsification suites;
- at most 512 total cases;
- 3 to 7 replicates;
- at most 32 KiB per verifier implementation;
- at most 1,000,000 traced execution steps per sandbox call;
- user-specified CPU threshold no greater than 3 seconds;
- user-specified memory threshold no greater than 64 MB.

These limits keep discovery verification bounded and make resource exhaustion an
`inconclusive` result rather than evidence against a hypothesis.

## Epistemic rule

A candidate enters `verified_knowledge.jsonl` only when:

```text
frontier provenance valid
AND protocol preregistered
AND sandbox isolation available
AND both implementations deterministic
AND both implementations agree
AND all primary predictions match
AND all falsification suites match
AND all resource bounds pass
```

This store is evidence for future research prioritization. It is not permission to
self-modify, bypass evaluation gates, or claim universal truth.
