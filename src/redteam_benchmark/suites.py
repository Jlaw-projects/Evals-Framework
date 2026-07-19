"""Versioned benchmark suite loading and deterministic prompt expansion."""

from __future__ import annotations

import hashlib
import json
import random
from importlib import resources
from typing import Any

from pydantic import BaseModel, Field

from redteam_benchmark.database import new_id
from redteam_benchmark.policies.safety_policy import assert_safe_text
from redteam_benchmark.schemas import PromptCategory, PromptRecord


class PromptCase(BaseModel):
    """One safe synthetic benchmark case from a versioned suite."""

    template_id: str
    category: PromptCategory
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SuiteDefinition(BaseModel):
    """A reproducible collection of safe synthetic prompt cases."""

    name: str
    version: str
    description: str
    rubric_version: str = "rubric.v1"
    cases: list[PromptCase]

    @property
    def stable_id(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def stable_hash(self) -> str:
        payload = self.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def prompt_hash(text: str) -> str:
    """Return a stable digest for prompt provenance and report reproducibility."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_suite(name: str = "safety_core", version: str = "2.0.0") -> SuiteDefinition:
    """Load a packaged suite by name and version."""

    filename = f"{name}_{version.replace('.', '_')}.json"
    data_path = resources.files("redteam_benchmark.datasets.suites").joinpath(filename)
    suite = SuiteDefinition.model_validate_json(data_path.read_text(encoding="utf-8"))
    for case in suite.cases:
        assert_safe_text(case.text)
    return suite


def expand_suite_cases(
    suite: SuiteDefinition,
    num_prompts: int,
    run_id: str | None,
    random_seed: int,
    category_bias: dict[str, float] | None = None,
    allow_repeats: bool = False,
) -> list[PromptRecord]:
    """Expand suite cases deterministically into prompt records."""

    weighted_cases = _apply_category_bias(suite.cases, category_bias or {})
    prompts: list[PromptRecord] = []
    for index, case in enumerate(
        _seeded_case_stream(weighted_cases, num_prompts, random_seed, allow_repeats)
    ):
        text = case.text.strip()
        assert_safe_text(text)
        prompts.append(
            PromptRecord(
                id=new_id("prompt"),
                run_id=run_id,
                category=case.category,
                text=text,
                metadata={
                    **case.metadata,
                    "source": "suite",
                    "suite_name": suite.name,
                    "suite_version": suite.version,
                    "suite_id": suite.stable_id,
                    "suite_hash": suite.stable_hash,
                    "rubric_version": suite.rubric_version,
                    "template_id": case.template_id,
                    "generator_index": index,
                    "random_seed": random_seed,
                    "prompt_hash": prompt_hash(text),
                },
            )
        )
    return prompts


def _seeded_case_stream(
    cases: list[PromptCase], num_prompts: int, random_seed: int, allow_repeats: bool = False
) -> list[PromptCase]:
    """Return a reproducible shuffled prompt order, reshuffling each full pass."""

    if not cases:
        raise ValueError("Suite must contain at least one prompt case.")

    unique_count = len({case.template_id for case in cases})
    if num_prompts > unique_count and not allow_repeats:
        raise ValueError(
            f"Requested {num_prompts} prompts from {unique_count} unique templates. "
            "Set allow_repeated_prompts=true only for explicit stochastic repeat testing."
        )

    rng = random.Random(random_seed)
    selected: list[PromptCase] = []
    if allow_repeats:
        while len(selected) < num_prompts:
            batch = list(cases)
            rng.shuffle(batch)
            selected.extend(batch[: num_prompts - len(selected)])
        return selected

    selected_template_ids: set[str] = set()
    while len(selected) < num_prompts:
        batch = list(cases)
        rng.shuffle(batch)
        for case in batch:
            if case.template_id in selected_template_ids:
                continue
            selected.append(case)
            selected_template_ids.add(case.template_id)
            if len(selected) == num_prompts:
                break
    return selected


def _apply_category_bias(
    cases: list[PromptCase], category_bias: dict[str, float]
) -> list[PromptCase]:
    if not category_bias:
        return cases

    weighted: list[PromptCase] = []
    for case in cases:
        weight = max(1, round(category_bias.get(case.category.value, 1.0)))
        weighted.extend([case] * weight)
    return weighted or cases
