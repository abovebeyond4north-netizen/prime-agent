"""Bounded frontier-discovery utilities.

This module finds *candidate* anomalies, contradictions, and cross-domain analogies.
It deliberately does not execute candidate code, browse the network, or promote
discoveries into the recursive-AI capability ledger.  Outputs remain hypotheses
until independently verified.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import math
import re
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MAX_ITEMS = 5_000
MAX_KNOWN_PATTERNS = 512
MAX_SIGNATURE_TOKENS = 32
MAX_PAIR_CANDIDATES = 50_000
TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _probability(value: Any, name: str) -> float:
    number = _finite(value, name)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]")
    return number


def _bounded_text(value: Any, name: str, *, allow_empty: bool = False, limit: int = 2_000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    text = value.strip()
    if not allow_empty and not text:
        raise ValueError(f"{name} must not be empty")
    if len(text) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return text


def _tokens(text: str) -> frozenset[str]:
    return frozenset(TOKEN_RE.findall(text.lower()))


def _signature(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    if len(value) > MAX_SIGNATURE_TOKENS:
        raise ValueError(f"{name} exceeds {MAX_SIGNATURE_TOKENS} entries")
    result: list[str] = []
    for index, token in enumerate(value):
        text = _bounded_text(token, f"{name}[{index}]", limit=80)
        normalized = TOKEN_RE.findall(text.lower())
        if not normalized:
            raise ValueError(f"{name}[{index}] contains no searchable token")
        for part in normalized:
            if part not in result:
                result.append(part)
                if len(result) > MAX_SIGNATURE_TOKENS:
                    raise ValueError(f"{name} expands beyond {MAX_SIGNATURE_TOKENS} tokens")
    return tuple(result)


@dataclass(frozen=True)
class Claim:
    id: str
    subject: str
    relation: str
    object: str
    polarity: bool
    confidence: float
    source: str
    domain: str
    signature: tuple[str, ...]


@dataclass(frozen=True)
class Observation:
    id: str
    expected: float
    observed: float
    uncertainty: float
    source: str
    domain: str
    signature: tuple[str, ...]
    prior_probability: float | None = None
    posterior_probability: float | None = None


@dataclass(frozen=True)
class Candidate:
    id: str
    kind: str
    statement: str
    score: float
    components: dict[str, float]
    evidence_ids: tuple[str, ...]
    domains: tuple[str, ...]
    verification_status: str = "candidate"


@dataclass(frozen=True)
class FrontierInput:
    claims: tuple[Claim, ...]
    observations: tuple[Observation, ...]
    known_patterns: tuple[frozenset[str], ...]


def _claim(raw: Any, index: int) -> Claim:
    if not isinstance(raw, dict):
        raise ValueError(f"claims[{index}] must be an object")
    polarity = raw.get("polarity", True)
    if not isinstance(polarity, bool):
        raise ValueError(f"claims[{index}].polarity must be boolean")
    return Claim(
        id=_bounded_text(raw.get("id", f"claim-{index}"), f"claims[{index}].id", limit=120),
        subject=_bounded_text(raw.get("subject"), f"claims[{index}].subject"),
        relation=_bounded_text(raw.get("relation"), f"claims[{index}].relation"),
        object=_bounded_text(raw.get("object"), f"claims[{index}].object"),
        polarity=polarity,
        confidence=_probability(raw.get("confidence", 0.5), f"claims[{index}].confidence"),
        source=_bounded_text(raw.get("source", "unspecified"), f"claims[{index}].source", limit=500),
        domain=_bounded_text(raw.get("domain", "unspecified"), f"claims[{index}].domain", limit=120).lower(),
        signature=_signature(raw.get("signature"), f"claims[{index}].signature"),
    )


def _observation(raw: Any, index: int) -> Observation:
    if not isinstance(raw, dict):
        raise ValueError(f"observations[{index}] must be an object")
    uncertainty = _finite(raw.get("uncertainty", 1.0), f"observations[{index}].uncertainty")
    if uncertainty <= 0.0:
        raise ValueError(f"observations[{index}].uncertainty must be > 0")
    prior = raw.get("prior_probability")
    posterior = raw.get("posterior_probability")
    if (prior is None) != (posterior is None):
        raise ValueError(
            f"observations[{index}] prior_probability and posterior_probability must be supplied together"
        )
    return Observation(
        id=_bounded_text(raw.get("id", f"observation-{index}"), f"observations[{index}].id", limit=120),
        expected=_finite(raw.get("expected"), f"observations[{index}].expected"),
        observed=_finite(raw.get("observed"), f"observations[{index}].observed"),
        uncertainty=uncertainty,
        source=_bounded_text(raw.get("source", "unspecified"), f"observations[{index}].source", limit=500),
        domain=_bounded_text(raw.get("domain", "unspecified"), f"observations[{index}].domain", limit=120).lower(),
        signature=_signature(raw.get("signature"), f"observations[{index}].signature"),
        prior_probability=None if prior is None else _probability(prior, f"observations[{index}].prior_probability"),
        posterior_probability=None if posterior is None else _probability(
            posterior, f"observations[{index}].posterior_probability"
        ),
    )


def parse_frontier_input(raw: Any) -> FrontierInput:
    if not isinstance(raw, dict):
        raise ValueError("frontier input must be a JSON object")
    claims_raw = raw.get("claims", [])
    observations_raw = raw.get("observations", [])
    known_raw = raw.get("known_patterns", [])
    if not isinstance(claims_raw, list) or not isinstance(observations_raw, list):
        raise ValueError("claims and observations must be lists")
    if len(claims_raw) + len(observations_raw) > MAX_ITEMS:
        raise ValueError(f"input exceeds {MAX_ITEMS} evidence items")
    if not isinstance(known_raw, list) or len(known_raw) > MAX_KNOWN_PATTERNS:
        raise ValueError(f"known_patterns must contain at most {MAX_KNOWN_PATTERNS} entries")
    claims = tuple(_claim(item, index) for index, item in enumerate(claims_raw))
    observations = tuple(_observation(item, index) for index, item in enumerate(observations_raw))
    identifiers = [item.id for item in (*claims, *observations)]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("evidence ids must be unique")
    patterns = []
    for index, pattern in enumerate(known_raw):
        text = _bounded_text(pattern, f"known_patterns[{index}]")
        patterns.append(_tokens(text))
    return FrontierInput(claims, observations, tuple(patterns))


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _bernoulli_kl(posterior: float, prior: float) -> float:
    epsilon = 1e-12
    p = min(1.0 - epsilon, max(epsilon, posterior))
    q = min(1.0 - epsilon, max(epsilon, prior))
    return p * math.log(p / q) + (1.0 - p) * math.log((1.0 - p) / (1.0 - q))


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


class FrontierDiscovery:
    """Generate bounded, provenance-bearing discovery candidates from structured evidence."""

    WEIGHTS = {
        "surprise": 0.24,
        "information_gain": 0.20,
        "novelty": 0.16,
        "explanatory_power": 0.10,
        "falsifiability": 0.12,
        "cross_domain": 0.10,
        "provenance": 0.08,
    }
    RISK_WEIGHT = 0.18

    def __init__(self, data: FrontierInput):
        self.data = data

    def _novelty(self, text: str, signature: Iterable[str] = ()) -> float:
        text_tokens = _tokens(text)
        signature_tokens = frozenset(signature)
        if not self.data.known_patterns:
            return 1.0
        maximum = 0.0
        for pattern in self.data.known_patterns:
            maximum = max(maximum, _jaccard(text_tokens, pattern))
            if signature_tokens:
                maximum = max(maximum, _jaccard(signature_tokens, pattern))
        return 1.0 - maximum

    def _score(self, **components: float) -> tuple[float, dict[str, float]]:
        normalized = {name: _clamp(components.get(name, 0.0)) for name in self.WEIGHTS}
        risk = _clamp(components.get("risk", 0.0))
        value = sum(self.WEIGHTS[name] * normalized[name] for name in self.WEIGHTS)
        value -= self.RISK_WEIGHT * risk
        normalized["risk"] = risk
        return round(_clamp(value), 8), {key: round(value, 8) for key, value in normalized.items()}

    def _candidate(
        self,
        kind: str,
        statement: str,
        evidence_ids: tuple[str, ...],
        domains: tuple[str, ...],
        **components: float,
    ) -> Candidate:
        score, normalized = self._score(**components)
        payload = {
            "kind": kind,
            "statement": statement,
            "evidence_ids": evidence_ids,
            "domains": domains,
        }
        return Candidate(
            id=_sha256(payload)[:20],
            kind=kind,
            statement=statement,
            score=score,
            components=normalized,
            evidence_ids=evidence_ids,
            domains=domains,
        )

    def contradiction_candidates(self) -> list[Candidate]:
        groups: dict[tuple[str, str, str], dict[bool, list[Claim]]] = defaultdict(lambda: {True: [], False: []})
        for claim in self.data.claims:
            key = (claim.subject.casefold(), claim.relation.casefold(), claim.object.casefold())
            groups[key][claim.polarity].append(claim)

        candidates = []
        for (subject, relation, obj), polarities in groups.items():
            positives, negatives = polarities[True], polarities[False]
            if not positives or not negatives:
                continue
            positive = max(positives, key=lambda item: (item.confidence, item.id))
            negative = max(negatives, key=lambda item: (item.confidence, item.id))
            independent = 1.0 if positive.source.casefold() != negative.source.casefold() else 0.45
            confidence = min(positive.confidence, negative.confidence)
            cross_domain = 1.0 if positive.domain != negative.domain else 0.0
            statement = (
                f"Resolve contradiction: evidence both supports and rejects "
                f"'{subject} {relation} {obj}'."
            )
            candidates.append(
                self._candidate(
                    "contradiction",
                    statement,
                    (positive.id, negative.id),
                    tuple(sorted({positive.domain, negative.domain})),
                    surprise=confidence,
                    information_gain=confidence * independent,
                    novelty=self._novelty(statement, (*positive.signature, *negative.signature)),
                    explanatory_power=0.65,
                    falsifiability=1.0,
                    cross_domain=cross_domain,
                    provenance=(positive.confidence + negative.confidence) * 0.5 * independent,
                    risk=1.0 - independent * confidence,
                )
            )
        return candidates

    def residual_candidates(self) -> list[Candidate]:
        signature_counts: dict[tuple[str, ...], int] = defaultdict(int)
        for observation in self.data.observations:
            if observation.signature:
                signature_counts[observation.signature] += 1

        candidates = []
        for observation in self.data.observations:
            z = abs(observation.observed - observation.expected) / observation.uncertainty
            residual_surprise = 1.0 - math.exp(-z / 3.0)
            bayes_gain = 0.0
            if observation.prior_probability is not None and observation.posterior_probability is not None:
                bayes_gain = 1.0 - math.exp(
                    -_bernoulli_kl(observation.posterior_probability, observation.prior_probability)
                )
            surprise = max(residual_surprise, bayes_gain)
            repeated = signature_counts.get(observation.signature, 0)
            explanatory_power = 0.35 if not observation.signature else min(1.0, 0.35 + 0.2 * repeated)
            statement = (
                f"Investigate residual for {observation.id}: observed={observation.observed:g}, "
                f"expected={observation.expected:g}, standardized_residual={z:.3f}."
            )
            candidates.append(
                self._candidate(
                    "residual_anomaly",
                    statement,
                    (observation.id,),
                    (observation.domain,),
                    surprise=surprise,
                    information_gain=max(bayes_gain, residual_surprise * 0.75),
                    novelty=self._novelty(statement, observation.signature),
                    explanatory_power=explanatory_power,
                    falsifiability=1.0,
                    cross_domain=0.0,
                    provenance=0.9 if observation.source != "unspecified" else 0.55,
                    risk=0.1 if observation.source != "unspecified" else 0.35,
                )
            )
        return candidates

    def analogy_candidates(self, similarity_threshold: float = 0.5) -> list[Candidate]:
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be in [0, 1]")

        items: list[tuple[str, str, str, tuple[str, ...]]] = []
        for claim in self.data.claims:
            if claim.signature:
                text = f"{claim.subject} {claim.relation} {claim.object}"
                items.append((claim.id, claim.domain, text, claim.signature))
        for observation in self.data.observations:
            if observation.signature:
                text = f"{observation.id} residual pattern"
                items.append((observation.id, observation.domain, text, observation.signature))

        inverted: dict[str, list[int]] = defaultdict(list)
        for index, (_, _, _, signature) in enumerate(items):
            for token in signature:
                inverted[token].append(index)

        pair_keys: set[tuple[int, int]] = set()
        for token in sorted(inverted):
            indices = inverted[token]
            for offset, left in enumerate(indices):
                left_domain = items[left][1]
                for right in indices[offset + 1 :]:
                    if left_domain == items[right][1]:
                        continue
                    pair = (left, right) if left < right else (right, left)
                    pair_keys.add(pair)
                    if len(pair_keys) >= MAX_PAIR_CANDIDATES:
                        break
                if len(pair_keys) >= MAX_PAIR_CANDIDATES:
                    break
            if len(pair_keys) >= MAX_PAIR_CANDIDATES:
                break

        candidates = []
        for left, right in sorted(pair_keys):
            left_id, left_domain, left_text, left_signature = items[left]
            right_id, right_domain, right_text, right_signature = items[right]
            similarity = _jaccard(left_signature, right_signature)
            if similarity < similarity_threshold:
                continue
            statement = (
                f"Test cross-domain analogy between {left_id} ({left_domain}) and "
                f"{right_id} ({right_domain}); structural_similarity={similarity:.3f}."
            )
            candidates.append(
                self._candidate(
                    "cross_domain_analogy",
                    statement,
                    (left_id, right_id),
                    tuple(sorted((left_domain, right_domain))),
                    surprise=0.55 * similarity,
                    information_gain=0.75 * similarity,
                    novelty=self._novelty(f"{left_text} {right_text}", (*left_signature, *right_signature)),
                    explanatory_power=similarity,
                    falsifiability=0.75,
                    cross_domain=1.0,
                    provenance=0.8,
                    risk=0.2,
                )
            )
        return candidates

    def discover(self, top_k: int = 20, similarity_threshold: float = 0.5) -> list[Candidate]:
        if not 1 <= top_k <= 100:
            raise ValueError("top_k must be in [1, 100]")
        candidates = (
            self.contradiction_candidates()
            + self.residual_candidates()
            + self.analogy_candidates(similarity_threshold)
        )
        return heapq.nlargest(top_k, candidates, key=lambda item: (item.score, item.id))


class DiscoveryLedger:
    """Append-only hash-chained candidate ledger for provenance and tamper detection."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid ledger JSON at line {line_number}") from error
            if not isinstance(record, dict):
                raise ValueError(f"invalid ledger record at line {line_number}")
            records.append(record)
        return records

    def verify(self) -> bool:
        previous_hash = "0" * 64
        for record in self._records():
            claimed = record.get("record_hash")
            payload = {key: value for key, value in record.items() if key != "record_hash"}
            if payload.get("previous_hash") != previous_hash:
                return False
            computed = _sha256(payload)
            if claimed != computed:
                return False
            previous_hash = computed
        return True

    def append(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.verify():
            raise ValueError("refusing to append to an invalid discovery ledger")
        records = self._records()
        previous_hash = records[-1]["record_hash"] if records else "0" * 64
        record = dict(payload)
        record["previous_hash"] = previous_hash
        record["record_hash"] = _sha256(record)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(record) + "\n")
        return record


def _demo_input() -> dict[str, Any]:
    return {
        "claims": [
            {
                "id": "demo-claim-a",
                "subject": "system-x",
                "relation": "requires",
                "object": "condition-y",
                "polarity": True,
                "confidence": 0.88,
                "source": "demo-source-a",
                "domain": "domain-a",
                "signature": ["threshold", "feedback", "phase-change"],
            },
            {
                "id": "demo-claim-b",
                "subject": "system-x",
                "relation": "requires",
                "object": "condition-y",
                "polarity": False,
                "confidence": 0.82,
                "source": "demo-source-b",
                "domain": "domain-b",
                "signature": ["threshold", "feedback", "phase-change"],
            },
        ],
        "observations": [
            {
                "id": "demo-observation",
                "expected": 10.0,
                "observed": 14.5,
                "uncertainty": 1.0,
                "source": "demo-instrument",
                "domain": "domain-c",
                "signature": ["threshold", "feedback", "phase-change"],
                "prior_probability": 0.2,
                "posterior_probability": 0.75,
            }
        ],
        "known_patterns": ["linear proportional response"],
    }


def run_frontier_discovery(
    state_root: str | Path,
    *,
    input_path: str | Path | None = None,
    top_k: int = 20,
    similarity_threshold: float = 0.5,
) -> dict[str, Any]:
    """Run one bounded study and persist only candidate-level evidence.

    No candidate is marked verified by this function. Verification must happen in
    a separate evaluation or experiment.
    """
    root = Path(state_root).resolve()
    destination = root / "frontier-discovery"
    destination.mkdir(parents=True, exist_ok=True)

    if input_path is None:
        raw = _demo_input()
        source = {"kind": "built-in-demo", "path": None}
    else:
        path = Path(input_path).expanduser().resolve()
        raw = json.loads(path.read_text(encoding="utf-8"))
        source = {"kind": "json-file", "path": str(path)}

    data = parse_frontier_input(raw)
    candidates = FrontierDiscovery(data).discover(top_k=top_k, similarity_threshold=similarity_threshold)
    input_hash = _sha256(raw)
    study_id = _sha256(
        {
            "input_hash": input_hash,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold,
            "engine": "frontier-discovery-v1",
        }
    )[:24]
    report = {
        "study_id": study_id,
        "engine": "frontier-discovery-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "input_sha256": input_hash,
        "evidence_count": len(data.claims) + len(data.observations),
        "candidate_count": len(candidates),
        "verification_status": "unverified_candidates_only",
        "candidates": [asdict(candidate) for candidate in candidates],
        "limits": {
            "max_items": MAX_ITEMS,
            "max_pair_candidates": MAX_PAIR_CANDIDATES,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold,
        },
    }

    study_dir = destination / study_id
    study_dir.mkdir(parents=True, exist_ok=True)
    report_path = study_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    ledger = DiscoveryLedger(destination / "ledger.jsonl")
    ledger_record = ledger.append(
        {
            "event_id": uuid.uuid4().hex,
            "created_at": report["created_at"],
            "study_id": study_id,
            "input_sha256": input_hash,
            "candidate_ids": [candidate.id for candidate in candidates],
            "verification_status": "unverified_candidates_only",
            "candidate_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        }
    )
    report["ledger_record_hash"] = ledger_record["record_hash"]
    report["ledger_verified"] = ledger.verify()
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for isolated frontier studies."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Find bounded, unverified frontier candidates from structured evidence."
    )
    parser.add_argument("--state", default=str(Path(__file__).parents[1] / ".lab-state"))
    parser.add_argument("--input", dest="input_path")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--similarity-threshold", type=float, default=0.5)
    args = parser.parse_args(argv)
    report = run_frontier_discovery(
        args.state,
        input_path=args.input_path,
        top_k=args.top_k,
        similarity_threshold=args.similarity_threshold,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
