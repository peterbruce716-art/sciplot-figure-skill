from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from jsonschema import Draft202012Validator


MODULE_PATH = Path(__file__).resolve().parents[1] / "check_canvas_safety.py"
SPEC_PATH = Path(__file__).resolve().parents[1] / "scaffold_figurespec.py"
ROOT = Path(__file__).resolve().parents[2]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CanvasSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checker = load_module(MODULE_PATH, "check_canvas_safety")

    def test_rejects_ink_inside_required_margin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unsafe.png"
            image = Image.new("RGB", (100, 60), "white")
            ImageDraw.Draw(image).rectangle((0, 15, 35, 45), fill="black")
            image.save(path)
            report = self.checker.analyze_canvas(path, margin_px=5)
        self.assertEqual("failed", report["status"])
        self.assertEqual(["left"], report["failed_edges"])

    def test_accepts_clear_margin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "safe.png"
            image = Image.new("RGB", (100, 60), "white")
            ImageDraw.Draw(image).rectangle((10, 10, 90, 50), fill="black")
            image.save(path)
            report = self.checker.analyze_canvas(path, margin_px=5)
        self.assertEqual("pass", report["status"])

    def test_allows_intentional_full_bleed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "full_bleed.png"
            Image.new("RGB", (100, 60), "black").save(path)
            report = self.checker.analyze_canvas(path, margin_px=5, required_edges=())
        self.assertEqual("pass", report["status"])
        self.assertEqual([], report["failed_edges"])

    def test_scaffold_enables_fixed_canvas_safety(self) -> None:
        scaffold = load_module(SPEC_PATH, "scaffold_figurespec")
        policy = scaffold.build_spec(["fig1"], "outputs", "inputs")["qa_policy"]["canvas_safety"]
        self.assertTrue(policy["enabled"])
        self.assertEqual(5, policy["margin_px"])
        self.assertEqual(["top", "right", "bottom", "left"], policy["required_edges"])

    def test_cli_writes_structured_report_for_missing_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            completed = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--image", str(Path(tmp) / "missing.png"), "--json-out", str(report_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertNotEqual(0, completed.returncode)
        self.assertEqual("failed", report["status"])
        self.assertEqual("canvas_safety_input_or_read_error", report["failure_type"])

    def test_schemas_accept_evidence_and_reject_bad_policy_edge(self) -> None:
        manifest_schema = json.loads((ROOT / "schemas" / "manifest-v2.schema.json").read_text(encoding="utf-8"))
        manifest = {
            "schema": "scientificfigure.manifest.v2",
            "status": "semantic_near_pass",
            "figures": {},
            "per_figure_scripts": {},
            "canvas_safety_status": "pass",
            "canvas_safety": {"schema": "scientificfigure.canvas_safety.v1", "status": "pass"},
        }
        self.assertEqual([], list(Draft202012Validator(manifest_schema).iter_errors(manifest)))

        visualspec_schema = json.loads((ROOT / "schemas" / "visualspec-v2.schema.json").read_text(encoding="utf-8"))
        spec = load_module(SPEC_PATH, "scaffold_schema_test").build_spec(["fig1"], "outputs", "inputs")
        spec["qa_policy"]["canvas_safety"]["required_edges"] = ["center"]
        self.assertTrue(list(Draft202012Validator(visualspec_schema).iter_errors(spec)))


if __name__ == "__main__":
    unittest.main()
