"""Runtime configuration for the benchmark."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Environment-backed settings with safe local defaults."""

    database_url: str = Field(default="sqlite:///./redteam_benchmark.db")
    report_dir: Path = Field(default=Path("reports"))
    model: str = Field(default="mock-safe-model")
    base_url: str = Field(default="mock")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1)
    judge_model: str | None = None
    judge_base_url: str | None = None
    judge_fallback_on_error: bool = False
    api_key: str | None = None
    judge_api_key: str | None = None
    api_allowed_base_urls: tuple[str, ...] = ("mock",)
    ollama_base_url: str = "http://localhost:11434"
    minimax_base_url: str = "https://api.minimax.io"
    minimax_api_key: str | None = None
    service_api_key: str | None = None
    allow_unauthenticated_api: bool = False
    api_calibration_report_path: str | None = None
    api_job_workers: int = Field(default=2, ge=1, le=32)
    api_max_pending_jobs: int = Field(default=100, ge=1, le=10000)


def get_settings() -> Settings:
    """Read settings from environment variables."""

    env_file = os.getenv("REDTEAM_ENV_FILE")
    if env_file:
        load_env_file(Path(env_file))

    return Settings(
        database_url=os.getenv("REDTEAM_DATABASE_URL", "sqlite:///./redteam_benchmark.db"),
        report_dir=Path(os.getenv("REDTEAM_REPORT_DIR", "reports")),
        model=os.getenv("REDTEAM_MODEL", "mock-safe-model"),
        base_url=os.getenv("REDTEAM_BASE_URL", "mock"),
        temperature=float(os.getenv("REDTEAM_TEMPERATURE", "0.2")),
        max_tokens=int(os.getenv("REDTEAM_MAX_TOKENS", "512")),
        judge_model=os.getenv("REDTEAM_JUDGE_MODEL") or None,
        judge_base_url=os.getenv("REDTEAM_JUDGE_BASE_URL") or None,
        judge_fallback_on_error=_env_bool("REDTEAM_JUDGE_FALLBACK_ON_ERROR", False),
        api_key=os.getenv("OPENAI_API_KEY") or os.getenv("REDTEAM_API_KEY") or None,
        judge_api_key=os.getenv("REDTEAM_JUDGE_API_KEY") or os.getenv("OPENAI_API_KEY") or None,
        api_allowed_base_urls=_csv_tuple(os.getenv("REDTEAM_API_ALLOWED_BASE_URLS", "mock")),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        minimax_base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io"),
        minimax_api_key=os.getenv("MINIMAX_API_KEY") or None,
        service_api_key=os.getenv("REDTEAM_SERVICE_API_KEY") or None,
        allow_unauthenticated_api=_env_bool("REDTEAM_ALLOW_UNAUTHENTICATED_API", False),
        api_calibration_report_path=os.getenv("REDTEAM_API_CALIBRATION_REPORT_PATH") or None,
        api_job_workers=int(os.getenv("REDTEAM_API_JOB_WORKERS", "2")),
        api_max_pending_jobs=int(os.getenv("REDTEAM_API_MAX_PENDING_JOBS", "100")),
    )


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs without overwriting values already set in the shell."""

    if not path.exists():
        raise FileNotFoundError(f"Environment file not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _csv_tuple(value: str) -> tuple[str, ...]:
    return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value.")
