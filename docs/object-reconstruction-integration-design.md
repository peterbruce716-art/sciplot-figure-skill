# Object reconstruction integration design

The integration boundary is `object-manifest-v1`. The pipeline stages are:

`source image -> scaffold/classify -> manifest validation -> preserved-asset crop/geometry -> connector audit -> geometry skeleton -> geometry gate -> final render -> masks/region QA/diff mapping -> optional Office export -> optional bundle`

Classification is policy-driven and records confidence and rationale. The geometry skeleton and final render use the same normalized boxes, anchors, and z-order, so later QA can address a stable object instead of a pixel coordinate. A whole-canvas raster remains a valid visual fallback but is explicitly reported as not structurally editable.

The pipeline is additive. Existing VisualSpec, semantic QA, vector QA, bundle, and source-free workflows continue to operate independently. The new scripts can be called directly or from `object_reconstruction_pipeline.py`.
