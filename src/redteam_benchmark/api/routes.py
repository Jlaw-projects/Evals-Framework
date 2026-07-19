"""FastAPI routes for benchmark runs and reports."""

from __future__ import annotations

import hmac
from functools import lru_cache

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, sessionmaker

from redteam_benchmark.agents.report_agent import ReportAgent
from redteam_benchmark.api.jobs import JobQueueFullError, RunJobExecutor
from redteam_benchmark.config import get_settings
from redteam_benchmark.database import RunModel as DbRun
from redteam_benchmark.database import get_run_result, init_db, run_to_schema, session_scope
from redteam_benchmark.pipeline import BenchmarkPipeline
from redteam_benchmark.schemas import ApiRunCreate, RunRecord, RunResult
from redteam_benchmark.schemas import RunStatus as BenchmarkRunStatus

router = APIRouter()


def get_session_factory() -> sessionmaker[Session]:
    return _session_factory(get_settings().database_url)


@lru_cache(maxsize=8)
def _session_factory(database_url: str) -> sessionmaker[Session]:
    return init_db(database_url)


@lru_cache(maxsize=1)
def get_job_executor() -> RunJobExecutor:
    settings = get_settings()
    return RunJobExecutor(
        max_workers=settings.api_job_workers,
        max_pending=settings.api_max_pending_jobs,
    )


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    """Require a bearer token when REDTEAM_SERVICE_API_KEY is configured."""

    expected = get_settings().service_api_key
    if expected is None:
        if get_settings().allow_unauthenticated_api:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@router.post("/runs", response_model=RunRecord, status_code=status.HTTP_202_ACCEPTED)
def create_run(
    request: ApiRunCreate,
    factory: sessionmaker[Session] = Depends(get_session_factory),
    jobs: RunJobExecutor = Depends(get_job_executor),
    _authenticated: None = Depends(require_api_key),
) -> RunRecord:
    settings = get_settings()
    if request.base_url.rstrip("/") not in settings.api_allowed_base_urls:
        raise HTTPException(
            status_code=400,
            detail="Base URL is not allowed by REDTEAM_API_ALLOWED_BASE_URLS",
        )
    internal_request = request.to_internal(settings.api_calibration_report_path)
    pipeline = BenchmarkPipeline(factory)
    run = pipeline.create(internal_request)
    try:
        jobs.submit(factory, run.id, internal_request)
    except JobQueueFullError as exc:
        BenchmarkPipeline(factory).fail(run.id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Benchmark job queue is full",
        ) from exc
    return run


@router.get("/runs/{run_id}", response_model=RunRecord)
def get_run(
    run_id: str,
    factory: sessionmaker[Session] = Depends(get_session_factory),
    _authenticated: None = Depends(require_api_key),
) -> RunRecord:
    with session_scope(factory) as session:
        row = session.get(DbRun, run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run_to_schema(row)


@router.get("/runs/{run_id}/results", response_model=RunResult)
def get_results(
    run_id: str,
    factory: sessionmaker[Session] = Depends(get_session_factory),
    _authenticated: None = Depends(require_api_key),
) -> RunResult:
    with session_scope(factory) as session:
        result = get_run_result(session, run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if result.run.status in {BenchmarkRunStatus.QUEUED, BenchmarkRunStatus.RUNNING}:
            raise HTTPException(status_code=409, detail="Run has not completed")
        return result


@router.get("/runs/{run_id}/report", response_class=PlainTextResponse)
def get_report(
    run_id: str,
    factory: sessionmaker[Session] = Depends(get_session_factory),
    _authenticated: None = Depends(require_api_key),
) -> str:
    with session_scope(factory) as session:
        row = session.get(DbRun, run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if row.status in {BenchmarkRunStatus.QUEUED.value, BenchmarkRunStatus.RUNNING.value}:
            raise HTTPException(status_code=409, detail="Run has not completed")
    try:
        return ReportAgent(factory).render_markdown(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
