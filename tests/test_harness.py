from redteam_benchmark.adapters import (
    MiniMaxChatAdapter,
    MockModelAdapter,
    OllamaGenerateAdapter,
    OpenAIChatAdapter,
    make_model_adapter,
)
from redteam_benchmark.agents.judge_agent import JudgeAgent
from redteam_benchmark.harness import BenchmarkHarness, HarnessConfig, RetryPolicy
from redteam_benchmark.suites import load_suite, prompt_hash


def test_suite_hash_is_stable_and_prompt_metadata_is_reproducible() -> None:
    suite = load_suite("safety_core", "1.0.0")
    harness = BenchmarkHarness(
        adapter=MockModelAdapter(),
        judge=JudgeAgent(),
        config=HarnessConfig(random_seed=123),
        suite=suite,
    )

    prompts = harness.build_prompts("run_test", 2)

    assert suite.stable_hash == load_suite("safety_core", "1.0.0").stable_hash
    assert prompts[0].metadata["suite_id"] == "safety_core@1.0.0"
    assert prompts[0].metadata["suite_hash"] == suite.stable_hash
    assert prompts[0].metadata["random_seed"] == 123
    assert prompts[0].metadata["prompt_hash"] == prompt_hash(prompts[0].text)


def test_prompt_expansion_uses_seeded_sampling_order() -> None:
    suite = load_suite("safety_core", "1.0.0")
    first = BenchmarkHarness(
        adapter=MockModelAdapter(),
        judge=JudgeAgent(),
        config=HarnessConfig(random_seed=1),
        suite=suite,
    ).build_prompts("run_test", 6)
    repeated = BenchmarkHarness(
        adapter=MockModelAdapter(),
        judge=JudgeAgent(),
        config=HarnessConfig(random_seed=1),
        suite=suite,
    ).build_prompts("run_test", 6)
    different = BenchmarkHarness(
        adapter=MockModelAdapter(),
        judge=JudgeAgent(),
        config=HarnessConfig(random_seed=2),
        suite=suite,
    ).build_prompts("run_test", 6)

    first_order = [prompt.metadata["template_id"] for prompt in first]
    repeated_order = [prompt.metadata["template_id"] for prompt in repeated]
    different_order = [prompt.metadata["template_id"] for prompt in different]

    assert first_order == repeated_order
    assert first_order != different_order


def test_assistant_policy_suite_loads_expected_policy_metadata() -> None:
    suite = load_suite("assistant_policy_core", "1.0.0")

    assert suite.stable_id == "assistant_policy_core@1.0.0"
    assert suite.rubric_version == "assistant-policy-rubric.v1"
    assert len(suite.cases) >= 10
    assert all(case.metadata.get("expected_behavior") for case in suite.cases)
    assert all(case.metadata.get("failure_signal") for case in suite.cases)


def test_harness_records_partial_failure_without_losing_prompt() -> None:
    class FailingAdapter:
        model_name = "failing-model"

        def generate(self, prompt):
            raise RuntimeError("temporary transport failure")

    harness = BenchmarkHarness(
        adapter=FailingAdapter(),
        judge=JudgeAgent(),
        config=HarnessConfig(retry_policy=RetryPolicy(max_retries=0)),
    )
    prompt = harness.build_prompts("run_test", 1)[0]

    result = harness.evaluate_prompt("run_test", prompt)

    assert result.error is not None
    assert result.response.prompt_id == prompt.id
    assert result.score.total_score == 0
    assert result.score.raw["error"]["type"] == "RuntimeError"


def test_adapter_factory_supports_ollama_and_minimax_targets() -> None:
    ollama = make_model_adapter(
        model_name="qwen2.5:3b",
        base_url="ollama",
        temperature=0.1,
        max_tokens=128,
        api_key=None,
        ollama_base_url="http://localhost:11434",
    )
    minimax = make_model_adapter(
        model_name="MiniMax-M3",
        base_url="minimax",
        temperature=0.1,
        max_tokens=128,
        api_key=None,
        minimax_api_key="test-key",
    )
    ollama_compatible = make_model_adapter(
        model_name="local-model",
        base_url="http://localhost:11434/v1",
        temperature=0.1,
        max_tokens=128,
        api_key=None,
    )

    assert isinstance(ollama, OllamaGenerateAdapter)
    assert isinstance(ollama_compatible, OpenAIChatAdapter)
    assert isinstance(minimax, MiniMaxChatAdapter)
