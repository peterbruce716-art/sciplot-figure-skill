---
name: sciplot-figure-skill
description: Use when reproducing, redrawing, auditing, digitizing, or visually optimizing scientific figures from source data, papers, screenshots, raster plots, extracted crops, multi-panel layouts, or scientific schematics.
---

# SciPlot Figure Skill

## Core Rule

Use `scripts/sciplot.py` as the default entry point and choose the **smallest workflow that supports the requested claim**.

- `quick`: explicit preview or style/layout iteration.
- `standard`: ordinary manuscript, collaborator, or data-driven work. This is the default.
- `audit`: archival/release bundles, reusable-data proof, benchmarks, attestation, or strict evidence unavailable from lighter profiles.

Python 3.14 is the supported runtime. Do not read every reference up front; load the matching protocol only when its branch is needed.

## Default Workflow

1. Identify the source: trustworthy raw/extracted data, raster-only plot, schematic, image/map, or visual-trace request.
2. Classify each panel independently; mixed figures may use different representations per panel.
3. Create or update `scientificfigure.visualspec.v2` with explicit mappings, units, geometry, annotations, QA policy, and outputs.
4. Run `scripts/sciplot.py run --profile standard` unless the request is clearly preview-only or audit-only.
5. Inspect the actual outputs. Validate data mapping, semantics, canvas safety, vector structure when relevant, and visible layout.
6. Fix in this order: geometry → axes → data marks → labels/legend → color → typography.
7. Escalate only when the requested claim needs stronger evidence.
8. Report the strongest status actually supported, plus material limitations.

For each reproduced figure, keep a dedicated runnable script and record it under `per_figure_scripts`, or use a batch runner with clear per-figure functions and output paths.

## Representation Selection

| Source | Strategy | Representation |
|---|---|---|
| Raw data or trustworthy table | `raw_data` | `semantic_vector` or `semantic_raster` |
| Raster plot only | `digitized_raster` | usually `semantic_vector` |
| Mechanism/equipment/schematic | `vector_redraw` | `semantic_vector` |
| Heatmap, contour, EBSD/phase map, micrograph | `raw_data` or `color_region_extraction` | `semantic_raster` or `mixed` |
| Appearance is explicitly more important than recovered data | `pixel_trace` | `pixel_primitives` |

A visual trace is not recovered experimental data. A raster pasted into SVG/PDF is not semantic-vector reconstruction.

## Load Details Only When Needed

| Situation | Read |
|---|---|
| Profile routing, output policy, escalation | `references/WORKFLOW_PROFILES.md` |
| Raster digitization/calibration | `references/DIGITIZATION_WORKFLOW.md` |
| Reusable renderer or changed-input proof | `references/DATA_SWAP_PROTOCOL.md`, `references/DATA_SWAP_TEMPLATE_PROTOCOL.md` |
| Shared curve geometry across segments/fills | `references/SHARED_GEOMETRY_PROTOCOL.md` |
| Batch reference-image QA | `references/BATCH_VISUAL_QA_PROTOCOL.md` |
| Scientific question, claim, panel roles | `references/FIGURE_CONTRACT_PROTOCOL.md` |
| n, center/spread, declared statistics | `references/STATISTICAL_REPORTING_PROTOCOL.md` |
| External visual priors | `references/FIGURE_PRIOR_PROTOCOL.md` |
| Mixed Python/R vector delivery | `references/MIXED_BACKEND_VECTOR_PROTOCOL.md` |
| Journal reviewer advisory | `references/JOURNAL_REVIEW_ADVISORY_PROTOCOL.md` |
| Export constraints | `references/EXPORT_REQUIREMENTS.md` |
| CJK fonts | `references/CJK_FONT_SUPPORT.md` |
| AI visual review | `references/AI_VISUAL_REVIEW.md` |
| Reconstruction connector anchors | `references/CONNECTOR_ANCHOR_PROTOCOL.md` |

Do not copy protocol detail back into this file. Keep `SKILL.md` as routing + invariants; keep deep rules in `references/` and implementation in `scripts/`.

## Command Routing

| Need | Command |
|---|---|
| Normal generation | `scripts/sciplot.py run --profile standard` |
| Fast preview | `scripts/sciplot.py run --profile quick` |
| Re-run profile checks | `scripts/sciplot.py validate` |
| Upgrade to strict bundle | `scripts/sciplot.py finalize --profile audit` |
| Fresh PDF trace | `scripts/sciplot.py trace-pdf` |
| Direct legacy audit path | `scripts/run_reproduction.py` |
| Advisor-first data workflow | `scripts/scientific_figure_pipeline.py` |

Run `--help` on the selected command instead of duplicating full flag documentation here.

## Scientific Invariants

- Preserve source provenance, units, mappings, transformations, and declared limitations.
- Never invent data, uncertainty semantics, sample size, statistical tests, significance, or causal claims.
- Error bars/bands require independent values and defensible semantics; do not duplicate `y` as `yerr` or infer uncertainty from ordinary measurement names.
- Do not resize a reference image to hide canvas mismatch during visual QA.
- `semantic_vector` must contain meaningful vector structure; raster-only spoofing fails.
- Reusable/data-swap proof is conditional: require it only for explicit reusable/data-driven claims or an equivalent audit requirement.
- AI review is advisory. Accepted suggestions require a deterministic rerun.
- Custom renderers and mixed backends do not self-certify strictness; validate the actual outputs.

## Raster and Schematic Rules

For raster plots, calibrate the plotting region and axis mapping before extracting data. Exclude legends, labels, arrows, and annotations from curve extraction. Smoothing may remove pixel stair-steps but must not invent a trend. Treat extracted values as `digitized_raster`, not primary raw data.

For schematics, prefer editable semantic primitives and preserve physical labels, units, symbols, panel letters, and relationships. If raster regions must be preserved, identify them explicitly rather than claiming the full canvas is editable.

## Status Vocabulary

- `semantic_strict_pass`: reference-backed visual, semantic, panel, and relevant vector gates pass.
- `semantic_validated_pass`: mapping, render integrity, semantics, and relevant vector checks pass without requiring visual-reference identity.
- `semantic_near_pass`: semantic reconstruction exists but reference-backed visual QA still differs.
- `visual_trace_pass`: appearance is reproduced with trace primitives without claiming recovered primary data.
- `render_only`: exports exist but evidence is insufficient for a stronger claim.
- `not_strict`: material differences or strict-gate failures remain.
- `failed`: the selected workflow did not complete successfully.

Publication readiness is separate from rendering or semantic validation.

## Completion Gate

A task is complete when the selected profile's enabled gates pass and the delivery records source inputs, source strategy, output paths, runnable script(s), representation, final status, and remaining deviations.

Additionally:

- strict reference-image work needs reference-backed visual evidence;
- semantic-vector outputs need vector validation;
- reusable/data-swap claims need the required template and changed-input proof;
- audit delivery needs bundle, lock, portability, environment, attestation, checksum, and manifest closure.

Do not run audit-only gates for ordinary `quick` or `standard` work unless the requested claim requires them.

## Common Mistakes

| Mistake | Correct action |
|---|---|
| Running full audit for every figure | Start with `standard`; escalate only when needed |
| Reading every protocol before starting | Load only the matching reference |
| Treating successful export as scientific validation | Check mapping, semantics, provenance, and relevant QA |
| Calling a raster trace editable scientific vector data | Use `pixel_trace` / `visual_trace_pass` |
| Inferring significance or uncertainty from appearance | Require explicit or auditable evidence |
| Tuning typography before geometry | Fix geometry and axes first |
