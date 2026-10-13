# Certified procedure learning in the autonomous controller

Code: 43a26e56e82dbec251290db46be0dff33ff077c7. Executed October 13, 2026.
Docker integration: https://github.com/abovebeyond4north-netizen/prime-agent/actions/runs/38336560354

Enable with `python main.py autonomous --goal "numeric inverses" --tier 1 --max-model-calls 0 --learn-inverse-procedure`.
The flag defaults off and requires the search provider. Sixteen bounded procedure configurations are screened using public examples in the same budgeted sandbox runner. An isolation probe precedes screening. All ten certification gates must pass before the model enters the promoted skill manifest. Protected tests do not select the configuration.

Only models from currently certified skills are reused. A model must exactly reconstruct its stored source; reuse reinduces the predicate from the receiving task's public examples and certifies the resulting program afresh. Procedure models live inside ordinary versioned checkpoints, so rollback removes them with their skills. Terminal summaries distinguish the opt-in mode.

Nine tests passed with real Docker, including acquisition of integer square root, fresh-process triangular-inverse transfer, huge-input invocation, rollback rejection and forward restoration. Both inverse skills passed certification; the final independent shifted audit passed 512 cases per task (1,536 total) with simultaneous lower bounds 0.992035 at confidence 0.95. There were four total attempts and zero model calls. The reported 18 containers are the final continuation session only, not the full acquisition cost.

Local full suite: 150 tests, 142 passed, eight Docker-dependent skips. Project checks passed without warnings.

This verifies controller integration, persistence and rollback. It does not establish a new efficiency advantage over the supplied-scaffold adapter. Loop form, midpoint, update grammar and candidate bounds remain designed; the production curriculum still requires a certified lower-bound prerequisite. Cubic/quartic transfer remains research-only.

