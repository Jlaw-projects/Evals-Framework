# Independent Annotation Workflow

## Current Status

The packaged evaluator controls are project-authored and unreviewed. `independent_review` is
`false`; no report may describe them as independently human-annotated until the evidence below
exists.

## Procedure

1. Freeze a dataset candidate and assign a version before review.
2. Give two reviewers the rubric and examples independently. Do not show one reviewer's labels
   to the other before both submissions are locked.
3. Each reviewer records pass/fail, severity, five dimension scores, rationale, reviewer ID,
   rubric version, and timestamp.
4. Retain agreements and disagreements verbatim in a versioned annotation record.
5. A separate adjudicator reviews disagreements, records the final label and rationale, and
   never overwrites either original review.
6. Calculate agreement statistics before changing the evaluator. Critical disagreements receive
   mandatory manual review.
7. Version any label correction, recalculate split hashes, freeze calibration/reserved-test again, and
   preserve the old release artifact.

Records must validate against
`src/redteam_benchmark/datasets/calibration/annotation_record.schema.json`. Reviewer identifiers
should be pseudonymous and must not contain email addresses or credentials.

## Separation Rules

- Development annotations may guide evaluator changes.
- Calibration results decide promotion after development logic is frozen.
- Holdout labels remain inaccessible during tuning and are opened only for an authorized final
  evaluation.
- A reserved-test failure triggers review and a new versioned development cycle; it is not silently
  folded into calibration.
