# Export Backends

Use official backend behavior when choosing export settings.

- Matplotlib `savefig` can save image or vector output. It infers the format from the filename extension when `format` is unset, and accepted formats include `png`, `pdf`, and `svg` depending on the backend.
- R `png()` creates bitmap graphics devices for PNG output. Use explicit width, height, and resolution for reproducible source comparison.
- R `pdf()` opens a PDF graphics device. Width and height are in inches, and font families should be chosen carefully for portability.

For strict visual comparison, keep figure pixel dimensions explicit and compare against the same source crop size.
