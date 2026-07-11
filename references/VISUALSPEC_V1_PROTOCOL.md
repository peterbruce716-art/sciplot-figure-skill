# ScientificFigure VisualSpec v1/v2

`scientificfigure.visualspec.v2` describes a source figure independently of any proprietary plotting tool. Legacy `scientificfigure.visualspec.v1` files may still be read, but new work should write v2, drive Python Matplotlib first, compare rendered output with the source crop, and record a fail-closed `scientificfigure.manifest.v2` manifest.

## Top-Level Fields

- `schema`: use `scientificfigure.visualspec.v2` for new work.
- `figure`: figure size, DPI, background, `crop_mode`, output directory, and optional source directory. Default `crop_mode` is `fixed_canvas`; do not use content-tight cropping unless requested.
- `delivery`: source-code, raster, and vector requirements. Prefer PNG plus SVG/PDF with text preserved as text.
- `panels`: one or more panel specifications.
- `qa_policy`: backend, completion rule, and iteration policy.

## Panel Fields

- `id`: stable panel or figure id.
- `source_crop`: source image crop used for comparison.
- `bbox_normalized`: panel rectangle on the final page as `[left, bottom, width, height]`.
- `axes`: axis scales, limits, ticks, labels, and units.
- `plots`: semantic plot objects.
- `annotations`: text, arrows, rectangles, polygons, callouts, and labels.
- `reconstruction_mode`: one of `semantic_reconstruction`, `visual_reconstruction`, or `pixel_trace`.

## Supported Plot Types

The bundled Python renderer supports:

- `line`
- `scatter`
- `errorbar`
- `fill_between`
- `grouped_bar`
- `stacked_bar`
- `heatmap`
- `contour`

Use a project-local renderer for specialized scientific schematics, EBSD maps, or figures requiring object extraction from the source crop.

## Data Sources

Plot data may be inline lists or external sources resolved through `scripts/data_resolver.py`:

- CSV / TSV
- JSON
- NPY / NPZ
- Excel through optional pandas

For external tables, use:

```json
{
  "source": "data/points.csv",
  "mapping": {"x": "time", "y": "response", "yerr": "response_sd"}
}
```

## Completion Rules

A Python/R-only run may report `overall_status=pass` only when:

- VisualSpec validation passes.
- The selected renderer builds without unsupported fields.
- Required PNG/SVG/PDF exports are written.
- Source-vs-render visual QA passes without arbitrary source resizing.

Required status fields are open-format states: `source_code_status`, `render_status`, `raster_export_status`, `vector_export_status`, `vector_validation_status`, `semantic_reconstruction_status`, and `visual_qa_status`. A manifest must not pass if any required gate is `not_run`, `failed`, `blocked`, `unsupported`, or `incomplete`.

Export success alone is `render_only`, not visual pass. Pixel trace may report `visual_trace_pass`, but it must also record `semantic_data_recovered=false` and `scientific_objects_editable=false`; it cannot claim semantic strict pass.
