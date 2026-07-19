# Technical Interview Guide

This guide is a concise explanation of the decisions that matter most in this project.

## Evaluator Calibration

The evaluator is treated as another model under evaluation. Development controls may influence
evaluator logic, the frozen calibration split decides promotion, and reserved-test labels require
explicit authorization. Calibration records the dataset and rubric hashes, evaluator
implementation hash, configured identity, observed methods, fallback use, infrastructure errors,
and confusion metrics. A model judge cannot be promoted if even one calibration case used the
deterministic fallback. A deterministic judge can be promoted only under its own deterministic
identity. This prevents a fallback's performance from silently authorizing a different evaluator.

## Provenance

Each run records the suite and rubric versions and hashes, ordered prompt hashes, target and judge
revisions, evaluator identity and method, calibration artifact, generation settings, retry and
timeout policy, dependency-lock hash, source commit, and dirty-worktree state. Credentials are
excluded from the public manifest. Strict publishability checks revalidate the underlying fields;
they do not trust a stored `public_report_ready` Boolean. The purpose is to make a result
traceable to the exact code, data, model, and evaluator that produced it.

## Database Design And Concurrency

SQLAlchemy models provide one persistence surface for SQLite locally and PostgreSQL in deployed
environments. Runs follow `queued -> running -> completed|failed`. The orchestrator commits the
queued and running transitions before external model work, performs network calls without an open
write transaction, and persists prompts, evaluations, and terminal status in short transactions.
It passes immutable records rather than live ORM objects across those boundaries. This lets a
reader observe `running` and lets another SQLite client create a run while an adapter call is
blocked.

## Failure Semantics

Target transport failures, judge failures, persistence errors, reporting errors, and reasoning
errors describe process health; they are not evidence that the target model behaved unsafely.
They are excluded from model-quality denominators and block strict release decisions when the
missing stage is required. An explicit exploratory fallback remains visible as a method change
and cannot silently become production evidence.

## Why Adaptive Cases Are Excluded From Headline Metrics

Fixed cases are versioned before the run, so baseline and candidate results can be paired by
prompt hash. Adaptive cases are generated after observing failures and therefore depend on a
particular run. Mixing them into the fixed score would give models different tests, contaminate
comparisons, and encourage overfitting to the current evaluator. Adaptive results remain useful
discovery evidence, but human review and a new versioned suite are required before a generated
case can enter future headline metrics.

## How To Describe The v0.2.0 Evidence

The published comparison changes one generation setting for the same local Qwen model while
holding the digest, suite, prompt hashes, rubric, and evaluator constant. All 12 cases match. The
mean-score delta is `-0.67`, with a paired-bootstrap 95% interval of `-2.67` to `+0.58`. The
candidate has one failed case, but the interval does not establish a regression beyond the
declared practical tolerance. The honest conclusion is not "both configurations are equally
safe"; it is that this small run did not provide enough evidence for the configured regression
rule to reject the candidate.

## Remaining Human-Review Requirement

The calibration examples are still project-authored and unreviewed. A stronger claim requires
two independent labels per example, retained disagreement, adjudication, and reported agreement.
The repository provides the schema and workflow, but it intentionally does not fabricate that
evidence.
