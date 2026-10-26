# Public experiment prerequisite

Added 2026-10-26: `research.active_boolean.discover` queries a supplied public
oracle, learns from four one-bit labels, then tests twelve uniform word probes.
Contradictions and insufficient budgets abstain. Candidates are explicitly not
certified. No protected evaluator feedback, generated-code execution, promotion,
production integration, or paid model calls occur in this module.

Executed: `python -m unittest tests.test_active_boolean -v`: six tests passed.
All sixteen ordinary Boolean rules survive sixteen public queries each; all
sixteen constructed width-shifted rules abstain after five. These are development
fixtures, not a new holdout or evidence of autonomous invention. A width-64
exception intentionally survives the policy, demonstrating incomplete coverage.

The hypothesis class and experiment policy remain developer supplied. The query
callback is trusted and must return promptly; the label budget is not a timeout.
This module is standalone and does not change previously verified study results.

Next invention experiment must freeze a task-independent synthesis grammar and
budget, discover reusable compositions without hand-coded target solutions, and
compare learned abstractions against primitive-only search at equal total cost.
Acceptance requires disjoint tasks, protected certification, restart reuse,
rollback, and no baseline regression. Novel composition within a supplied grammar
must be described as such, not as open-ended invention or general intelligence.
