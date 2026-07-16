from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from common import ROOT

import object_reconstruction as obj


class ObjectReconstructionTest(unittest.TestCase):
    def _manifest(self, asset: str | None = None) -> dict:
        elements = [{
            "id": "box",
            "bbox_px": [10, 10, 40, 30],
            "bbox_norm": [0.1, 0.1, 0.4, 0.3],
            "bucket": "editable_vector",
            "primitive": "rectangle",
            "semantic_role": "process_box",
            "provenance": "user_confirmed",
            "confidence": 0.9,
            "z_order": 1,
            "style": {"fill": "#ffffff", "stroke": "#000000"},
        }]
        if asset:
            elements.append({
                "id": "micrograph",
                "bbox_px": [55, 10, 35, 35],
                "bbox_norm": [0.55, 0.1, 0.35, 0.35],
                "bucket": "preserved_raster",
                "primitive": "image",
                "semantic_role": "micrograph",
                "provenance": "observed",
                "confidence": 1.0,
                "z_order": 2,
                "asset_path": asset,
                "asset_sha256": "sha256:" + "0" * 64,
                "preserve_reason": "source texture",
            })
        return {"schema": "scientificfigure.object_manifest.v1", "schema_version": "1.0", "canvas": {"coordinate_space": "source_pixel", "origin": "top_left"}, "source": {"path": "source.png", "width_px": 100, "height_px": 100, "sha256": "sha256:" + "0" * 64}, "manifest_completeness_status": "complete", "elements": elements}

    def test_manifest_validation_and_classification(self):
        payload = self._manifest()
        report = obj.validate_manifest(payload, schema_path=ROOT / "schemas" / "object-manifest-v1.schema.json")
        self.assertEqual(report["status"], "pass")
        classified = obj.classify_elements(payload, {})
        self.assertEqual(classified["elements"][0]["bucket"], "editable_vector")

    def test_whole_canvas_raster_is_not_editable(self):
        payload = self._manifest()
        payload["elements"][0].update({"bucket": "preserved_raster", "primitive": "image", "semantic_role": "background", "bbox_px": [0, 0, 100, 100], "bbox_norm": [0, 0, 1, 1], "asset_path": "source.png", "asset_sha256": "sha256:" + "0" * 64, "preserve_reason": "fallback"})
        report = obj.editability_report(payload)
        self.assertEqual(report["whole_canvas_rasters"], ["box"])
        self.assertEqual(report["status"], "failed")

    def test_masks_and_diff_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.png"
            Image.new("RGB", (20, 20), "white").save(path)
            payload = self._manifest()
            payload["source"].update({"width_px": 20, "height_px": 20})
            masks = obj.build_object_masks(payload, Path(tmp) / "masks", id_map_path=Path(tmp) / "masks" / "object_id_map.png")
            self.assertEqual(masks["status"], "pass")
            self.assertTrue((Path(tmp) / "masks" / "object_id_map.png").exists())


if __name__ == "__main__":
    unittest.main()
