"""Typed extension interfaces for benchmark components.

These protocols intentionally mirror the registry-oriented style used by mature
evaluation frameworks: core orchestration depends on small contracts, while
adapters, judges, mutators, and exporters can evolve independently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from redteam_benchmark.schemas import (
    ModelResponseRecord,
    PromptMutationRecord,
    PromptRecord,
    RunResult,
    ScoreRecord,
)


class AdapterResponseLike(Protocol):
    text: str
    latency_ms: float
    raw: dict[str, Any]


class BenchmarkAdapter(Protocol):
    model_name: str

    def generate(self, prompt: PromptRecord) -> AdapterResponseLike:
        """Generate a response for one prompt."""


class BenchmarkJudge(Protocol):
    def score(
        self, run_id: str, prompt: PromptRecord, response: ModelResponseRecord
    ) -> ScoreRecord:
        """Score one model response."""


class BenchmarkMutator(Protocol):
    def mutate(
        self, run_id: str, prompt: PromptRecord, score: ScoreRecord
    ) -> tuple[PromptRecord, PromptMutationRecord] | None:
        """Return a safe prompt mutation and lineage record when useful."""


class VerdictPolicy(Protocol):
    def verdict(self, result: RunResult) -> dict[str, Any]:
        """Return machine-readable pass/fail metadata for a completed run."""


class ReportExporter(Protocol):
    def export(self, result: RunResult, output_dir: Path) -> list[Path]:
        """Write report artifacts and return created paths."""
