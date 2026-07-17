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

For `grouped_bar`, the default remains side-by-side groups using `bar_width`. The optional style fields support raster-faithful layouts without project-private renderer logic:

- `group_mode`: `side_by_side` or `overlap`.
- `group_offset`: shared center spacing for side-by-side or overlapping groups.
- `bar_widths`: per-group widths; its length must match `data.groups`.
- `group_offsets`: explicit per-group center offsets relative to each `data.x`; when present, it overrides the computed group spacing.

Renderers must preserve these observed widths and offsets in semantic extraction so nested or hybrid overlap remains auditable.

For bar-top uncertainty, add separate `errorbar` plots at the bar centers and set `style.line_style` to `none`; this prevents Matplotlib from connecting independent bar uncertainties with a misleading trend line.

When the uncertainties belong directly to grouped bars, prefer a `yerr` array inside each group. The grouped-bar style accepts `errorbar_color`, `errorbar_line_width_pt`, and `errorbar_capsize`; the renderer then shares the exact side-by-side, concentric, or hybrid bar centers with the uncertainty markers.

Panels may define an optional `legend` object for raster-faithful placement without changing plot semantics. Supported fields are `visible`, `frameon`, `font_size_pt`, `loc`, `ncol`, `bbox_to_anchor`, `handle_length`, `handle_height`, `column_spacing`, `label_spacing`, `border_pad`, and `handle_text_pad`. Omitted fields preserve the previous renderer defaults.

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

For fixed canvases that require a blank border, declare `qa_policy.canvas_safety` with `enabled`, `margin_px`, `background`, `tolerance`, and `required_edges`. The bundle runner fails before manifest finalization if non-background pixels enter a required edge band and records passing evidence as root-level `canvas_safety` / `canvas_safety_status`. Intentional full bleed must disable the policy or omit those edges from `required_edges`.

For fixed-canvas reproductions whose axes rectangle must match a reference, declare `qa_policy.plot_geometry_safety.enabled` plus one or more regions. Each region requires an inclusive `expected_bbox_px`, may narrow detection with `search_bbox_px`, and sets `max_edge_error_px`. The RGB selector identifies the plot background; `min_column_matches` and `min_row_matches` prevent thin arrows or annotations from expanding the measured bbox. When visible axes matter, add `axis_spines` with `expected_origin_px`, horizontal/vertical extents, a dark-pixel threshold, and minimum coverage ratios. This separately proves that the bottom and left axes actually meet; a matching background bbox is insufficient. Passing evidence is recorded as root-level `plot_geometry_safety` / `plot_geometry_safety_status`.

For boxed annotations and legends, declare `qa_policy.boxed_text_safety.enabled` plus one `regions` entry per text item. A region uses either `[left, top, right, bottom]` pixel coordinates or normalized `[left, top, width, height]` coordinates. Minimum ink height and vertical padding are deterministic; `reference_glyph_check` additionally requires `text`, `font_family`, and `font_size_px` and fails closed when the font cannot be resolved. Passing evidence is recorded as root-level `boxed_text_safety` / `boxed_text_safety_status`.

Final manifests should use project-root-relative paths for sources, specs, scripts, runtime, QA reports, checksums, and exports when those files are inside the project. `run_reproduction.py` treats `--out-dir` as a portable bundle root and copies external source/spec/data dependencies into it unless the dependency is intentionally external and documented.

## Strict Semantic Gate

`semantic_strict_pass` requires:

- semantic audit pass from `render_semantics.json`,
- whole-figure visual QA strict pass,
- required panel QA strict pass,
- SVG/PDF vector validation pass for `semantic_vector`.
