# Digitization Workflow

Use this for raster-only plots when raw data are unavailable.

1. Identify the plot rectangle, axis limits, ticks, units, and scale type.
2. Segment only inside the plot rectangle. Exclude legends, labels, arrows, and peak annotations.
3. Use connected components or equivalent filtering so short legend strokes are not treated as data.
4. Map pixels to data coordinates from the calibrated axis rectangle.
5. Export `panel`, `curve`, `x`, and `y` columns, plus units when known.
6. Compare extracted peaks, plateaus, and endpoints against visible labels.
7. Record uncertainty and mark the result as `digitized_raster`, not raw experimental data.

Document any visual calibration, such as using a labeled peak or plateau when a crop edge is unreliable.
