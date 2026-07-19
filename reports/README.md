# Evaluation Artifacts

Generated run directories are ignored by default because they may contain large artifacts,
local paths, or sensitive model responses. Curate and explicitly add only reports intended for
publication.

A professional published experiment should include:

- `report.md`
- `report.json`
- embedded chart images
- exact target and judge model revisions
- suite and rubric hashes
- source revision
- evaluator calibration report
- a short failure-analysis narrative

`example_report.md` is a deterministic mock demonstration, not evidence about a real model.
Generate real local-model artifacts with the commands documented in `docs/open_source_models.md`.
