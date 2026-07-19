---
name: scientific-figure-reproduction
description: Use when reproducing, redrawing, auditing, or visually optimizing scientific figures from papers, screenshots, extracted crops, source data, raster-only PNGs, multi-panel schematics, digitized plots, or annotation-heavy figure panels.
---

# Scientific Figure Reproduction

## Advisor Layer (v2.6)

For CSV/TSV/Excel redraws, think before rendering. The optional Advisor Layer creates deterministic, reviewable artifacts and never replaces the VisualSpec renderer or QA gates:

1. Profile data with `scripts/profile_scientific_data.py` and preserve the source hash.
2. Record the scientific claim and uncertainty semantics in a `figure-intent-v1` JSON file.
3. Run `scripts/recommend_scientific_chart.py` to obtain a recommendation, alternatives, rejected choices, reasons, and required disclosures.
4. Run `scripts/evaluate_scientific_plot_policy.py` for configurable warnings and blockers.
5. Resolve a journal-like style and actual installed fonts with `resolve_style_profile.py` and `font_resolver.py`.
6. Prepare an offline visual-review request with `prepare_ai_visual_review.py` after rendering. AI review is advisory only; any accepted suggestion requires the full deterministic rerun.

Use `scripts/scientific_figure_pipeline.py` to resume these stages from one output directory. `--dry-run` stops before rendering; `--disable-advisor` preserves the pre-v2.6 path. Advisor artifacts can be attached to `run_reproduction.py` with `--data-profile`, `--figure-intent`, `--chart-decision`, `--policy-report`, `--style-profile`, `--font-resolution`, and `--ai-review`; they are copied into the bundle and recorded in `companion_artifacts`.

The Advisor is strongest for data-driven redraws. It is auxiliary for screenshot fidelity and does not recover primary data from a raster image. It does not delete outliers, infer causation from correlation, or treat a style preset as an official current journal rule.

## Object Reconstruction and Hybrid Delivery

For raster-only or mixed schematics, use the object reconstruction protocol rather than treating the whole canvas as one editable object:

1. Scaffold or author `object-manifest-v1` with stable element IDs, normalized geometry, semantic roles, z-order, provenance, and confidence.
2. Classify each element into `editable_vector`, `preserved_raster`, or `background` with `classify_reconstruction_elements.py`; record the policy and rationale.
3. Validate preserved-raster crops with `crop_preserved_assets.py` and `validate_preserved_geometry.py`. A preserved asset must keep its source hash, crop rectangle, aspect ratio, alpha behavior, and placement contract.
4. Audit connector anchors before rendering. Connector endpoints must reference stable element IDs and semantic sides or named anchors; pixel-only guesses are not accepted as complete geometry.
5. Run `object_reconstruction_pipeline.py` in its two stages. The geometry stage writes a skeleton and must pass the geometry gate before the final PNG/SVG/PDF stage. Masks, region scores, and diff-to-object mapping are emitted for QA.
6. Use `export_office_vba.py` only as an optional delivery artifact. It produces a ratio-safe VBA skeleton and reports whether runtime verification was performed. No Office dependency is required for reconstruction or deterministic QA.

The pipeline supports `--dry-run`, `--manifest-only`, `--run-geometry-stage`, `--run-final-stage`, `--export-office`, and `--create-bundle`. Do not claim full editability when a whole-canvas raster is preserved; the editability report is a required companion artifact.

## Advisor P0/P1 Invariants

- Default `FigureIntent.priority_variables` is built from x, y, grouping, and uncertainty columns and is never an empty placeholder.
- Uncertainty names are recognized only from explicit token or phrase evidence such as `sd`, `sem`, `ci95`, `error_bar`, or their documented equivalents. Ordinary measurement names are never matched by substrings. `--uncertainty <column>` has priority over name inference, and every candidate records its evidence source, matched token, and semantics.
- A trend receives error bars or bands only when independent values and declared or confirmed semantics support them. Semantics without values fall back to markers or scatter with `uncertainty_values_missing`; inferred names without confirmation do not materialize error bars.
- Error mappings fail closed for same-source y/yerr or x/xerr, negative or non-numeric values, length mismatch, row-wise measurement copies, missing evidence, and unknown definitions. A reasoned user override must be explicit and auditable; automatic inference cannot create one.
- Automatic error bands are limited to standard deviation or standard error (computed from repeated groups); confidence intervals must provide explicit lower/upper bounds, and the generic renderer does not silently drop xerr.
- Physical axes such as temperature are not suspected IDs merely because all values are unique. Identifier names such as sample/specimen IDs remain flagged.
- `ChartDecision` must be materialized into a `VisualSpec` by `chart_decision_to_visualspec.py`; unsupported mappings fail explicitly instead of silently falling back to a line plot.
- Advisor materialization verifies x/y mapping, confirmation state, uncertainty source, and source-data hash. `semantic_validated_pass` requires both `render_integrity=pass` and `mapping_validity=pass`; `publication_readiness` is reported separately and is not implied by successful export.
- Resolved style settings are applied to the renderer theme and recorded in `style_application.v1`.
- Policy context can be generated from the actual rendered artist tree with `build_policy_context_from_render.py`.
- AI review is advisory. Any accepted patch requires explicit approval and a deterministic rerun.

## Academic Figure Planning Additions

- Use scripts/build_figure_contract.py and scripts/validate_figure_contract.py for scientific questions, claims, evidence chains, panel roles, archetypes, hero panels, and approval modes. Read references/FIGURE_CONTRACT_PROTOCOL.md when authoring contracts or changing approval/hero-panel behavior.
- Use scripts/resolve_figure_prior.py and scripts/validate_figure_prior.py to adapt external visual conventions into VisualSpec-compatible hints, not copied production scripts.
- Use scripts/build_statistics_report.py and scripts/validate_statistics_report.py to record n definition, center/spread, declared test status, source trace, and publication readiness. Pass --statistics-json only for user-declared or auditable upstream statistics; the builder must import those declarations without recomputing or inventing tests. Unknown statistics may permit reproduction but block publication-ready claims. Read references/STATISTICAL_REPORTING_PROTOCOL.md before adding significance, p-value, or manuscript-readiness logic.
- Use scripts/audit_mixed_backend.py before mixed Python/R delivery. Semantic-vector panels must remain SVG/PDF unless a native raster or explicit rasterized_panel reason is recorded.
- Read references/FIGURE_PRIOR_PROTOCOL.md, references/MIXED_BACKEND_VECTOR_PROTOCOL.md, and references/JOURNAL_REVIEW_ADVISORY_PROTOCOL.md when extending these flows.

## Runtime Rule

Run this skill with Python 3.14 only. Use `py -3.14` on Windows or `python3.14` on macOS/Linux before activating a virtual environment. Do not use Python 3.10, 3.11, 3.12, or 3.13 for this skill.

## Overview

Use this skill to reproduce scientific figures with open Python-first workflows. The v2.8.11 primary deliverable is a self-contained deterministic reproduction bundle with optional Advisor artifacts, semantic coverage, verifiable attestation, shared-geometry QA, batch visual gates, object-level reconstruction, path-portable delivery JSON, and an explicit data-swap protocol. Read `references/DATA_SWAP_PROTOCOL.md` when a renderer will be reused with replacement measurements. When no reference image is supplied for a raw-data figure, successful semantic and vector checks produce `semantic_validated_pass`; this is intentionally not a visual strict claim. Do not use proprietary project conversion, desktop GUI automation, or approval-chain-dependent plotting tools in this skill.

## Workflow

1. Locate the source crop, source data, or extraction method.
2. Inventory every requested figure/panel and classify it as data plot, schematic geometry, contour/heatmap/map, image/micrograph, or mixed.
3. If only raster images are available and web use is allowed, search targeted labels, annotations, and captions for the source paper, high-resolution original, or raw data. If no reliable hit is found, record that fallback and continue from the raster.
4. Create or update a `scientificfigure.visualspec.v2` file for metadata, simple standard plots, panel layout, QA requirements, and output tracking. Accept v1 files only as legacy inputs to migrate.
5. Use `scripts/run_reproduction.py` for the normal closure. It preflights external inputs, builds a self-contained bundle, writes environment records, writes `bundle.lock.json` over immutable inputs/runtime/environment/entrypoints, validates the spec, runs bundle-local `reproduce.py`, scores whole-figure and panels, audits semantics from actual renderer objects, checks SVG/PDF vector output, finalizes the manifest, writes per-run attestation, validates path portability, writes and verifies canonical checksums, validates the manifest, and returns non-zero when incomplete.
6. For complex schematics, EBSD/phase maps, irregular fills, broken axes, custom paths, or domain-specific image processing, create a project-level Python/R script and still route it through the manifest/QA closure.
7. Export PNG, SVG, and PDF.
8. Compare source and render with image metrics that preserve source scale; never stretch the source image to hide canvas errors.
9. Patch geometry, axes, plots, labels, colors, and typography in that order.
10. When a logical curve is split into visible pieces, reused as a fill boundary, or paired with a local fill, load its geometry once and derive every artist from the same immutable source object and hash. Read `references/SHARED_GEOMETRY_PROTOCOL.md` and retain the geometry audit.
11. Preserve one runnable script per reproduced figure, or a batch runner plus documented per-figure functions/sections when that is more practical. Record each script path in the manifest or notes.
12. Record deviations honestly; do not mark the result strict when it still differs.

## Mode Selection

Choose a reconstruction mode before drawing:

| Source situation | `source_strategy` | `representation` | Notes |
|---|---|---|
| Raw data or trustworthy extracted table exists | `raw_data` | `semantic_vector` or `semantic_raster` | Replot from data; preserve units, scales, legends. |
| Raster plot only | `digitized_raster` | `semantic_vector` | Map plot bbox/ticks to data coordinates; export extracted CSV. |
| Equipment, mechanism, or parametric diagram | `vector_redraw` | `semantic_vector` | Rebuild with editable primitives and text. |
| Contour, heatmap, EBSD, phase, or image map | `color_region_extraction` or `raw_data` | `semantic_raster` or `mixed` | Prefer source arrays; otherwise document extracted color regions. |
| User explicitly wants visual trace | `pixel_trace` | `pixel_primitives` | Visual match only; not semantic scientific reconstruction. |

For multi-figure tasks, modes may differ by panel. Do not force all panels through one method when the figures mix curves and schematics.

Final manifest status is a separate field. Use only `semantic_strict_pass`, `semantic_near_pass`, `visual_trace_pass`, `render_only`, `not_strict`, or `failed`.

`semantic_strict_pass` does not require exact pixel match. It does require semantic audit pass, visual QA strict pass, vector validation pass for `semantic_vector`, and all required panel QA strict pass. If semantic audit fails, the result must be `not_strict`; do not soften it to `semantic_near_pass`. Exact pixel match belongs only to trace-profile/pixel-trace work.

`qa.execution_status` records whether QA ran (`not_run`, `completed`, `failed`). `qa.result` records quality (`strict_pass`, `near_pass`, `not_strict`, `not_applicable`). At root level use `run_status`, `qa_execution_status`, `quality_status`, and final `status`; legacy `qa_status` is compatibility only and must not be treated as quality pass.

## Raster Plot Digitization

- Identify the plotting rectangle, axis limits, tick labels, units, and log/linear scale before extracting curves.
- Segment curves by color or contrast only inside the plotting rectangle; exclude legends, labels, arrows, and peak annotations.
- Check connected components so legend strokes or short labels are not mistaken for data.
- Export digitized data with at least `panel`, `curve`, `x`, and `y` columns; include units in notes or column names when known.
- Use smoothing only to remove pixel stair-steps. Do not invent trend lines, error bars, or statistics. For deterministic NumPy-only smoothing, use `scripts/shared_geometry.py:smooth_curve_points()` with endpoint preservation and explicit bounds.
- If a crop edge, baseline, or axis mapping is unreliable, use visible ticks, labeled peaks, plateaus, or stated values only as documented visual calibration. Mark the result as digitized approximation, not primary experimental data.
- When peak labels are visible, verify extracted maxima against those labels and note any mismatch.
- For same-layout raster small multiples of grouped bars, scaffold the calibration JSON first, review it, then digitize. Do not hand-type repeated panel boxes, offsets, widths, and colors when they can be detected and audited.
- Detect group widths and horizontal offsets independently for every panel. A single figure may combine side-by-side bars, concentric nested bars, and left/right foreground bars over a wider background bar; never propagate one panel's nesting geometry to another panel.
- Treat `baseline_visibility: occluded_by_front_groups` as an explicit calibration fact for a covered background or middle bar. By default, accept a non-baseline-connected run only when it is tall enough and a narrow same-color edge continues to the baseline. A foreground-only vertical bridge is pixel-ambiguous with a legend swatch, so it requires explicit `allow_front_group_bridge: true` after manual review. Record evidence type and pixel interval. Otherwise omit the row and fail the audit.
- A scaffolded grouped-bar config is consumable only when `calibration_status` is `pass` and `unresolved_segments` is empty. Equal-width fallback remains `review_required` across the scaffold-to-digitizer boundary and must fail closed until manually resolved.


## Raster-Only Visual Fidelity Fallback

When the only available source is a raster chart and the user asks for a result that is "fully close", "exact", "completely close to the original", or otherwise prioritizes visual fidelity over editable scientific reconstruction, use a dual-track output:

- Keep or create a semantic reconstruction when it is useful for editable axes, bars, curves, labels, and approximate digitized values, but cap it at semantic_near_pass unless built-in semantic and visual QA genuinely pass.
- Add a separate pixel_trace / pixel_primitives output for the high-fidelity visual deliverable. This may use vector pixel primitives or other trace primitives, but it must not paste the source raster as the main figure and must not be described as recovered experimental data.
- Validate the visual trace with fixed-canvas source-scale QA. For exact visual requests, record whether the rendered PNG is pixel-identical to the source or provide the measured residuals and deviation ledger.
- Validate SVG/PDF outputs for parseability and reject raster-only spoofing: SVG should contain meaningful vector primitives and no full-page raster image fallback for a visual_trace_pass claim.
- In the manifest or notes, explicitly separate the two artifacts: semantic data/editable reconstruction versus visual trace reproduction. Use visual_trace_pass only for the trace artifact and never upgrade it to semantic_strict_pass.

If repeated geometry, color, typography, antialiasing, or legend tuning fails to materially improve a raster-only semantic redraw after a bounded iteration, stop retuning the semantic renderer and switch to this dual-track route.
## Schematic Redrawing

- Rebuild schematics with semantic vector primitives: lines, polygons, circles, arrows, dimension arrows, labels, color regions, and scale/coordinate axes.
- Preserve physical labels, symbols, units, panel letters, and relative mechanism relationships.
- Avoid raster-pasting the original into the figure unless it is explicitly an image panel or trace reference.
- After export, visually inspect labels and dimension text for overlaps at final PNG size. Fix collisions in the script, not by editing exported images.
- For annotation-heavy figures, keep text editable in SVG/PDF whenever possible.

## Tool Routing

- Use `scripts/run_reproduction.py` as the default one-command closure. It treats `--out-dir` as the portable bundle root, copies source/spec/data/runtime/custom renderer into that root, writes concise `run_report.json` summaries, and keeps detailed child-process logs under `logs/`.
- In bundles, use `render.py` only to draw exports, `reproduce.py` to rerun the full validate/render/QA/audit/vector/finalize/checksum/manifest closure after first verifying `bundle.lock.json`, and `verify.py` to verify `bundle.lock.json`, checksums, and manifest status without redrawing.
- Use `scripts/scaffold_figurespec.py` to create a VisualSpec skeleton.
- Use `scripts/validate_visualspec.py` before rendering. `validate_visualspec_v1.py` remains only as a compatibility wrapper target.
- Use `scripts/render_matplotlib.py` or `scripts/render_visualspec_matplotlib.py` for line, scatter, errorbar, grouped bar, stacked bar, fill-between, heatmap, contour, multi-panel layouts, legends, colorbars, text, arrows, rectangles, and polygons. It defaults to fixed canvas export.
- Validator and renderer capabilities come from the single source of truth in `scripts/capability_model.py`, surfaced through `scripts/capabilities.py`. The declared generic renderer plot types are line, scatter, errorbar, fill_between, grouped_bar, stacked_bar, heatmap, and contour; annotation types are text, arrow, rectangle, and polygon. v2.5 capability entries include strict audited fields such as contour x/y/z hashes and levels, heatmap aspect, bar group color mapping, fill_between boundary identity, and annotation geometry/style. Types not listed there are unsupported by the generic renderer and must fail validation or be routed to a project script.
- Use `scripts/data_resolver.py` through the renderer for CSV, TSV, JSON, NPY, NPZ, and optional Excel data sources.
- Use `scripts/scaffold_grouped_bar_digitizer_config.py` before `scripts/digitize_grouped_bar_raster.py` for grouped-bar screenshots or triptychs. Provide panel count, category count, group labels, and y-axis range; review every panel's independently detected widths, offsets, and baseline visibility before treating values as evidence.
- Use `scripts/digitize_grouped_bar_raster.py` for raster-only grouped bars after explicitly calibrating each panel rectangle, y-axis mapping, category centers, group offsets, widths, and fill colors. For scaffolded configs, require `calibration_status: pass` and an empty `unresolved_segments` list. The digitizer may recover a visible achromatic error-bar extent above each fill, but this remains visual evidence and must not be called SD, SEM, CI, or another statistical quantity without independent metadata. Keep its CSV and audit JSON as companion evidence; the extracted values remain `digitized_raster`, not raw data.
- For grouped-bar panels, preserve a continuous panel baseline when the reference visibly contains one unless the requester explicitly asks to remove it. When `panel_baseline_policy: omit` is selected, validate that panel gaps contain no long baseline-like black run. In both policies, draw and validate each bar's own bottom edge as part of its rectangle. Record this as a geometry contract and test the final exported PNG, not only an intermediate semantic render.
- For an explicitly user-constrained grouped-bar redraw, make the four contact invariants explicit: `panel_baseline_policy` (omit or preserve from reference), zero-white-gap contacts, one shared `common_bottom_px` for all bar bodies, and centered text inside circular category labels. The omit policy is a deliberate corrected-delivery transformation, not a visual-trace claim; its final export must be the exact artifact tested for both missing panel-spanning baselines and present per-bar bottom frames.
- Use `scripts/validate_grouped_bar_delivery.py` on the final PNG for corrected grouped-bar deliveries. Its contract must check either required continuous panel-baseline regions or panel-baseline gaps, every required bar bottom frame, and every legend swatch's fill plus `top_clear` row; a pixel-trace audit must not be presented as the corrected user delivery when the request requires a complete legend.
- When enforcing `common_bottom_px`, recompute every grounded bar height as `common_bottom_px - top_px`; never combine an independently measured `height_px` with a separately calibrated bottom. For stacked bars, recompute the lower segment to the common bottom and the upper segment to the shared boundary, then validate the target bottom row on the exported raster.
- Use `scripts/finalize_manifest.py` to write score reports, source paths, script paths, QA profile, and final status into `reproduction_manifest.json`.
- Use `scripts/score_visual.py` or `scripts/score_iteration.py` to score without resizing source images and to write comparison artifacts. Pass `--spec` so `qa_regions` and `ignore` masks enter the one-command closure.
- The default semantic strict visual gate requires MAE/canvas checks plus `ssim_score >= 0.85`, `edge_score >= 0.70`, `layout_score >= 0.90`, and registration shift within 2 px on both axes. Missing structural metrics fail closed; low MAE alone cannot certify strict fidelity.
- Use `scripts/score_batch.py` when all figures in a declared set must pass their own fixed visual gates. It rejects missing figures, duplicate IDs, canvas mismatch, and threshold regressions; read `references/BATCH_VISUAL_QA_PROTOCOL.md` before authoring the batch manifest.
- Use `scripts/audit_semantics.py` to compare VisualSpec expectations with `render_semantics.json` extracted from actual Matplotlib Figure/Axes/Artist objects; strict semantic status is blocked if axes, data hashes, styles, labels, legend mapping, units, annotations, coverage, or provenance fail. Provenance must distinguish `observed`, `derived`, `declared`, and `unavailable`; strict built-in semantic closure must not depend on `declared` or `unavailable` critical plot/annotation fields.
- Use `scripts/check_vector_output.py` to validate SVG/PDF parseability and reject raster-only or full-page-raster-spoofed semantic-vector output. SVG semantic-vector output must keep raster coverage at or below 0.05 after intersecting raster images with the canvas and must contain meaningful vector content. Semantic-vector PDF validation requires `pypdf`; missing `pypdf` is a failure rather than a text-scan fallback. Fake/minimal PDFs without a valid cross-reference/EOF structure must fail.
- Use `scripts/check_canvas_safety.py` for fixed-canvas plots whose outer border is expected to remain blank. It fails when non-background pixels enter any required edge band and writes `qa/canvas_safety.json` when enabled through `qa_policy.canvas_safety`. Disable it or remove intentional full-bleed edges from `required_edges`; this guard detects edge intrusion, not text meaning or glyph completeness.
- Use `scripts/check_plot_geometry_safety.py` for fixed-canvas reproductions whose axes rectangle must match a reference. Declare the expected inclusive plot-region pixel bbox and, when axes are visible, an `axis_spines` guard under `qa_policy.plot_geometry_safety`. The checker measures the plot-region edges plus the actual left/bottom spine intersection and full spine coverage before boxed-text QA. Use row/column coverage thresholds to exclude thin arrows or annotations from background detection.
- Use `scripts/check_boxed_text_safety.py` when callout boxes or legend rows are vulnerable to font clipping or thumbnail loss. Declare each row separately under `qa_policy.boxed_text_safety`; require minimum ink height and vertical padding, and enable reference-glyph comparison when the exact font is available. The bundle fails before manifest finalization if any declared row fails.
- Use `scripts/bundle_lock.py` to write or verify immutable bundle state. `bundle.lock.json` covers the copied VisualSpec, inputs, runtime, entrypoints, renderer configuration, and environment records. It does not cover mutable run reports, QA logs, outputs, checksums, or attestation.
- Use `scripts/environment_policy.py` to record or verify exact, compatible, or record-only runtime policy. Bundles default to exact policy for Python/package versions and require `pypdf` plus `scikit-image`.
- Use `scripts/verify_checksums.py` to write final byte and canonical checksums only after the final manifest and run attestation exist, and to verify delivery files plus unexpected-file absence. `logs/`, `run_report.json`, checksum files, generated verification reports, and Matplotlib config/cache files are not immutable payload files. `run_attestation.json` is checksum-protected but is still an integrity snapshot, not a cryptographic signature.
- Use `scripts/check_environment.py` before diagnosing font or dependency-related visual drift.
- Use `scripts/validate_source_policy.py` for fresh-digitization runs. It validates the declared reference-only input set, forbidden historical-path tokens, current file existence, and per-input SHA-256 values before extraction or rendering. When `fresh_outputs_required` is declared, it also fails closed unless every fresh JSON artifact exists, points to an allowed reference, carries that reference's current SHA-256, and declares `historical_data_consumed: false`.
- Use `scripts/pdf_reference_set.py` before fresh digitization when the reference originates in a PDF. Its manifest must record the current PDF SHA-256, relative source PNG paths, positive PDF-point clip boxes, page numbers, DPI, and source PNG hashes; stale PDF or clip metadata fails closed before measurement.
- Use `scripts/validate_portability.py --root <bundle>` before delivery or when debugging checksum/attestation portability. Delivered machine-readable JSON must not contain host absolute paths; logs are exempt.
- Use `scripts/build_skill_package.py` and then `scripts/validate_skill_package.py --root . --zip <zip>` before sharing a skill package. ZIP paths must use `/`, and package output must exclude `__pycache__` and bytecode.
- Use `scripts/release_acceptance.py` as the stable release gate. It validates the skill root, builds and validates the ZIP, runs the official line-plot example through `semantic_strict_pass`, executes bundle `verify.py`, and runs portability validation.
- Treat `scripts/render_visualspec_r.R` as an experimental plugin unless the project already has reliable R plotting code and the output is validated by the same manifest/QA path.
- Use `scripts/trace_image_primitives.py` only when the user explicitly accepts visual trace mode; label it `pixel_trace` / `visual_trace_pass`, never semantic scientific reconstruction.
- When the requirement is strict visual identity against a supplied raster reference, route the authoritative delivery through `trace_image_primitives.py` (or an equivalent pixel-trace workflow), compare the exported PNG to the reference without resizing, and keep any semantic/corrected redraw as a clearly secondary candidate. Never promote a semantically adjusted redraw to the strict delivery just because its layout metrics pass.
- When the requester explicitly selects a corrected reference format and says not to provide other versions, use a canonical corrected-delivery mode: publish one contract-checked semantic export per figure under the declared delivery directory (for example `final_corrected/figN/figN.*`), apply the same delivery contract to every figure in the declared set, and label trace/semantic/intermediate directories as internal QA only. Do not advertise or present those internal tracks as alternate user-facing versions.
- Use `scripts/pdf_vector_trace.py` when the requested reference is a PDF and exact visual clipping is required. It preserves native PDF paths when present, records target-region raster image hashes when the paper embeds a figure as an image, and scores a fresh rasterization of the exported PDF against the source-page clip. Keep its result at `pixel_primitives` / `visual_trace_pass`; neither path recovery nor image extraction recovers primary scientific data.
- For repeated PDF figure sets, run a deterministic extraction stage first, then validate its `reference-extraction.json` with `scripts/pdf_reference_set.py`. The extraction stage must regenerate the reference PNGs from the current PDF before any digitizer reads them; retaining a previous PNG without a current PDF hash is not fresh evidence.
- Use `scripts/shared_geometry.py` in project renderers when continuous curves, visible curve segments, fill boundaries, or filled vector regions must share one source. Run `audit_shared_geometry()` and store its report with QA artifacts.
- Use `scripts/create_trace_figure_scripts.py` to generate one runnable trace script per target figure instead of hand-writing repeated wrappers.
- Use `scripts/validate_manifest.py` or `scripts/validate_reproduction_manifest.py` before final response; use `--require-strict` only with the correct QA profile.
- Use `scripts/estimate_visual_patch.py`, `scripts/apply_visual_patch.py`, `scripts/rollback_iteration.py`, and `scripts/run_visual_optimization_loop.py` only for bounded canvas/layout correction. The loop must fail if any child render, score, patch, application, or candidate step fails.
- Read `references/VISUALSPEC_V2_PROTOCOL.md` when authoring or debugging VisualSpec fields.
- Read `references/QA_PROFILES.md`, `references/DIGITIZATION_WORKFLOW.md`, and `references/EXPORT_REQUIREMENTS.md` for QA, raster digitization, and export rules.
- Read `references/export-backends.md` when choosing PNG/SVG/PDF export settings.
- Read `references/FREEZE_POLICY.md` before changing VisualSpec, manifest status semantics, default rendering behavior, output structure, or CLI meanings on the stable branch.
- Read `references/SHARED_GEOMETRY_PROTOCOL.md` before drawing split curves, curve-derived fills, or locally filled vector paths.

## Rules

- Do not paste the source crop as the main plotted image and call it reproduced.
- Do not claim "strict", "exact", or "fully close" unless the manifest and visual comparison support it.
- Do not treat export success as visual success. PNG/SVG/PDF existence means `render_only` until QA passes.
- Do not let VisualSpec become a giant drawing language. Use it for metadata, simple plots, layout, data sources, QA, and output tracking; use project scripts for complex rendering.
- Do not let VisualSpec/manifest requirements block a useful project-local reproduction when the local scripts cannot express the figure. Create a clear project script plus notes/manifest-lite and state the limitation.
- Do not let a custom command renderer self-declare semantic strict pass. It may produce valid exports and pass QA, but its attestation ceiling is `semantic_near_pass` unless its semantics are independently extracted by the built-in renderer/auditor path.
- Keep `figure.crop_mode` at `fixed_canvas` by default. Use content-tight export only when the user explicitly requests cropped output.
- For fixed-canvas figures with legends, labels, or callouts near the canvas boundary, declare `qa_policy.canvas_safety` and require a clear outer margin. Treat a failed required edge as incomplete output. Intentional full-bleed figures must explicitly disable the gate or declare only the edges that should remain blank.
- For custom Python/R fixed-canvas reproductions, declare the reference plot-region bbox and visible axis spines under `qa_policy.plot_geometry_safety`, then verify them after every export. A background rectangle is not evidence that the bottom/left axes meet. In R, use an explicit normalized `par(plt=...)` region and draw complete spines when exact axes placement is required; do not tune `mar` visually and assume device/font margin conversion will preserve the reference origin.
- For R legends and boxed annotations, render the final PNG with a glyph-complete backend such as `ragg::agg_png`, declare each text row in `qa_policy.boxed_text_safety`, and verify the exported pixels at delivery size. A complete surrounding rectangle does not prove that the glyph interior is complete.
- Prefer semantic objects: curves, bars, contours, heatmaps, text, arrows, regions, and labels.
- For schematic figures, extract object coordinates and rebuild with vector primitives.
- For contour/heatmap figures, prefer source data or extracted color regions over hand-tuned analytic surfaces.
- If using trace primitives for exact visual matching, state that the result is visually strict but not semantic scientific data reconstruction; pixel trace cannot claim semantic strict pass.
- Do not use `near_not_strict`; use `semantic_near_pass` or `not_strict`.
- Do not default to Arial-only rendering. Use font candidates and record resolved fonts.
- Every target figure must keep a dedicated runnable script, even when a combined batch runner also exists.
- A manifest must list `per_figure_scripts` for every reproduced figure before claiming completion.
- A manifest should store paths relative to the project root whenever files are inside the project. Do not write absolute source/export/script paths into the final manifest unless the file is intentionally outside the project and documented.
- A bundle must keep `visualspec.json`, copied inputs under `inputs/`, runtime under `runtime/`, exports under `outputs/`, QA artifacts under `qa/`, immutable state in `bundle.lock.json`, per-run state in `run_attestation.json`, and hashes in `checksums.json` whenever `run_reproduction.py` is used.
- A bundle must keep `environment/requirements.txt`, `environment/requirements-lock.txt`, `environment/environment.json`, `environment/fonts.json`, and `environment/environment_policy.json`. Child Python processes should run with `PYTHONDONTWRITEBYTECODE=1`, `MPLBACKEND=Agg`, fixed single-thread numeric environment variables, a temporary `MPLCONFIGDIR` outside the bundle, and deterministic Matplotlib metadata settings. Record resolved font family/style/weight/filename/hash and FreeType where possible; do not record host interpreter or font absolute paths in delivery JSON. Do not include Matplotlib font cache as immutable payload. `__pycache__`, `.pyc`, and `.pyo` files are unexpected in delivered bundles.
- Delivery JSON must be path-portable: use bundle-relative POSIX paths, command role/script/arguments structures, and `project_root: "."`; keep raw absolute command lines only in logs.
- Run manifest validation before final delivery; do not rely on a narrative claim that files exist.
- Preserve units, log scales, tick locations, legends, panel labels, and captions.
- Never digitize adjacent pieces of one continuous curve into separate arrays. Never hand-tune a fill boundary independently of the line it follows. A repeated logical `source_id` with different geometry hashes is a QA failure.
- Keep project-specific scripts in the project until they are reusable across more than one task.

## Python Quick Start

```powershell
py -3.14 scripts\scaffold_figurespec.py --figures fig1 --json-out visualspec.json
py -3.14 scripts\check_environment.py --json-out outputs\environment.json
py -3.14 scripts\run_reproduction.py --spec visualspec.json --source source.png --out-dir outputs\fig1 --require-strict
py -3.14 scripts\release_acceptance.py
```

## R Quick Start

```powershell
Rscript scripts\render_visualspec_r.R --demo --out-dir outputs\r_demo
```

For VisualSpec input with R, install `jsonlite` in the active R library and run only when the project already has reliable R plotting code:

```powershell
Rscript scripts\render_visualspec_r.R --spec visualspec.json --out-dir outputs\r_render
```

## Completion Gate

A run is complete only when the manifest lists source inputs, rendered exports, visual scores, per-figure scripts, source strategy, representation, final status, and remaining deviations. If any figure is still approximate, label it `semantic_near_pass` or `not_strict`; do not soften the wording.

When the full manifest workflow is unavailable, the notes/manifest-lite must list source inputs, scripts, export paths, reconstruction modes, key transformations, calibration assumptions, and remaining deviations.

Do not call a multi-figure task complete unless each requested figure has:

- a source path,
- a rendered PNG/SVG/PDF or declared alternative,
- whole-figure and panel visual score or deviation ledger,
- a per-figure runnable script path.

Before final delivery, freshly verify:

- `scripts/run_reproduction.py` or an equivalent project runner completes from the project root,
- `reproduce.py` can run from the bundle root without the original skill directory,
- `bundle.lock.json` passes before rerendering and `verify.py` fails if tracked runtime, inputs, entrypoints, renderer configuration, or environment records are modified,
- every expected SVG/PDF/PNG exists,
- PNG previews are non-empty and have plausible dimensions,
- required fixed-canvas edge bands pass `check_canvas_safety.py`, or intentional full bleed is explicitly declared,
- every enabled plot-region bbox passes `check_plot_geometry_safety.py`, including the lower-left plot origin and all four edges,
- every enabled boxed-text region passes `check_boxed_text_safety.py`, including each legend row rather than only the enclosing legend frame,
- at least one visual preview inspection was performed,
- digitized CSV files have rows and documented coordinate mapping,
- `checksums.json` contains stable canonical hashes for deterministic outputs and `verify.py` reports unexpected non-exempt files,
- `scripts/validate_portability.py --root <bundle>` reports `status: pass` and no failures,
- the manifest or notes/manifest-lite records limitations,
- any workspace log/memory file required by the project was updated safely.

Use these status names:

- `semantic_strict_pass`: semantic objects, visual QA, vector validation, and panel QA all pass strict gates.
- `semantic_near_pass`: semantic objects are reconstructed but visual QA still differs.
- `visual_trace_pass`: trace primitives match visually but do not recover scientific data.
- `render_only`: exports exist but source-image QA has not passed.
- `not_strict`: remaining differences are material.
