"""Credential-safe run provenance and publishability validation."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field

from redteam_benchmark.calibration import CalibrationReport

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DEPENDENCIES = (
    "alembic",
    "fastapi",
    "httpx",
    "matplotlib",
    "pandas",
    "pydantic",
    "sqlalchemy",
    "typer",
    "uvicorn",
)


class PublishableRunValidation(BaseModel):
    strict: bool
    publishable: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "value": None, "reason": reason}


def available(value: Any) -> dict[str, Any]:
    return {"available": True, "value": value, "reason": None}


def sanitize_url(value: str | None) -> str | None:
    """Strip URL credentials, query parameters, and fragments from stored metadata."""

    if value is None or "://" not in value:
        return value
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def collect_source_metadata(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Inspect Git directly and retain an explicit reason when immutable state is unavailable."""

    git_dir = project_root / ".git"
    if not git_dir.exists():
        return {
            "commit_sha": unavailable("not_a_git_repository"),
            "dirty_worktree": unavailable("not_a_git_repository"),
        }
    commit = _git(project_root, "rev-parse", "HEAD")
    if commit is None:
        commit_metadata = unavailable("repository_has_no_commits_or_invalid_head")
    else:
        commit_metadata = available(commit)
    status = _git(project_root, "status", "--porcelain", "--untracked-files=normal")
    dirty_metadata = (
        unavailable("git_status_unavailable") if status is None else available(bool(status))
    )
    return {"commit_sha": commit_metadata, "dirty_worktree": dirty_metadata}


def collect_runtime_metadata(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    try:
        package_version = metadata.version("agentic-llm-redteam-benchmark")
    except metadata.PackageNotFoundError:
        package_version = "editable_or_uninstalled"
    lock_path = project_root / "requirements.lock"
    lock_metadata = (
        available(_sha256_file(lock_path))
        if lock_path.exists()
        else unavailable("requirements.lock_not_found")
    )
    return {
        "package_version": package_version,
        "python_version": platform.python_version(),
        "dependency_versions": {
            dependency: _package_version(dependency) for dependency in RUNTIME_DEPENDENCIES
        },
        "dependency_lock": {
            "path": "requirements.lock",
            "sha256": lock_metadata,
        },
    }


def load_calibration_provenance(
    report_path: str | None,
    *,
    expected_evaluator_identity: dict[str, Any],
) -> dict[str, Any]:
    """Load only declared calibration fields; never copy arbitrary report content."""

    if not report_path:
        return {
            "available": False,
            "reason": "calibration_report_not_supplied",
            "suitable_for_release_gates": False,
        }
    path = Path(report_path)
    try:
        report = CalibrationReport.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {
            "available": False,
            "reason": f"invalid_calibration_report:{type(exc).__name__}",
            "suitable_for_release_gates": False,
        }
    identity_mismatches = sorted(
        key
        for key in set(report.evaluator_identity) | set(expected_evaluator_identity)
        if report.evaluator_identity.get(key) != expected_evaluator_identity.get(key)
    )
    identity_matches = not identity_mismatches
    observed_methods_match = report.observed_evaluation_methods == [
        report.authorized_evaluation_method
    ]
    method_evidence_valid = observed_methods_match and report.fallback_evaluations == 0
    promoted = (
        report.promotion.suitable_for_release_gates and identity_matches and method_evidence_valid
    )
    if not identity_matches:
        reason = "evaluator_identity_mismatch"
    elif not method_evidence_valid:
        reason = "calibration_observed_method_not_authorized"
    else:
        reason = None
    return {
        "available": True,
        "reason": reason,
        "identity_mismatches": identity_mismatches,
        "evaluator_identity": report.evaluator_identity,
        "judge_model": report.judge_model,
        "rubric_version": report.rubric_version,
        "rubric_hash": report.rubric_hash,
        "authorized_evaluation_method": report.authorized_evaluation_method,
        "observed_evaluation_methods": report.observed_evaluation_methods,
        "evaluation_method_counts": report.evaluation_method_counts,
        "fallback_evaluations": report.fallback_evaluations,
        "fallback_evaluation_rate": report.fallback_evaluation_rate,
        "infrastructure_errors": report.infrastructure_errors,
        "infrastructure_error_rate": report.infrastructure_error_rate,
        "dataset": {
            "name": report.dataset.name,
            "version": report.dataset.version,
            "split": report.dataset.split.value,
            "sha256": report.dataset.sha256,
            "annotation_status": report.dataset.annotation_status,
            "independent_review": report.dataset.independent_review,
        },
        "promotion_status": report.promotion.status,
        "suitable_for_release_gates": promoted,
    }


def validate_publishable_run(
    provenance: dict[str, Any], *, strict: bool = False
) -> PublishableRunValidation:
    """Warn or fail when a run lacks the provenance required for publication."""

    issues: list[str] = []
    git = provenance.get("git", {})
    commit = git.get("commit_sha", {})
    dirty = git.get("dirty_worktree", {})
    if not commit.get("available"):
        issues.append(f"Git commit unavailable: {commit.get('reason', 'unknown')}.")
    if not dirty.get("available"):
        issues.append(f"Dirty-worktree state unavailable: {dirty.get('reason', 'unknown')}.")
    elif dirty.get("value"):
        issues.append("Git worktree is dirty.")
    target_revision = provenance.get("target", {}).get("revision", {})
    if not target_revision.get("available"):
        issues.append(
            f"Target model revision unavailable: {target_revision.get('reason', 'unknown')}."
        )
    lock_hash = provenance.get("runtime", {}).get("dependency_lock", {}).get("sha256", {})
    if not lock_hash.get("available"):
        issues.append(f"Dependency lock hash unavailable: {lock_hash.get('reason', 'unknown')}.")
    if not provenance.get("ordered_prompt_hashes"):
        issues.append("Ordered prompt hashes are missing.")
    suite = provenance.get("suite", {})
    if not _present(suite.get("version")):
        issues.append("Suite version is missing.")
    if not _present(suite.get("sha256")):
        issues.append("Suite hash is missing.")
    rubric = provenance.get("rubric", {})
    if not _present(rubric.get("version")):
        issues.append("Rubric version is missing.")
    if not _present(rubric.get("sha256")):
        issues.append("Rubric hash is missing.")
    calibration = provenance.get("evaluator_calibration", {})
    if not calibration.get("suitable_for_release_gates", False):
        issues.append(
            "Evaluator lacks a matching promoted calibration result; scores are experimental."
        )
    if calibration.get("evaluator_identity") != provenance.get("evaluator_identity"):
        issues.append("Run evaluator identity does not match the promoted calibration artifact.")
    if calibration.get("rubric_version") != rubric.get("version") or calibration.get(
        "rubric_hash"
    ) != rubric.get("sha256"):
        issues.append("Run rubric does not match the promoted calibration artifact.")
    methods = provenance.get("evaluation_methods", [])
    if len(methods) != 1:
        issues.append("A publishable run must use exactly one evaluator method.")
    elif methods[0] != calibration.get("authorized_evaluation_method"):
        issues.append(
            "Observed evaluator method does not match the method authorized by calibration."
        )
    if strict:
        return PublishableRunValidation(
            strict=True, publishable=not issues, errors=issues, warnings=[]
        )
    return PublishableRunValidation(
        strict=False,
        publishable=not issues,
        errors=[],
        warnings=issues,
    )


def public_manifest_hash(payload: dict[str, Any]) -> str:
    """Hash a credential-free manifest."""

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value != "unavailable"


def _git(project_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _package_version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "unavailable"
