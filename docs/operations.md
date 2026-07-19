# Operations Guide

## Runtime Profiles

### Local development

- SQLite persistence.
- Mock or Ollama target.
- Deterministic evaluator.
- Local report artifacts.

### Reproducible local-model evaluation

- Ollama, vLLM, llama.cpp server, or another OpenAI-compatible runtime.
- Immutable model digest recorded through `--model-revision`.
- Fixed v2 suite, temperature zero, explicit seed.
- Strict judge errors and generated Markdown/JSON reports.

### Service deployment

- PostgreSQL with Alembic migrations.
- API authentication enabled.
- Exact target-endpoint allowlist.
- Bounded worker count and pending-job capacity.
- External supervision and persistent report storage.

The included in-process worker executor is appropriate for a single service instance. A
horizontally scaled deployment requires a durable external queue or database leasing system.

## Failure Semantics

- Target transport failures are `infrastructure_error` at stage `target`.
- Judge transport/schema failures are `infrastructure_error` at stage `judge`.
- Infrastructure errors are excluded from model safety scores and fail gates by default.
- Explicit fallback is allowed only when configured and is recorded in every affected score.
- Calibration promotion rejects any fallback-derived or mixed-method evidence.
- Unexpected run-level failures transition the durable run record to `failed`.
- Adaptive reports separate `model_risk`, `audit_status`, and `release_decision`. Any failed
  required reasoning, evaluator, persistence, or reporting stage makes the release decision
  `unknown`, even if evaluable target behavior appears low risk.
- Audit schema `2.0` retains `final_risk` only as a deprecated alias for `model_risk`.

SQLite runs use short transactions: queued and running states are committed before external
adapter work, prompts/results are persisted in bounded transactions, and terminal state is
committed separately. Readers can observe `running`, and another run can be submitted while an
adapter call is blocked.

## Security Checklist

- Configure `REDTEAM_SERVICE_API_KEY` outside local-only environments.
- Restrict `REDTEAM_API_ALLOWED_BASE_URLS` to exact trusted endpoints.
- Never commit `.env`, databases, raw private prompts, or credentials.
- Treat model and judge outputs as untrusted data in reports and downstream systems.
- Review report-retention policy when prompts or responses may contain user data.
- Run the service with least-privilege filesystem and network permissions.

## Release Checklist

1. Validate all suites.
2. Calibrate the selected judge.
3. Run the fixed baseline and candidate suites with matched case hashes.
4. Review infrastructure errors and critical failures.
5. Inspect per-category deltas and failure examples.
6. Store reports with immutable model, source, suite, and rubric provenance.
7. Run the configured safety gate. Production mode revalidates completed status, fixed-suite
   completeness, strict provenance, and exact promoted evaluator-method authorization.

`gate.require_publishable_run` defaults to `true`. Setting it to `false` produces an explicitly
labelled exploratory threshold result, never production-release approval.
