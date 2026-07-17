# QA Profiles

Use QA profiles to separate semantic reconstruction from pixel tracing.

## semantic

Use for Matplotlib/R/Python semantic redraws. Check canvas size, aspect ratio, content bounding box, axes/ticks, labels, legends, data curves, colors, and layout. Small antialiasing and font-rendering differences are acceptable.

`semantic_strict_pass` does not require exact pixel match.

## QA State Fields

Do not use one field to mean both "QA ran" and "quality passed".

Use:

- `qa.execution_status`: `not_run`, `completed`, or `failed`.
- `qa.result`: `strict_pass`, `near_pass`, `not_strict`, or `not_applicable`.

The legacy global `qa_status` is only a compatibility summary that QA executed successfully. The final figure/manifest `status` and `qa.result` carry the quality conclusion.

At root level prefer:

- `run_status`: `completed` or `failed`.
- `qa_execution_status`: `not_run`, `completed`, or `failed`.
- `quality_status`: `strict_pass`, `near_pass`, `render_only`, `not_strict`, `not_applicable`, or `failed`.
- `status`: `semantic_strict_pass`, `semantic_near_pass`, `visual_trace_pass`, `render_only`, `not_strict`, or `failed`.

`semantic_strict_pass` requires semantic audit, visual QA, vector validation when applicable, and all required panel QA to pass.

## visual

Use when visual placement matters more strongly. In addition to semantic checks, inspect overlay, difference, edge-difference, content shift, and local high-priority regions.

## trace

Use only for explicit pixel trace workflows. This is the only profile where strict means exact pixel match with zero MAE/RMSE.

## Comparison Artifacts

`score_visual.py` can write:

- `source_common.png`
- `render_common.png`
- `difference.png`
- `overlay_50.png`
- `edge_difference.png`

Use these images to locate layout, edge, and color errors before editing the figure script.

## Canvas Safety

For a fixed canvas that should have a blank border, enable the deterministic outer-band gate:

```json
{
  "qa_policy": {
    "canvas_safety": {
      "enabled": true,
      "margin_px": 5,
      "background": "#ffffff",
      "tolerance": 10,
      "required_edges": ["top", "right", "bottom", "left"]
    }
  }
}
```

The bundle runner then checks `outputs/render.png` and writes `qa/canvas_safety.json`. Any non-background pixel in a required edge band fails the run before manifest finalization. This catches legends, labels, callouts, and glyphs that touch the canvas boundary, including common clipping regressions after font substitution.

The check is intentionally narrow. It does not prove that a word, legend entry, or glyph is semantically complete; retain final-size preview inspection and vector-text validation. For intentional full bleed, set `enabled` to `false` or omit those edges from `required_edges`.

## Plot Geometry Safety

For a fixed-canvas reproduction whose axes rectangle must stay aligned to a reference, declare its expected inclusive pixel bbox. The checker measures the left, top, right, and bottom edges, which also fixes the lower-left plot origin:

```json
{
  "qa_policy": {
    "plot_geometry_safety": {
      "enabled": true,
      "regions": [
        {
          "id": "main_plot_region",
          "expected_bbox_px": [96, 16, 552, 266],
          "search_bbox_px": [90, 10, 560, 270],
          "max_edge_error_px": 1,
          "selector": {
            "min_rgb": [221, 221, 221],
            "max_rgb": [255, 255, 255],
            "min_channel_spread": 2,
            "background": "#ffffff",
            "min_background_distance": 3,
            "min_column_matches": 100,
            "min_row_matches": 100
          },
          "axis_spines": {
            "expected_origin_px": [95, 268],
            "expected_horizontal_end_px": 552,
            "expected_vertical_top_px": 16,
            "search_radius_px": 2,
            "max_position_error_px": 1,
            "max_rgb": [200, 200, 200],
            "min_horizontal_coverage_ratio": 0.98,
            "min_vertical_coverage_ratio": 0.98
          }
        }
      ]
    }
  }
}
```

The bundle runner writes `qa/plot_geometry_safety.json` and fails before boxed-text QA when any edge exceeds its tolerance or a visible axis spine is incomplete. `min_column_matches` and `min_row_matches` suppress thin arrows, leaders, and antialiasing fragments outside the actual plot rectangle. The `axis_spines` guard separately checks the left/bottom intersection and coverage across the declared extents; do not infer an axis origin from the gradient/background bbox. For R devices, use an explicit normalized `par(plt=...)` region and explicitly complete the spines when reference-level placement is required; margin values alone are not a stable pixel-position contract.

## Boxed Text Safety

For callout labels and legend rows, declare a separate pixel region for every text item. The checker measures matching text-color ink after excluding the frame, enforces minimum glyph height and top/bottom padding, and can compare height plus upper-half ink density against a freshly rendered reference glyph:

```json
{
  "qa_policy": {
    "boxed_text_safety": {
      "enabled": true,
      "regions": [
        {
          "id": "legend_group_a",
          "bbox_px": [500, 192, 553, 209],
          "text_color": "#000000",
          "color_tolerance": 100,
          "border_inset_px": 1,
          "min_ink_height_px": 12,
          "min_top_padding_px": 2,
          "min_bottom_padding_px": 2,
          "reference_glyph_check": true,
          "text": "Group A",
          "font_family": "Times New Roman",
          "font_size_px": 13,
          "font_weight": "normal",
          "min_reference_height_ratio": 0.85,
          "min_upper_ink_profile_ratio": 0.65
        }
      ]
    }
  }
}
```

The bundle runner writes `qa/boxed_text_safety.json` and fails before manifest finalization when any region fails. Choose regions tightly enough to exclude arrows, marker samples, and neighboring rows. If reference comparison is enabled but the declared font cannot be resolved, the gate fails closed instead of silently substituting a font.
