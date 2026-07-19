# Evaluator Calibration Report

Dataset: `safety-evaluator-controls@1.1.0`  
Split: `calibration`  
Dataset SHA-256: `cebc2714a0272ffa878e17c895d4726bde35fa2f88411b7d0edd8bfe5ddf01a1`  
Judge: `rule-based`  
Rubric: `safety-rubric.v2` (`779faa0cb3500f07da48a1eb922bbd6719f724b3811c44ce83546dcfb91165c6`)
Evaluator implementation: `9cc69bc23b26626cbc203f8ef8cc6985a239514f57d5df493258e55ccc6319a0`

Configured evaluator method: `deterministic_rule_based`  
Observed evaluator methods: `["deterministic_rule_based"]`  
Observed method counts: `{"deterministic_rule_based": 32}`

## Label Provenance

- Annotation status: `project_authored_unreviewed`
- Independent review completed: `false`
- Provenance: Project-authored synthetic labels created during repository development; no independent annotator evidence is available.

## Promotion Decision

Status: `promoted`  
Suitable for release gates: `true`

- All declared promotion thresholds passed.

## Coverage

- Labelled examples: 32
- Evaluable examples: 32
- Deterministic fallback evaluations: 0
- Deterministic fallback rate: 0.000
- Evaluator infrastructure errors: 0
- Evaluator infrastructure-error rate: 0.000
- Categories: `{"artifact safety": 2, "citation integrity": 2, "copyright boundary": 2, "current-info uncertainty": 2, "identity honesty": 2, "image limitation honesty": 2, "jailbreak attempt": 2, "malicious request refusal": 2, "past-chat honesty": 2, "policy ambiguity": 2, "prompt injection": 2, "refusal consistency": 2, "roleplay bypass": 2, "system prompt leakage attempt": 2, "tool honesty": 2, "wellbeing safety": 2}`
- Severities: `{"critical": 2, "high": 8, "medium": 6, "none": 16}`

### Infrastructure Error Details

| Case | Category | Type | Message |
| --- | --- | --- | --- |
| None | - | - | - |

## Failure Detection

| Metric | Value |
| --- | ---: |
| Accuracy | 1.000 |
| Failure Precision | 1.000 |
| Failure Recall | 1.000 |
| Failure F1 | 1.000 |
| False Positive Rate | 0.000 |
| False Negative Rate | 0.000 |
| Infrastructure Error Rate | 0.000 |
| Cohen Kappa | 1.000 |

Confusion matrix: `{"false_failure": 0, "missed_failure": 0, "true_failure": 16, "true_pass": 16}`

## Per-Category Validation

| Category | Examples | Failure examples | Accuracy | Failure recall |
| --- | ---: | ---: | ---: | ---: |
| artifact safety | 2 | 1 | 1.000 | 1.000 |
| citation integrity | 2 | 1 | 1.000 | 1.000 |
| copyright boundary | 2 | 1 | 1.000 | 1.000 |
| current-info uncertainty | 2 | 1 | 1.000 | 1.000 |
| identity honesty | 2 | 1 | 1.000 | 1.000 |
| image limitation honesty | 2 | 1 | 1.000 | 1.000 |
| jailbreak attempt | 2 | 1 | 1.000 | 1.000 |
| malicious request refusal | 2 | 1 | 1.000 | 1.000 |
| past-chat honesty | 2 | 1 | 1.000 | 1.000 |
| policy ambiguity | 2 | 1 | 1.000 | 1.000 |
| prompt injection | 2 | 1 | 1.000 | 1.000 |
| refusal consistency | 2 | 1 | 1.000 | 1.000 |
| roleplay bypass | 2 | 1 | 1.000 | 1.000 |
| system prompt leakage attempt | 2 | 1 | 1.000 | 1.000 |
| tool honesty | 2 | 1 | 1.000 | 1.000 |
| wellbeing safety | 2 | 1 | 1.000 | 1.000 |

## Rubric Score Agreement

Mean absolute error by dimension: `{"helpfulness_within_safe_limits": 0.5938, "leakage_resistance": 0.5, "policy_consistency": 0.6562, "refusal_quality": 0.3438, "safety_compliance": 0.3125}`

## Misclassifications

| Case | Category | Severity | Expected | Predicted | Total score |
| --- | --- | --- | --- | --- | ---: |
| None | - | - | - | - | - |

## Interpretation

This report measures agreement with project-authored synthetic controls. Independent annotation
has not occurred. It does not establish universal evaluator validity or model safety.
