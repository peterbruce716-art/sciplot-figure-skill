---
name: sciplot-figure-skill
description: Use when reproducing, redrawing, auditing, or visually optimizing scientific figures from papers, screenshots, raster images, extracted plots, source data, or multi-panel scientific schematics.
---

# SciPlot Figure Skill

## Core Rule

Use `scripts/sciplot.py` as the default entry point and choose the **smallest workflow that supports the requested claim**.

Default ordinary figure work to `standard`. Use `quick` for explicit previews. Escalate to `audit` only for archival/release bundles, reusable-data proof, benchmarks, or strict evidence that the lighter workflow cannot provide.

Do not load or reproduce low-frequency protocol details in this file. Read the matching document under `references/` only when that path is actually needed.

## Quick Start

```bash
# Windows
py -3.14 scripts/sciplot.py run \
  --input data.csv \
  --profile standard \
  --out-dir out/figure

# macOS/Linux
python3.14 scripts/sciplot.py run \
  --input data.csv \
  --profile standard \
  --out-dir out/figure
```

Python **3.14** is the supported runtime.

## Choose a Profile

| Profile | Use when | Typical result |
|---|---|---|
| `quick` | Previewing layout, style, typography, or axes | One lightweight render with basic input/output safety |
| `standard` | Normal manuscript, collaborator, or data-driven delivery | Semantic/mapping checks, vector checks when relevant, checksums, compact environment evidence |
| `audit` | Archival, release, benchmark, reusable-data, strict bundle, or attested delivery | Portable bundle, locks, full environment/attestation/portability and manifest closure |

Use `--profile auto` only when automatic routing is useful. Read `references/WORKFLOW_PROFILES.md` before changing profile selection or gate meanings.

## Main Workflow

1. **Identify the source.** Use raw/extracted data when trustworthy data exists; otherwise classify the figure as raster digitization, vector redraw, image/map, or visual trace.
2. **Inventory panels.** For multi-panel figures, classify each panel independently. Do not force curves, schematics, maps, and image panels through one representation.
3. **Create or update `scientificfigure.visualspec.v2`.** Keep scientific mappings, units, plot geometry, annotations, QA policy, and output expectations explicit.
4. **Render with the smallest suitable path.** Start with `scripts/sciplot.py run --profile standard` unless the request is explicitly preview-only or audit-only.
5. **Inspect the rendered artifact.** Validate mappings, semantics, canvas safety, vector structure when applicable, and visible layout. Compare against a supplied reference without resizing it to hide canvas errors.
6. **Fix in this order:** geometry → axes → data marks → labels/legend → color → typography.
7. **Escalate only when required.** Load the relevant protocol or switch to `audit` when the claim requires evidence not provided by the current profile.
8. **Report limitations and status exactly.** A successful export is not automatically a strict scientific or publication-ready result.

For a complex figure, preserve one runnable script per figure, or a batch runner with clear per-figure functions and paths.

## Representation Selection

| Source situation | Preferred strategy | Representation |
|---|---|---|
| Raw data or trustworthy extracted table | `raw_data` | `semantic_vector` or `semantic_raster` |
| Raster plot only | `digitized_raster` | usually `semantic_vector` |
| Equipment/mechanism/parametric diagram | `vector_redraw` | `semantic_vector` |
| Heatmap, contour, EBSD/phase map, micrograph | `raw_data` or `color_region_extraction` | `semantic_raster` or `mixed` |
| User explicitly prioritizes visual identity over recovered data | `pixel_trace` | `pixel_primitives` |

A visual trace is **not** recovered experimental data. A raster pasted into an SVG/PDF is **not** semantic-vector reconstruction.

## Load Details Only When Needed

| Situation | Read / use |
|---|---|
| Profile routing, output policy, audit escalation | `references/WORKFLOW_PROFILES.md` |
| Raster plot digitization and calibration | `references/DIGITIZATION_WORKFLOW.md` |
| Reusable renderer or changed-input proof | `references/DATA_SWAP_PROTOCOL.md`, `references/DATA_SWAP_TEMPLATE_PROTOCOL.md` |
| One curve reused across segments/fills | `references/SHARED_GEOMETRY_PROTOCOL.md` |
| Batch reference-image QA | `references/BATCH_VISUAL_QA_PROTOCOL.md` |
| Scientific question, claim, panel roles, hero panel | `references/FIGURE_CONTRACT_PROTOCOL.md` |
| Statistics, n, center/spread, declared tests | `references/STATISTICAL_REPORTING_PROTOCOL.md` |
| External figure-style priors | `references/FIGURE_PRIOR_PROTOCOL.md` |
| Mixed Python/R vector delivery | `references/MIXED_BACKEND_VECTOR_PROTOCOL.md` |
| Journal-style reviewer advisory | `references/JOURNAL_REVIEW_ADVISORY_PROTOCOL.md` |
| Export requirements | `references/EXPORT_REQUIREMENTS.md` |
| CJK font handling | `references/CJK_FONT_SUPPORT.md` |
| AI visual-review handoff | `references/AI_VISUAL_REVIEW.md` |
| Connector anchors in reconstructed schematics | `references/CONNECTOR_ANCHOR_PROTOCOL.md` |

Do not read every reference up front.

## Data-Driven Figures

For CSV/TSV/Excel redraws, preserve the source hash and explicit x/y/group/uncertainty mapping.

Use `scripts/scientific_figure_pipeline.py` when the Advisor layer is useful for profiling, chart selection, policy checks, style/font resolution, or an offline visual-review request. Advisor output is advisory; deterministic rendering and validation remain authoritative.

Uncertainty must have independent values and defensible semantics. Do not infer error bars from ordinary measurement columns, duplicate `y` as `yerr`, invent confidence intervals, or add statistical tests that are not declared or auditable. If uncertainty evidence is incomplete, render a form that does not pretend the missing evidence exists.

## Raster-Only Figures

Digitize only inside calibrated plot regions. Exclude legends, labels, arrows, and annotations from curve extraction. Preserve visible ticks, axis mappings, units, and calibration assumptions.

Use smoothing only to remove raster stair-stepping; never use it to invent a scientific trend.

For grouped-bar screenshots, scaffold and review calibration before digitizing:

```bash
py -3.14 scripts/scaffold_grouped_bar_digitizer_config.py ...
py -3.14 scripts/digitize_grouped_bar_raster.py ...
```

Treat extracted values as `digitized_raster`, not primary raw data.

If the user asks for near-exact visual fidelity and semantic redraw tuning stops improving, use a separate visual-trace path rather than mislabeling a trace as semantic reconstruction.

## Schematics and Mixed Figures

Rebuild mechanisms and schematics with editable primitives when possible: lines, polygons, arrows, labels, color regions, dimensions, and axes.

Preserve physical labels, units, symbols, panel letters, and semantic relationships. Keep text editable in SVG/PDF where practical.

For raster-only or mixed object reconstruction, use the existing object-manifest and reconstruction scripts rather than treating the whole canvas as one editable object. Preserved raster regions must remain explicitly identified as raster.

## Command Routing

| Need | Command |
|---|---|
| Normal figure generation | `scripts/sciplot.py run --profile standard` |
| Fast preview | `scripts/sciplot.py run --profile quick` |
| Re-run profile checks | `scripts/sciplot.py validate` |
| Upgrade a working project to strict bundle | `scripts/sciplot.py finalize --profile audit` |
| Fresh PDF figure trace | `scripts/sciplot.py trace-pdf` |
| Backward-compatible direct audit runner | `scripts/run_reproduction.py` |
| Advisor-first data workflow | `scripts/scientific_figure_pipeline.py` |

Use project-level Python/R renderers for unsupported complex plots, but route final outputs through the same manifest/QA closure. Run `--help` on the selected script instead of duplicating its full flag reference here.

## Scientific and QA Invariants

- Preserve source provenance, units, mappings, transformations, and limitations.
- Never invent data, significance, sample size, uncertainty semantics, or causal claims.
- Never stretch a source reference during visual comparison to improve a score.
- A lighter profile may provide less evidence; it must never upgrade the scientific claim.
- `semantic_vector` requires meaningful vector structure; raster-only spoofing fails.
- Reusable/data-swap proof is conditional. Require it only for an explicit reusable/data-driven claim or equivalent audit requirement.
- AI review is advisory. Accepted suggestions require a deterministic rerun.
- Custom renderers and mixed backends do not self-certify strictness; validate their actual outputs.

## Status Vocabulary

Use the strongest status supported by evidence, not the status the requester hopes to see:

- `semantic_strict_pass` — reference-backed visual, semantic, panel, and vector gates required for strict semantic reproduction pass.
- `semantic_validated_pass` — no visual reference is required; data mapping, render integrity, semantics, and relevant vector checks pass.
- `semantic_near_pass` — semantic reconstruction exists, but reference-backed visual QA still differs.
- `visual_trace_pass` — trace primitives reproduce appearance without claiming recovered primary data.
- `render_only` — exports exist, but semantic/visual evidence is insufficient for a stronger claim.
- `not_strict` — material differences or failed strict gates remain.
- `failed` — the selected workflow did not complete successfully.

Publication readiness is separate from successful rendering or semantic validation.

## Completion Gate

A task is complete when the **selected profile's enabled gates** pass and the delivery records:

- source inputs and source strategy;
- rendered output paths;
- runnable figure script(s);
- representation and final status;
- material deviations or limitations.

Additionally:

- strict reference-image work must have reference-backed visual evidence;
- semantic-vector outputs must pass vector validation;
- reusable/data-swap claims must include the required template and changed-input proof;
- audit delivery must pass its bundle, lock, portability, environment, attestation, checksum, and manifest closure.

Do not run audit-only checks for ordinary `quick` or `standard` work unless the claim requires them.

## Common Mistakes

| Mistake | Correct action |
|---|---|
| Running the full audit bundle for every figure | Start with `standard`; escalate only for an audit-level claim |
| Reading every protocol before starting | Load the matching `references/` file only when its branch is needed |
| Treating successful PNG export as scientific validation | Check mapping, semantics, provenance, and relevant QA |
| Calling a raster trace editable scientific vector data | Label it `pixel_trace` / `visual_trace_pass` |
| Inferring error bars or significance from appearance | Require explicit or auditable evidence |
| Tuning typography before geometry | Fix geometry and axes first |
| Hiding mismatch by resizing the source image | Compare at source scale and report residual differences |
