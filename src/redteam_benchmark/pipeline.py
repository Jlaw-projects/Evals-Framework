"""End-to-end benchmark pipeline entrypoint."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from redteam_benchmark.agents.orchestrator_agent import OrchestratorAgent
from redteam_benchmark.schemas import RunCreate, RunRecord, RunResult


class BenchmarkPipeline:
    """Stable pipeline facade that delegates run planning to the Orchestrator Agent."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def run(self, request: RunCreate) -> RunResult:
        return OrchestratorAgent(self.session_factory).run(request)

    def create(self, request: RunCreate) -> RunRecord:
        """Persist a queued run before execution begins."""

        return OrchestratorAgent(self.session_factory).create(request)

    def execute(self, run_id: str, request: RunCreate) -> RunResult:
        """Execute a previously created run."""

        return OrchestratorAgent(self.session_factory).execute(run_id, request)

    def fail(self, run_id: str, exc: Exception) -> None:
        """Record a terminal failure for a run that could not be submitted."""

        OrchestratorAgent(self.session_factory).mark_failed(run_id, exc)
