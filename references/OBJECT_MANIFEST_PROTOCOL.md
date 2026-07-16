# Object manifest protocol

`object-manifest-v1` is the stable intermediate representation for mixed figure reconstruction. Each element has a stable ID, normalized bounding box, bucket, primitive, semantic role, provenance, confidence, and z-order. The manifest is validated before classification, cropping, rendering, masks, diff mapping, or export.

The three buckets are intentionally explicit:

- `editable_vector`: text, paths, lines, arrows, markers, and other renderer-native primitives.
- `preserved_raster`: a bounded source crop kept as a raster asset with a source hash and geometry contract.
- `background`: non-semantic backdrop content that should not be mistaken for an editable scientific object.

Use `validate_object_manifest.py` and retain the generated editability report. Stable IDs make QA and later patching addressable.
