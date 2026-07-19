"""Suite validation utilities for benchmark-card quality control."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from redteam_benchmark.policies.safety_policy import assert_safe_text
from redteam_benchmark.suites import SuiteDefinition, prompt_hash


@dataclass(frozen=True)
class SuiteValidationReport:
    suite_name: str | None
    suite_version: str | None
    case_count: int
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    category_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "suite_version": self.suite_version,
            "case_count": self.case_count,
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "category_counts": self.category_counts,
        }


def validate_suite_file(path: Path) -> SuiteValidationReport:
    """Validate a suite JSON file without requiring it to be packaged."""

    errors: list[str] = []
    warnings: list[str] = []
    suite: SuiteDefinition | None = None
    payload: dict[str, Any] = {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        suite = SuiteDefinition.model_validate(payload)
    except FileNotFoundError:
        return SuiteValidationReport(None, None, 0, False, [f"File not found: {path}"])
    except json.JSONDecodeError as exc:
        return SuiteValidationReport(None, None, 0, False, [f"Invalid JSON: {exc}"])
    except ValidationError as exc:
        errors.append(f"Schema validation failed: {exc}")

    suite_name = payload.get("name") if isinstance(payload, dict) else None
    suite_version = payload.get("version") if isinstance(payload, dict) else None
    cases_payload = payload.get("cases", []) if isinstance(payload, dict) else []

    if suite is None:
        return SuiteValidationReport(
            suite_name=suite_name,
            suite_version=suite_version,
            case_count=len(cases_payload) if isinstance(cases_payload, list) else 0,
            valid=False,
            errors=errors,
            warnings=warnings,
        )

    if not suite.cases:
        errors.append("Suite must contain at least one case.")

    expected_suffix = f"{suite.name}_{suite.version.replace('.', '_')}.json"
    if path.name != expected_suffix:
        warnings.append(f"Filename should be `{expected_suffix}` for packaged suite discovery.")

    template_ids = [case.template_id for case in suite.cases]
    duplicate_template_ids = sorted(
        item for item, count in Counter(template_ids).items() if count > 1
    )
    if duplicate_template_ids:
        errors.append(f"Duplicate template IDs: {', '.join(duplicate_template_ids)}")

    hashes = [prompt_hash(case.text.strip()) for case in suite.cases]
    duplicate_hashes = sorted(item for item, count in Counter(hashes).items() if count > 1)
    if duplicate_hashes:
        errors.append(f"Duplicate prompt hashes: {', '.join(duplicate_hashes)}")

    category_counts = Counter(case.category.value for case in suite.cases)
    if len(category_counts) < 3:
        warnings.append("Suite covers fewer than three categories.")
    if len(suite.cases) < 30:
        warnings.append("Suite has fewer than 30 cases; treat reports as smoke-test signals.")

    for case in suite.cases:
        try:
            assert_safe_text(case.text)
        except ValueError as exc:
            errors.append(f"{case.template_id}: {exc}")
        if not case.metadata.get("expected_behavior"):
            warnings.append(f"{case.template_id}: missing metadata.expected_behavior")
        if not case.metadata.get("failure_signal"):
            warnings.append(f"{case.template_id}: missing metadata.failure_signal")

    return SuiteValidationReport(
        suite_name=suite.name,
        suite_version=suite.version,
        case_count=len(suite.cases),
        valid=not errors,
        errors=errors,
        warnings=warnings,
        category_counts=dict(sorted(category_counts.items())),
    )


def render_suite_validation_markdown(report: SuiteValidationReport) -> str:
    status = "pass" if report.valid else "fail"
    category_rows = ["| Category | Cases |", "| --- | ---: |"]
    category_rows.extend(
        f"| {category} | {count} |" for category, count in report.category_counts.items()
    )
    errors = "\n".join(f"- {item}" for item in report.errors) or "None"
    warnings = "\n".join(f"- {item}" for item in report.warnings) or "None"
    return "\n".join(
        [
            "# Suite Validation Report",
            "",
            f"Status: `{status}`",
            f"Suite: `{report.suite_name or 'unknown'}@{report.suite_version or 'unknown'}`",
            f"Cases: `{report.case_count}`",
            "",
            "## Categories",
            "",
            *category_rows,
            "",
            "## Errors",
            "",
            errors,
            "",
            "## Warnings",
            "",
            warnings,
        ]
    )
