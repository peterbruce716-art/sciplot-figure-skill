# Reconstruction benchmark

The bundled benchmark is deliberately small and reproducible. It uses three synthetic, privacy-safe figures that exercise different failure modes: connector geometry, multi-step route layout, and preserved raster texture. Run `examples/object_reconstruction/generate_examples.py`, then execute `object_reconstruction_pipeline.py` for each manifest.

The acceptance dimensions are manifest validity, geometry gate, preserved-asset hash/aspect checks, final raster/vector export, object masks, object-region QA, and optional delivery artifact status. Synthetic examples verify engineering behavior; they are not evidence of fidelity on arbitrary published figures. A larger paper-derived benchmark requires redistribution permission for every source image.
