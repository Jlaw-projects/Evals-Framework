# Contributing

Contributions should preserve the benchmark's defensive and non-actionable safety posture.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m pytest
ruff check .
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m pytest
ruff check .
```

## Adding Benchmark Suites

- Add suite files under `src/redteam_benchmark/datasets/suites/`.
- Use the filename pattern `<suite_name>_<version>.json`, replacing dots in the version with underscores.
- Keep prompts synthetic, benign, and non-actionable.
- Include `template_id`, `category`, `text`, and metadata with `expected_behavior` and `failure_signal` where possible.
- Do not include malware, weaponization, fraud, self-harm, illegal operational details, or real instructions for abuse.
- Run `python -m pytest` before submitting changes.

## Adding Adapters

- Implement the `ModelAdapter` protocol in `src/redteam_benchmark/adapters.py`.
- Return an `AdapterResponse` with response text, latency, and raw transport metadata.
- Add tests for adapter factory routing and failure behavior.
- Avoid logging API keys, raw secrets, or private endpoint credentials.

## Adding Judge Logic

- Prefer transparent, deterministic checks when they are reliable.
- Keep model-judge prompts non-actionable.
- Add tests for both true positives and safe negated cases.
- Document any new rubric assumptions in `docs/methodology.md`.

## Pull Request Checklist

- Tests pass with `python -m pytest`.
- New suites remain safe and placeholder-based.
- Reports remain reproducible and include suite/run metadata.
- README or docs are updated for user-visible behavior.
- No credentials, private responses, or generated local databases are committed.
