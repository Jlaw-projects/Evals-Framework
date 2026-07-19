import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from redteam_benchmark.api.main import app
from redteam_benchmark.api.routes import get_job_executor, get_session_factory
from redteam_benchmark.config import get_settings, load_env_file
from redteam_benchmark.config_files import (
    gate_thresholds_from_config,
    load_config,
    run_create_from_config,
)
from redteam_benchmark.database import init_db


def test_load_env_file_sets_missing_values_without_overwriting_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "REDTEAM_MODEL=from-file\nREDTEAM_BASE_URL='mock'\nREDTEAM_TEMPERATURE=0.4\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("REDTEAM_MODEL", "from-shell")

    load_env_file(env_path)

    assert get_settings().model == "from-shell"
    assert get_settings().base_url == "mock"
    assert get_settings().temperature == 0.4


def test_get_settings_parses_allowed_base_url_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDTEAM_API_ALLOWED_BASE_URLS", "mock, http://localhost:8000/v1/ ")

    settings = get_settings()

    assert settings.api_allowed_base_urls == ("mock", "http://localhost:8000/v1")


def test_get_settings_uses_strict_judge_errors_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDTEAM_JUDGE_FALLBACK_ON_ERROR", raising=False)

    assert get_settings().judge_fallback_on_error is False

    monkeypatch.setenv("REDTEAM_JUDGE_FALLBACK_ON_ERROR", "true")
    assert get_settings().judge_fallback_on_error is True


def test_load_env_file_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_env_file(tmp_path / "missing.env")


def test_json_config_builds_run_request_and_default_gate_thresholds(tmp_path: Path) -> None:
    config_path = tmp_path / "eval.json"
    config_path.write_text(
        '{"model": {"name": "mock-safe-model", "base_url": "mock"}, '
        '"suite": {"name": "assistant_policy_core", "num_prompts": 3}}',
        encoding="utf-8",
    )

    config = load_config(config_path)
    request = run_create_from_config(config)
    thresholds = gate_thresholds_from_config(config)

    assert request.suite_name == "assistant_policy_core"
    assert request.suite_version == "2.0.0"
    assert request.num_prompts == 3
    assert thresholds["max_failure_rate"] == 0.05


def test_simple_yaml_parser_rejects_unsupported_lines(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text("model\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported YAML line"):
        load_config(config_path)


def test_api_health_endpoint() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_rejects_disallowed_base_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    factory = init_db(f"sqlite:///{tmp_path / 'benchmark.db'}")
    app.dependency_overrides[get_session_factory] = lambda: factory
    monkeypatch.setenv("REDTEAM_API_ALLOWED_BASE_URLS", "mock")
    monkeypatch.setenv("REDTEAM_ALLOW_UNAUTHENTICATED_API", "true")
    try:
        response = TestClient(app).post(
            "/runs",
            json={
                "model": "mock-safe-model",
                "base_url": "http://blocked.example",
                "num_prompts": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"]


def test_api_requires_configured_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDTEAM_SERVICE_API_KEY", "service-secret")

    unauthorized = TestClient(app).post(
        "/runs", json={"model": "mock-safe-model", "base_url": "mock", "num_prompts": 1}
    )

    assert unauthorized.status_code == 401


def test_api_creates_mock_run_with_dependency_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = init_db(f"sqlite:///{tmp_path / 'benchmark.db'}")
    app.dependency_overrides[get_session_factory] = lambda: factory
    monkeypatch.setenv("REDTEAM_API_ALLOWED_BASE_URLS", "mock")
    monkeypatch.setenv("REDTEAM_ALLOW_UNAUTHENTICATED_API", "true")
    try:
        response = TestClient(app).post(
            "/runs", json={"model": "mock-safe-model", "base_url": "mock", "num_prompts": 1}
        )
        run_id = response.json()["id"]
        client = TestClient(app)
        for _ in range(100):
            status_response = client.get(f"/runs/{run_id}")
            if status_response.json()["status"] in {"completed", "failed"}:
                break
            time.sleep(0.01)
        result_response = client.get(f"/runs/{run_id}/results")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert status_response.json()["status"] == "completed"
    assert result_response.status_code == 200
    assert len(result_response.json()["scores"]) == 1


def test_api_rejects_results_for_queued_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class HoldingExecutor:
        def submit(self, _factory, _run_id, _request) -> None:
            return None

    factory = init_db(f"sqlite:///{tmp_path / 'queued.db'}")
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_job_executor] = HoldingExecutor
    monkeypatch.setenv("REDTEAM_API_ALLOWED_BASE_URLS", "mock")
    monkeypatch.setenv("REDTEAM_ALLOW_UNAUTHENTICATED_API", "true")
    try:
        create_response = TestClient(app).post(
            "/runs", json={"model": "mock-safe-model", "base_url": "mock", "num_prompts": 1}
        )
        result_response = TestClient(app).get(f"/runs/{create_response.json()['id']}/results")
    finally:
        app.dependency_overrides.clear()

    assert create_response.status_code == 202
    assert result_response.status_code == 409


def test_api_fails_closed_without_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDTEAM_SERVICE_API_KEY", raising=False)
    monkeypatch.delenv("REDTEAM_ALLOW_UNAUTHENTICATED_API", raising=False)
    response = TestClient(app).post(
        "/runs", json={"model": "mock-safe-model", "base_url": "mock", "num_prompts": 1}
    )
    assert response.status_code == 503


def test_api_rejects_client_filesystem_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDTEAM_ALLOW_UNAUTHENTICATED_API", "true")
    response = TestClient(app).post(
        "/runs",
        json={
            "model": "mock-safe-model",
            "base_url": "mock",
            "num_prompts": 1,
            "calibration_report_path": "C:/arbitrary/calibration.json",
        },
    )
    assert response.status_code == 422
