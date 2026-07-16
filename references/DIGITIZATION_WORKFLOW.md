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
2. Record each panel rectangle, category center, group offset, and bar width in source pixels before mapping values.
3. Segment fill colors only inside each panel. Exclude legend swatches by requiring components to touch or approach the calibrated baseline.
4. Use the top edge of the filled rectangle for the central value. Treat antialiasing and compression as a pixel uncertainty and record the implied data-unit uncertainty.
5. Detect error-bar stems and caps separately from fills. If the raster cannot distinguish the uncertainty magnitude reliably, record it as unavailable rather than fabricating a value.
6. In VisualSpec, render bar-top uncertainty with `errorbar` and `line_style: none`; connecting independent bars changes the scientific meaning.

Use the calibrated helper when the bar geometry and colors are known:

```powershell
py -3.14 scripts\digitize_grouped_bar_raster.py --source source.png --config grouped_bar_calibration.json --csv-out digitized_bars.csv --audit-out grouped_bar_audit.json
```

The calibration JSON uses schema `scientificfigure.grouped_bar_digitization.v1`. Each panel records `plot_bbox_px`, `category_centers_px`, `y_axis.pixel_baseline`, `y_axis.pixel_top`, `y_axis.value_min`, `y_axis.value_max`, and groups with `label`, `color_rgb`, `offset_px`, and `width_px`. A nested bar may set group-level `min_row_coverage` lower than the panel default because inner bars occlude the outer fill near the baseline. The helper still rejects components that do not reach the calibrated baseline neighborhood, which filters compact legend swatches from bar measurements.
