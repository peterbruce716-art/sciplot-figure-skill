# Preserved raster geometry

Every preserved asset records its source image hash, crop rectangle, normalized placement, output dimensions, aspect ratio, and alpha mode. Validation rejects silent stretching, canvas-size changes, or mismatched crop hashes. The geometry contract is checked before final rendering.
