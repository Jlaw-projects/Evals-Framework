# Agent Instructions

This repository treats evaluation agents as governed components with explicit inputs, outputs,
state transitions, and validation. Do not add an `Agent` class unless it owns a distinct decision
contract that is persisted and tested.

## Skill Routing

- Use `skills/engineer-eval-prompts/SKILL.md` for suite cases, rubric anchors, target prompts,
  judge prompts, and adversarial controls.
- Use `skills/engineer-eval-harness/SKILL.md` for execution, retries, provenance, comparison,
  persistence, and failure semantics.
- Use `skills/calibrate-eval-judge/SKILL.md` for evaluator selection, calibration, thresholds,
  and misclassification analysis.
- Use `skills/improve-eval-loop/SKILL.md` for adaptive audits, strategy memory, candidate
  generation, stopping conditions, and human promotion.

Read the relevant skill completely before changing that evaluation surface.

## Non-Negotiable Invariants

1. Never count an infrastructure error as a target-model safety failure.
2. Never silently change evaluator methods within a run.
3. Never mix adaptive or calibration examples into fixed-suite headline metrics.
4. Never auto-promote generated cases into a packaged suite.
5. Never expose holdout labels to candidate-generation agents.
6. Record versions and hashes for suites, rubrics, prompts, targets, judges, and run configs.
7. Keep local/open-source model execution fully supported without commercial API keys.

