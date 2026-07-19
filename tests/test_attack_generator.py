from redteam_benchmark.agents.attack_generator import AttackGeneratorAgent
from redteam_benchmark.policies.safety_policy import DISALLOWED_ACTIONABLE_TERMS


def test_attack_generator_creates_safe_prompt_count() -> None:
    prompts = AttackGeneratorAgent().generate(num_prompts=12, run_id="run_test")

    assert len(prompts) == 12
    assert all(prompt.run_id == "run_test" for prompt in prompts)
    assert {prompt.metadata["source"] for prompt in prompts} == {"attack_generator"}


def test_attack_generator_prompts_are_non_actionable() -> None:
    prompts = AttackGeneratorAgent().generate(num_prompts=20)
    disallowed = {term.lower() for term in DISALLOWED_ACTIONABLE_TERMS}

    for prompt in prompts:
        lowered = prompt.text.lower()
        assert "placeholder" in lowered
        assert not any(term in lowered for term in disallowed)


def test_attack_generator_uses_category_bias() -> None:
    prompts = AttackGeneratorAgent().generate(
        num_prompts=4,
        category_bias={"roleplay bypass": 4.0},
    )

    categories = [prompt.category.value for prompt in prompts]
    assert categories.count("roleplay bypass") >= 2
