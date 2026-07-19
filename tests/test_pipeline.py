from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from redteam_benchmark.adapters import MockModelAdapter
from redteam_benchmark.agents.report_agent import ReportAgent
from redteam_benchmark.database import RunModel, fail_incomplete_runs, init_db, session_scope
from redteam_benchmark.pipeline import BenchmarkPipeline
from redteam_benchmark.registry import register_adapter
from redteam_benchmark.schemas import RunCreate, RunStatus


def test_mock_pipeline_end_to_end(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    factory = init_db(f"sqlite:///{db_path}")
    result = BenchmarkPipeline(factory).run(
        RunCreate(model="mock-safe-model", base_url="mock", num_prompts=6)
    )

    assert result.run.status == RunStatus.COMPLETED
    assert len([prompt for prompt in result.prompts if prompt.mutation_depth == 0]) == 6
    assert len(result.responses) == 6
    assert len(result.scores) == 6
    assert min(score.total_score for score in result.scores) >= 20
    assert result.run.metadata["orchestrator_plan"]["planner"] == "orchestrator_agent"
    assert result.run.metadata["harness"]["suite_id"] == "safety_core@2.0.0"
    provenance = result.run.metadata["reproducibility"]
    assert len(provenance["suite"]["sha256"]) == 64
    assert len(provenance["ordered_prompt_hashes"]) == 6
    assert provenance["evaluation_methods"] == ["deterministic_rule_based"]
    assert provenance["evaluator_calibration"]["suitable_for_release_gates"] is False
    assert result.run.metadata["learning_summary"]["strategy"] == "instinct_based_category_bias"


def test_borderline_mutations_are_evaluated_end_to_end(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    factory = init_db(f"sqlite:///{db_path}")
    result = BenchmarkPipeline(factory).run(
        RunCreate(model="mock-borderline-model", base_url="mock", num_prompts=1)
    )

    assert len([prompt for prompt in result.prompts if prompt.mutation_depth == 0]) == 1
    assert len([prompt for prompt in result.prompts if prompt.mutation_depth == 1]) == 1
    assert len(result.responses) == 2
    assert len(result.scores) == 2
    assert len(result.mutations) == 1
    assert result.mutations[0].bypassed is False
    assert any(score.raw.get("mutation") for score in result.scores)


def test_assistant_policy_suite_runs_through_pipeline(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    factory = init_db(f"sqlite:///{db_path}")
    result = BenchmarkPipeline(factory).run(
        RunCreate(
            model="mock-safe-model",
            base_url="mock",
            num_prompts=4,
            suite_name="assistant_policy_core",
            suite_version="1.0.0",
        )
    )

    assert result.run.status == RunStatus.COMPLETED
    assert result.run.metadata["harness"]["suite_id"] == "assistant_policy_core@1.0.0"
    assert len(result.responses) == 4
    assert len(result.scores) == 4
    assert {prompt.metadata["rubric_version"] for prompt in result.prompts} == {
        "assistant-policy-rubric.v1"
    }


def test_assistant_policy_suite_detects_policy_violating_mock(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    factory = init_db(f"sqlite:///{db_path}")
    result = BenchmarkPipeline(factory).run(
        RunCreate(
            model="mock-policy-violating-model",
            base_url="mock",
            num_prompts=12,
            suite_name="assistant_policy_core",
            suite_version="1.0.0",
            mutate_failures=False,
        )
    )

    assert max(score.total_score for score in result.scores) < 20
    assert all(not score.raw["evaluator"]["pass"] for score in result.scores)
    assert sum(score.raw["evaluator"]["policy_failure_count"] for score in result.scores) >= 10


def test_report_agent_writes_artifacts(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    report_dir = tmp_path / "reports"
    factory = init_db(f"sqlite:///{db_path}")
    result = BenchmarkPipeline(factory).run(
        RunCreate(
            model="mock-safe-model",
            base_url="mock",
            num_prompts=4,
            model_revision="mock-revision-1",
        )
    )

    markdown_path, json_path = ReportAgent(factory, report_dir=report_dir).generate(result.run.id)

    assert markdown_path.exists()
    assert json_path.exists()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Safety Statement" in markdown
    assert "Evaluation Metrics" in markdown
    assert "Mean score 95% CI (prompt-clustered bootstrap)" in markdown
    assert "Failure-rate 95% CI" in markdown
    assert "Rubric | `safety-rubric.v2`" in markdown
    assert "Model revision | `mock-revision-1`" in markdown
    assert result.run.metadata["reproducibility"]["run_config_sha256"] in markdown
    assert result.run.metadata["reproducibility"]["public_manifest_sha256"] in markdown
    assert "![" in markdown
    assert str(report_dir.resolve()) not in markdown
    assert (report_dir / result.run.id / f"{result.run.id}_category_scores.png").exists()


def test_report_fails_strictly_when_any_prompt_fails(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    report_dir = tmp_path / "reports"
    factory = init_db(f"sqlite:///{db_path}")
    result = BenchmarkPipeline(factory).run(
        RunCreate(
            model="mock-policy-violating-model",
            base_url="mock",
            num_prompts=12,
            suite_name="assistant_policy_core",
            suite_version="1.0.0",
            mutate_failures=False,
        )
    )

    markdown_path, _ = ReportAgent(factory, report_dir=report_dir).generate(result.run.id)
    markdown = markdown_path.read_text(encoding="utf-8")

    assert "Pass/fail indicator | FAIL" in markdown


def test_unexpected_execution_failure_is_persisted(tmp_path: Path) -> None:
    factory = init_db(f"sqlite:///{tmp_path / 'benchmark.db'}")

    with pytest.raises(FileNotFoundError):
        BenchmarkPipeline(factory).run(
            RunCreate(
                model="mock-safe-model",
                base_url="mock",
                suite_name="missing-suite",
                num_prompts=1,
            )
        )

    with session_scope(factory) as session:
        runs = session.query(RunModel).all()
        assert len(runs) == 1
        assert runs[0].status == RunStatus.FAILED.value
        assert "execution_error" in runs[0].metadata_json


def test_startup_recovery_fails_interrupted_runs(tmp_path: Path) -> None:
    factory = init_db(f"sqlite:///{tmp_path / 'recovery.db'}")
    queued = BenchmarkPipeline(factory).create(
        RunCreate(model="mock-safe-model", base_url="mock", num_prompts=1)
    )

    assert fail_incomplete_runs(factory) == 1

    with session_scope(factory) as session:
        row = session.get(RunModel, queued.id)
        assert row is not None
        assert row.status == RunStatus.FAILED.value
        assert "ServiceRestart" in row.metadata_json


def test_sqlite_running_state_is_visible_and_second_run_can_be_created(
    tmp_path: Path,
) -> None:
    adapter_started = Event()
    adapter_release = Event()

    class BlockingAdapter:
        model_name = "blocking-model"

        def generate(self, prompt):
            adapter_started.set()
            if not adapter_release.wait(timeout=5):
                raise TimeoutError("test did not release blocking adapter")
            return MockModelAdapter("mock-safe-model").generate(prompt)

    component_name = "test-sqlite-blocking-adapter"
    register_adapter(component_name, lambda **_: BlockingAdapter())
    factory = init_db(f"sqlite:///{tmp_path / 'concurrent.db'}")
    pipeline = BenchmarkPipeline(factory)
    request = RunCreate(
        model="blocking-model",
        base_url="https://unused.invalid/v1",
        adapter_name=component_name,
        num_prompts=1,
        mutate_failures=False,
    )
    first = pipeline.create(request)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(pipeline.execute, first.id, request)
        assert adapter_started.wait(timeout=5)

        with session_scope(factory) as session:
            running = session.get(RunModel, first.id)
            assert running is not None
            assert running.status == RunStatus.RUNNING.value

        second = pipeline.create(request)
        assert second.status is RunStatus.QUEUED
        adapter_release.set()
        first_result = future.result(timeout=5)

    second_result = pipeline.execute(second.id, request)
    assert first_result.run.status is RunStatus.COMPLETED
    assert second_result.run.status is RunStatus.COMPLETED


def test_adapter_exception_commits_failed_status(tmp_path: Path) -> None:
    class ExplodingAdapter:
        model_name = "exploding-model"

        def generate(self, _prompt):
            raise RuntimeError("adapter exploded")

    component_name = "test-fail-fast-adapter"
    register_adapter(component_name, lambda **_: ExplodingAdapter())
    factory = init_db(f"sqlite:///{tmp_path / 'failed.db'}")
    pipeline = BenchmarkPipeline(factory)
    request = RunCreate(
        model="exploding-model",
        base_url="https://unused.invalid/v1",
        adapter_name=component_name,
        num_prompts=1,
        max_retries=0,
        fail_fast=True,
    )
    run = pipeline.create(request)

    with pytest.raises(RuntimeError, match="adapter exploded"):
        pipeline.execute(run.id, request)

    with session_scope(factory) as session:
        failed = session.get(RunModel, run.id)
        assert failed is not None
        assert failed.status == RunStatus.FAILED.value
        assert "adapter exploded" in failed.metadata_json
