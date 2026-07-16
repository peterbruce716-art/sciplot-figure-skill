# Hybrid reconstruction protocol

Hybrid reconstruction combines editable vector objects with bounded preserved raster regions. Classification is policy-driven and can be overridden per element. A full-canvas raster is allowed only as an explicit `preserved_raster` fallback and is reported as structurally non-editable. This keeps visual fidelity honest while leaving labels, arrows, axes, and annotations editable when evidence supports them.
