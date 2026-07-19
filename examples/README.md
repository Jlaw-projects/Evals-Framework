# Examples

Run the fastest local demo with the deterministic mock model:

```bash
redteam run --model mock-safe-model --base-url mock --suite-name assistant_policy_core --num-prompts 10
```

The command writes Markdown and JSON report artifacts under `reports/<run_id>/`.

Run an adaptive audit loop with deterministic mock failures:

```bash
redteam run-config examples/mock_audit_loop.yaml
```

Run a CI-style safety gate:

```bash
redteam gate --config examples/mock_safety_gate.yaml
```

Minimal GitHub Actions job:

```yaml
name: LLM Safety Gate

on:
  pull_request:

jobs:
  safety-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install -e .
      - run: redteam gate --config examples/mock_safety_gate.yaml
```

List packaged suites and components:

```bash
redteam list-suites
redteam list-components
```
