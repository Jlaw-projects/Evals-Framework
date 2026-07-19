---
name: improve-eval-loop
description: Design and operate governed continuous-improvement loops for LLM evaluations, including observation, diagnosis, candidate generation, validation, memory, stopping rules, holdout protection, human promotion, and rollback. Use for adaptive red teaming, self-improving eval corpora, recurring audits, and semi-autonomous agent workflows.
---

# Improve Eval Loop

Improve the evaluation corpus and strategy without optimizing against judge bugs or contaminating
the holdout. Keep promotion human-governed.

## State Machine

Use this explicit loop:

```text
observe -> diagnose -> propose -> safety-check -> evaluate -> challenge -> review -> promote
   ^                                                                        |
   +-------------------------- update memory --------------------------------+
```

Every transition must emit a structured decision record.

## Agent Contracts

### Observer

Summarize fixed-suite failures, uncertainty, infrastructure errors, and coverage gaps. Do not
generate solutions.

### Diagnostician

Cluster failures by behavior and distinguish target failure, judge failure, dataset ambiguity,
and infrastructure failure.

### Proposer

Generate minimal candidate cases that test the diagnosed behavior. Include expected behavior,
failure signal, source lineage, and novelty rationale.

### Challenger

Attempt to falsify the candidate label and expose evaluator shortcuts, duplicated wording,
unsafe content, or holdout leakage.

### Reviewer

Approve, reject, or request changes using recorded evidence. Only this stage may promote cases.

## Memory Schema

Persist:

- Suite, rubric, target, and judge versions.
- Observed weak categories.
- Candidate lineage and deduplication hashes.
- Judge disagreement and human decisions.
- Strategy attempts, successes, and failures.
- Stop reason and resource usage.

Never store credentials, hidden holdout answers, or unredacted private prompts in strategy memory.

## Guardrails

- Freeze a holdout that candidate generation cannot read.
- Calibrate the judge before starting and after any judge change.
- Keep adaptive results outside fixed-suite headline metrics.
- Require safety validation before executing generated prompts.
- Require human review before changing packaged suites, rubrics, or gates.
- Preserve rollback to the previous suite and strategy version.
- Cap iterations, prompts, tokens, wall time, and candidate count.

## Stopping Rules

Stop when any condition holds:

- Infrastructure errors prevent valid measurement.
- No new failure cluster or coverage gain appears for the configured patience window.
- Candidate novelty falls below threshold.
- Judge disagreement exceeds tolerance.
- The iteration or resource budget is exhausted.
- Human review is required.

Do not use "the current model passes" as the only stopping rule; that invites overfitting to one
target and one evaluator.
