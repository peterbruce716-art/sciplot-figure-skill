# Shared Geometry Protocol

Use this protocol whenever one logical curve is drawn in several visible pieces, a curve also defines a filled region, or a filled region has a visible boundary.

## Invariant

- Load or digitize the logical geometry once.
- Give it one stable `source_id` and content hash.
- Derive visible segments by slicing that immutable source; do not copy and edit point arrays per segment.
- Derive `fill_between` boundaries from the same curve objects used for their visible lines.
- Build a locally filled vector region and its boundary from one compound path.
- Fail QA if one `source_id` resolves to more than one geometry hash.

Use `scripts/shared_geometry.py` for project-level Matplotlib renderers. `SharedSeries` supports full curves, sliced visible segments, and fills. `SharedPathGeometry` keeps compound vector fills and boundaries tied to one path. Run `audit_shared_geometry()` and retain its JSON report with the figure QA artifacts.

For PDF figures whose source is already vector, use `scripts/pdf_vector_trace.py` only when visual trace is the requested goal. It rebuilds PDF path primitives as editable SVG/PDF paths and records the shared-geometry audit. This remains `pixel_primitives` / `visual_trace_pass`; it does not recover primary experimental data and must not be called a semantic strict reconstruction.

For native PDF clipping, the smallest trustworthy source identity is one PDF compound path or one image XObject. Do not infer that adjacent PDF paths share an experimental dataset. Visual QA must compare the source-page clip with a fresh rasterization of the exported PDF; comparing two copies of one pixmap is invalid.
