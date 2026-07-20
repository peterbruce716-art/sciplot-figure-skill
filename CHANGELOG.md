## 2026-07-20 v2.9.0 Universal Data-Swap Template Contract

- Made a reusable `scientificfigure.data-swap-template.v1` manifest mandatory for every reproduced figure, not only the AA2195 example.
- Added `trace_rerun_manifest.json` to fresh PDF trace batches so pixel-trace deliveries have an auditable, source-bound rerun contract without being mislabeled as data-swap templates.
- Added a schema validator and generic isolated runner with explicit input mode, replacement-data schema validation, output hashes, and historical-data fail-closed checks.
- Added `validate_reproduction_manifest.py --require-data-swap-template` to enforce template coverage for every declared figure.
- Added regression tests and documented the changed-input hash proof required before completion.
- Included the data-swap validator in portable reproduction runtimes so source-free bundles verify after relocation.

## 2026-07-20 v2.8.12 Per-Figure Fresh Trace Reruns

- Added one independently runnable `scripts/figN_trace.py` entry point per fresh PDF target.
- Bound each generated rerun script to the current source PDF SHA-256 and fail closed on stale or substituted inputs.
- Recorded `per_figure_scripts` in the fresh batch manifest so the five-figure completion gate is auditable.

## 2026-07-20 v2.8.11 Fresh PDF Batch Trace

- Added a source-bound fresh PDF batch runner for the AA2195 Fig. 3/12/14/15/16 set.
- Added fail-closed output freshness and historical-path rejection, source PDF identity, per-figure clip provenance, and output hashes.
- Extended native PDF trace manifests with source and output hashes for independent audit.
- Added regression tests for the five-figure declaration and fresh-lineage controls.

## 2026-07-19 v2.8.11 Reusable Data-Swap Contract

- Added `references/DATA_SWAP_PROTOCOL.md` for isolated replacement-data runs.
- Required explicit input mode, complete figure-specific shape validation,
  output isolation, and input/output hash manifests for reusable renderers.
- Clarified that alternate data must not inherit a false PDF-digitization claim
  and must not invoke a batch command that overwrites canonical fresh data.

## 2026-07-19 v2.8.10 PDF Reference Set Provenance Gate

- Added `scripts/pdf_reference_set.py` to validate PDF-derived reference manifests before fresh digitization, including current PDF hash, relative source paths, source hashes, positive clip boxes, page numbers, and DPI.
- Added regression tests for current-hash acceptance, stale-PDF rejection, and invalid clip rejection.
- Documented a deterministic PDF extraction stage so a prior PNG cannot silently become the input to a fresh run.
- Explicitly marked external PDFs as opt-in provenance inputs; ordinary source paths still reject absolute and parent-directory escapes.

## 2026-07-19 v2.8.8 Continuous Panel Baseline Contract

- Added explicit required continuous panel-baseline regions for grouped-bar references that include an x-axis baseline, while retaining optional gap rejection for references without one.
- Kept required per-bar bottom-frame checks and complete legend top-clearance checks in the same final-PNG validator.
- Added regression coverage for accepted continuous baselines and rejection of missing baselines plus clipped legends.

## 2026-07-19 v2.8.9 User-Requested Baseline Omission

- Clarified that an explicit `panel_baseline_policy: omit` request overrides a visible reference baseline for corrected grouped-bar delivery.
- Required a final-PNG gap scan proving that no panel-spanning black baseline remains while every bar retains its own bottom frame.

## 2026-07-19 v2.8.7 Grouped-Bar Bottom-Frame and PDF Crop Closure

- Changed the grouped-bar final-PNG validator to distinguish individual bar bottom frames from an independent panel baseline by checking category-gap regions and required bottom-frame regions.
- Added regression coverage for missing bar bottoms, separated category gaps, complete legend top clearance, and long baseline rejection.
- Added a reproducible PDF page-crop helper for source figures whose screenshot crop loses legend pixels or other boundary geometry.

## 2026-07-19 v2.8.6 Corrected Grouped-Bar Delivery Gate

- Added `scripts/validate_grouped_bar_delivery.py` to validate final exported PNG pixels for omitted panel-wide baselines and complete legend swatches, including the top-clear row that catches clipped legend frames.
- Clarified that exact pixel-trace audits may preserve defects in a cropped reference and must remain internal when a user requests a corrected grouped-bar delivery.

## 2026-07-19 v2.8.5 Fresh Output Provenance Closure

- Extended `scripts/validate_source_policy.py` to validate declared `fresh_outputs_required` JSON artifacts, including project-relative paths, current source hashes, allowed reference binding, and explicit historical-data exclusion.
- Added regression coverage for valid fresh artifacts and stale-output hash rejection so a rerender cannot silently reuse old digitization results.

## 2026-07-19 v2.8.4 Portable Manifest Validation Reports

- Preserved a caller-supplied relative `--root` in manifest-validation JSON while still resolving it internally for file checks.
- Prevented validator-generated QA reports from failing the skill's own portability gate solely because `--root .` was expanded to an absolute Windows path.
- Excluded `validate_portability.py`'s own `--json-out` from its scan so a stale report cannot poison all later runs.
- Added regression tests for relative-root report output and portability-report self-exclusion.

## 2026-07-19 v2.8.4 Canonical Corrected Delivery Mode

- Added explicit guidance for requests that select one corrected reference format and prohibit alternate user-facing versions.
- Require one contract-checked semantic export per figure under the declared corrected-delivery directory, with trace/semantic tracks retained only as internal QA evidence.

## 2026-07-19 v2.8.4 Trace PDF Vector Primitive Regression Fix

- Fixed `trace_image_primitives.py` so PDF output is built from grouped RGB run-length vector paths instead of a full-page Pillow raster image.
- Added manifest evidence (`pdf_vector_primitives_used`) and regression coverage requiring trace PDFs to contain vector primitives and no `/Image` XObjects.
- Added NumPy-only `smooth_curve_points()` for deterministic raster stair-step removal with endpoint preservation, shape-preserving cubic interpolation, and optional bounds clipping.
- Clarified grouped-bar geometry: shared bar bottoms do not justify an independent panel-wide baseline; preserve each rectangle's own bottom outline and validate the exported image for accidental continuous baseline lines.
- Clarified strict raster-reference delivery: pixel-trace output is authoritative for exact identity, while semantic/corrected redraws remain secondary and cannot be promoted by layout metrics alone.
- Added a grouped-bar contract for explicit baseline policy, zero-white-gap contacts, shared bottom coordinates, and centered circular labels, with final-export rather than intermediate-render validation.
- Fixed the common-bottom guidance to recompute grounded segment heights from `bottom - top`, preventing one-pixel bar-base drift when raster-derived heights and bottoms disagree.

## 2026-07-19 v2.8.4 Fresh Raster Reproduction and Semantic QA

- Replaced substring-based uncertainty detection with token-boundary and phrase matching plus auditable match evidence.
- Added explicit uncertainty priority, physical-axis ID safeguards, missing-value fallback, and fail-closed value checks for negative, non-numeric, length-mismatched, copied, or same-source uncertainty.
- Added ChartDecision-to-VisualSpec x/y/uncertainty/source-hash consistency gates and bundled the shared uncertainty runtime module.
- Restricted automatic bands to SD/SE (SE uses group count); confidence intervals require explicit lower/upper bounds, and generic xerr mappings fail closed.
- Separated render integrity, mapping validity, and publication readiness so export success cannot certify a scientifically invalid mapping.
- Extended inline and grouped-bar uncertainty validation and regression coverage for the v2.8.4 release.
- Tightened semantic visual strictness: SSIM, edge, layout, and registration-shift evidence are now required in addition to MAE and canvas checks; low-MAE shifted figures are downgraded honestly.
- Added raster grouped-bar error-bar extent detection with explicit semantic safeguards: the visible pixel span is auditable, but no SD/SEM/CI meaning is inferred from the image.

## 2026-07-18 v2.8.3 Ambiguous-Occlusion and Edge-Contact Guards

- Changed foreground-only vertical bridges to explicit opt-in evidence because an aligned legend swatch is pixel-indistinguishable from a fully covered background cap.
- Preserved near-equal nested bars when a short visible cap still has a same-color edge continuing to the baseline; the minimum-height guard now applies only to ambiguous foreground-bridge evidence.
- Stabilized wide-background ordering and baseline visibility when narrow foreground layers leave only small positive overlap after raster overdraw; edge contact alone remains side-by-side.
- Strengthened grouped-bar regressions with a threshold-height swatch and a small-overlap/adjacent mixed-layer layout.

## 2026-07-18 v2.8.2 Grouped-Bar Fail-Closed Review Gates

- Propagated unresolved equal-width fallback into `calibration_status` and `unresolved_segments`; the digitizer now rejects unreviewed scaffold configs instead of converting them into a passing audit.
- Replaced left-edge-only color-layer ordering with overlap-aware back-to-front ordering, preserving a wide background even when a legal foreground bar protrudes beyond its left edge.
- Rejected compact non-baseline components before foreground-bridge evaluation so adjacent legend swatches cannot borrow a real bar's baseline continuity.
- Added structured occlusion evidence with evidence type and source-pixel intervals while preserving the existing evidence-group field.
- Added red-green regressions for the scaffold-to-digitizer review gate, adjacent swatch bridging, and offset foregrounds that protrude beyond a wide background.

## 2026-07-18 v2.8.1 Panel-Specific Grouped-Bar Geometry

- Detect grouped-bar color layers, widths, and offsets independently for each panel.
- Preserve distinct side-by-side, concentric nested, and offset-foreground layouts within one multi-panel raster figure.
- Added explicit `baseline_visibility` handling with positive edge-continuity or foreground-bridge evidence for bars whose normal baseline contact is covered.
- Prevented compact legend swatches from replacing occluded bar-height measurements; unverified candidates now produce no data row and a non-passing audit.
- Marked unresolved equal-width scaffold fallback as `review_required` instead of a passing calibration.
- Added regression coverage for a triptych whose second panel is concentric while its third panel uses D-left/F-right foreground bars over a wide B bar.
- Aligned GitHub Actions with the declared Python 3.14 runtime.

## 2026-07-18 v2.8.0 Academic Figure Integration

- Added VisualSpec layout.inference_log so auto-derived hero panels, fallback archetypes, default narrative order, and hero-panel weight promotion remain machine-traceable.
- Added StatisticsReport declared-statistics import through --statistics-json and aligned publication-readiness blockers for unknown n definitions and missing source traces.
- Fixed default FigureContract generation so a provided hero panel ID is represented by the generated default panel plan.
- Added protocol references and lightweight bundled examples for FigureContract, StatisticsReport, and all four layout archetypes.
- Added VisualSpec-compatible figure priors with provenance and validation.
- Added mixed backend audit and composition manifest scripts.
- Added journal reviewer advisory policy, protocol docs, and expanded rubric scope.
- Added third-party provenance records for academic-figure-skill concept adaptation.
- Added integration reports and focused regression tests.

# Changelog

## 2026-07-16 v2.7.1 Grouped-Bar Raster Reproduction

- Added explicit-calibration raster digitization for side-by-side, concentric nested, and hybrid nested grouped bars, with CSV and audit JSON outputs.
- Added optional panel-level legend layout controls and disconnected error-bar rendering through `line_style: none`.
- Added group-bound `yerr` rendering so grouped-bar uncertainty markers share the exact bar-center geometry.
- Added schema, semantic-validation, documentation, and regression coverage for the new grouped-bar workflow.
- Restored the documented `generic_sci` style profile so advisor resolution and package regression remain complete.

## 2026-07-16 v2.7.0 Object Reconstruction and Advisor Closure

- Added object-manifest classification, preserved-raster geometry contracts, semantic connector anchors, two-stage rendering, object masks, region QA, diff mapping, and optional VBA delivery reports.
- Added chart-decision materialization, non-empty default FigureIntent variables, uncertainty-aware trend recommendations, render-derived policy context, and applied-style reports.
- Added explicit AI-review patch approval and deterministic-rerun contracts, examples, version checks, and regression tests.

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
## 2026-07-19 Fresh Digitization Source Closure

- Added `scripts/validate_source_policy.py` to fail closed when a fresh raster-measurement run consumes historical tables, arrays, projects, QA artifacts, non-PNG inputs, missing references, stale hashes, or absolute/parent path escapes.
- Added focused regression tests for accepted reference-only input sets and forbidden historical paths.
- Kept rendering, VisualSpec semantics, manifest statuses, and existing CLI meanings unchanged.
## 2026-07-19 v2.8.8 Continuous Panel Baseline Contract
- Added explicit required continuous panel-baseline regions for grouped-bar references that include an x-axis baseline, while retaining optional gap rejection for references without one.
- Kept required per-bar bottom-frame checks and complete legend top-clearance checks in the same final-PNG validator.
- Added regression coverage for accepted continuous baselines and rejection of missing baselines plus clipped legends.
## 2026-07-20 v2.9.0 Universal Data-Swap Template Contract

- Made a reusable `scientificfigure.data-swap-template.v1` manifest mandatory for every reproduced figure, not only the AA2195 example.
- Added a schema validator and generic isolated runner with explicit input mode, complete shape/schema declarations, output hashes, and historical-data fail-closed checks.
- Added regression tests and documented the changed-input hash proof required before completion.
