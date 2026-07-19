import json

from redteam_benchmark.agents import loop_reasoner
from redteam_benchmark.agents.agent_prompts import AGENT_PROMPTS, prompt_manifest
from redteam_benchmark.agents.audit_loop_agent import AuditLoopAgent
from redteam_benchmark.agents.loop_reasoner import LoopAdvice, OpenAICompatibleLoopReasoner


def test_agent_prompt_registry_is_versioned_and_injection_aware() -> None:
    manifest = prompt_manifest()

    assert set(manifest) == {"observer", "diagnostician", "proposer", "challenger", "reviewer"}
    assert all(len(item["hash"]) == 64 for item in manifest.values())
    messages = AGENT_PROMPTS["observer"].messages(
        {"allowed_categories": ["prompt injection"], "metrics": {"failure_count": 1}}
    )
    assert "untrusted" in messages[0]["content"].lower()
    assert "do not rename keys" in messages[0]["content"].lower()
    assert "UNTRUSTED_AUDIT_STATE_JSON=" in messages[1]["content"]


def test_local_reasoner_runs_governed_stage_pipeline(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            content = json.dumps(
                {
                    "summary": "A measured weakness remains.",
                    "weak_categories": ["prompt injection", "invented category"],
                    "recommended_bias": [
                        {"category": "prompt injection", "weight": 5.0},
                        {"category": "invented category", "weight": 4.0},
                    ],
                    "stop_recommended": False,
                    "risks": ["judge shortcut"],
                    "rationale": "Collect more bounded evidence.",
                    "confidence": 0.7,
                }
            )
            return {"choices": [{"message": {"content": content}}]}

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def post(self, _url, *, headers, json):
            calls.append(json)
            return FakeResponse()

    monkeypatch.setattr(loop_reasoner.httpx, "Client", FakeClient)
    advice = OpenAICompatibleLoopReasoner("local-reasoner", "http://localhost:11434/v1").advise(
        metrics={"failure_count": 2},
        prior_decision={"stop": False},
        allowed_categories=["prompt injection"],
    )

    assert len(calls) == 5
    assert all(call["response_format"]["type"] == "json_schema" for call in calls)
    assert all(call["response_format"]["json_schema"]["strict"] is True for call in calls)
    assert [stage["stage"] for stage in advice.stages] == [
        "observer",
        "diagnostician",
        "proposer",
        "challenger",
        "reviewer",
    ]
    assert advice.final_bias == {"prompt injection": 5.0}
    assert "invented category" not in advice.final_bias


def test_deterministic_guardrails_bound_agent_advice() -> None:
    advice = LoopAdvice(
        stages=[],
        final_bias={"prompt injection": 3.0},
        stop_recommended=True,
        rationale="Human review is appropriate.",
        prompt_manifest=prompt_manifest(),
    )
    deterministic = {
        "stop": False,
        "reason": "continue_targeting_weak_categories",
        "next_category_bias": {"roleplay bypass": 2.0},
    }

    before_minimum = AuditLoopAgent._apply_advice(
        advice,
        iteration=1,
        min_iterations=2,
        deterministic_decision=deterministic,
    )
    after_minimum = AuditLoopAgent._apply_advice(
        advice,
        iteration=2,
        min_iterations=2,
        deterministic_decision=deterministic,
    )

    assert before_minimum["stop"] is False
    assert before_minimum["next_category_bias"] == {"prompt injection": 3.0}
    assert after_minimum["stop"] is True
    assert after_minimum["human_review_required"] is True


def test_agent_cannot_override_hard_infrastructure_stop() -> None:
    advice = LoopAdvice(
        stages=[],
        final_bias={"prompt injection": 5.0},
        stop_recommended=False,
        rationale="Continue.",
        prompt_manifest=prompt_manifest(),
    )
    decision = AuditLoopAgent._apply_advice(
        advice,
        iteration=2,
        min_iterations=2,
        deterministic_decision={
            "stop": True,
            "reason": "infrastructure_errors_detected",
            "next_category_bias": {},
        },
    )

    assert decision["stop"] is True
    assert decision["reason"] == "infrastructure_errors_detected"
