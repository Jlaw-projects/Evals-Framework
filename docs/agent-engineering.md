# Agent Engineering

This project treats agents as governed decision components, not autonomous sources of truth.
Prompt engineering, harness engineering, and loop engineering have separate responsibilities and
testable contracts.

For compatibility, several deterministic helper classes retain names ending in `Agent`:
`RedTeamJudgeAgent`, `BlueTeamJudgeAgent`, and `AuditorJudgeAgent`. They collect lexical evidence
and apply fixed policies; they are not autonomous agents and do not have semantic understanding.
The optional five-stage reasoning pipeline is model-driven, but advisory. The orchestrator,
pipeline, report generator, and mutation workflow are deterministic workflow stages.

## Prompt Engineering

The five audit roles live in `src/redteam_benchmark/agents/agent_prompts.py`. Each template has a
semantic version and stable SHA-256 hash. System prompts define one bounded responsibility, mark
all audit state as untrusted quoted data, prohibit changes to labels and policies, and require one
strict JSON response.

The observer reports measured evidence. The diagnostician separates target, evaluator, dataset,
and infrastructure hypotheses. The proposer recommends a bounded sampling experiment. The
challenger searches for overfitting and weak evidence. The reviewer produces final advisory
weights and a stop recommendation.

## Harness Engineering

The harness validates every agent response with a strict Pydantic schema. It discards unknown
categories, clamps sampling weights to 0.5 through 5.0, records each stage and prompt hash, and
turns invalid model output or transport failure into an explicit reasoning-agent error.

The reasoning model cannot change scores, labels, rubrics, thresholds, packaged suites, or fixed
benchmark results. It cannot override target or evaluator infrastructure errors.

## Loop Engineering

Each iteration first makes a deterministic decision from persisted benchmark evidence. Agent
advice may refine only the next iteration's category weights. Deterministic controls retain the
authority to stop for infrastructure errors, maximum iterations, and human-review conditions.
Minimum iteration limits cannot be bypassed by model advice.

Generated or mutated cases remain an adaptive evaluation surface. They are reported separately
from the fixed suite and require human approval before promotion.

## Continuous Improvement Cycle

1. Run the immutable fixed suite and preserve full provenance.
2. Calibrate the evaluator independently on labelled gold examples.
3. Diagnose category gaps and evaluator disagreements.
4. Run bounded adaptive tests without changing the headline score.
5. Review candidates and failures manually.
6. Version any approved dataset, rubric, or prompt change.
7. Rerun calibration, fixed-suite comparisons, and release gates.

This is semi-automated by design: local agents accelerate analysis while humans retain authority
over the measurement system.
