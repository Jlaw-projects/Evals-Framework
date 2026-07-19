"""Report Generator Agent for JSON, Markdown, and chart artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter
from sqlalchemy.orm import Session, sessionmaker

from redteam_benchmark.config import get_settings
from redteam_benchmark.database import get_run_result, session_scope
from redteam_benchmark.reporting.charts import write_category_chart, write_rubric_chart
from redteam_benchmark.reporting.markdown_report import render_markdown_report, scores_dataframe
from redteam_benchmark.schemas import RunResult


class ReportAgent:
    """Generate reproducible report artifacts from stored benchmark results."""

    def __init__(
        self, session_factory: sessionmaker[Session], report_dir: Path | None = None
    ) -> None:
        self.session_factory = session_factory
        self.report_dir = report_dir or get_settings().report_dir

    def load_result(self, run_id: str) -> RunResult:
        with session_scope(self.session_factory) as session:
            result = get_run_result(session, run_id)
            if result is None:
                raise KeyError(f"Run not found: {run_id}")
            return result

    def generate(self, run_id: str) -> tuple[Path, Path]:
        """Write JSON and Markdown reports and return their paths."""

        result = self.load_result(run_id)
        run_dir = self.report_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        df = scores_dataframe(result)
        chart_paths = [
            path
            for path in (
                write_category_chart(df, run_dir, run_id),
                write_rubric_chart(df, run_dir, run_id),
            )
            if path is not None
        ]

        json_path = run_dir / "report.json"
        markdown_path = run_dir / "report.md"
        adapter = TypeAdapter(RunResult)
        json_path.write_text(adapter.dump_json(result, indent=2).decode("utf-8"), encoding="utf-8")
        markdown_path.write_text(render_markdown_report(result, chart_paths), encoding="utf-8")
        return markdown_path, json_path

    def render_markdown(self, run_id: str) -> str:
        result = self.load_result(run_id)
        return render_markdown_report(result, [])

    def render_json(self, run_id: str) -> dict:
        result = self.load_result(run_id)
        return json.loads(TypeAdapter(RunResult).dump_json(result).decode("utf-8"))
