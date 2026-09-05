# Export Requirements

Every completed reproduction should provide:

- PNG preview with non-empty content and plausible dimensions.
- SVG with editable text where possible (`svg.fonttype = none`).
- PDF with embedded TrueType text where possible (`pdf.fonttype = 42`).
- A manifest listing source inputs, script path, export paths, QA report, source strategy, representation, and status.

Use fixed canvas export by default. Content-tight export is allowed only when the target figure is meant to be cropped.

For vector claims, inspect SVG/PDF output for unintended raster-only delivery. Image panels may remain raster, but plots, schematic labels, arrows, and dimensions should be vector primitives whenever practical.

SVG raster coverage uses the root [viewBox coordinate rectangle](https://www.w3.org/TR/SVG2/coords.html#ViewBoxAttribute), including its origin, when present. Numeric, percentage, and CSS absolute lengths are supported; unresolved raster lengths cannot certify `semantic_vector`. Invalid or non-rendering viewBox dimensions fail validation. This is an estimate within that rectangle, not a complete SVG layout engine; nested viewports, CSS, transforms, and clipping still require inspection of the rendered output.
