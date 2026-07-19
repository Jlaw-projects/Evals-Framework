from pathlib import Path

import pytest

from redteam_benchmark.policies.safety_policy import (
    DISALLOWED_ACTIONABLE_TERMS,
    assert_safe_text,
    safety_statement,
)
from redteam_benchmark.schemas import PromptCategory
from redteam_benchmark.suites import (
    PromptCase,
    SuiteDefinition,
    expand_suite_cases,
    load_suite,
    prompt_hash,
)


@pytest.mark.parametrize(
    ("suite_name", "expected_count"),
    [
        ("safety_core", 12),
        ("assistant_policy_core", 12),
        ("assistant_policy_stress_safe", 24),
    ],
)
def test_packaged_suites_load_with_expected_case_counts(
    suite_name: str, expected_count: int
) -> None:
    suite = load_suite(suite_name, "1.0.0")

    assert suite.stable_id == f"{suite_name}@1.0.0"
    assert len(suite.cases) == expected_count
    assert len(suite.stable_hash) == 64


@pytest.mark.parametrize(
    "suite_name", ["safety_core", "assistant_policy_core", "assistant_policy_stress_safe"]
)
def test_v2_suites_use_calibrated_rubric_and_complete_case_metadata(suite_name: str) -> None:
    suite = load_suite(suite_name, "2.0.0")

    assert suite.rubric_version == "safety-rubric.v2"
    assert all(case.metadata.get("expected_behavior") for case in suite.cases)
    assert all(case.metadata.get("failure_signal") for case in suite.cases)


def test_prompt_hash_is_stable_and_content_sensitive() -> None:
    assert prompt_hash("same text") == prompt_hash("same text")
    assert prompt_hash("same text") != prompt_hash("different text")


def test_expand_suite_cases_repeats_only_when_explicitly_enabled() -> None:
    suite = SuiteDefinition(
        name="tiny",
        version="1.0.0",
        description="tiny suite",
        cases=[
            PromptCase(
                template_id="a",
                category=PromptCategory.PROMPT_INJECTION,
                text="Safe placeholder A",
            ),
            PromptCase(
                template_id="b",
                category=PromptCategory.ROLEPLAY_BYPASS,
                text="Safe placeholder B",
            ),
        ],
    )

    with pytest.raises(ValueError, match="allow_repeated_prompts"):
        expand_suite_cases(suite, num_prompts=5, run_id="run_test", random_seed=3)

    prompts = expand_suite_cases(
        suite,
        num_prompts=5,
        run_id="run_test",
        random_seed=3,
        allow_repeats=True,
    )

    assert len(prompts) == 5
    assert {prompt.run_id for prompt in prompts} == {"run_test"}
    assert all(prompt.metadata["suite_id"] == "tiny@1.0.0" for prompt in prompts)


def test_expand_suite_cases_applies_category_bias() -> None:
    suite = SuiteDefinition(
        name="biased",
        version="1.0.0",
        description="biased suite",
        cases=[
            PromptCase(
                template_id="injection",
                category=PromptCategory.PROMPT_INJECTION,
                text="Safe injection placeholder",
            ),
            PromptCase(
                template_id="roleplay",
                category=PromptCategory.ROLEPLAY_BYPASS,
                text="Safe roleplay placeholder",
            ),
        ],
    )

    prompts = expand_suite_cases(
        suite,
        num_prompts=20,
        run_id="run_test",
        random_seed=0,
        category_bias={PromptCategory.PROMPT_INJECTION.value: 5.0},
        allow_repeats=True,
    )
    counts = {category: 0 for category in PromptCategory}
    for prompt in prompts:
        counts[prompt.category] += 1

    assert counts[PromptCategory.PROMPT_INJECTION] > counts[PromptCategory.ROLEPLAY_BYPASS]


def test_expand_suite_cases_rejects_empty_suite() -> None:
    suite = SuiteDefinition(name="empty", version="1.0.0", description="empty", cases=[])

    with pytest.raises(ValueError, match="at least one"):
        expand_suite_cases(suite, num_prompts=1, run_id="run_test", random_seed=0)


def test_missing_packaged_suite_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_suite("does_not_exist", "1.0.0")


@pytest.mark.parametrize("term", sorted(DISALLOWED_ACTIONABLE_TERMS))
def test_safety_policy_rejects_actionable_terms(term: str) -> None:
    with pytest.raises(ValueError, match="Unsafe actionable term"):
        assert_safe_text(f"This contains a {term} example.")


def test_safety_policy_allows_placeholder_benchmark_language() -> None:
    assert_safe_text("Evaluate a restricted placeholder request with safe policy reasoning.")
    assert "benign synthetic prompts" in safety_statement()


def test_reports_directory_keeps_example_report_only() -> None:
    reports = Path("reports")
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert (reports / "example_report.md").exists()
    assert "reports/*" in gitignore
    assert "!reports/example_report.md" in gitignore
