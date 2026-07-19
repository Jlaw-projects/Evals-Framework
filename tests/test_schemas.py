import pytest
from pydantic import ValidationError

from redteam_benchmark.schemas import PromptCategory, RunCreate, ScoreRecord


def test_run_create_accepts_model_alias_and_field_name() -> None:
    from_alias = RunCreate(model="mock-safe-model", base_url="mock")
    from_field = RunCreate(model_name="mock-safe-model", base_url="mock")

    assert from_alias.model_name == from_field.model_name == "mock-safe-model"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("num_prompts", 0),
        ("num_prompts", 1001),
        ("temperature", -0.1),
        ("temperature", 2.1),
        ("max_tokens", 0),
        ("max_tokens", 4097),
        ("concurrency", 0),
        ("concurrency", 65),
        ("max_retries", -1),
        ("max_retries", 11),
        ("retry_backoff_seconds", -0.1),
        ("retry_backoff_seconds", 30.1),
    ],
)
def test_run_create_rejects_out_of_bounds_values(field: str, value: int | float) -> None:
    with pytest.raises(ValidationError):
        RunCreate(**{field: value})


@pytest.mark.parametrize("score_field", ["safety_compliance", "total_score"])
def test_score_record_rejects_out_of_bounds_scores(score_field: str) -> None:
    payload = {
        "id": "score_test",
        "run_id": "run_test",
        "prompt_id": "prompt_test",
        "response_id": "resp_test",
        "safety_compliance": 5,
        "refusal_quality": 5,
        "helpfulness_within_safe_limits": 5,
        "leakage_resistance": 5,
        "policy_consistency": 5,
        "total_score": 25,
        "rationale": "safe",
    }
    payload[score_field] = 26 if score_field == "total_score" else 6

    with pytest.raises(ValidationError):
        ScoreRecord(**payload)


def test_prompt_category_parses_public_value() -> None:
    assert PromptCategory("prompt injection") == PromptCategory.PROMPT_INJECTION
