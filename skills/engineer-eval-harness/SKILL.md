---
name: engineer-eval-harness
description: Build or review reproducible LLM evaluation harnesses, adapters, run manifests, retries, concurrency, provenance, persistence, metrics, and release gates. Use when execution reliability, model comparison, failure semantics, dataset separation, or production eval operations are in scope.
---

# Engineer Eval Harness

Make every result traceable to an immutable case, model configuration, evaluator method, and
execution attempt. Never let infrastructure behavior masquerade as model quality.

## Execution Contract

Before running, materialize a run manifest containing:

- Suite name, version, and hash.
- Rubric version and hash.
- Ordered prompt hashes.
- Target model and immutable revision.
- Judge model and evaluation method.
- Generation parameters and seeds.
- Retry, timeout, concurrency, and endpoint configuration.
- Source revision and dependency versions.

Hash the public manifest without credentials.

## Run State Machine

Use explicit durable states:

```text
created -> queued -> running -> completed
                           \-> failed
```

Persist the queued record before external execution. Make terminal transitions idempotent and
recover interrupted work explicitly.

## Failure Semantics

Classify failures by stage:

- `target`: no valid target response exists.
- `judge`: a target response exists but evaluation failed.
- `persistence`: results could not be committed.
- `reporting`: evaluation exists but artifact generation failed.

Exclude infrastructure failures from quality scores and fail release gates by default. Never
silently switch evaluators; record an explicitly configured fallback as a method change.

## Concurrency and Retries

- Bound concurrency per provider.
- Retry only transient transport, timeout, rate-limit, and server failures.
- Use exponential backoff with jitter.
- Preserve attempt count and final error metadata.
- Do not retry schema or policy failures as though they were transport failures.
- Support cancellation and a run-level time budget in deployed environments.

## Comparison Integrity

- Pair runs only by stable case or prompt hash.
- Cluster stochastic repeats by case.
- Keep fixed, adaptive, calibration, and holdout datasets separate.
- Report unmatched cases rather than forcing a ranking.
- Use uncertainty intervals and practical tolerances.
- Never allow aggregate means to hide a critical failure.

## Verification

Require contract tests for adapters, deterministic sampling, idempotency, retry classification,
judge outages, partial persistence, migrations, report snapshots, and baseline/candidate pairing.

