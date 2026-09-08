# Workflow Profiles

`scripts/sciplot.py` is the user-facing workflow entry point. Existing low-level scripts remain stable compatibility and audit tools.

## Gate Matrix

| Gate | Quick | Standard | Audit |
|---|---:|---:|---:|
| Input existence/hash/schema | required | required | required |
| Mapping validation and output path isolation | required | required | required |
| Single deterministic render | required | required | required |
| Basic output parsing and canvas safety | required | required | required |
| Semantic audit and render integrity | no | required | required |
| SVG/PDF vector validation | no | required when vector output exists | required |
| Plot geometry and boxed text | no | declared/relevant | declared/relevant |
| Basic checksums and environment summary | no | required | superseded by full records |
| Bundle structure, frozen runtime, and reproduction entrypoint | no | no | required |
| Bundle/environment locks and checksum verification | no | no | required |
| Attestation, portability/path scan, and bundle verification | no | no | required |
| Data-swap template and changed-input proof | explicit only | explicit only | required for reusable/data-driven claims |
| Release acceptance | no | no | explicit release only |

`render_only`, `semantic_validated_pass`, `semantic_strict_pass`, and `visual_trace_pass` retain their existing evidence meanings. A lighter profile never upgrades a claim.

## Auto Routing

`--profile auto` selects:

- `audit` for `archival`, `release`, `reusable`, explicit data-swap, changed-input proof, bundle creation, or PDF trace;
- `audit` for a supplied reference image or `--require-strict`, so visual evidence is never silently ignored;
- `standard` for ordinary `manuscript` work;
- `quick` for an explicit preview;
- `standard` for otherwise ordinary data-driven figure work.

Explicit profiles override auto routing, but unsafe contradictions fail instead of silently weakening the claim.

## Output Policy

- Vector-compatible line, scatter, bar, errorbar, mechanism, and schematic figures use PNG+SVG in quick and PNG+SVG+PDF in standard/audit.
- Raster-dominant heatmaps, EBSD maps, micrographs, and image panels use PNG in quick and PNG+PDF in standard/audit.
- Preview-only work uses PNG.
- Fresh PDF trace uses PNG+PDF and adds SVG only through an existing trace contract that proves meaningful vector structure.

The selected formats and reason are stored in the execution report. All profiles retain PNG for the base canvas-safety check.

## Two-Stage Delivery

Quick and standard write a working project with `input/`, `src/render.py`, `output/`, `qa/`, `visualspec.json`, `execution_plan.json`, and `manifest.json`. `finalize --profile audit` passes that VisualSpec and its copied inputs to `run_reproduction.py`, which builds the existing portable audit bundle. Missing reusable-data evidence is reported as a structured failure; no audit gate is silently skipped.

## Readability Advisories

The built-in Matplotlib renderer checks actual artist geometry for legend intersections with line/bar marks and scatter centers. It also flags automatic ticks between grouped-bar positions and samples the rendered background beneath unboxed annotations for low contrast (median luminance contrast below 3:1). Warnings identify the panel, problem and suggested correction. No data, color, tick or legend location is silently changed.

Read `readability.warnings` in the CLI run result and `qa/report.json` (or `quick_report.json`). Standard/audit render manifests and five-figure reports retain the same evidence. `validate`/`finalize` expose the saved renderer advisory with `evidence: recorded_at_render`; validation does not independently remeasure it. Quick validation has no saved render manifest and reports `not_run` for this advisory. Custom renderers that do not supply the evidence also report `not_run`.

Defaults are advisory (`qa_policy.readability: "warn"`). To reject a built-in render with any warning, set `"qa_policy": {"readability": "error"}` in the VisualSpec. This fails the render before exports. This policy applies to the built-in renderer, not arbitrary custom renderers. It is separate from semantic and strict-reference QA. A typo in the policy is rejected rather than silently weakening it.

These are bounded heuristics: filled areas/error bars, marker extents, complex clipping, annotation boxes, text-to-text overlap and all possible crowded layouts are not fully covered. A clean advisory means **no detected warning**, not proven readability. Inspect the final image; use the existing boxed-text/geometry gates for their declared regions. Rerender after accepted layout changes.

For real-paper reproduction evaluation, follow the source/evidence requirements in `benchmarks/README.md`; synthetic fixture success is not paper fidelity.

## Performance Measurement

Run `py -3.14 scripts/benchmark_workflow_profiles.py` to compare the compatible v2.9.4 full runner with quick, standard, and audit on the same local line-plot fixture. The report stores internal subprocess count, render count, created files, enabled gate count, and wall time in `outputs/workflow_profile_benchmark.json`. The old full workflow uses the same 24-capability audit taxonomy; recorded subprocess steps remain a separate metric.
