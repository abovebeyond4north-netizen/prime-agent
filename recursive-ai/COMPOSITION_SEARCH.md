# Learned composition: development evidence

2026-10-26. A bounded breadth-first synthesizer uses increment, double and negate.
It solves six training tasks from examples, then a generic contiguous-sequence
compressor selects the abstraction with greatest positive net token saving.
The discovered sequence is `double, increment`; that sequence is not supplied to
the learner. Primitive semantics, grammar, task distribution and algorithms are
developer supplied. This is learned composition, not open-ended invention.

## Executed comparison

`python -m research.composition_study` sweeps every offset 0..31 for multipliers
16 and 32, distinct from the six training functions. Each arm has a fixed 10,000
primitive-evaluation budget per task. Macro execution pays for expanded primitive
operations on each public input. Both arms solve 64/64 tasks. Each solution passes
201 additional integer inputs: 12,864 checks per arm, 25,728 total.

- Primitive-only search: 170,658 primitive evaluations.
- Learned-composition search: 131,655 (22.85% fewer).
- Reuse is cheaper on 39 tasks and more expensive on 25; none loses correctness.
- Training costs 2,790 primitive evaluations. Charging this only to reuse yields
  134,445 evaluations, still below 170,658, but excludes compression and overhead.

Raw per-task programs and costs are in `composition_results.json`. Six unit tests
pass; repository `npm run check` passes with npm 11.10.1. No paid calls.

## Limits and next gate

This is an exploratory internal development sweep after initial example trials,
not a preregistered holdout, independent replication or protected certification.
Primitive evaluation count omits compression, queue/hash work and wall time.
The trusted interpreter executes a finite tuple DSL, never generated Python.
There is no persistent promotion or production integration. Public semantic
deduplication is task-example dependent and may discard useful alternatives.

Before promotion: freeze this implementation; measure end-to-end cost including
compression on separately generated tasks; compare primitive-only, learned and
matched-size irrelevant-macro arms; require no correctness loss and report all
per-task regressions. Persist and replay the learned abstraction, then verify
removal/restoration under rollback. Existing protected evaluation remains required.
