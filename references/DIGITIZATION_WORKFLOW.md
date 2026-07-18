# Digitization Workflow

Use this for raster-only plots when raw data are unavailable.

1. Identify the plot rectangle, axis limits, ticks, units, and scale type.
2. Segment only inside the plot rectangle. Exclude legends, labels, arrows, and peak annotations.
3. Use connected components or equivalent filtering so short legend strokes are not treated as data.
4. Map pixels to data coordinates from the calibrated axis rectangle.
5. Export `panel`, `curve`, `x`, and `y` columns for curves. For grouped bars, export `panel`, `category`, `group`, `value`, and optional `yerr`, plus units when known.
6. Compare extracted peaks, plateaus, and endpoints against visible labels.
7. Record uncertainty and mark the result as `digitized_raster`, not raw experimental data.

Document any visual calibration, such as using a labeled peak or plateau when a crop edge is unreliable.

## Grouped Bars

1. Calibrate the y mapping from the baseline and at least two visible ticks; do not infer the scale from bar heights alone.
2. Record each panel rectangle, category center, group offset, and bar width in source pixels before mapping values. Detect these values independently per panel; do not assume that adjacent panels share side-by-side or nested geometry.
3. Segment fill colors only inside each panel. Exclude legend swatches by requiring components to touch or approach the calibrated baseline.
4. Use the top edge of the filled rectangle for the central value. Treat antialiasing and compression as a pixel uncertainty and record the implied data-unit uncertainty.
5. Detect error-bar stems and caps separately from fills. `digitize_grouped_bar_raster.py` records an achromatic or locally contrasting component immediately above a fill as `errorbar_upper_px` and maps that visible extent to `errorbar_value_from_pixels`. This is visual evidence only: do not relabel it as SD, SEM, CI, or another statistical definition unless independent metadata supplies that meaning. If the raster cannot distinguish the extent reliably, leave it unavailable rather than fabricating a value.
6. In VisualSpec, render bar-top uncertainty with `errorbar` and `line_style: none`; connecting independent bars changes the scientific meaning.

Use the calibrated helper when the bar geometry and colors are known:

```powershell
py -3.14 scripts\digitize_grouped_bar_raster.py --source source.png --config grouped_bar_calibration.json --csv-out digitized_bars.csv --audit-out grouped_bar_audit.json
```

The calibration JSON uses schema `scientificfigure.grouped_bar_digitization.v1`. Each panel records `plot_bbox_px`, `category_centers_px`, `y_axis.pixel_baseline`, `y_axis.pixel_top`, `y_axis.value_min`, `y_axis.value_max`, and groups with `label`, `color_rgb`, `offset_px`, `width_px`, and `baseline_visibility`. An automatically scaffolded config also records `calibration_status` and `unresolved_segments`; digitization is blocked until the status is `pass` and the unresolved list is empty. The optional group field `allow_front_group_bridge` defaults to `false` and must be a boolean.

Panel layouts are independent. For example, one panel may have three nearly zero offsets with descending widths (concentric B/D/F nesting), while the next uses a wide B background plus negative D and positive F offsets (left/right foreground bars). The scaffold must preserve those distinct offsets and widths instead of averaging them into one figure-wide layout.

Use `baseline_visibility: visible` when the group's fill reaches the calibrated baseline neighborhood. Use `occluded_by_front_groups` only when later foreground groups overlap that bar. A non-baseline-connected run is accepted by default only when it has plausible vertical extent and a narrow edge of the same fill continues to the baseline. A foreground fill starting immediately below the candidate is not sufficient by itself because that pattern is indistinguishable from an aligned legend swatch; enable `allow_front_group_bridge` only after manual review makes that inference defensible. Evidence type and source-pixel intervals are retained in the output. Without accepted evidence, the row is omitted and the audit fails or becomes partial. The scaffold also reports and propagates `review_required` when it must estimate unresolved touching groups with equal-width fallback; the digitizer rejects that config until manual review clears the unresolved segments. The extracted values remain raster-derived approximations.
