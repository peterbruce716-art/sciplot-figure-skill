# Batch Visual QA Protocol

Use `scripts/score_batch.py` when a task has several required figures and completion depends on all of them. The batch gate is additive: it does not replace semantic audit, vector validation, manifest validation, or per-panel QA.

The input schema is `scientificfigure.visual_batch.v1`. Each figure record requires a unique `id`, `source`, and `actual`. Paths are resolved relative to the batch manifest. Optional per-figure thresholds are `max_mae_0_1`, `max_rmse_0_1`, `min_ssim_score`, `min_edge_score`, `min_layout_score`, `min_color_score`, `max_registration_shift_px`, and `require_canvas_match`.

The command writes a score JSON and comparison images for every evaluated figure. It returns non-zero when a file is missing, an ID is duplicated, a declared threshold fails, or the batch is otherwise incomplete. Thresholds must be fixed before the candidate is scored; do not lower them after seeing a regression.

Example:

```powershell
python scripts\score_batch.py --manifest batch.json --out-dir qa\batch --json-out qa\batch-report.json --project-root .
```

Batch visual pass only means that the declared visual gates passed. A project-level custom renderer remains capped at `semantic_near_pass` unless built-in semantic extraction and audit independently pass.
