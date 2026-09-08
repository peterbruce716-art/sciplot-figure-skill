# Reconstruction benchmark

The bundled benchmark is deliberately small and reproducible. It uses three synthetic, privacy-safe figures that exercise different failure modes: connector geometry, multi-step route layout, and preserved raster texture. Run `examples/object_reconstruction/generate_examples.py`, then execute `object_reconstruction_pipeline.py` for each manifest.

The acceptance dimensions are manifest validity, geometry gate, preserved-asset hash/aspect checks, final raster/vector export, object masks, object-region QA, and optional delivery artifact status. Synthetic examples verify engineering behavior; they are not evidence of fidelity on arbitrary published figures. A larger paper-derived benchmark requires redistribution permission for every source image.

## Evaluating real source figures

Use a held-out paper image or original dataset that the evaluator has permission to use. Keep restricted inputs local. Before rendering, record the source DOI/URL, figure/panel, permission or license, original image dimensions, axis calibration and units, requested representation, and the acceptance thresholds. Preserve the source image bytes and a hash; do not rescale a source merely to improve a visual score.

Evaluate at least the task actually claimed: for CSV plotting, compare rendered mappings with the supplied values; for screenshot digitization, compare extracted coordinates with independent ground truth or report that numerical accuracy is unmeasured; for multi-panel reproduction, inspect panel geometry, labels, units and legend/data overlap at the intended print size. Record time, failed attempts and manual correction count. Any ground truth used for scoring must be kept out of the reconstruction prompt.

Report source-backed visual/semantic results, numerical error (when measurable), unresolved readability warnings and operator intervention separately. An image-match score cannot prove statistical correctness or recover primary experimental data. Without an eligible independent source, report this evaluation as **not run**, even if all synthetic cases pass. Do not upload external paper images or measurements in the public synthetic CI artifact step.
