"""Deterministic benchmark harness for suite execution and evaluation."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from redteam_benchmark.adapters import (
    ModelAdapter,
    adapter_response_to_record,
)
from redteam_benchmark.agents.judge_agent import JudgeAgent
from redteam_benchmark.database import new_id
from redteam_benchmark.schemas import ModelResponseRecord, PromptRecord, ScoreRecord
from redteam_benchmark.suites import SuiteDefinition, expand_suite_cases, load_suite


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 1
    backoff_seconds: float = 0.1
    fail_fast: bool = False


@dataclass(frozen=True)
class HarnessConfig:
    suite_name: str = "safety_core"
    suite_version: str = "2.0.0"
    random_seed: int = 0
    concurrency: int = 8
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    allow_repeated_prompts: bool = False


@dataclass(frozen=True)
class EvaluationRecord:
    prompt: PromptRecord
    response: ModelResponseRecord
    score: ScoreRecord
    error: dict[str, Any] | None = None


class BenchmarkHarness:
    """Execute benchmark prompt cases through adapters and evaluators."""

    def __init__(
        self,
        adapter: ModelAdapter,
        judge: JudgeAgent,
        config: HarnessConfig | None = None,
        suite: SuiteDefinition | None = None,
    ) -> None:
        self.adapter = adapter
        self.judge = judge
        self.config = config or HarnessConfig()
        self.suite = suite or load_suite(self.config.suite_name, self.config.suite_version)

    def suite_metadata(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite.name,
            "suite_version": self.suite.version,
            "suite_id": self.suite.stable_id,
            "suite_hash": self.suite.stable_hash,
            "rubric_version": self.suite.rubric_version,
            "random_seed": self.config.random_seed,
            "concurrency": self.config.concurrency,
            "retry_policy": {
                "max_retries": self.config.retry_policy.max_retries,
                "backoff_seconds": self.config.retry_policy.backoff_seconds,
                "fail_fast": self.config.retry_policy.fail_fast,
            },
            "allow_repeated_prompts": self.config.allow_repeated_prompts,
        }

    def build_prompts(
        self, run_id: str, num_prompts: int, category_bias: dict[str, float] | None = None
    ) -> list[PromptRecord]:
        return expand_suite_cases(
            self.suite,
            num_prompts=num_prompts,
            run_id=run_id,
            random_seed=self.config.random_seed,
            category_bias=category_bias,
            allow_repeats=self.config.allow_repeated_prompts,
        )

    def evaluate_prompts(self, run_id: str, prompts: list[PromptRecord]) -> list[EvaluationRecord]:
        max_workers = min(self.config.concurrency, max(1, len(prompts)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(lambda prompt: self.evaluate_prompt(run_id, prompt), prompts))

    def evaluate_prompt(self, run_id: str, prompt: PromptRecord) -> EvaluationRecord:
        attempts = self.config.retry_policy.max_retries + 1
        last_error: dict[str, Any] | None = None
        for attempt in range(1, attempts + 1):
            try:
                adapter_response = self.adapter.generate(prompt)
                response = adapter_response_to_record(
                    run_id=run_id,
                    prompt=prompt,
                    model_name=self.adapter.model_name,
                    adapter_response=adapter_response,
                )
                score = self.judge.score(run_id, prompt, response)
                score.raw["harness"] = {
                    "attempt": attempt,
                    "suite_id": prompt.metadata.get("suite_id"),
                    "template_id": prompt.metadata.get("template_id"),
                    "prompt_hash": prompt.metadata.get("prompt_hash"),
                }
                return EvaluationRecord(prompt=prompt, response=response, score=score)
            except Exception as exc:
                last_error = {
                    "attempt": attempt,
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
                if self.config.retry_policy.fail_fast or attempt == attempts:
                    break
                time.sleep(self.config.retry_policy.backoff_seconds * attempt)

        response = ModelResponseRecord(
            id=new_id("resp"),
            run_id=run_id,
            prompt_id=prompt.id,
            model_name=self.adapter.model_name,
            text="",
            latency_ms=0.0,
            raw={"error": last_error, "adapter": "error"},
        )
        score = ScoreRecord(
            id=new_id("score"),
            run_id=run_id,
            prompt_id=prompt.id,
            response_id=response.id,
            safety_compliance=0,
            refusal_quality=0,
            helpfulness_within_safe_limits=0,
            leakage_resistance=0,
            policy_consistency=0,
            total_score=0,
            rationale="Target model call failed; this evaluation is unevaluable.",
            judge_model="harness-error",
            raw={
                "error": last_error,
                "evaluation_status": "infrastructure_error",
                "harness": {"partial_failure": True},
            },
        )
        if self.config.retry_policy.fail_fast:
            raise RuntimeError(last_error)  # pragma: no cover - defensive guard
        return EvaluationRecord(prompt=prompt, response=response, score=score, error=last_error)
