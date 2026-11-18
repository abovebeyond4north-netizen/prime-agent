"""Fail-closed identity and resource preflight for external verification.

This module never runs an external verifier.  It binds a proposed run and any
cached receipt to the benchmark revision, runtime image, dataset,
predictions/patches and evaluator inputs so a harness cache with a weaker key
cannot silently stand in for fresh evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Iterable


PROTOCOL = "external-verifier-preflight-7"


def digest_files(paths: Iterable[Path], *, role: str, workspace_root: Path) -> str:
    digest = hashlib.sha256()
    if not role or role.strip() != role:
        raise ValueError("file role must be a nonempty canonical string")
    root = workspace_root.resolve()
    if not root.is_dir():
        raise ValueError(f"workspace root is not a directory: {root}")
    resolved = [Path(path).resolve() for path in paths]
    if not resolved:
        raise ValueError("at least one file is required")
    entries = []
    names = set()
    for path in resolved:
        if not path.is_file():
            raise ValueError(f"not a regular file: {path}")
        content = path.read_bytes()
        try:
            name = path.relative_to(root).as_posix()
        except ValueError as error:
            raise ValueError(f"file is outside workspace root: {path}") from error
        if name in names:
            raise ValueError(f"duplicate canonical file name: {name}")
        names.add(name)
        entries.append(
            {
                "role": role,
                "path": name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        )
    for entry in sorted(entries, key=lambda item: item["path"]):
        digest.update(json.dumps(entry, sort_keys=True, separators=(",", ":")).encode())
    return digest.hexdigest()


def digest_evaluator_bundles(
    paths: Iterable[Path],
    *,
    dependencies: Iterable[Path] = (),
    workspace_root: Path,
) -> str:
    """Bind evaluator entry points and explicitly declared immutable dependencies."""
    root = workspace_root.resolve()
    if not root.is_dir():
        raise ValueError(f"workspace root is not a directory: {root}")
    entry_points = [Path(path).resolve() for path in paths]
    if not entry_points:
        raise ValueError("at least one evaluator is required")
    for entry_point in entry_points:
        if not entry_point.is_file():
            raise ValueError(f"not a regular file: {entry_point}")
        try:
            entry_point.relative_to(root)
        except ValueError as error:
            raise ValueError(f"file is outside workspace root: {entry_point}") from error

    files = set(entry_points)
    for dependency in (Path(path).resolve() for path in dependencies):
        try:
            dependency.relative_to(root)
        except ValueError as error:
            raise ValueError(f"evaluator dependency is outside workspace root: {dependency}") from error
        if dependency.is_symlink():
            raise ValueError(f"evaluator dependency is a symbolic link: {dependency}")
        if not dependency.is_file():
            raise ValueError(
                f"evaluator dependency must be an explicit regular file: {dependency}"
            )
        files.add(dependency)
    return digest_files(files, role="evaluator-bundle", workspace_root=root)


def evaluation_identity(
    *,
    benchmark_revision: str,
    runtime_image_digest: str,
    workspace_root: Path,
    datasets: Iterable[Path],
    predictions: Path,
    evaluators: Iterable[Path],
    evaluator_dependencies: Iterable[Path] = (),
) -> dict[str, str]:
    revision = benchmark_revision.strip()
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise ValueError("benchmark revision must be a full lowercase 40-character SHA")
    image_digest = runtime_image_digest.strip()
    if not image_digest.startswith("sha256:") or len(image_digest) != 71:
        raise ValueError("runtime image digest must be sha256 followed by 64 lowercase hex characters")
    if any(character not in "0123456789abcdef" for character in image_digest[7:]):
        raise ValueError("runtime image digest must be sha256 followed by 64 lowercase hex characters")
    identity = {
        "protocol": PROTOCOL,
        "benchmark_revision": revision,
        "runtime_image_digest": image_digest,
        "dataset_sha256": digest_files(
            datasets, role="dataset", workspace_root=workspace_root
        ),
        "predictions_sha256": digest_files(
            (predictions,), role="predictions", workspace_root=workspace_root
        ),
        "evaluator_sha256": digest_evaluator_bundles(
            evaluators,
            dependencies=evaluator_dependencies,
            workspace_root=workspace_root,
        ),
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    identity["evaluation_sha256"] = hashlib.sha256(payload).hexdigest()
    identity["run_id"] = f"nucleus-{identity['evaluation_sha256'][:24]}"
    return identity


def cache_decision(
    receipt: dict[str, object] | None,
    identity: dict[str, str],
    *,
    result: Path | None = None,
    workspace_root: Path,
) -> dict[str, object]:
    if receipt is None:
        return {"reusable": False, "reasons": ["cache receipt absent"]}
    reasons = []
    for key in (
        "protocol",
        "benchmark_revision",
        "runtime_image_digest",
        "dataset_sha256",
        "predictions_sha256",
        "evaluator_sha256",
        "evaluation_sha256",
        "run_id",
    ):
        if receipt.get(key) != identity[key]:
            reasons.append(f"{key} mismatch")
    expected_result = receipt.get("result_sha256")
    if result is None:
        reasons.append("result file absent")
    elif not isinstance(expected_result, str) or not expected_result:
        reasons.append("result digest absent")
    elif digest_files(
        (result,), role="result", workspace_root=workspace_root
    ) != expected_result:
        reasons.append("result digest mismatch")
    return {"reusable": not reasons, "reasons": reasons}


def resource_preflight(path: Path, *, minimum_free_gib: int = 60) -> dict[str, object]:
    if minimum_free_gib <= 0:
        raise ValueError("minimum free space must be positive")
    free_bytes = shutil.disk_usage(path).free
    docker = shutil.which("docker")
    python_ok = sys.version_info >= (3, 11)
    checks = {
        "python_3_11_or_newer": python_ok,
        "docker_cli_available": docker is not None,
        "minimum_free_space": free_bytes >= minimum_free_gib * 1024**3,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "python": platform.python_version(),
        "machine": platform.machine(),
        "docker_cli": docker,
        "free_bytes": free_bytes,
        "minimum_free_bytes": minimum_free_gib * 1024**3,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-revision", required=True)
    parser.add_argument("--runtime-image-digest", required=True)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--dataset", action="append", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--evaluator", action="append", required=True, type=Path)
    parser.add_argument(
        "--evaluator-dependency",
        action="append",
        default=[],
        type=Path,
        help="immutable evaluator dependency file; repeat for each file",
    )
    parser.add_argument("--cache-receipt", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--resource-path", type=Path, default=Path.cwd())
    parser.add_argument("--minimum-free-gib", type=int, default=60)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    identity = evaluation_identity(
        benchmark_revision=args.benchmark_revision,
        runtime_image_digest=args.runtime_image_digest,
        workspace_root=args.workspace_root,
        datasets=args.dataset,
        predictions=args.predictions,
        evaluators=args.evaluator,
        evaluator_dependencies=args.evaluator_dependency,
    )
    receipt = None
    if args.cache_receipt is not None:
        receipt = json.loads(args.cache_receipt.read_text())
        if not isinstance(receipt, dict):
            raise ValueError("cache receipt must be a JSON object")
    report = {
        "identity": identity,
        "cache": cache_decision(
            receipt,
            identity,
            result=args.result,
            workspace_root=args.workspace_root,
        ),
        "resources": resource_preflight(
            args.resource_path, minimum_free_gib=args.minimum_free_gib
        ),
        "external_verifier_executed": False,
        "limits": [
            "This preflight does not install or execute an external verifier.",
            "Resource readiness does not establish evaluator correctness or independence.",
            "The runtime digest binds cache identity but does not prove that image was executed.",
            "Evaluator hashing covers entry points and declared dependency files, not undeclared dependencies.",
            "A reusable receipt proves identity continuity, not that its result is correct.",
        ],
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
