from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

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
        elements.append({"id": "label", "bbox_px": [12, 12, 36, 20], "bbox_norm": [0.12, 0.12, 0.36, 0.2], "bucket": "editable_vector", "primitive": "textbox", "semantic_role": "annotation_text", "provenance": "generated", "confidence": 1.0, "z_order": 3, "text": {"content": "Deformation"}})
        return {"schema": "scientificfigure.object_manifest.v1", "schema_version": "1.0", "canvas": {"coordinate_space": "source_pixel", "origin": "top_left"}, "source": {"path": "source.png", "width_px": 100, "height_px": 100, "sha256": "sha256:" + "0" * 64}, "manifest_completeness_status": "complete", "visible_content": {"required_text": ["Deformation"]}, "elements": elements}

    def test_manifest_validation_and_classification(self):
        payload = self._manifest()
        report = obj.validate_manifest(payload, schema_path=ROOT / "schemas" / "object-manifest-v1.schema.json")
        self.assertEqual(report["status"], "pass")
        classified = obj.classify_elements(payload, {})
        self.assertEqual(classified["elements"][0]["bucket"], "editable_vector")

    def test_whole_canvas_raster_is_not_editable(self):
        payload = self._manifest()
        payload["elements"] = [payload["elements"][0]]
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

    def test_complete_manifest_rejects_missing_required_visible_text(self):
        payload = self._manifest()
        payload["visible_content"] = {"required_text": ["Missing Label"]}
        report = obj.validate_manifest(payload, schema_path=ROOT / "schemas" / "object-manifest-v1.schema.json")
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any(issue["code"] == "required_text_missing" for issue in report["issues"]))

    def test_complete_manifest_requires_a_nonempty_visible_text_ledger(self):
        payload = self._manifest()
        payload.pop("visible_content")
        report = obj.validate_manifest(payload, schema_path=ROOT / "schemas" / "object-manifest-v1.schema.json")
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any(issue["code"] == "visible_content_required" for issue in report["issues"]))

    def test_visible_text_completeness_allows_nonrequired_labels(self):
        payload = self._manifest()
        payload["elements"].append({"id": "caption", "bbox_px": [12, 24, 42, 32], "bbox_norm": [0.12, 0.24, 0.42, 0.32], "bucket": "editable_vector", "primitive": "textbox", "semantic_role": "annotation_text", "provenance": "generated", "confidence": 1.0, "z_order": 3, "text": {"content": "Supplementary note"}})
        report = obj._visible_text_completeness(payload)
        self.assertEqual("pass", report["status"])
        self.assertEqual([], report["missing_text_ids"])

    def test_materials_mechanism_declares_all_required_labels(self):
        path = ROOT / "examples" / "object_reconstruction" / "materials_mechanism" / "object_manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        required = {"Deformation", "Subgrain rotation", "HAGB increase"}
        declared = {item["text"]["content"] for item in payload["elements"] if item["primitive"] == "textbox"}
        self.assertEqual(set(payload["visible_content"]["required_text"]), required)
        self.assertEqual(declared, required)
        self.assertEqual(obj.validate_manifest(payload, schema_path=ROOT / "schemas" / "object-manifest-v1.schema.json")["status"], "pass")

    def test_materials_mechanism_exports_all_expected_label_text(self):
        path = ROOT / "examples" / "object_reconstruction" / "materials_mechanism" / "object_manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        required = payload["visible_content"]["required_text"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            png, svg, pdf = root / "mechanism.png", root / "mechanism.svg", root / "mechanism.pdf"
            png_report = obj.render_manifest(payload, png, stage="final")
            svg_report = obj.export_vector_manifest(payload, svg)
            pdf_report = obj.export_vector_manifest(payload, pdf)
            for report in (png_report, svg_report, pdf_report):
                completeness = report["visible_content_completeness"]
                self.assertEqual("pass", completeness["status"])
                self.assertEqual(3, completeness["expected_text_count"])
                self.assertEqual(3, completeness["rendered_text_count"])
            self.assertTrue(png.is_file() and png.stat().st_size > 0)
            svg_text = svg.read_text(encoding="utf-8")
            pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf).pages)
            for label in required:
                self.assertIn(label, svg_text)
                self.assertIn(label, pdf_text)


if __name__ == "__main__":
    unittest.main()
