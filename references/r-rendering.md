# R Rendering Notes

Use R when an existing project already has reliable R plotting code or when base R/ggplot2 is a better fit than Matplotlib.

The bundled `scripts/render_visualspec_r.R` stays within open R plotting. `--demo` uses only base R. `--spec` supports a small VisualSpec line-plot subset and requires `jsonlite`.

For complex R figures, create project-local R scripts first, export PNG/SVG/PDF, and score outputs with `scripts/score_iteration.py`.
