from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


SKILL_ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = SKILL_ROOT / "scripts" / "check_plot_geometry_safety.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_plot_geometry_safety", CHECKER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {CHECKER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()


def _region() -> dict[str, object]:
    return {
        "id": "main_panel",
        "expected_bbox_px": [20, 10, 79, 49],
        "max_edge_error_px": 1,
        "selector": {
            "min_rgb": [220, 220, 220],
            "max_rgb": [254, 254, 254],
            "min_channel_spread": 2,
            "background": "#ffffff",
            "min_background_distance": 3,
        },
    }


def _region_with_axis_spines() -> dict[str, object]:
    region = _region()
    region["axis_spines"] = {
        "expected_origin_px": [20, 50],
        "expected_horizontal_end_px": 79,
        "expected_vertical_top_px": 10,
        "search_radius_px": 1,
        "max_position_error_px": 1,
        "max_rgb": [200, 200, 200],
        "min_horizontal_coverage_ratio": 0.95,
        "min_vertical_coverage_ratio": 0.95,
    }
    return region


class PlotGeometrySafetyTests(unittest.TestCase):
    def test_accepts_declared_plot_bbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aligned.png"
            image = Image.new("RGB", (100, 60), "white")
            ImageDraw.Draw(image).rectangle((20, 10, 79, 49), fill="#f4e9ef")
            image.save(path)
            report = CHECKER.analyze_plot_geometry(path, [_region()])
        self.assertEqual("pass", report["status"])

    def test_rejects_shifted_plot_bbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shifted.png"
            image = Image.new("RGB", (100, 60), "white")
            ImageDraw.Draw(image).rectangle((10, 10, 89, 54), fill="#f4e9ef")
            image.save(path)
            report = CHECKER.analyze_plot_geometry(path, [_region()])
        self.assertEqual("failed", report["status"])
        self.assertEqual([-10, 0, 10, 5], report["regions"][0]["edge_deltas_px"])

    def test_rejects_image_without_selector_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blank.png"
            Image.new("RGB", (100, 60), "white").save(path)
            report = CHECKER.analyze_plot_geometry(path, [_region()])
        self.assertEqual("failed", report["status"])
        self.assertIn("no_matching_plot_region_pixels", report["regions"][0]["failure_reasons"])

    def test_ignores_thin_annotation_pixels_outside_plot_bbox(self) -> None:
        region = _region()
        region["selector"]["min_column_matches"] = 20
        region["selector"]["min_row_matches"] = 30
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "annotated.png"
            image = Image.new("RGB", (100, 60), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((20, 10, 79, 49), fill="#f4e9ef")
            draw.line((5, 30, 94, 30), fill="#f4e9ef", width=1)
            image.save(path)
            report = CHECKER.analyze_plot_geometry(path, [region])
        self.assertEqual("pass", report["status"])
        self.assertEqual([20, 10, 79, 49], report["regions"][0]["actual_bbox_px"])

    def test_accepts_complete_axis_spines_at_declared_origin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "complete_spines.png"
            image = Image.new("RGB", (100, 60), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((20, 10, 79, 49), fill="#f4e9ef")
            draw.line((20, 50, 79, 50), fill="#404040", width=1)
            draw.line((20, 10, 20, 50), fill="#404040", width=1)
            image.save(path)
            report = CHECKER.analyze_plot_geometry(path, [_region_with_axis_spines()])
        self.assertEqual("pass", report["status"])
        self.assertEqual([20, 50], report["regions"][0]["axis_spines"]["actual_origin_px"])

    def test_rejects_bottom_axis_that_starts_at_first_data_tick(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "incomplete_bottom_axis.png"
            image = Image.new("RGB", (100, 60), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((20, 10, 79, 49), fill="#f4e9ef")
            draw.line((30, 50, 79, 50), fill="#404040", width=1)
            draw.line((20, 10, 20, 50), fill="#404040", width=1)
            image.save(path)
            report = CHECKER.analyze_plot_geometry(path, [_region_with_axis_spines()])
        self.assertEqual("failed", report["status"])
        self.assertIn(
            "horizontal_axis_coverage_below_minimum",
            report["regions"][0]["axis_spines"]["failure_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
