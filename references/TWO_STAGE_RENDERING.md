# Two-stage rendering

The geometry stage renders a deterministic skeleton and executes the geometry gate. The final stage is permitted only after that gate passes, then emits final raster/vector outputs and the same-canvas QA artifacts. This separates layout failures from styling or typography failures.
