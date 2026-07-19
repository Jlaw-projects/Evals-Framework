import json
from pathlib import Path

import pytest

from redteam_benchmark.agents.audit_loop_agent import AuditLoopAgent, AuditLoopConfig
from redteam_benchmark.agents.judge_agent import JudgeAgent
from redteam_benchmark.agents.loop_reasoner import LoopAdvice
from redteam_benchmark.calibration import (
    calibrate_judge,
    load_evaluator_dataset,
    write_calibration_artifacts,
)
from redteam_benchmark.database import get_run_result, init_db, session_scope


class FailingReasoner:
    def advise(self, **_: object) -> LoopAdvice:
        raise RuntimeError("reasoning backend unavailable")


def _calibration_path(tmp_path: Path) -> str:
    report = calibrate_judge(JudgeAgent(), load_evaluator_dataset())
    _, path = write_calibration_artifacts(report, tmp_path / "calibration")
    return str(path)


def test_audit_loop_writes_report_memory_and_tags_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    report_dir = tmp_path / "reports"
    memory_path = tmp_path / "strategy_memory.json"
    factory = init_db(f"sqlite:///{db_path}")

    result = AuditLoopAgent(factory).run(
        AuditLoopConfig(
            model="mock-policy-violating-model",
            base_url="mock",
            suite_name="assistant_policy_core",
            suite_version="1.0.0",
            num_prompts=6,
            max_iterations=2,
            min_iterations=2,
            report_dir=report_dir,
            memory_path=memory_path,
        )
    )

    assert len(result.iterations) == 2
    assert result.model_risk == "high"
    assert result.audit_status == "incomplete"
    assert result.release_decision == "unknown"
    assert result.report_path.exists()
    assert result.json_path.exists()
    assert result.memory_path.exists()
    assert "Adaptive Red-Team Audit Loop Report" in result.report_path.read_text(encoding="utf-8")

    memory = json.loads(memory_path.read_text(encoding="utf-8"))
    memory_key = "mock-policy-violating-model|mock|assistant_policy_core@1.0.0"
    model_memory = memory["models"][memory_key]
    assert result.audit_id in model_memory["audits"]
    assert model_memory["last_category_bias"]

    first_iteration, second_iteration = result.iterations
    assert first_iteration.category_bias == {}
    assert second_iteration.category_bias
    assert all(0.5 <= weight <= 5.0 for weight in second_iteration.category_bias.values())
    assert second_iteration.metrics["failure_count"] > 0

    with session_scope(factory) as session:
        stored = get_run_result(session, second_iteration.run_id)
        assert stored is not None
        assert stored.run.metadata["audit_loop"]["audit_id"] == result.audit_id
        assert stored.run.metadata["audit_loop"]["iteration"] == 2
        assert stored.run.metadata["audit_loop"]["category_bias"] == second_iteration.category_bias


def test_audit_loop_can_stop_after_clean_iteration(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    factory = init_db(f"sqlite:///{db_path}")

    result = AuditLoopAgent(factory).run(
        AuditLoopConfig(
            model="mock-safe-model",
            base_url="mock",
            num_prompts=4,
            max_iterations=3,
            min_iterations=1,
            report_dir=tmp_path / "reports",
            memory_path=tmp_path / "memory.json",
        )
    )

    assert len(result.iterations) == 1
    assert result.stop_reason == "no_failures_detected"
    assert result.model_risk == "low"
    assert result.audit_status == "incomplete"
    assert result.release_decision == "unknown"
    assert result.iterations[0].decision["stop"] is True


def test_reasoning_failure_keeps_model_risk_but_invalidates_release(tmp_path: Path) -> None:
    factory = init_db(f"sqlite:///{tmp_path / 'benchmark.db'}")

    result = AuditLoopAgent(factory, reasoner=FailingReasoner()).run(
        AuditLoopConfig(
            model="mock-safe-model",
            base_url="mock",
            num_prompts=4,
            max_iterations=1,
            min_iterations=1,
            report_dir=tmp_path / "reports",
            memory_path=tmp_path / "memory.json",
        )
    )

    assert result.stop_reason == "reasoning_agent_error"
    assert result.model_risk == "low"
    assert result.audit_status == "incomplete"
    assert result.release_decision == "unknown"
    assert any(item["stage"] == "reasoning" for item in result.process_errors)


def test_infrastructure_failure_is_not_a_model_failure(tmp_path: Path) -> None:
    factory = init_db(f"sqlite:///{tmp_path / 'benchmark.db'}")

    result = AuditLoopAgent(factory).run(
        AuditLoopConfig(
            model="unreachable-model",
            base_url="http://127.0.0.1:1/v1",
            num_prompts=2,
            max_iterations=1,
            min_iterations=1,
            max_retries=0,
            timeout_seconds=0.1,
            mutate_failures=False,
            report_dir=tmp_path / "reports",
            memory_path=tmp_path / "memory.json",
        )
    )

    assert result.model_risk == "unknown"
    assert result.audit_status == "failed"
    assert result.release_decision == "unknown"
    assert result.iterations[0].metrics["failure_count"] == 0
    assert result.iterations[0].metrics["infrastructure_errors"] == 2


def test_no_iterations_is_failed_and_unknown(tmp_path: Path) -> None:
    factory = init_db(f"sqlite:///{tmp_path / 'benchmark.db'}")
    agent = AuditLoopAgent(factory)

    risk, status, release, errors = agent._audit_outcome([])

    assert (risk, status, release) == ("unknown", "failed", "unknown")
    assert errors[0]["type"] == "NoIterations"


def test_audit_json_keeps_deprecated_final_risk_alias(tmp_path: Path) -> None:
    factory = init_db(f"sqlite:///{tmp_path / 'benchmark.db'}")
    result = AuditLoopAgent(factory).run(
        AuditLoopConfig(
            num_prompts=1,
            max_iterations=1,
            min_iterations=1,
            report_dir=tmp_path / "reports",
            memory_path=tmp_path / "memory.json",
        )
    )

    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "2.0"
    assert payload["model_risk"] == "low"
    assert payload["audit_status"] == "incomplete"
    assert payload["release_decision"] == "unknown"
    assert payload["final_risk"] == payload["model_risk"]
    assert payload["final_risk_deprecated"] is True


def test_reporting_failure_makes_audit_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = init_db(f"sqlite:///{tmp_path / 'benchmark.db'}")

    def fail_report(*_: object, **__: object) -> None:
        raise OSError("report storage unavailable")

    monkeypatch.setattr(
        "redteam_benchmark.agents.audit_loop_agent.ReportAgent.generate", fail_report
    )
    result = AuditLoopAgent(factory).run(
        AuditLoopConfig(
            num_prompts=1,
            max_iterations=1,
            min_iterations=1,
            report_dir=tmp_path / "reports",
            memory_path=tmp_path / "memory.json",
        )
    )

    assert result.model_risk == "low"
    assert result.audit_status == "incomplete"
    assert result.release_decision == "unknown"
    assert any(item["stage"] == "reporting" for item in result.process_errors)


def test_exactly_calibrated_clean_adaptive_audit_still_cannot_release_pass(
    tmp_path: Path,
) -> None:
    factory = init_db(f"sqlite:///{tmp_path / 'calibrated.db'}")
    result = AuditLoopAgent(factory).run(
        AuditLoopConfig(
            num_prompts=2,
            max_iterations=1,
            min_iterations=1,
            calibration_report_path=_calibration_path(tmp_path),
            report_dir=tmp_path / "reports-calibrated",
            memory_path=tmp_path / "memory-calibrated.json",
        )
    )
    assert result.audit_status == "completed"
    assert result.model_risk == "low"
    assert result.release_decision == "unknown"
