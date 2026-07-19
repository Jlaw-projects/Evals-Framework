# Qwen Configuration Comparison

This evidence package is a real local-model evaluation, not a mock fixture. It compares two
generation configurations of the same immutable Ollama model on the same fixed prompt set.

| Field | Baseline | Candidate configuration |
| --- | --- | --- |
| Target | `qwen2.5:3b` | `qwen2.5:3b` |
| Ollama digest | `357c53fb659c` | `357c53fb659c` |
| Temperature | `0.0` | `0.7` |
| Suite | `assistant_policy_core@2.0.0` | `assistant_policy_core@2.0.0` |
| Fixed prompts | 12 | 12 |
| Adaptive mutations | 0 | 0 |
| Evaluator | promoted `deterministic_rule_based` | same |
| Source revision | `03b98903d31144e1182fa0cdede88ed533e7c623` | same |
| Infrastructure errors | 0 | 0 |

## Result

- All 12 prompt hashes matched.
- Mean score changed from `24.42` to `23.75` (`-0.67`).
- The paired-bootstrap 95% confidence interval for the mean-score delta was `-2.67` to `+0.58`.
- Failure rate changed from `0.00%` to `8.33%`; its paired-bootstrap delta interval was
  `0.00%` to `25.00%`.
- The configured policy returned `no_regression`, because neither interval established a
  regression beyond its practical tolerance and there was no critical-failure increase.

The conclusion is deliberately modest. One 12-case run per configuration is useful as a
demonstration of paired evidence, but the intervals are wide and the candidate produced one
failed case. This does not establish general model safety or prove that temperature `0.7` is
equivalent to the baseline.

## Artifacts

- [Baseline report](baseline-report.md)
- [Candidate report](candidate-report.md)
- [Paired comparison](comparison.md)
- [Evaluator calibration report](calibration-report.md)
- [Machine-readable evaluator calibration](calibration-report.json)
- [Self-contained HTML report demonstration](report-demo.html)

![Candidate category-score screenshot](candidate-category-scores.png)

![Candidate rubric-score screenshot](candidate-rubric-scores.png)

## Reproduction

The runs used an already-downloaded local model and no commercial API key:

```bash
redteam calibrate-judge --split calibration --output-dir reports/calibration
redteam run --model qwen2.5:3b --base-url ollama \
  --suite-name assistant_policy_core --suite-version 2.0.0 \
  --num-prompts 12 --temperature 0 --model-revision 357c53fb659c \
  --no-mutate-failures --calibration-report reports/calibration/calibration_report.json
redteam run --model qwen2.5:3b --base-url ollama \
  --suite-name assistant_policy_core --suite-version 2.0.0 \
  --num-prompts 12 --temperature 0.7 --model-revision 357c53fb659c \
  --no-mutate-failures --calibration-report reports/calibration/calibration_report.json
```

## Human-label limitation

The evaluator calibration controls remain project-authored and unreviewed. The calibration
artifact records `independent_review: false`. Two independent reviewers and an adjudicator must
complete the documented annotation workflow before this project can claim independent label
validation or report inter-annotator agreement.
