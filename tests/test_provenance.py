from pathlib import Path

from redteam_benchmark.agents.judge_agent import JudgeAgent, evaluator_identity_manifest
from redteam_benchmark.calibration import calibrate_judge, load_evaluator_dataset
from redteam_benchmark.provenance import (
    available,
    collect_runtime_metadata,
    collect_source_metadata,
    load_calibration_provenance,
    public_manifest_hash,
    sanitize_url,
    unavailable,
    validate_publishable_run,
)


def test_sanitize_url_removes_credentials_query_and_fragment() -> None:
    value = "https://user:secret@example.test:8443/v1?api_key=secret#token"

    assert sanitize_url(value) == "https://example.test:8443/v1"
    assert sanitize_url("mock") == "mock"


def test_missing_git_and_lock_have_explicit_reasons(tmp_path: Path) -> None:
    source = collect_source_metadata(tmp_path)
    runtime = collect_runtime_metadata(tmp_path)

    assert source["commit_sha"] == unavailable("not_a_git_repository")
    assert source["dirty_worktree"] == unavailable("not_a_git_repository")
    assert runtime["dependency_lock"]["sha256"] == unavailable("requirements.lock_not_found")


def test_calibration_provenance_requires_matching_judge(tmp_path: Path) -> None:
    report = calibrate_judge(JudgeAgent(), load_evaluator_dataset())
    report_path = tmp_path / "calibration.json"
    report_path.write_text(report.model_dump_json(), encoding="utf-8")

    identity = evaluator_identity_manifest(JudgeAgent())
    matching = load_calibration_provenance(str(report_path), expected_evaluator_identity=identity)
    mismatched_identity = {**identity, "implementation_sha256": "different"}
    mismatched = load_calibration_provenance(
        str(report_path), expected_evaluator_identity=mismatched_identity
    )

    assert matching["dataset"]["split"] == "calibration"
    assert matching["suitable_for_release_gates"] is True
    assert mismatched["reason"] == "evaluator_identity_mismatch"
    assert mismatched["identity_mismatches"] == ["implementation_sha256"]
    assert mismatched["suitable_for_release_gates"] is False


def test_publishability_warns_or_fails_without_mutating_evidence() -> None:
    provenance = {
        "git": {
            "commit_sha": unavailable("no_commit"),
            "dirty_worktree": available(True),
        },
        "target": {"revision": unavailable("not_supplied")},
        "runtime": {"dependency_lock": {"sha256": available("abc")}},
        "ordered_prompt_hashes": ["prompt-hash"],
        "evaluator_calibration": {"suitable_for_release_gates": False},
        "evaluation_methods": ["deterministic_policy_v2"],
    }

    warning_result = validate_publishable_run(provenance)
    strict_result = validate_publishable_run(provenance, strict=True)

    assert warning_result.publishable is False
    assert warning_result.errors == []
    assert "Git commit unavailable: no_commit." in warning_result.warnings
    assert "Suite version is missing." in warning_result.warnings
    assert "Rubric hash is missing." in warning_result.warnings
    assert strict_result.publishable is False
    assert strict_result.warnings == []
    assert strict_result.errors == warning_result.warnings


def test_fallback_observation_cannot_use_model_judge_calibration() -> None:
    provenance = {
        "git": {
            "commit_sha": available("commit-sha"),
            "dirty_worktree": available(False),
        },
        "target": {"revision": available("target-sha")},
        "runtime": {"dependency_lock": {"sha256": available("lock-sha")}},
        "suite": {"version": "2.0.0", "sha256": "suite-sha"},
        "rubric": {"version": "rubric-v2", "sha256": "rubric-sha"},
        "ordered_prompt_hashes": ["prompt-hash"],
        "evaluator_calibration": {
            "suitable_for_release_gates": True,
            "authorized_evaluation_method": "model_judge_with_deterministic_guardrails",
        },
        "evaluation_methods": ["deterministic_rule_based"],
    }

    validation = validate_publishable_run(provenance, strict=True)

    assert validation.publishable is False
    assert any("does not match" in reason for reason in validation.errors)


def test_manifest_hash_is_stable_and_sensitive() -> None:
    first = public_manifest_hash({"b": 2, "a": 1})
    second = public_manifest_hash({"a": 1, "b": 2})

    assert first == second
    assert first != public_manifest_hash({"a": 1, "b": 3})
