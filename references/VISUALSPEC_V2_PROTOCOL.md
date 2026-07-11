# VisualSpec V2 Protocol

VisualSpec v2 is metadata and simple-standard-plot structure. It should not absorb every complex paper-figure drawing primitive.

## Required Fields

- `schema`: `scientificfigure.visualspec.v2`
- `figure.size_mm`
- `figure.dpi`
- `panels[].id`
- `panels[].bbox_normalized`

## Strategy Fields

Use separate fields rather than mixing method and status:

- `source_strategy`: `raw_data`, `digitized_raster`, `manual_measurement`, `vector_redraw`, `color_region_extraction`, or `pixel_trace`.
- `representation`: `semantic_vector`, `semantic_raster`, `mixed`, or `pixel_primitives`.
- `status`: final manifest status only, never a drawing mode.

Final status values:

- `semantic_strict_pass`
- `semantic_near_pass`
- `visual_trace_pass`
- `render_only`
- `not_strict`
- `failed`

## Routing

Use VisualSpec plus the generic renderer for simple line, scatter, bar, errorbar, heatmap, contour, and straightforward annotations.

Use a project-level Python/R script for complex diagrams, irregular fills, inset-heavy layouts, EBSD/phase maps, custom paths, broken axes, or domain-specific image processing. Still record the script and outputs in the manifest.

## Generic Renderer Capability Contract

The authoritative capability list lives in `scripts/capabilities.py`.

Official generic plot types:

- `line`
- `scatter`
- `errorbar`
- `fill_between`
- `grouped_bar`
- `stacked_bar`
- `heatmap`
- `contour`

Official generic annotation types:

- `text`
- `arrow`
- `rectangle`
- `polygon`

Types such as `region_fill`, `gradient_fill`, `clip_path`, `arc`, `bezier_path`, and `dimension_arrow` are project-script-only until they have renderer implementations and tests. The validator must reject them for generic VisualSpec rendering rather than accepting the spec and letting Matplotlib fail later.

## Manifest Shape

One manifest figure record represents the whole exported figure. Panels live under `figures.<figure_id>.panels`, with their own bounding boxes and optional panel QA. Do not duplicate the whole-figure export and whole-figure score into every panel record.

Use separate QA fields:

- `qa.execution_status`: `not_run`, `completed`, or `failed`.
- `qa.result`: `strict_pass`, `near_pass`, `not_strict`, or `not_applicable`.

Root manifests use `run_status`, `qa_execution_status`, `quality_status`, and final `status`; `qa_status` is compatibility only.

Final manifests should use project-root-relative paths for sources, specs, scripts, runtime, QA reports, checksums, and exports when those files are inside the project. `run_reproduction.py` treats `--out-dir` as a portable bundle root and copies external source/spec/data dependencies into it unless the dependency is intentionally external and documented.

## Strict Semantic Gate

`semantic_strict_pass` requires:

- semantic audit pass from `render_semantics.json`,
- whole-figure visual QA strict pass,
- required panel QA strict pass,
- SVG/PDF vector validation pass for `semantic_vector`.
