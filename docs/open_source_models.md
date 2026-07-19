# Running With Open-Source Models

The project is designed to work without commercial API keys. The two supported local paths
are native Ollama generation and any local server that exposes an OpenAI-compatible chat API,
including vLLM, llama.cpp server, LocalAI, and Ollama's compatibility endpoint.

## Ollama Target With Deterministic Rule-Based Evaluation

Start Ollama, ensure the model is already available locally, and run:

```bash
redteam run-config examples/ollama_local.yaml
```

Or use the CLI directly:

```bash
redteam run \
  --model your-local-model \
  --base-url ollama \
  --suite-name assistant_policy_core \
  --suite-version 2.0.0 \
  --num-prompts 12 \
  --temperature 0
```

No API key is required. `OLLAMA_BASE_URL` defaults to `http://localhost:11434`.

## Local OpenAI-Compatible Target

For vLLM, llama.cpp server, LocalAI, or another compatible runtime:

```bash
redteam run \
  --model your-local-model \
  --base-url http://localhost:8000/v1 \
  --suite-name assistant_policy_core \
  --suite-version 2.0.0 \
  --num-prompts 12
```

The API key is optional. Servers that do not require authentication work without one.

## Local Open-Source Model Judge

Ollama exposes an OpenAI-compatible endpoint suitable for judge calibration. Run:

```bash
redteam calibrate-judge \
  --judge-model your-local-judge-model \
  --judge-base-url ollama \
  --output-dir reports/calibration/your-local-judge
```

For normal benchmark runs, configure the same local judge:

```text
REDTEAM_JUDGE_MODEL=your-local-judge-model
REDTEAM_JUDGE_BASE_URL=http://localhost:11434/v1
REDTEAM_JUDGE_FALLBACK_ON_ERROR=false
```

Strict error handling is intentional. If the local judge is unavailable or returns invalid
JSON, the case becomes an evaluator infrastructure error instead of silently receiving a
score from a different evaluator.

## Local Reasoning Agents for the Improvement Loop

The continuous-improvement loop remains deterministic by default. To enable the governed
observer, diagnostician, proposer, challenger, and reviewer stages with a local Ollama model:

```bash
redteam audit-loop \
  --model your-local-target-model \
  --base-url ollama \
  --suite-name assistant_policy_core \
  --suite-version 2.0.0 \
  --num-prompts 12 \
  --reasoning-model your-local-reasoning-model \
  --reasoning-base-url ollama
```

Every stage uses a versioned prompt and strict JSON contract. The local agents may recommend
sampling weights or a review stop, but deterministic code controls allowed categories, weight
bounds, infrastructure stops, iteration budgets, and suite promotion.

## Reproducibility Notes

- Record an immutable model digest in `--model-revision` when the runtime exposes one.
- Use temperature zero for fixed regression suites.
- Keep the target model and judge model distinct when resources allow it.
- Re-run stochastic configurations over multiple seeds.
- Calibrate every judge model against the packaged gold set before using it as a release gate.
