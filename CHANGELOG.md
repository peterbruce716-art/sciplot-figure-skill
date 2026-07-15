# Changelog

## 2026-07-16 Grouped-Bar Geometry Fidelity

- Added audited `group_mode`, `group_offset`, `bar_widths`, and `group_offsets` support for side-by-side, nested, and hybrid overlapping grouped bars.
- Added regression coverage for per-group widths and explicit center offsets.
- Preserved per-group widths and explicit center offsets in renderer semantics so nested and hybrid overlap layouts remain auditable.

## 2026-07-16 v2.6.0 Advisor and Review Contracts

- Added deterministic DataProfile, FigureIntent, ChartDecision, configurable plotting-policy, style-profile, font-resolution, and AI visual-review schemas.
- Added advisor CLIs for profiling CSV/TSV/Excel data, selecting charts with rationale, evaluating warnings, resolving installed fonts, and preparing offline visual-review requests.
- Added journal-like style presets with explicit provenance and disclaimers; no fonts are bundled.
- Added `scientific_figure_pipeline.py` with dry-run, resume-friendly output directories, optional VisualSpec generation, and optional bundle QA.
- Added optional companion artifacts to `run_reproduction.py`; they are copied into portable bundles and listed in the final manifest without changing legacy VisualSpec behavior.

## 2026-07-14 v2.5.4 Batch Visual QA

- Added fail-closed visual scoring for declared multi-figure batches.
- Added per-figure MAE, RMSE, SSIM, edge, layout, color, canvas, and registration gates without changing single-figure scoring semantics.
- Added duplicate-ID and missing-file rejection plus per-figure comparison evidence.
- Added batch QA protocol documentation and regression tests.
- Unified public version metadata and added batch-scorer coverage to the GitHub Actions fast job.

## 2026-07-13 v2.5.3 Independent Native-Clip QA

- Fixed PDF trace QA so the source-page clip is compared with a fresh rasterization of the exported PDF instead of a duplicate of the same pixmap.
- Made canvas mismatch a scoring failure without resizing either image.
- Added explicit comparison-pipeline, independent-render, render-method, and native source-identity fields.
- Made `visual_trace_pass` contingent on a valid same-canvas independent comparison within the visual MAE gate.
- Removed an unreachable Matplotlib replay branch and made trace output paths relative to the per-figure output directory.

## 2026-07-13 v2.5.2 Shared Geometry and Native PDF Trace

- Added immutable shared-series and shared-path helpers for continuous curves, visible segments, curve-derived fills, and compound filled boundaries.
- Added blocking geometry audits for repeated source IDs with conflicting hashes.
- Added native PDF figure clipping to PNG, SVG, and PDF with exact canvas preservation.
- Added target-region source classification and hashing for native PDF paths versus embedded raster figures.
- Added regression tests for shared curve segments, fill boundaries, hash conflicts, and PDF trace export.
- Kept PDF trace output explicitly classified as `pixel_trace` / `pixel_primitives` / `visual_trace_pass`; it does not claim primary scientific data recovery.

## 2026-07-12 v2.5.1 Documentation and Source-Free Validation Fix

- Fixed the README Quick Start command to use the required `--spec` and `--out-dir` flags.
- Added `semantic_validated_pass` for raw-data figures that have no reference image but pass semantic and vector validation.
- Kept source-free validation distinct from visual strict status; `--require-strict` now fails fast unless `--source` is supplied.
- Updated manifest schemas, validators, verification behavior, and regression tests for the source-free workflow.
- Added GitHub Actions for fast, integration, source-free bundle, and release-acceptance tests.
- Unified public version references on v2.5.1.

## 2026-07-05 v2.5.1 Stability and Path Portability

- Converted deliverable JSON paths to bundle-relative POSIX paths.
- Added delivery portability validation and connected it to generated `verify.py`.
- Split fast, integration, bundle, portability, and acceptance test suites.
- Added executable release acceptance for the official line-plot example.
- Added stable-branch freeze policy.
- No changes to VisualSpec v2 semantics or supported rendering behavior.

## 2026-07-05 v2.5 Semantic Coverage and Verifiable Attestation

- Added strict semantic coverage for contour x/y/z hashes, z shape, and resolved levels; heatmap aspect; bar group colors/alpha; crossing `fill_between` boundary identity; and richer text/arrow/shape annotation styles.
- Changed provenance gating so `declared`, `unavailable`, or missing critical plot/annotation fields block strict semantic audit.
- Changed final status classification so failed semantic audit cannot become `semantic_near_pass`, and missing/failed required panel QA blocks strict status.
- Added `scripts/environment_policy.py`, exact/compatible/record-only policy metadata, `pypdf` as a formal semantic-vector PDF dependency, and stricter environment checks for `scikit-image`.
- Moved Matplotlib `MPLCONFIGDIR` to a temporary directory outside bundles and expanded font records with file paths, hashes, and FreeType metadata where available.
- Changed final checksum coverage so `run_attestation.json` is protected by checksums; attestation is documented as an integrity snapshot rather than a cryptographic signature.
- Improved canonical checksum stability with bijective SVG ID canonicalization and parser-based PDF structure canonicalization when `pypdf` is available.
- Added v2.5 regression tests for contour tamper, heatmap aspect, bar color swaps, crossing fills, text/arrow semantics, provenance gates, panel-score gates, environment mismatch, and attestation tamper.

## 2026-07-05 v2.4 Capability Closure and Bundle Integrity

- Added `scripts/capability_model.py` as the renderer/auditor capability source for supported plots and annotations.
- Extended the built-in Matplotlib path to render and extract line, scatter, errorbar, fill_between, grouped/stacked bar, heatmap, contour, text, arrow, rectangle, and polygon objects.
- Added immutable bundle locking for copied VisualSpec, inputs, runtime, entrypoints, renderer config, and environment records before rerendering.
- Added canonical output checksums and unexpected-file detection for delivered bundles.
- Added stricter vector and package validation tests, including runtime tamper detection and moved-bundle reproducibility.

## 2026-07-05 v2.3 Manifest and Portability Hardening

- Tightened final manifest portability so in-bundle source, script, export, score, checksum, and runner paths are project-root-relative where possible.
- Added stronger custom command renderer capping so command renderers cannot self-certify semantic strict pass.
- Strengthened panel-level QA propagation and status vocabulary for multi-panel figures.
- Added portable skill ZIP build/validation helpers and tests for POSIX archive paths and cache exclusion.

## 2026-07-05 v2.2 Reproducibility and QA Integrity

- Changed `run_reproduction.py` to create a self-contained bundle rooted at `--out-dir`, with copied inputs, runtime, renderer config, `reproduce.py`, outputs, QA artifacts, and checksums.
- Fixed generated reproduction entrypoints so they do not depend on the original skill path and preserve custom renderer commands.
- Added renderer semantic output plus `scripts/audit_semantics.py` so strict semantic status requires axes/data/labels/legend/units/annotation agreement.
- Added `scripts/check_vector_output.py` and strict vector gates for semantic-vector SVG/PDF exports.
- Connected VisualSpec `qa_regions` to scoring, implemented ignore masks, and added panel-level QA reports.
- Tightened VisualSpec plot validation for empty data, finite numeric arrays, length mismatches, and unknown style fields.
- Split root status fields into `run_status`, `qa_execution_status`, `quality_status`, and final `status` while retaining legacy summaries for compatibility.

## 2026-07-05 v2.1 Contract and Portability

- Added `scripts/capabilities.py` so validator and renderer share one supported plot/annotation contract.
- Connected VisualSpec and manifest validation to the JSON schema files and tightened schemas with `additionalProperties` controls.
- Made `visualspec.py` the v2 implementation surface; legacy v1 wrappers now call the v2 validator path.
- Changed renderer manifests from per-panel figure records to whole-figure records with nested panel metadata.
- Changed final manifests to prefer project-root-relative paths and split QA execution status from QA result.
- Changed image scoring to compare max-canvas padded images instead of left-top common crops, and to use real SSIM when `scikit-image` is available.
- Added timeout-aware subprocess execution and concise run reports with separate logs.
- Added `scripts/build_skill_package.py` for portable ZIP creation with POSIX paths and cache exclusion.
- Added tests for strict success, strict mismatch, capability consistency, unsupported types, portable manifests, and ZIP package portability.

## 2026-07-05

- Added `run_reproduction.py` to run validate, render, score, finalize, and manifest validation as one closure.
- Added `finalize_manifest.py` to write QA scores, script paths, source paths, and final status back into the manifest.
- Added v2 entrypoints: `visualspec.py`, `validate_visualspec.py`, `render_matplotlib.py`, `score_visual.py`, and `validate_manifest.py`.
- Added lightweight JSON schemas for VisualSpec v2 and manifest v2.
- Added QA, digitization, export, and VisualSpec v2 references.
- Changed default Matplotlib fonts from Arial-only to candidate fallback fonts.
- Changed renderer manifest defaults to `render_only`/`incomplete` until scripts and QA evidence exist.
- Changed strict QA semantics so only trace profile requires exact pixel match.
- Changed the visual optimization loop to propagate child-step failures.
