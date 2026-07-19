"""Initial benchmark schema shipped with the installed package.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-13 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "runs" in inspector.get_table_names():
        _upgrade_existing_schema(inspector)
        return

    _create_schema()


def _create_schema() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=False),
        sa.Column("num_prompts", sa.Integer(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "prompts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("parent_prompt_id", sa.String(length=64), nullable=True),
        sa.Column("mutation_depth", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompts_run_id", "prompts", ["run_id"])
    op.create_index("ix_prompts_category", "prompts", ["category"])

    op.create_table(
        "responses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("prompt_id", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompts.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_responses_run_id", "responses", ["run_id"])
    op.create_index("ix_responses_prompt_id", "responses", ["prompt_id"])

    op.create_table(
        "scores",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("prompt_id", sa.String(length=64), nullable=False),
        sa.Column("response_id", sa.String(length=64), nullable=False),
        sa.Column("safety_compliance", sa.Integer(), nullable=False),
        sa.Column("refusal_quality", sa.Integer(), nullable=False),
        sa.Column("helpfulness_within_safe_limits", sa.Integer(), nullable=False),
        sa.Column("leakage_resistance", sa.Integer(), nullable=False),
        sa.Column("policy_consistency", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("judge_model", sa.String(length=255), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("safety_compliance BETWEEN 0 AND 5", name="ck_scores_safety_compliance"),
        sa.CheckConstraint("refusal_quality BETWEEN 0 AND 5", name="ck_scores_refusal_quality"),
        sa.CheckConstraint(
            "helpfulness_within_safe_limits BETWEEN 0 AND 5",
            name="ck_scores_helpfulness_within_safe_limits",
        ),
        sa.CheckConstraint(
            "leakage_resistance BETWEEN 0 AND 5",
            name="ck_scores_leakage_resistance",
        ),
        sa.CheckConstraint(
            "policy_consistency BETWEEN 0 AND 5",
            name="ck_scores_policy_consistency",
        ),
        sa.CheckConstraint(
            "total_score = safety_compliance + refusal_quality + "
            "helpfulness_within_safe_limits + leakage_resistance + policy_consistency",
            name="ck_scores_total_score_sum",
        ),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompts.id"]),
        sa.ForeignKeyConstraint(["response_id"], ["responses.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scores_run_id", "scores", ["run_id"])
    op.create_index("ix_scores_prompt_id", "scores", ["prompt_id"])
    op.create_index("ix_scores_response_id", "scores", ["response_id"])

    op.create_table(
        "prompt_mutations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("source_prompt_id", sa.String(length=64), nullable=False),
        sa.Column("mutated_prompt_id", sa.String(length=64), nullable=False),
        sa.Column("strategy", sa.String(length=255), nullable=False),
        sa.Column("bypassed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mutated_prompt_id"], ["prompts.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.ForeignKeyConstraint(["source_prompt_id"], ["prompts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompt_mutations_run_id", "prompt_mutations", ["run_id"])
    op.create_index(
        "ix_prompt_mutations_source_prompt_id",
        "prompt_mutations",
        ["source_prompt_id"],
    )
    op.create_index(
        "ix_prompt_mutations_mutated_prompt_id",
        "prompt_mutations",
        ["mutated_prompt_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_prompt_mutations_mutated_prompt_id", table_name="prompt_mutations")
    op.drop_index("ix_prompt_mutations_source_prompt_id", table_name="prompt_mutations")
    op.drop_index("ix_prompt_mutations_run_id", table_name="prompt_mutations")
    op.drop_table("prompt_mutations")
    op.drop_index("ix_scores_response_id", table_name="scores")
    op.drop_index("ix_scores_prompt_id", table_name="scores")
    op.drop_index("ix_scores_run_id", table_name="scores")
    op.drop_table("scores")
    op.drop_index("ix_responses_prompt_id", table_name="responses")
    op.drop_index("ix_responses_run_id", table_name="responses")
    op.drop_table("responses")
    op.drop_index("ix_prompts_category", table_name="prompts")
    op.drop_index("ix_prompts_run_id", table_name="prompts")
    op.drop_table("prompts")
    op.drop_table("runs")


def _upgrade_existing_schema(inspector: sa.Inspector) -> None:
    """Patch databases created before Alembic without recreating user data."""

    tables = set(inspector.get_table_names())
    if "prompt_mutations" in tables:
        existing_columns = {column["name"] for column in inspector.get_columns("prompt_mutations")}
        if "bypassed" not in existing_columns:
            op.add_column("prompt_mutations", sa.Column("bypassed", sa.Boolean(), nullable=True))

    for table_name, index_name, index_columns in (
        ("prompts", "ix_prompts_run_id", ["run_id"]),
        ("responses", "ix_responses_run_id", ["run_id"]),
        ("responses", "ix_responses_prompt_id", ["prompt_id"]),
        ("scores", "ix_scores_run_id", ["run_id"]),
        ("scores", "ix_scores_prompt_id", ["prompt_id"]),
        ("scores", "ix_scores_response_id", ["response_id"]),
        ("prompt_mutations", "ix_prompt_mutations_run_id", ["run_id"]),
        ("prompt_mutations", "ix_prompt_mutations_source_prompt_id", ["source_prompt_id"]),
        ("prompt_mutations", "ix_prompt_mutations_mutated_prompt_id", ["mutated_prompt_id"]),
    ):
        if table_name in tables:
            _create_index_if_missing(inspector, table_name, index_name, index_columns)


def _create_index_if_missing(
    inspector: sa.Inspector, table_name: str, index_name: str, columns: list[str]
) -> None:
    existing = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)
