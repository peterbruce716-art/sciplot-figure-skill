# Image-to-VBA gap analysis

The reference skill, [xiaobei-skill-image-to-vba](https://github.com/xiao24bei/xiaobei-skill-image-to-vba), demonstrates a practical image-to-editable-slide workflow: inspect the image, decompose it into objects, preserve difficult raster regions, emit editable shapes, and verify the result. Its Apache-2.0 license is compatible with this repository's MIT implementation when concepts are reimplemented without copying source code.

SciPlot previously had strong scientific rendering and QA but lacked a stable object intermediate representation, bounded raster preservation, connector semantics, object-level diffs, and an optional Office-compatible delivery artifact. The new protocol closes those gaps while keeping the Python renderer and deterministic gates authoritative.

The implementation deliberately does not require a desktop host or an Office package. VBA is generated as an optional artifact and is marked runtime-unverified unless an external host test is supplied. This preserves portability and avoids turning a visual reconstruction into an unverifiable automation claim.
