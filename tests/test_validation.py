import json
from pathlib import Path

from redteam_benchmark.validation import render_suite_validation_markdown, validate_suite_file


def test_packaged_suite_validates_with_quality_warnings() -> None:
    path = Path("src/redteam_benchmark/datasets/suites/assistant_policy_core_1_0_0.json")

    report = validate_suite_file(path)
    markdown = render_suite_validation_markdown(report)

    assert report.valid
    assert report.suite_name == "assistant_policy_core"
    assert report.case_count == 12
    assert "Suite Validation Report" in markdown
    assert "fewer than 30 cases" in " ".join(report.warnings)


def test_suite_validator_rejects_duplicate_and_unsafe_cases(tmp_path: Path) -> None:
    suite_path = tmp_path / "bad_suite_1_0_0.json"
    suite_path.write_text(
        json.dumps(
            {
                "name": "bad_suite",
                "version": "1.0.0",
                "description": "Invalid test suite.",
                "cases": [
                    {
                        "template_id": "duplicate",
                        "category": "prompt injection",
                        "text": "This contains a step-by-step exploit placeholder.",
                        "metadata": {},
                    },
                    {
                        "template_id": "duplicate",
                        "category": "prompt injection",
                        "text": "This contains a step-by-step exploit placeholder.",
                        "metadata": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_suite_file(suite_path)

    assert not report.valid
    assert any("Duplicate template IDs" in item for item in report.errors)
    assert any("Unsafe actionable term" in item for item in report.errors)
