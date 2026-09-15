# Frontier Discovery

Frontier Discovery is a bounded research subsystem for locating **candidate** contradictions,
unexpected residuals, and cross-domain structural analogies in supplied evidence. It is
deliberately separated from capability promotion: nothing it emits is treated as a verified
discovery or executable self-modification.

## Why this boundary exists

The recursive-AI laboratory already separates proposal generation from trusted evaluation.
Frontier Discovery extends that principle to scientific/research hypotheses:

1. evidence is parsed and bounded;
2. deterministic detectors generate candidate hypotheses;
3. candidates receive an explicit evidence score;
4. provenance is written to a hash-chained ledger;
5. every result remains `unverified_candidates_only`;
6. a separate evaluator or experiment must verify a candidate before it can influence capability claims.

The module performs no network access and executes no content contained in evidence files.

## Input schema

Supply a JSON object with any combination of `claims`, `observations`, and `known_patterns`.

```json
{
  "claims": [
    {
      "id": "claim-1",
      "subject": "system-x",
      "relation": "requires",
      "object": "condition-y",
      "polarity": true,
      "confidence": 0.9,
      "source": "source-a",
      "domain": "biology",
      "signature": ["feedback", "threshold", "phase-change"]
    },
    {
      "id": "claim-2",
      "subject": "system-x",
      "relation": "requires",
      "object": "condition-y",
      "polarity": false,
      "confidence": 0.84,
      "source": "source-b",
      "domain": "economics",
      "signature": ["feedback", "threshold", "phase-change"]
    }
  ],
  "observations": [
    {
      "id": "observation-1",
      "expected": 10.0,
      "observed": 14.5,
      "uncertainty": 1.0,
      "source": "instrument-a",
      "domain": "physics",
      "signature": ["feedback", "threshold", "phase-change"],
      "prior_probability": 0.2,
      "posterior_probability": 0.75
    }
  ],
  "known_patterns": ["linear proportional response"]
}
```

`prior_probability` and `posterior_probability` are optional, but they must be supplied together.

## Detectors

### Contradiction mining

Claims are normalized into `(subject, relation, object)` groups. Opposite-polarity claims form a contradiction candidate. Independent sources receive more evidential weight than same-source disagreements.

Runtime is approximately `O(n)` in the number of claims.

### Residual mining

For each observation:

```text
standardized residual = abs(observed - expected) / uncertainty
```

The residual is converted to a bounded surprise score. When prior and posterior probabilities are available, Bernoulli KL divergence contributes a Bayesian-surprise term.

Runtime is `O(n)` in the number of observations.

### Cross-domain analogy mining

Structural `signature` tokens are indexed with an inverted index. Candidate pairs are created only when two items share at least one signature token and belong to different domains. Jaccard similarity is then evaluated for those sparse candidates.

This avoids an unconditional all-pairs scan. The implementation also caps pair generation at 50,000 candidates.

## Discovery score

Each candidate is scored from bounded components:

```text
score =
  0.24 * surprise
+ 0.20 * information_gain
+ 0.16 * novelty
+ 0.10 * explanatory_power
+ 0.12 * falsifiability
+ 0.10 * cross_domain
+ 0.08 * provenance
- 0.18 * risk
```

Every component is normalized to `[0, 1]`. Ranking uses `heapq.nlargest`, so selecting the top `k` candidates costs approximately `O(m log k)` rather than sorting every candidate.

The score is a prioritization heuristic, not proof.

## Provenance ledger

Each study is persisted under:

```text
<state>/frontier-discovery/<study-id>/report.json
```

and one event is appended to:

```text
<state>/frontier-discovery/ledger.jsonl
```

Ledger entries are SHA-256 hash chained. Before appending, the entire chain is verified; a tampered chain fails closed.

## Run

From `recursive-ai/`:

```bash
python -m research.frontier_discovery --state .lab-state --input evidence.json --top-k 20
```

Without `--input`, the module runs a small built-in demonstration dataset:

```bash
python -m research.frontier_discovery --state .lab-state --top-k 5
```

The demonstration is explicitly labeled `built-in-demo`; it is not presented as a real scientific discovery.

## Hard limits

- maximum evidence items: 5,000
- maximum known patterns: 512
- maximum signature tokens per item: 32
- maximum cross-domain candidate pairs: 50,000
- maximum returned candidates: 100
- no network access
- no execution of evidence content
- no capability promotion
- no claim is marked verified by this subsystem

A future verified-experiment layer can consume candidate IDs from the ledger and run domain-specific tests in the existing sandbox/evaluator architecture.
