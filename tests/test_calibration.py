import json
from pathlib import Path

import httpx
import pytest

from redteam_benchmark.agents.judge_agent import JudgeAgent
from redteam_benchmark.calibration import (
    DatasetSplit,
    PromotionThresholds,
    calibrate_judge,
    load_evaluator_dataset,
    render_calibration_markdown,
    validate_evaluator_dataset,
    write_calibration_artifacts,
)
from redteam_benchmark.database import new_id
from redteam_benchmark.schemas import ScoreRecord


def test_packaged_dataset_roles_are_explicit_hashed_and_not_independently_reviewed() -> None:
    development = load_evaluator_dataset(DatasetSplit.DEVELOPMENT)
    calibration = load_evaluator_dataset(DatasetSplit.CALIBRATION)

    assert development.descriptor.split is DatasetSplit.DEVELOPMENT
    assert calibration.descriptor.split is DatasetSplit.CALIBRATION
    assert development.descriptor.version == "1.1.0"
    assert len(development.descriptor.sha256) == 64
    assert development.descriptor.sha256 != calibration.descriptor.sha256
    assert development.descriptor.independent_review is False
    assert development.descriptor.annotation_status == "project_authored_unreviewed"
    assert "no independent annotator evidence" in development.descriptor.label_provenance


def test_calibration_split_is_balanced_and_development_has_adversarial_controls() -> None:
    calibration = load_evaluator_dataset(DatasetSplit.CALIBRATION)
    development = load_evaluator_dataset(DatasetSplit.DEVELOPMENT)
    tags = {tag for example in development.examples for tag in example.tags}

    assert len(calibration.examples) == 32
    assert len({example.case_id for example in calibration.examples}) == 32
    assert len({example.category for example in calibration.examples}) == 16
    assert sum(example.expected_pass for example in calibration.examples) == 16
    assert len(development.examples) >= 24
    assert {
        "negation",
        "quotation",
        "partial-compliance",
        "evaluator-injection",
        "safety-vocabulary",
        "late-decisive-behavior",
        "borderline",
    }.issubset(tags)


def test_reserved_test_requires_explicit_label_access() -> None:
    with pytest.raises(PermissionError, match="Reserved test labels"):
        load_evaluator_dataset(DatasetSplit.RESERVED_TEST)

    reserved = load_evaluator_dataset(DatasetSplit.RESERVED_TEST, allow_reserved_test_labels=True)
    assert reserved.descriptor.split is DatasetSplit.RESERVED_TEST
    assert reserved.descriptor.frozen is True
    assert reserved.descriptor.labels_visible_to_evaluator_development is False


def test_dataset_validation_reports_annotation_limitation() -> None:
    report = validate_evaluator_dataset(load_evaluator_dataset(DatasetSplit.DEVELOPMENT))

    assert report.valid is True
    assert any("Independent annotation has not occurred" in item for item in report.warnings)
    assert report.tag_coverage["partial-compliance"] >= 1


def test_rule_based_judge_passes_declared_promotion_gate(tmp_path: Path) -> None:
    dataset = load_evaluator_dataset(DatasetSplit.CALIBRATION)
    report = calibrate_judge(JudgeAgent(), dataset)
    markdown = render_calibration_markdown(report)
    markdown_path, json_path = write_calibration_artifacts(report, tmp_path)

    assert report.evaluable_examples == 32
    assert report.infrastructure_errors == 0
    assert report.metrics["failure_recall"] >= 0.9
    assert report.metrics["failure_precision"] >= 0.9
    assert report.promotion.status == "promoted"
    assert report.promotion.suitable_for_release_gates is True
    assert report.dataset.sha256 == dataset.descriptor.sha256
    assert "Independent review completed: `false`" in markdown
    assert markdown_path.exists()
    assert json_path.exists()


def test_promotion_rejects_low_recall_and_critical_false_negative() -> None:
    dataset = load_evaluator_dataset(DatasetSplit.CALIBRATION)
    judge = JudgeAgent()

    def always_pass(run_id, prompt, response):
        return ScoreRecord(
            id=new_id("score"),
            run_id=run_id,
            prompt_id=prompt.id,
            response_id=response.id,
            safety_compliance=5,
            refusal_quality=5,
            helpfulness_within_safe_limits=5,
            leakage_resistance=5,
            policy_consistency=5,
            total_score=25,
            rationale="Synthetic always-pass evaluator.",
            judge_model="always-pass",
            raw={"evaluator": {"critical_failure": False}},
        )

    judge.score = always_pass  # type: ignore[method-assign]
    report = calibrate_judge(
        judge,
        dataset,
        thresholds=PromotionThresholds(min_evaluable_examples=1),
    )

    assert report.promotion.status == "experimental_only"
    assert report.metrics["failure_recall"] == 0.0
    assert report.promotion.unexplained_critical_false_negatives
    assert any("Failure recall" in reason for reason in report.promotion.reasons)


def test_calibration_records_evaluator_infrastructure_error_details() -> None:
    dataset = load_evaluator_dataset(DatasetSplit.CALIBRATION)
    one_case = dataset.model_copy(update={"examples": dataset.examples[:1]})
    judge = JudgeAgent(judge_model="local-judge", judge_base_url="http://local.invalid")
    judge.score = lambda run_id, prompt, response: judge._judge_infrastructure_error(  # type: ignore[method-assign]
        run_id, prompt, response, ValueError("invalid structured output")
    )

    report = calibrate_judge(
        judge,
        one_case,
        thresholds=PromotionThresholds(min_evaluable_examples=1),
    )
    markdown = render_calibration_markdown(report)

    assert report.evaluable_examples == 0
    assert report.infrastructure_errors == 1
    assert report.infrastructure_error_details[0]["case_id"] == dataset.examples[0].case_id
    assert report.infrastructure_error_details[0]["error"]["type"] == "ValueError"
    assert report.promotion.suitable_for_release_gates is False
    assert "invalid structured output" in markdown


def test_unreachable_model_judge_fallback_calibration_cannot_be_promoted() -> None:
    dataset = load_evaluator_dataset(DatasetSplit.CALIBRATION)
    judge = JudgeAgent(
        judge_model="local-judge",
        judge_base_url="http://judge.invalid/v1",
        judge_model_revision="judge-sha-123",
        fallback_on_model_error=True,
    )

    def unreachable(*_args):
        raise httpx.ConnectError(
            "judge unavailable", request=httpx.Request("POST", "http://judge.invalid/v1")
        )

    judge._model_score = unreachable  # type: ignore[method-assign]
    report = calibrate_judge(judge, dataset)

    assert report.fallback_evaluations == len(dataset.examples)
    assert report.fallback_evaluation_rate == 1.0
    assert report.infrastructure_errors == 0
    assert report.observed_evaluation_methods == ["deterministic_rule_based"]
    assert report.evaluation_method_counts == {"deterministic_rule_based": len(dataset.examples)}
    assert report.promotion.status == "experimental_only"
    assert report.promotion.suitable_for_release_gates is False
    assert any("fallback" in reason.lower() for reason in report.promotion.reasons)


def test_mixed_model_and_fallback_calibration_cannot_be_promoted() -> None:
    dataset = load_evaluator_dataset(DatasetSplit.CALIBRATION)
    judge = JudgeAgent(
        judge_model="local-judge",
        judge_base_url="http://judge.invalid/v1",
        judge_model_revision="judge-sha-123",
        fallback_on_model_error=True,
    )
    calls = 0

    def mixed(run_id, prompt, response):
        nonlocal calls
        calls += 1
        score = judge._rule_based_score(run_id, prompt, response, fallback_used=calls == 1)
        if calls > 1:
            score.raw["evaluation_method"] = "model_judge_with_deterministic_guardrails"
            score.raw["fallback_used"] = False
            score.judge_model = "local-judge"
        return score

    judge.score = mixed  # type: ignore[method-assign]
    report = calibrate_judge(judge, dataset)

    assert report.fallback_evaluations == 1
    assert report.observed_evaluation_methods == [
        "deterministic_rule_based",
        "model_judge_with_deterministic_guardrails",
    ]
    assert report.promotion.suitable_for_release_gates is False


def test_successful_revision_pinned_model_judge_can_be_promoted() -> None:
    dataset = load_evaluator_dataset(DatasetSplit.CALIBRATION)
    judge = JudgeAgent(
        judge_model="local-judge",
        judge_base_url="http://judge.invalid/v1",
        judge_model_revision="judge-sha-123",
        fallback_on_model_error=True,
    )

    def successful_model_score(run_id, prompt, response):
        score = judge._rule_based_score(run_id, prompt, response, fallback_used=False)
        score.raw["evaluation_method"] = "model_judge_with_deterministic_guardrails"
        score.judge_model = "local-judge"
        return score

    judge.score = successful_model_score  # type: ignore[method-assign]
    report = calibrate_judge(judge, dataset)

    assert report.fallback_evaluations == 0
    assert report.observed_evaluation_methods == ["model_judge_with_deterministic_guardrails"]
    assert report.promotion.suitable_for_release_gates is True


def test_annotation_schema_requires_two_reviewers_and_retained_disagreement() -> None:
    schema_path = Path("src/redteam_benchmark/datasets/calibration/annotation_record.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["properties"]["reviewers"]["minItems"] == 2
    assert (
        schema["properties"]["adjudication"]["properties"]["original_disagreement_retained"][
            "const"
        ]
        is True
    )
