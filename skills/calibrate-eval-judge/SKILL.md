---
name: calibrate-eval-judge
description: Validate deterministic or model-based LLM evaluators against human-labelled gold data. Use for judge selection, rubric revisions, evaluator prompt changes, disagreement analysis, threshold setting, false-negative review, and deciding whether a judge is safe to use in release gates.
---

# Calibrate Eval Judge

Treat the judge as a model under evaluation. Do not promote it because its rationales sound
convincing.

## Workflow

1. Freeze a versioned gold dataset before evaluating the judge.
2. Verify label balance, category coverage, severities, and duplicate IDs.
3. Run the judge with strict evaluator-error handling.
4. Measure failure precision, recall, F1, false-negative rate, and kappa.
5. Measure rubric-score error when human dimension scores exist.
6. Inspect every critical false negative and a sample of true positives.
7. Slice results by category, severity, style, and adversarial tag.
8. Change one judge component at a time and rerun the frozen calibration set.
9. Version any promoted rubric, prompt, model, or label change.

## Gold-Set Requirements

Include:

- Clear passes and failures.
- Borderline cases.
- Safe answers without refusal markers.
- Unsafe answers with safety vocabulary.
- Negation and quotation counterexamples.
- Partial compliance.
- Evaluator-injection attempts.
- Multiple response styles and lengths.

Keep calibration examples separate from few-shot examples used by the measured judge.

## Promotion Gate

Set thresholds from deployment risk. At minimum:

- No unexplained critical false negatives.
- Failure recall and category recall meet the declared target.
- Infrastructure-error rate is within tolerance.
- Performance does not rely on one wording template.
- Misclassifications and limitations are published in the evaluator card.

Do not compare two judges when either evaluated a materially different gold-set version.

## Human Review

Retain annotator labels, disagreement, adjudicator decision, rationale, and timestamp. Do not
overwrite disagreement with a consensus label without retaining the original evidence.

