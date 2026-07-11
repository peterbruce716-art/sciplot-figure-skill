# QA Profiles

Use QA profiles to separate semantic reconstruction from pixel tracing.

## semantic

Use for Matplotlib/R/Python semantic redraws. Check canvas size, aspect ratio, content bounding box, axes/ticks, labels, legends, data curves, colors, and layout. Small antialiasing and font-rendering differences are acceptable.

`semantic_strict_pass` does not require exact pixel match.

## QA State Fields

Do not use one field to mean both "QA ran" and "quality passed".

Use:

- `qa.execution_status`: `not_run`, `completed`, or `failed`.
- `qa.result`: `strict_pass`, `near_pass`, `not_strict`, or `not_applicable`.

The legacy global `qa_status` is only a compatibility summary that QA executed successfully. The final figure/manifest `status` and `qa.result` carry the quality conclusion.

At root level prefer:

- `run_status`: `completed` or `failed`.
- `qa_execution_status`: `not_run`, `completed`, or `failed`.
- `quality_status`: `strict_pass`, `near_pass`, `render_only`, `not_strict`, `not_applicable`, or `failed`.
- `status`: `semantic_strict_pass`, `semantic_near_pass`, `visual_trace_pass`, `render_only`, `not_strict`, or `failed`.

`semantic_strict_pass` requires semantic audit, visual QA, vector validation when applicable, and all required panel QA to pass.

## visual

Use when visual placement matters more strongly. In addition to semantic checks, inspect overlay, difference, edge-difference, content shift, and local high-priority regions.

## trace

Use only for explicit pixel trace workflows. This is the only profile where strict means exact pixel match with zero MAE/RMSE.

## Comparison Artifacts

`score_visual.py` can write:

- `source_common.png`
- `render_common.png`
- `difference.png`
- `overlay_50.png`
- `edge_difference.png`

Use these images to locate layout, edge, and color errors before editing the figure script.
