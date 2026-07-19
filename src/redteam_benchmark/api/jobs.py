"""Bounded in-process execution service for API benchmark jobs."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock

from sqlalchemy.orm import Session, sessionmaker

from redteam_benchmark.pipeline import BenchmarkPipeline
from redteam_benchmark.schemas import RunCreate, RunResult


class JobQueueFullError(RuntimeError):
    """The bounded API execution queue has reached capacity."""


class RunJobExecutor:
    """Submit durable runs without holding an HTTP request open."""

    def __init__(self, max_workers: int = 2, max_pending: int = 100) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="redteam-run"
        )
        self._futures: dict[str, Future[RunResult]] = {}
        self._lock = Lock()
        self._max_pending = max_pending

    def submit(
        self, factory: sessionmaker[Session], run_id: str, request: RunCreate
    ) -> Future[RunResult]:
        with self._lock:
            active = self._futures.get(run_id)
            if active is not None:
                return active
            if len(self._futures) >= self._max_pending:
                raise JobQueueFullError("The benchmark job queue is full.")
            future = self._executor.submit(BenchmarkPipeline(factory).execute, run_id, request)
            self._futures[run_id] = future
            future.add_done_callback(lambda _: self._forget(run_id))
            return future

    def _forget(self, run_id: str) -> None:
        with self._lock:
            self._futures.pop(run_id, None)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
