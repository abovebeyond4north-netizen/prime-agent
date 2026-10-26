# Versioned learned-composition lifecycle

Implemented 2026-10-26 in `research.composition_contract`. This is a separate,
opt-in POSIX research service, not production controller integration or a change
to macro search priority. The previously failed macro-transfer experiment remains
negative evidence; reliable storage does not make that search policy effective.

## Contract

`learn(state, problems, max_evaluations=100000)` takes one to sixteen public
example sets. Each set has two to 32 distinct integer inputs and outputs bounded
by 10^12. Examples must fit an integer affine function. Eager primitive-only
search solves each new set, sharing one total primitive-evaluation budget.
No task IDs, supplied target programs, private evaluations, model calls, or
generated Python execution enter acquisition. The grammar and search/compression
algorithms remain developer supplied.

Repeated subsequences are compressed into data-only macros of two to eight
primitives. Each checkpoint contains at most 32 solved problems and eight macros.
Before activation and on every load, the service reconstructs macro provenance,
checks every retained program with the symbolic affine interpreter, and verifies
implementation-version bindings. Git stores immutable manifests; a SQLite
transaction registers the active checkpoint and its event. A nonblocking exclusive
file lock prevents concurrent service writers. State cannot share a directory
with the production service.

`invoke(state, macro_id, value)` accepts signed integers with absolute bit length
at most 256. It interprets the saved finite primitive tuple and checks the output
against its affine certificate. `activate(state, checkpoint)` permits only
registered, valid checkpoints, supporting rollback and restoration. A `STOP` file
blocks acquisition/invocation and final activation during learning; explicit
checkpoint recovery remains allowed while stopped. No arbitrary source is loaded.

This certificate establishes equivalence of a finite primitive program to an
affine expression. Sparse examples do not prove that an unknown external task is
affine. Integrity checks are not cryptographic authentication against an operator
able to replace both Git and SQLite. There is no claim of open-world invention,
independent evaluation, search-cost gain, or resistance to a compromised host.

## Reproduction

From `recursive-ai`, using a new state path:

```sh
python3 -m unittest tests.test_composition_contract -v
python3 -m research.composition_lifecycle --state composition-evidence/state --output composition-evidence/result.json
```

Create the `composition-evidence` output directory first. The lifecycle command
learns two libraries, invokes their saved macros in twelve fresh processes,
switches to the first checkpoint, verifies the later macro is unavailable,
restores it, and verifies STOP. Repeated acquisition reuses the saved result with
zero new primitive-search evaluations; persistence/proof checks still have cost.

Fifteen targeted tests include actual fresh-process invocation, crash rollback
after uncommitted activation, transaction/event failure, retained-program and
macro tampering, stale bindings, non-production state enforcement, STOP races,
budget exhaustion, cached reuse, and exclusive locking. Mocks only inject faults
or assert absence of retraining; persistence, search, Git, SQLite and normal
invocation execute for real. These are not Docker containment tests: execution
uses a trusted, bounded data interpreter rather than arbitrary generated code.

Local verification: 239 tests, 226 passed, 13 Docker-dependent skips; repository
checks passed with npm 11.10.1. The dedicated CI workflow also runs the eleven
search tests and preserves Git/SQLite state plus an exact-integer result receipt
as a 30-day artifact. CI outcomes must be linked separately once observed.

Next capability gate remains adaptive optional reuse with equal-total-cost
comparisons on a fresh evaluation set, including lost baseline tasks and overhead.
Saved invocation verifies retention, not improved search coverage.
