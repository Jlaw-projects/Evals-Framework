import json
from pathlib import Path

from redteam_benchmark.agents.self_improvement_agent import (
    SelfImprovementAgent,
    SelfImprovementConfig,
)
from redteam_benchmark.database import init_db


def test_self_improvement_loop_exports_review_candidates(tmp_path: Path) -> None:
    factory = init_db(f"sqlite:///{tmp_path / 'benchmark.db'}")

    result = SelfImprovementAgent(factory).run(
        SelfImprovementConfig(
            model="mock-policy-violating-model",
            base_url="mock",
            suite_name="assistant_policy_core",
            suite_version="1.0.0",
            num_prompts=4,
            iterations=1,
            variants_per_failure=1,
            report_dir=tmp_path / "reports",
        )
    )

    assert result.candidate_count > 0
    assert result.promoted_count > 0
    assert result.candidates_path.exists()
    assert result.report_path.exists()
    assert "Self-Improving Benchmark Loop Report" in result.report_path.read_text(encoding="utf-8")

    payload = json.loads(result.candidates_path.read_text(encoding="utf-8"))
    assert payload["loop_id"] == result.loop_id
    assert payload["candidates"]
    assert all("step-by-step exploit" not in item["text"].lower() for item in payload["candidates"])
