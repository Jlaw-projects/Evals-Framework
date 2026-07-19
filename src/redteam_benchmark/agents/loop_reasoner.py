"""Optional local-LLM reasoning stages for the governed audit loop."""

from __future__ import annotations

from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from redteam_benchmark.agents.agent_prompts import AGENT_PROMPTS, prompt_manifest


class CategoryBiasRecommendation(BaseModel):
    """One schema-friendly category weighting recommendation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    category: str = Field(min_length=1)
    weight: float = Field(ge=0.5, le=5.0)


class AgentStageOutput(BaseModel):
    """Strict shared output contract for every reasoning stage."""

    model_config = ConfigDict(extra="forbid", strict=True)

    summary: str = Field(min_length=1, max_length=2000)
    weak_categories: list[str] = Field(default_factory=list, max_length=32)
    recommended_bias: list[CategoryBiasRecommendation] = Field(default_factory=list)
    stop_recommended: bool = False
    risks: list[str] = Field(default_factory=list, max_length=32)
    rationale: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0.0, le=1.0)


class LoopAdvice(BaseModel):
    """Complete trace and final advisory output for one audit iteration."""

    stages: list[dict[str, Any]]
    final_bias: dict[str, float]
    stop_recommended: bool
    rationale: str
    prompt_manifest: dict[str, dict[str, str]]


class LoopReasoner(Protocol):
    def advise(
        self,
        *,
        metrics: dict[str, Any],
        prior_decision: dict[str, Any],
        allowed_categories: list[str],
    ) -> LoopAdvice:
        """Return bounded advisory output for one loop iteration."""


class OpenAICompatibleLoopReasoner:
    """Run governed reasoning stages on a local OpenAI-compatible model."""

    stage_order = ("observer", "diagnostician", "proposer", "challenger", "reviewer")

    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        max_tokens: int = 700,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    def advise(
        self,
        *,
        metrics: dict[str, Any],
        prior_decision: dict[str, Any],
        allowed_categories: list[str],
    ) -> LoopAdvice:
        context: dict[str, Any] = {
            "metrics": metrics,
            "deterministic_decision": prior_decision,
            "allowed_categories": allowed_categories,
            "prior_stages": [],
        }
        stages: list[dict[str, Any]] = []
        for stage_name in self.stage_order:
            output = self._run_stage(stage_name, context)
            normalized = self._normalize(output, allowed_categories)
            stage_record = {
                "stage": stage_name,
                "prompt": prompt_manifest()[stage_name],
                "output": normalized.model_dump(mode="json"),
            }
            stages.append(stage_record)
            context["prior_stages"].append(stage_record)
        final = AgentStageOutput.model_validate(stages[-1]["output"])
        return LoopAdvice(
            stages=stages,
            final_bias={item.category: item.weight for item in final.recommended_bias},
            stop_recommended=final.stop_recommended,
            rationale=final.rationale,
            prompt_manifest=prompt_manifest(),
        )

    def _run_stage(self, stage_name: str, context: dict[str, Any]) -> AgentStageOutput:
        prompt = AGENT_PROMPTS[stage_name]
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": prompt.messages(context),
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "governed_audit_stage_output",
                    "strict": True,
                    "schema": _agent_stage_json_schema(),
                },
            },
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
        return AgentStageOutput.model_validate_json(data["choices"][0]["message"]["content"])

    @staticmethod
    def _normalize(output: AgentStageOutput, allowed_categories: list[str]) -> AgentStageOutput:
        allowed = set(allowed_categories)
        bias = [
            CategoryBiasRecommendation(category=item.category, weight=item.weight)
            for item in output.recommended_bias
            if item.category in allowed
        ]
        weak_categories = [category for category in output.weak_categories if category in allowed]
        return output.model_copy(
            update={"recommended_bias": bias, "weak_categories": weak_categories}
        )


def _agent_stage_json_schema() -> dict[str, Any]:
    """Return an Ollama-compatible schema without dynamic object keys or references."""

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "weak_categories": {"type": "array", "items": {"type": "string"}},
            "recommended_bias": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "category": {"type": "string"},
                        "weight": {"type": "number", "minimum": 0.5, "maximum": 5.0},
                    },
                    "required": ["category", "weight"],
                },
            },
            "stop_recommended": {"type": "boolean"},
            "risks": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": [
            "summary",
            "weak_categories",
            "recommended_bias",
            "stop_recommended",
            "risks",
            "rationale",
            "confidence",
        ],
    }
