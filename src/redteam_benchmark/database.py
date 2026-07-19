"""SQLAlchemy models and repository helpers."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    select,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    column_property,
    mapped_column,
    relationship,
    sessionmaker,
)

from redteam_benchmark.config import get_settings
from redteam_benchmark.schemas import (
    ModelResponseRecord,
    PromptMutationRecord,
    PromptRecord,
    RunRecord,
    RunResult,
    RunStatus,
    ScoreRecord,
)


def new_id(prefix: str) -> str:
    """Return a short stable-looking identifier for benchmark records."""

    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class RunModel(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    num_prompts: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RunStatus.CREATED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    prompts: Mapped[list[PromptModel]] = relationship(back_populates="run")
    responses: Mapped[list[ResponseModel]] = relationship(back_populates="run")
    scores: Mapped[list[ScoreModel]] = relationship(back_populates="run")
    mutations: Mapped[list[PromptMutationModel]] = relationship(back_populates="run")


class PromptModel(Base):
    __tablename__ = "prompts"
    __table_args__ = (Index("ix_prompts_run_id", "run_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    parent_prompt_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mutation_depth: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[RunModel | None] = relationship(back_populates="prompts")


class ResponseModel(Base):
    __tablename__ = "responses"
    __table_args__ = (
        Index("ix_responses_run_id", "run_id"),
        Index("ix_responses_prompt_id", "prompt_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[RunModel] = relationship(back_populates="responses")


class ScoreModel(Base):
    __tablename__ = "scores"
    __table_args__ = (
        CheckConstraint("safety_compliance BETWEEN 0 AND 5", name="ck_scores_safety_compliance"),
        CheckConstraint("refusal_quality BETWEEN 0 AND 5", name="ck_scores_refusal_quality"),
        CheckConstraint(
            "helpfulness_within_safe_limits BETWEEN 0 AND 5",
            name="ck_scores_helpfulness_within_safe_limits",
        ),
        CheckConstraint("leakage_resistance BETWEEN 0 AND 5", name="ck_scores_leakage_resistance"),
        CheckConstraint("policy_consistency BETWEEN 0 AND 5", name="ck_scores_policy_consistency"),
        CheckConstraint(
            "total_score = safety_compliance + refusal_quality + "
            "helpfulness_within_safe_limits + leakage_resistance + policy_consistency",
            name="ck_scores_total_score_sum",
        ),
        Index("ix_scores_run_id", "run_id"),
        Index("ix_scores_prompt_id", "prompt_id"),
        Index("ix_scores_response_id", "response_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), nullable=False)
    response_id: Mapped[str] = mapped_column(ForeignKey("responses.id"), nullable=False)
    safety_compliance: Mapped[int] = mapped_column(Integer, nullable=False)
    refusal_quality: Mapped[int] = mapped_column(Integer, nullable=False)
    helpfulness_within_safe_limits: Mapped[int] = mapped_column(Integer, nullable=False)
    leakage_resistance: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_consistency: Mapped[int] = mapped_column(Integer, nullable=False)
    # The physical column remains for SQLite/backward compatibility, but application code
    # reads total_score from the computed column_property below and the DB constraint enforces it.
    stored_total_score: Mapped[int] = mapped_column("total_score", Integer, nullable=False)
    total_score = column_property(
        safety_compliance
        + refusal_quality
        + helpfulness_within_safe_limits
        + leakage_resistance
        + policy_consistency
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    judge_model: Mapped[str] = mapped_column(String(255), default="rule-based")
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[RunModel] = relationship(back_populates="scores")


class PromptMutationModel(Base):
    __tablename__ = "prompt_mutations"
    __table_args__ = (
        Index("ix_prompt_mutations_run_id", "run_id"),
        Index("ix_prompt_mutations_source_prompt_id", "source_prompt_id"),
        Index("ix_prompt_mutations_mutated_prompt_id", "mutated_prompt_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    source_prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), nullable=False)
    mutated_prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), nullable=False)
    strategy: Mapped[str] = mapped_column(String(255), nullable=False)
    bypassed: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[RunModel] = relationship(back_populates="mutations")


def make_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    connect_args: dict[str, Any] = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def make_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    engine = make_engine(database_url)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def init_db(database_url: str | None = None) -> sessionmaker[Session]:
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(value)


def _dumps(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, sort_keys=True)


def run_to_schema(row: RunModel) -> RunRecord:
    return RunRecord(
        id=row.id,
        model_name=row.model_name,
        base_url=row.base_url,
        num_prompts=row.num_prompts,
        temperature=row.temperature,
        max_tokens=row.max_tokens,
        status=RunStatus(row.status),
        created_at=row.created_at,
        completed_at=row.completed_at,
        metadata=_loads(row.metadata_json),
    )


def prompt_to_schema(row: PromptModel) -> PromptRecord:
    return PromptRecord(
        id=row.id,
        run_id=row.run_id,
        category=row.category,
        text=row.text,
        parent_prompt_id=row.parent_prompt_id,
        mutation_depth=row.mutation_depth,
        metadata=_loads(row.metadata_json),
    )


def response_to_schema(row: ResponseModel) -> ModelResponseRecord:
    return ModelResponseRecord(
        id=row.id,
        run_id=row.run_id,
        prompt_id=row.prompt_id,
        model_name=row.model_name,
        text=row.text,
        latency_ms=row.latency_ms,
        raw=_loads(row.raw_json),
    )


def score_to_schema(row: ScoreModel) -> ScoreRecord:
    return ScoreRecord(
        id=row.id,
        run_id=row.run_id,
        prompt_id=row.prompt_id,
        response_id=row.response_id,
        safety_compliance=row.safety_compliance,
        refusal_quality=row.refusal_quality,
        helpfulness_within_safe_limits=row.helpfulness_within_safe_limits,
        leakage_resistance=row.leakage_resistance,
        policy_consistency=row.policy_consistency,
        total_score=row.total_score,
        rationale=row.rationale,
        judge_model=row.judge_model,
        raw=_loads(row.raw_json),
    )


def mutation_to_schema(row: PromptMutationModel) -> PromptMutationRecord:
    return PromptMutationRecord(
        id=row.id,
        run_id=row.run_id,
        source_prompt_id=row.source_prompt_id,
        mutated_prompt_id=row.mutated_prompt_id,
        strategy=row.strategy,
        bypassed=row.bypassed,
    )


def get_run_result(session: Session, run_id: str) -> RunResult | None:
    run = session.get(RunModel, run_id)
    if run is None:
        return None
    prompts = session.scalars(select(PromptModel).where(PromptModel.run_id == run_id)).all()
    responses = session.scalars(select(ResponseModel).where(ResponseModel.run_id == run_id)).all()
    scores = session.scalars(select(ScoreModel).where(ScoreModel.run_id == run_id)).all()
    try:
        mutations = session.scalars(
            select(PromptMutationModel).where(PromptMutationModel.run_id == run_id)
        ).all()
        mutation_records = [mutation_to_schema(row) for row in mutations]
    except OperationalError:
        mutation_records = _legacy_mutations(session, run_id)
    return RunResult(
        run=run_to_schema(run),
        prompts=[prompt_to_schema(row) for row in prompts],
        responses=[response_to_schema(row) for row in responses],
        scores=[score_to_schema(row) for row in scores],
        mutations=mutation_records,
    )


def json_text(value: dict[str, Any] | None) -> str:
    return _dumps(value)


def fail_incomplete_runs(factory: sessionmaker[Session]) -> int:
    """Mark work interrupted by a prior process exit as terminally failed."""

    recovered = 0
    with session_scope(factory) as session:
        rows = session.scalars(
            select(RunModel).where(
                RunModel.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value])
            )
        ).all()
        for run in rows:
            metadata_value = _loads(run.metadata_json)
            metadata_value["execution_error"] = {
                "type": "ServiceRestart",
                "message": "Run was interrupted before the service restarted.",
            }
            run.metadata_json = _dumps(metadata_value)
            run.status = RunStatus.FAILED.value
            run.completed_at = utcnow()
            recovered += 1
    return recovered


def _legacy_mutations(session: Session, run_id: str) -> list[PromptMutationRecord]:
    rows = session.execute(
        text(
            "SELECT id, run_id, source_prompt_id, mutated_prompt_id, strategy "
            "FROM prompt_mutations WHERE run_id = :run_id"
        ),
        {"run_id": run_id},
    ).mappings()
    return [
        PromptMutationRecord(
            id=row["id"],
            run_id=row["run_id"],
            source_prompt_id=row["source_prompt_id"],
            mutated_prompt_id=row["mutated_prompt_id"],
            strategy=row["strategy"],
            bypassed=None,
        )
        for row in rows
    ]
