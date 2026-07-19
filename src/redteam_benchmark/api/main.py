"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from redteam_benchmark.api.routes import get_job_executor, get_session_factory, router
from redteam_benchmark.database import fail_incomplete_runs


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    fail_incomplete_runs(get_session_factory())
    yield
    get_job_executor().shutdown()
    get_job_executor.cache_clear()


app = FastAPI(
    title="Agentic LLM Red Team Benchmark",
    version="0.1.0",
    description="Safe benchmark framework for LLM refusal consistency and safety robustness.",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
