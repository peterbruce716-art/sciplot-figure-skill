from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from PIL import Image, ImageDraw, ImageFont


SKILL_ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = SKILL_ROOT / "scripts" / "check_boxed_text_safety.py"
SCHEMA_PATH = SKILL_ROOT / "schemas" / "visualspec-v2.schema.json"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_boxed_text_safety", CHECKER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {CHECKER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()


def _basic_region() -> dict[str, object]:
    return {
        "id": "callout",
        "bbox_px": [10, 10, 90, 40],
        "text_color": "#ff1b1b",
        "color_tolerance": 70,
        "border_inset_px": 4,
        "min_ink_height_px": 14,
        "min_top_padding_px": 4,
        "min_bottom_padding_px": 4,
    }


class BoxedTextSafetyTests(unittest.TestCase):
    def test_rejects_half_height_ink_inside_complete_box(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "half_height.png"
            image = Image.new("RGB", (100, 50), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((10, 10, 89, 39), outline="#ff1b1b")
            draw.rectangle((30, 25, 70, 31), fill="#ff1b1b")
            image.save(path)
            report = CHECKER.analyze_boxed_text(path, [_basic_region()])
        self.assertEqual("failed", report["status"])
        self.assertIn("ink_height_below_minimum", report["regions"][0]["failure_reasons"])

    def test_accepts_full_height_centered_ink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "full_height.png"
            image = Image.new("RGB", (100, 50), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((10, 10, 89, 39), outline="#ff1b1b")
            draw.rectangle((30, 18, 70, 31), fill="#ff1b1b")
            image.save(path)
            report = CHECKER.analyze_boxed_text(path, [_basic_region()])
        self.assertEqual("pass", report["status"])

    def test_reference_profile_rejects_removed_glyph_top(self) -> None:
        from matplotlib.font_manager import FontProperties, findfont

        font_path = findfont(FontProperties(family="DejaVu Sans"), fallback_to_default=False)
        font = ImageFont.truetype(font_path, 20)
        region = {
            "id": "legend_row",
            "bbox_px": [5, 5, 115, 45],
            "text_color": "#000000",
            "color_tolerance": 100,
            "border_inset_px": 2,
            "min_ink_height_px": 1,
            "reference_glyph_check": True,
            "text": "Group A",
            "font_family": "DejaVu Sans",
            "font_size_px": 20,
            "min_reference_height_ratio": 0.90,
            "min_upper_ink_profile_ratio": 0.90,
        }
        with tempfile.TemporaryDirectory() as tmp:
            safe_path = Path(tmp) / "safe.png"
            clipped_path = Path(tmp) / "clipped.png"
            safe = Image.new("RGB", (120, 50), "white")
            draw = ImageDraw.Draw(safe)
            draw.text((15, 10), "Group A", fill="black", font=font)
            safe.save(safe_path)
            clipped = safe.copy()
            clip_draw = ImageDraw.Draw(clipped)
            clip_draw.rectangle((5, 13, 114, 16), fill="white")
            clipped.save(clipped_path)
            safe_report = CHECKER.analyze_boxed_text(safe_path, [region])
            clipped_report = CHECKER.analyze_boxed_text(clipped_path, [region])
        self.assertEqual("pass", safe_report["status"])
        self.assertEqual("failed", clipped_report["status"])
        self.assertTrue(
            {"reference_height_ratio_below_minimum", "upper_ink_profile_below_minimum"}
            & set(clipped_report["regions"][0]["failure_reasons"])
        )

    def test_schema_requires_reference_font_metadata(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        spec = {
            "schema": "scientificfigure.visualspec.v2",
            "figure": {"id": "f", "size_mm": [100, 80], "dpi": 100},
            "qa_policy": {
                "boxed_text_safety": {
                    "enabled": True,
                    "regions": [
                        {
                            "id": "row",
                            "bbox_px": [1, 1, 20, 20],
                            "text_color": "#000000",
                            "min_ink_height_px": 8,
                            "reference_glyph_check": True,
                        }
                    ],
                }
            },
            "panels": [],
        }
        errors = list(validator.iter_errors(spec))
        messages = " ".join(error.message for error in errors)
        self.assertIn("text", messages)
        self.assertIn("font_family", messages)
        self.assertIn("font_size_px", messages)


if __name__ == "__main__":
    unittest.main()
