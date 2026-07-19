"""Pydantic schemas shared by agents, API routes, and reports."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PromptCategory(StrEnum):
    """Safe adversarial prompt categories used by the benchmark."""

    JAILBREAK_ATTEMPT = "jailbreak attempt"
    ROLEPLAY_BYPASS = "roleplay bypass"
    PROMPT_INJECTION = "prompt injection"
    POLICY_AMBIGUITY = "policy ambiguity"
    REFUSAL_CONSISTENCY = "refusal consistency"
    SYSTEM_PROMPT_LEAKAGE_ATTEMPT = "system prompt leakage attempt"
    IDENTITY_HONESTY = "identity honesty"
    TOOL_HONESTY = "tool honesty"
    CITATION_INTEGRITY = "citation integrity"
    IMAGE_LIMITATION_HONESTY = "image limitation honesty"
    CURRENT_INFO_UNCERTAINTY = "current-info uncertainty"
    COPYRIGHT_BOUNDARY = "copyright boundary"
    ARTIFACT_SAFETY = "artifact safety"
    MALICIOUS_REQUEST_REFUSAL = "malicious request refusal"
    PAST_CHAT_HONESTY = "past-chat honesty"
    WELLBEING_SAFETY = "wellbeing safety"


class RunStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunCreate(BaseModel):
    model_name: str = Field(default="mock-safe-model", alias="model")
    base_url: str = "mock"
    num_prompts: int = Field(default=10, ge=1, le=1000)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=4096)
    mutate_failures: bool = True
    suite_name: str = "safety_core"
    suite_version: str = "2.0.0"
    random_seed: int = 0
    concurrency: int = Field(default=8, ge=1, le=64)
    max_retries: int = Field(default=1, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=0.1, ge=0.0, le=30.0)
    timeout_seconds: float = Field(default=120.0, gt=0.0, le=3600.0)
    fail_fast: bool = False
    category_bias: dict[str, float] | None = None
    adapter_name: str = "auto"
    judge_name: str = "auto"
    mutator_name: str = "safe_reframe"
    allow_repeated_prompts: bool = False
    model_revision: str | None = None
    judge_model_revision: str | None = None
    calibration_report_path: str | None = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("base_url")
    @classmethod
    def reject_credentials_in_base_url(cls, value: str) -> str:
        """Credentials belong in headers or environment variables, never persisted URLs."""

        if "://" not in value:
            return value
        parsed = urlsplit(value)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(
                "base_url must not contain credentials, query parameters, or fragments"
            )
        return value


class ApiRunCreate(BaseModel):
    """Path-free public API contract; server configuration owns local resources."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    model_name: str = Field(default="mock-safe-model", alias="model")
    base_url: str = "mock"
    num_prompts: int = Field(default=10, ge=1, le=1000)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=4096)
    mutate_failures: bool = True
    suite_name: str = Field(default="safety_core", pattern=r"^[a-z][a-z0-9_]*$")
    suite_version: str = Field(default="2.0.0", pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    random_seed: int = 0
    concurrency: int = Field(default=8, ge=1, le=64)
    max_retries: int = Field(default=1, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=0.1, ge=0.0, le=30.0)
    timeout_seconds: float = Field(default=120.0, gt=0.0, le=3600.0)
    fail_fast: bool = False
    category_bias: dict[str, float] | None = None
    allow_repeated_prompts: bool = False
    model_revision: str | None = None
    judge_model_revision: str | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return RunCreate.reject_credentials_in_base_url(value)

    def to_internal(self, calibration_report_path: str | None) -> RunCreate:
        return RunCreate(
            **self.model_dump(mode="python", by_alias=True),
            calibration_report_path=calibration_report_path,
        )


class RunRecord(BaseModel):
    id: str
    model_name: str
    base_url: str
    num_prompts: int
    temperature: float
    max_tokens: int
    status: RunStatus
    created_at: datetime
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptRecord(BaseModel):
    id: str
    run_id: str | None = None
    category: PromptCategory
    text: str
    parent_prompt_id: str | None = None
    mutation_depth: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelResponseRecord(BaseModel):
    id: str
    run_id: str
    prompt_id: str
    model_name: str
    text: str
    latency_ms: float
    raw: dict[str, Any] = Field(default_factory=dict)


class ScoreRecord(BaseModel):
    id: str
    run_id: str
    prompt_id: str
    response_id: str
    safety_compliance: int = Field(ge=0, le=5)
    refusal_quality: int = Field(ge=0, le=5)
    helpfulness_within_safe_limits: int = Field(ge=0, le=5)
    leakage_resistance: int = Field(ge=0, le=5)
    policy_consistency: int = Field(ge=0, le=5)
    total_score: int = Field(ge=0, le=25)
    rationale: str
    judge_model: str = "rule-based"
    raw: dict[str, Any] = Field(default_factory=dict)


class PromptMutationRecord(BaseModel):
    id: str
    run_id: str
    source_prompt_id: str
    mutated_prompt_id: str
    strategy: str
    bypassed: bool | None = None


class RunResult(BaseModel):
    run: RunRecord
    prompts: list[PromptRecord]
    responses: list[ModelResponseRecord]
    scores: list[ScoreRecord]
    mutations: list[PromptMutationRecord]
