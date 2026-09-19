# Research-to-execution update — 2026-09-19

This update distinguishes implemented mechanisms from paper claims and future experiments. None of the cited results establishes a gain in this repository.

## Implemented in this change

1. **Per-case Pareto survival**, inspired by GEPA's preservation of complementary solutions. Opt-in `parent_selection="pareto"` in `run_search_policy_evolution` uses matched development cases, correctness-first dominance, and the existing quality-diversity tie-breaker. It preserves tradeoffs instead of collapsing every task into one mean. Complexity is O(p²r), bounded by the existing population and replication limits. This is not GEPA's reflective prompt optimizer.
2. **Matched-pair resource evidence** automatically accompanies search-policy holdout reports. It reports effect sizes, wins/losses/ties, exact one-sided sign-test probabilities, and Holm correction across attempts, container runs, and model calls. Failed audits, coverage losses, or per-case resource regressions block the supported-gain label. Wall time remains telemetry.
3. **Protocol provenance** includes both new modules in the existing study fingerprint. A changed method cannot reuse an old cached report.

The default selector and promotion decision are unchanged. The old `holdout_improved` field is a descriptive mean comparison, not statistical evidence. Consult `paired_resource_evidence` alongside it. No analysis can make repeated identical/correlated tasks independent: prespecify independently generated instances and freeze the finalist before gathering holdouts. Sign tests address directional win probability, not the population mean. Correction applies within one study, not across repeated adaptive experiments.

## Research map

| Primary source | Finding relevant to this lab | Current treatment | Next acceptance experiment |
|---|---|---|---|
| [GEPA](https://arxiv.org/abs/2507.19457), July 2025 | Reflective evolution and complementary/Pareto candidates | Per-case Pareto survival implemented as an adaptation; reflection remains future work | Compare selectors at equal actual trial/model budgets on independent task instances; preserve audit success and report held-out effects |
| [EvoX](https://arxiv.org/abs/2602.23413), February 26, revised March 16, 2026 | Joint evolution of solutions and search strategies | Existing bounded policy evolution provides a related experimental surface, not an EvoX replication | Ablate fixed profile vs evolved profile vs Pareto survival with a frozen evaluator |
| [Effective Harness Engineering](https://arxiv.org/abs/2605.15221), May 13, 2026 | Generation depth/breadth tradeoffs; evaluation exploits | Existing independent oracles and audits retained; equal-token experiment pending | Compare generation budgets and deliberately faulty candidates; zero exploit promotions |
| [Dream-RSI](https://arxiv.org/abs/2609.14858), September 14, 2026 | Replay discovery trees to cheaply screen exploration policies | Proposed only | Measure replay ranking against fresh online evaluation; quantify unseen-action support and reject unsupported counterfactual claims |
| [SIFT](https://arxiv.org/abs/2609.19526), September 17, 2026 | Pairwise LLM judging with regularized Bradley–Terry ranking reduces expensive evaluation demand in reported experiments | Proposed only; no judge or paid calls added | Compare judge-guided vs existing racing at equal total cost; calibrate judge against actual tests; judge never grants certification |
| [Darwin Gödel Machine](https://arxiv.org/abs/2505.22954), May 29, 2025 | Diverse archives of empirically evaluated agent modifications | Existing lineage/archive mechanism is related but substantially narrower | Compare archive reuse against scratch while holding verification and budget fixed |
| [AlphaEvolve mathematical exploration](https://arxiv.org/abs/2511.02864), November 3, 2025 | LLM-driven executable construction search with automated evaluation | Existing program-search loop is bounded to trusted task families | Add a separately specified new family with independent oracle before claiming new capability |

Priority: collect matched evidence first; test Pareto survival; then assess replay screening. Reflective model-based mutation and SIFT need a validated model adapter and measured call/token cost. Adding every technique at once would prevent useful attribution.

## Run an ablation

On a Docker-capable host, from `recursive-ai`:

```python
from research.search_policy_evolution import run_search_policy_evolution

for selection in ("quality_diversity", "pareto"):
    report = run_search_policy_evolution(
        ".lab-state-pareto-ablation",
        train_goal="compound arithmetic",
        holdout_goal="sorted search",
        population=4, generations=2,
        development_replicates=2, holdout_replicates=6,
        base_seed=20260919, max_model_calls=0,
        parent_selection=selection,
    )
    print(selection, report["study_id"], report["sample_efficiency"],
          report["cross_family_holdout"]["paired_resource_evidence"])
```

This command is an executable diagnostic, not a prespecified independent replication study. The fixed sorted-search task family may share deterministic behavior across seeds; the statistical assumptions must be checked before interpreting significance. Holdouts compare each selected finalist with the immutable default, not directly with the other selector. Compare actual development costs too: saved trials alone are not evidence of better search quality.

## Verification

- 16 focused unit/controller tests passed locally on 2026-09-19, including both default and Pareto study paths.
- Deterministic fixtures show complementary specialists survive while dominated policies do not; six uniformly favorable independent pairs would yield 3/64 Holm-adjusted p for one changing metric, whereas one favorable pair is inconclusive.
- Fixtures and mocked studies validate mechanics only. No real capability gain or live-model result is claimed.
- Docker is absent locally. Real Docker validation is delegated to the branch workflow; its outcome must be checked separately.

Statistical reference: [SciPy binomial-test documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html). Implementation uses Python's standard library and adds no dependencies.
