# Portfolio Guide

This project is best evaluated as an AI engineering portfolio project: it shows how to build a complete, safe LLM evaluation workflow rather than claiming to be a final research benchmark.

## What To Review

- `README.md` for the product positioning, quickstart, CLI/API examples, and roadmap.
- `src/redteam_benchmark/pipeline.py` and `src/redteam_benchmark/agents/orchestrator_agent.py` for the benchmark orchestration path.
- `src/redteam_benchmark/harness.py` for deterministic suite execution, retry behavior, and metadata recording.
- `src/redteam_benchmark/agents/judge_agent.py` for transparent rubric scoring.
- `src/redteam_benchmark/datasets/suites/` for safe synthetic benchmark cases.
- `src/redteam_benchmark/reporting/` for Markdown reports and chart generation.
- `tests/` and `.github/workflows/tests.yml` for the current quality gate.

## Skills Demonstrated

- LLM safety evaluation design with non-actionable synthetic prompts.
- Python package structure with typed schemas and extension protocols.
- CLI and FastAPI entrypoints over one shared pipeline.
- SQLite/PostgreSQL-ready persistence and migration support.
- Reproducible run metadata, suite hashes, prompt hashes, and report artifacts.
- Dockerized API deployment and CI-based lint/test checks.

## Evidence To Open First

The [v0.2.0 Qwen comparison](evidence/v0.2.0/README.md) is the shortest end-to-end demonstration.
It contains real local-model baseline and candidate-configuration runs, fixed prompt matching,
generated charts, evaluator calibration, and paired-bootstrap confidence intervals. The
[technical interview guide](interview-guide.md) explains the design decisions behind the
calibration, provenance, persistence, failure, and adaptive-evidence boundaries.

## Honest Limitations

- The packaged suites are intentionally compact and should be expanded for broader claims.
- The default judge is transparent and deterministic, but it is not a substitute for expert human review.
- The project is an automated safety-regression signal, not proof that a model is safe.
