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

Use Python 3.14. Do not read every reference up front; load the relevant protocol on demand.

Five-figure benchmark: `py -3.14 scripts/benchmark_five_figures.py --profile audit --out-dir <new-directory>`. Read `references/FIVE_FIGURE_BENCHMARK.md`; synthetic fixtures do not prove experimental accuracy or paper-image fidelity.

## Default Workflow

1. Identify the source and classify each panel independently using the table below.
2. Write `scientificfigure.visualspec.v2`: mappings, units, geometry, annotations, QA policy, outputs.
3. Run the smallest profile supporting the claim; inspect outputs and layout.
4. Fix geometry → axes → data marks → labels/legend → color → typography; rerun and report status and limitations.

Keep a dedicated runnable script per figure (`per_figure_scripts`), or batch functions with per-figure output paths.

## Representation Selection

| Source | Strategy | Representation |
|---|---|---|
| Trustworthy data/table | `raw_data` | `semantic_vector` or `semantic_raster` |
| Raster plot only | `digitized_raster` | usually `semantic_vector` |
| Mechanism/equipment/schematic | `vector_redraw` | `semantic_vector` |
| Heatmap, contour, EBSD/phase map, micrograph | `raw_data` or `color_region_extraction` | `semantic_raster` or `mixed` |
| Explicit appearance-first tracing | `pixel_trace` | `pixel_primitives` |

Traces are not recovered experimental data; raster pasted into SVG/PDF is not semantic-vector reconstruction.

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

Keep protocol details in `references/`, not this routing entrypoint.

## Command Routing

| Need | Command |
|---|---|
| Generate | `scripts/sciplot.py run --profile standard` |
| Fast preview | `scripts/sciplot.py run --profile quick` |
| Re-run profile checks | `scripts/sciplot.py validate` |
| Upgrade to strict bundle | `scripts/sciplot.py finalize --profile audit` |
| Fresh PDF trace | `scripts/sciplot.py trace-pdf` |
| Direct legacy audit path | `scripts/run_reproduction.py` |
| Advisor-first data workflow | `scripts/scientific_figure_pipeline.py` |

Use the selected command's `--help` for flags.

## Scientific Invariants

- Preserve provenance, units, mappings, transformations, and limitations.
- Never invent data, uncertainty semantics, sample size, statistical tests, significance, or causal claims.
- Error bars/bands require independent values and defensible semantics; do not duplicate `y` as `yerr` or infer uncertainty from ordinary measurement names.
- Do not resize a reference image to hide canvas mismatch during visual QA.
- `semantic_vector` must contain meaningful vector structure; raster-only spoofing fails.
- Reusable/data-swap proof is conditional: require it only for explicit reusable/data-driven claims or an equivalent audit requirement.
- AI review is advisory. Accepted suggestions require a deterministic rerun.
- Custom renderers and mixed backends do not self-certify strictness; validate the actual outputs.

## Raster and Schematic Rules

Calibrate raster plotting regions and axes; exclude legends, labels, arrows, and annotations from curve extraction. Smoothing must not invent trends. Label extracted values `digitized_raster`, never primary data.

Use editable schematic primitives; preserve physical labels, units, symbols, panel letters, and relationships. Declare preserved raster regions instead of claiming a fully editable canvas.

## Status Vocabulary

- `semantic_strict_pass`: reference-backed visual, semantic, panel, and relevant vector gates pass.
- `semantic_validated_pass`: mapping, render integrity, semantics, and relevant vector checks pass; no reference identity claimed.
- `semantic_near_pass`: semantic reconstruction exists; reference-image QA differs.
- `visual_trace_pass`: trace primitives match appearance; not recovered primary data.
- `render_only`: exports exist; insufficient validation.
- `not_strict`: material differences or strict-gate failures.
- `failed`: selected workflow unsuccessful.

Publication readiness is separate from rendering or semantic validation.

## Completion Gate

Completion requires all enabled profile gates to pass. Record source inputs/strategy, representation, output paths, runnable scripts, supported status, and deviations; exports alone are insufficient.

Require reference-backed visual evidence for strict claims, vector validation for semantic vectors, and template plus changed-input proof for reusable/data-swap claims. Audit also requires bundle, lock, portability, environment, attestation, checksum, and manifest closure. Do not run audit-only gates for ordinary quick/standard work unless the claim requires them.
