# Export Requirements

Every completed reproduction should provide:

- PNG preview with non-empty content and plausible dimensions.
- SVG with editable text where possible (`svg.fonttype = none`).
- PDF with embedded TrueType text where possible (`pdf.fonttype = 42`).
- A manifest listing source inputs, script path, export paths, QA report, source strategy, representation, and status.

Use fixed canvas export by default. Content-tight export is allowed only when the target figure is meant to be cropped.

For vector claims, inspect SVG/PDF output for unintended raster-only delivery. Image panels may remain raster, but plots, schematic labels, arrows, and dimensions should be vector primitives whenever practical.
