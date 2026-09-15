"""Preregistered verification pipeline for Frontier Discovery candidates.

"Verified" in this module means reproducibly verified under the exact preregistered
sandbox protocol. It does not mean an unrestricted claim about external reality,
and it never promotes code or capabilities into the recursive-AI capability ledger.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ast_validator import parse, validate
from research.frontier_discovery import DiscoveryLedger
from sandbox.runner import SandboxRunner

ENGINE = "verified-discovery-v1"
MAX_PLAN_BYTES = 2_000_000
MAX_CASES = 512
MAX_SUITES = 16
MAX_REPLICATES = 7
MAX_SOURCE_BYTES = 32_768
MAX_STEPS = 1_000_000


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    data = value if isinstance(value, (bytes, bytearray)) else _canonical(value).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _text(value: Any, name: str, *, limit: int = 4_000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{name} must not be empty")
    if len(text) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return text


def _positive_number(value: Any, name: str, *, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number <= 0 or number > maximum:
        raise ValueError(f"{name} must be in (0, {maximum}]")
    return number


def _positive_int(value: Any, name: str, *, maximum: int) -> int:
    if type(value) is not int or value <= 0 or value > maximum:
        raise ValueError(f"{name} must be an integer in [1, {maximum}]")
    return value


def _source(value: Any, name: str) -> str:
    text = _text(value, name, limit=MAX_SOURCE_BYTES)
    if len(text.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError(f"{name} exceeds {MAX_SOURCE_BYTES} bytes")
    return text


def _validated_source(source: str, entrypoint: str) -> tuple[str, str]:
    tree = parse(source)
    validate(tree)
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    if entrypoint not in names:
        raise ValueError(f"source does not define entrypoint {entrypoint!r}")
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    structural_hash = hashlib.sha256(
        ast.dump(tree, annotate_fields=True, include_attributes=False).encode("utf-8")
    ).hexdigest()
    return source_hash, structural_hash


def _cases(value: Any, name: str) -> tuple[tuple[Any, ...], ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty list")
    result = []
    for index, case in enumerate(value):
        if not isinstance(case, list):
            raise ValueError(f"{name}[{index}] must be a list of positional arguments")
        encoded = json.dumps(case, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 65_536:
            raise ValueError(f"{name}[{index}] exceeds 64 KiB")
        result.append(tuple(json.loads(encoded)))
    return tuple(result)


def _expected(value: Any, name: str, count: int) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f"{name} must contain exactly {count} outputs")
    if any(type(item) is not int for item in value):
        raise ValueError(f"{name} outputs must be integers")
    return tuple(value)


@dataclass(frozen=True)
class ExperimentSuite:
    name: str
    role: str
    cases: tuple[tuple[Any, ...], ...]
    expected_outputs: tuple[int, ...]


@dataclass(frozen=True)
class VerificationPlan:
    study_id: str
    candidate_id: str
    hypothesis: str
    entrypoint: str
    primary_source: str
    independent_source: str
    prediction: ExperimentSuite
    falsification_suites: tuple[ExperimentSuite, ...]
    replicates: int
    max_steps: int
    max_cpu_seconds: float
    max_peak_bytes: int


def _suite(raw: Any, name: str, role: str) -> ExperimentSuite:
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must be an object")
    cases = _cases(raw.get("cases"), f"{name}.cases")
    expected = _expected(raw.get("expected_outputs"), f"{name}.expected_outputs", len(cases))
    suite_name = _text(raw.get("name", role), f"{name}.name", limit=120)
    return ExperimentSuite(suite_name, role, cases, expected)


def parse_verification_plan(raw: Any) -> VerificationPlan:
    if not isinstance(raw, dict):
        raise ValueError("verification plan must be a JSON object")
    encoded = _canonical(raw).encode("utf-8")
    if len(encoded) > MAX_PLAN_BYTES:
        raise ValueError(f"verification plan exceeds {MAX_PLAN_BYTES} bytes")

    study_id = _text(raw.get("study_id"), "study_id", limit=120)
    candidate_id = _text(raw.get("candidate_id"), "candidate_id", limit=120)
    hypothesis = _text(raw.get("hypothesis"), "hypothesis", limit=4_000)
    entrypoint = _text(raw.get("entrypoint", "experiment"), "entrypoint", limit=120)
    if not entrypoint.isidentifier() or entrypoint.startswith("_"):
        raise ValueError("entrypoint must be a public Python identifier")

    primary_source = _source(raw.get("primary_source"), "primary_source")
    independent_source = _source(raw.get("independent_source"), "independent_source")
    primary_hash, primary_structure = _validated_source(primary_source, entrypoint)
    independent_hash, independent_structure = _validated_source(independent_source, entrypoint)
    if primary_hash == independent_hash or primary_structure == independent_structure:
        raise ValueError("independent_source must be structurally distinct from primary_source")

    prediction = _suite(raw.get("prediction"), "prediction", "prediction")
    falsification_raw = raw.get("falsification_suites")
    if not isinstance(falsification_raw, list) or not falsification_raw:
        raise ValueError("falsification_suites must be a non-empty list")
    if len(falsification_raw) > MAX_SUITES:
        raise ValueError(f"falsification_suites exceeds {MAX_SUITES} suites")
    falsification = tuple(
        _suite(item, f"falsification_suites[{index}]", "falsification")
        for index, item in enumerate(falsification_raw)
    )
    total_cases = len(prediction.cases) + sum(len(suite.cases) for suite in falsification)
    if total_cases > MAX_CASES:
        raise ValueError(f"verification plan exceeds {MAX_CASES} total cases")

    replicates = _positive_int(raw.get("replicates", 3), "replicates", maximum=MAX_REPLICATES)
    if replicates < 3:
        raise ValueError("replicates must be at least 3")
    max_steps = _positive_int(raw.get("max_steps", 500_000), "max_steps", maximum=MAX_STEPS)
    max_cpu_seconds = _positive_number(raw.get("max_cpu_seconds", 1.0), "max_cpu_seconds", maximum=3.0)
    max_peak_bytes = _positive_int(raw.get("max_peak_bytes", 32_000_000), "max_peak_bytes", maximum=64_000_000)

    return VerificationPlan(
        study_id=study_id,
        candidate_id=candidate_id,
        hypothesis=hypothesis,
        entrypoint=entrypoint,
        primary_source=primary_source,
        independent_source=independent_source,
        prediction=prediction,
        falsification_suites=falsification,
        replicates=replicates,
        max_steps=max_steps,
        max_cpu_seconds=max_cpu_seconds,
        max_peak_bytes=max_peak_bytes,
    )


def _load_candidate(state_root: Path, plan: VerificationPlan) -> tuple[dict[str, Any], dict[str, Any]]:
    frontier_root = state_root / "frontier-discovery"
    ledger = DiscoveryLedger(frontier_root / "ledger.jsonl")
    if not ledger.verify():
        raise ValueError("frontier discovery ledger failed integrity verification")

    report_path = frontier_root / plan.study_id / "report.json"
    if not report_path.is_file():
        raise ValueError("frontier discovery report does not exist")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("study_id") != plan.study_id:
        raise ValueError("frontier discovery study id mismatch")
    if report.get("verification_status") != "unverified_candidates_only":
        raise ValueError("candidate report has an unexpected verification status")

    matches = [
        candidate
        for candidate in report.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("id") == plan.candidate_id
    ]
    if len(matches) != 1:
        raise ValueError("candidate id is missing or ambiguous")
    candidate = matches[0]
    if plan.hypothesis != candidate.get("statement"):
        raise ValueError("hypothesis must exactly match the frontier candidate statement")

    ledger_record_hash = report.get("ledger_record_hash")
    anchored = False
    if ledger.path.exists():
        for line in ledger.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if (
                record.get("record_hash") == ledger_record_hash
                and record.get("study_id") == plan.study_id
                and plan.candidate_id in record.get("candidate_ids", [])
            ):
                anchored = True
                break
    if not anchored:
        raise ValueError("candidate is not anchored by the frontier discovery ledger")
    return report, candidate


def _suite_payload(suite: ExperimentSuite) -> dict[str, Any]:
    return {
        "name": suite.name,
        "role": suite.role,
        "case_count": len(suite.cases),
        "expected_sha256": _sha256(list(suite.expected_outputs)),
    }


def _protocol_payload(plan: VerificationPlan, candidate: dict[str, Any]) -> dict[str, Any]:
    primary_hash, primary_structure = _validated_source(plan.primary_source, plan.entrypoint)
    independent_hash, independent_structure = _validated_source(plan.independent_source, plan.entrypoint)
    return {
        "engine": ENGINE,
        "study_id": plan.study_id,
        "candidate_id": plan.candidate_id,
        "candidate_statement_sha256": _sha256(candidate.get("statement")),
        "hypothesis": plan.hypothesis,
        "entrypoint": plan.entrypoint,
        "primary_source_sha256": primary_hash,
        "primary_structure_sha256": primary_structure,
        "independent_source_sha256": independent_hash,
        "independent_structure_sha256": independent_structure,
        "prediction": {
            **_suite_payload(plan.prediction),
            "cases_sha256": _sha256([list(case) for case in plan.prediction.cases]),
        },
        "falsification_suites": [
            {
                **_suite_payload(suite),
                "cases_sha256": _sha256([list(case) for case in suite.cases]),
            }
            for suite in plan.falsification_suites
        ],
        "replicates": plan.replicates,
        "max_steps": plan.max_steps,
        "max_cpu_seconds": plan.max_cpu_seconds,
        "max_peak_bytes": plan.max_peak_bytes,
    }


def _execute_impl(
    runner: Any,
    source: str,
    source_label: str,
    entrypoint: str,
    suite: ExperimentSuite,
    plan: VerificationPlan,
) -> tuple[dict[str, Any], tuple[tuple[int, ...], ...]]:
    source_hash, structure_hash = _validated_source(source, entrypoint)
    expected = list(suite.expected_outputs)
    output_sets: list[tuple[int, ...]] = []
    records = []
    for replicate in range(plan.replicates):
        result = runner.execute(
            source,
            [list(case) for case in suite.cases],
            entrypoint=entrypoint,
            max_steps=plan.max_steps,
        )
        outputs = result.get("outputs")
        if not isinstance(outputs, list) or len(outputs) != len(expected) or any(type(x) is not int for x in outputs):
            raise RuntimeError("invalid sandbox experiment outputs")
        cpu = result.get("cpu_seconds")
        peak = result.get("peak_bytes")
        if type(cpu) not in (int, float) or not math.isfinite(cpu) or cpu < 0:
            raise RuntimeError("invalid sandbox CPU measurement")
        if type(peak) not in (int, float) or not math.isfinite(peak) or peak < 0:
            raise RuntimeError("invalid sandbox memory measurement")
        output_tuple = tuple(outputs)
        output_sets.append(output_tuple)
        records.append(
            {
                "replicate": replicate,
                "outputs_sha256": _sha256(outputs),
                "matches_preregistered_prediction": outputs == expected,
                "cpu_seconds": float(cpu),
                "peak_bytes": int(peak),
                "resource_bounds_passed": cpu <= plan.max_cpu_seconds and peak <= plan.max_peak_bytes,
            }
        )
    deterministic = len(set(output_sets)) == 1
    summary = {
        "implementation": source_label,
        "source_sha256": source_hash,
        "structure_sha256": structure_hash,
        "deterministic": deterministic,
        "all_match_preregistered_prediction": all(record["matches_preregistered_prediction"] for record in records),
        "resource_bounds_passed": all(record["resource_bounds_passed"] for record in records),
        "replicates": records,
    }
    return summary, tuple(output_sets)


def _evaluate_suite(
    runner: Any,
    plan: VerificationPlan,
    suite: ExperimentSuite,
) -> dict[str, Any]:
    primary, primary_outputs = _execute_impl(
        runner, plan.primary_source, "primary", plan.entrypoint, suite, plan
    )
    independent, independent_outputs = _execute_impl(
        runner, plan.independent_source, "independent", plan.entrypoint, suite, plan
    )
    implementations_deterministic = primary["deterministic"] and independent["deterministic"]
    resource_bounds_passed = primary["resource_bounds_passed"] and independent["resource_bounds_passed"]
    independent_agreement = (
        implementations_deterministic
        and bool(primary_outputs)
        and bool(independent_outputs)
        and primary_outputs[0] == independent_outputs[0]
    )
    consensus_matches_prediction = (
        independent_agreement
        and primary["all_match_preregistered_prediction"]
        and independent["all_match_preregistered_prediction"]
    )
    return {
        "name": suite.name,
        "role": suite.role,
        "case_count": len(suite.cases),
        "expected_sha256": _sha256(list(suite.expected_outputs)),
        "primary": primary,
        "independent": independent,
        "implementations_deterministic": implementations_deterministic,
        "independent_agreement": independent_agreement,
        "resource_bounds_passed": resource_bounds_passed,
        "consensus_matches_preregistered_prediction": consensus_matches_prediction,
    }


def _status(suites: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    deterministic = all(suite["implementations_deterministic"] for suite in suites)
    resources = all(suite["resource_bounds_passed"] for suite in suites)
    agreement = all(suite["independent_agreement"] for suite in suites)
    prediction = suites[0]["consensus_matches_preregistered_prediction"]
    falsification = all(suite["consensus_matches_preregistered_prediction"] for suite in suites[1:])
    gates = [
        {"name": "replication_determinism", "passed": deterministic},
        {"name": "resource_bounds", "passed": resources},
        {"name": "independent_implementation_agreement", "passed": agreement},
        {"name": "preregistered_prediction", "passed": prediction},
        {"name": "adversarial_falsification", "passed": falsification},
    ]
    if not deterministic or not resources or not agreement:
        return "inconclusive", gates
    if not prediction or not falsification:
        return "rejected", gates
    return "verified_under_protocol", gates


def run_verified_discovery(
    state_root: str | Path,
    *,
    plan_path: str | Path,
    image: str = "recursive-ai-runner:local",
    runner: Any | None = None,
) -> dict[str, Any]:
    """Verify one Frontier candidate under a preregistered, replicated protocol.

    The protocol is hash-committed to an append-only ledger *before* any sandbox
    experiment runs. Passing produces a scoped verified-knowledge record; it never
    mutates the capability ledger or executes experiment code on the host.
    """
    root = Path(state_root).resolve()
    path = Path(plan_path).expanduser().resolve()
    raw_bytes = path.read_bytes()
    if len(raw_bytes) > MAX_PLAN_BYTES:
        raise ValueError(f"verification plan exceeds {MAX_PLAN_BYTES} bytes")
    raw = json.loads(raw_bytes)
    plan = parse_verification_plan(raw)
    frontier_report, candidate = _load_candidate(root, plan)

    verified_root = root / "verified-discovery"
    verified_root.mkdir(parents=True, exist_ok=True)
    ledger = DiscoveryLedger(verified_root / "ledger.jsonl")
    if not ledger.verify():
        raise ValueError("verified-discovery ledger failed integrity verification")

    protocol = _protocol_payload(plan, candidate)
    protocol_sha = _sha256(protocol)
    created_at = datetime.now(timezone.utc).isoformat()
    verification_id = _sha256(
        {
            "protocol_sha256": protocol_sha,
            "created_at": created_at,
            "nonce": uuid.uuid4().hex,
        }
    )[:24]
    attempt_dir = verified_root / verification_id
    attempt_dir.mkdir(parents=False, exist_ok=False)
    (attempt_dir / "protocol.json").write_text(
        json.dumps(protocol, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    started = ledger.append(
        {
            "event": "verification_preregistered",
            "created_at": created_at,
            "verification_id": verification_id,
            "study_id": plan.study_id,
            "candidate_id": plan.candidate_id,
            "protocol_sha256": protocol_sha,
            "capability_promotion": False,
        }
    )

    active_runner = runner if runner is not None else SandboxRunner(image)
    suites: list[dict[str, Any]] = []
    execution_error_type = None
    try:
        active_runner.boot()
        for suite in (plan.prediction, *plan.falsification_suites):
            suites.append(_evaluate_suite(active_runner, plan, suite))
        status, gates = _status(suites)
    except Exception as error:
        status = "inconclusive"
        execution_error_type = type(error).__name__
        gates = [
            {"name": "sandbox_execution", "passed": False, "error_type": execution_error_type}
        ]

    completed_at = datetime.now(timezone.utc).isoformat()
    report = {
        "verification_id": verification_id,
        "engine": ENGINE,
        "created_at": created_at,
        "completed_at": completed_at,
        "study_id": plan.study_id,
        "candidate_id": plan.candidate_id,
        "candidate_kind": candidate.get("kind"),
        "candidate_score": candidate.get("score"),
        "candidate_statement": candidate.get("statement"),
        "candidate_statement_sha256": _sha256(candidate.get("statement")),
        "frontier_report_ledger_record_hash": frontier_report.get("ledger_record_hash"),
        "protocol_sha256": protocol_sha,
        "preregistration_record_hash": started["record_hash"],
        "verification_status": status,
        "scope": "reproducibly verified only under this preregistered computational protocol",
        "gates": gates,
        "suites": suites,
        "execution_error_type": execution_error_type,
        "capability_promotion": False,
    }
    report_payload_sha = _sha256(report)
    completed = ledger.append(
        {
            "event": "verification_completed",
            "created_at": completed_at,
            "verification_id": verification_id,
            "study_id": plan.study_id,
            "candidate_id": plan.candidate_id,
            "protocol_sha256": protocol_sha,
            "preregistration_record_hash": started["record_hash"],
            "verification_status": status,
            "report_payload_sha256": report_payload_sha,
            "capability_promotion": False,
        }
    )
    envelope = {
        "report": report,
        "report_payload_sha256": report_payload_sha,
        "completion_record_hash": completed["record_hash"],
        "ledger_verified": ledger.verify(),
    }
    (attempt_dir / "report.json").write_text(
        json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    knowledge_record_hash = None
    if status == "verified_under_protocol":
        knowledge = DiscoveryLedger(verified_root / "verified_knowledge.jsonl")
        if not knowledge.verify():
            raise ValueError("verified-knowledge ledger failed integrity verification")
        record = knowledge.append(
            {
                "event": "knowledge_verified_under_protocol",
                "created_at": completed_at,
                "verification_id": verification_id,
                "study_id": plan.study_id,
                "candidate_id": plan.candidate_id,
                "candidate_kind": candidate.get("kind"),
                "candidate_statement": candidate.get("statement"),
                "candidate_statement_sha256": _sha256(candidate.get("statement")),
                "protocol_sha256": protocol_sha,
                "verification_completion_record_hash": completed["record_hash"],
                "scope": "preregistered computational protocol",
                "capability_promotion": False,
            }
        )
        knowledge_record_hash = record["record_hash"]

    envelope["verified_knowledge_record_hash"] = knowledge_record_hash
    return envelope


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Preregister, replicate, falsify, and independently verify a Frontier candidate."
    )
    parser.add_argument("--state", default=str(Path(__file__).parents[1] / ".lab-state"))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--image", default="recursive-ai-runner:local")
    args = parser.parse_args(argv)
    result = run_verified_discovery(args.state, plan_path=args.plan, image=args.image)
    print(json.dumps(result, indent=2, sort_keys=True))
    status = result["report"]["verification_status"]
    return 0 if status == "verified_under_protocol" else 2


if __name__ == "__main__":
    raise SystemExit(main())
