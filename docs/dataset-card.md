# Dataset Card

## Dataset Surfaces

| Surface | Purpose | May influence evaluator logic? | Included in fixed score? |
| --- | --- | --- | --- |
| Fixed suite | Comparable target-model regression | No | Yes |
| Development | Adversarial evaluator engineering | Yes | No |
| Calibration | Promotion decision after development | Metrics only | No |
| Holdout | Authorized final validation after freeze | No | No |
| Adaptive | Nearby failure discovery | No automatic promotion | No |

No loader combines these surfaces. Holdout labels require an explicit authorization flag, and
adaptive candidates are written only to review artifacts.

## Evaluator Dataset Family

`datasets/calibration/manifest_v1.json` declares dataset name, semantic version, split files,
label provenance, annotation status, independent-review status, and frozen/visibility policy.
The loader calculates a stable SHA-256 hash over split metadata and canonical examples and
reports example count plus category and severity coverage.

The development split includes clear and borderline passes/failures, safe direct answers,
safety-vocabulary traps, negation, quotation, partial compliance, evaluator injection,
paraphrases, varied tones, and long responses with decisive behavior near the end. Calibration
retains the 32 balanced legacy controls. Holdout is loadable only by explicit final-evaluation
code.

All labels are project-authored synthetic controls. Independent annotation has not occurred.

## Case Schema and Controls

Evaluator examples include stable ID, category, prompt, response, expected pass/fail, severity,
five rubric scores, rationale, and adversarial tags. Fixed-suite cases include template ID,
prompt, expected behavior, failure signal, risk metadata, variation metadata, and stable hashes.

Validation checks schema, duplicate identifiers, split metadata, expected coverage, annotation
honesty, and protected reserved-test access. The independent-review record schema is stored at
`datasets/calibration/annotation_record.schema.json`.

## Annotation Requirement

Before stronger claims, two reviewers must label each item independently. Original labels and
disagreements must remain visible; an adjudicator records a final decision and reason without
overwriting either review. See [Annotation Workflow](annotation-workflow.md).

## Limitations

- Compact, synthetic, English-only coverage.
- No measured inter-annotator agreement yet.
- Placeholder wording reduces ecological validity.
- No demographic, cultural, domain-specific, or novel-attack coverage claim.
- Calibration agreement is conditional on this finite dataset version and hash.
