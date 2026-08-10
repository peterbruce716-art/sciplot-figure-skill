from __future__ import annotations

import unittest
from pathlib import Path

from common import ROOT
from check_version_consistency import find_versions
from build_policy_context_from_render import build_context
from apply_style_profile import apply_style
from preflight_figure import inspect_raster


class AIAndVersionTest(unittest.TestCase):
    def test_local_version_declarations_are_consistent(self):
        versions = find_versions(ROOT)
        self.assertTrue(versions)
        self.assertEqual(set(versions.values()), {"2.9.4"})

    def test_policy_context_uses_render_objects(self):
        context = build_context({"panels": [{"id": "A"}], "artists": [{"kind": "line", "y_axis": "left"}, {"kind": "text"}], "theme": {"font": {"family": "DejaVu Sans", "size": 8}}})
        self.assertEqual(context["chart"]["artist_count"], 2)
        self.assertEqual(context["layout"]["text_artist_count"], 1)
        self.assertEqual(context["style"]["font_family"], "DejaVu Sans")

    def test_canonical_style_keys_are_all_accounted_for(self):
        spec = {"figure": {}, "theme": {}}
        profile = {
            "profile_id": "canonical",
            "settings": {
                "font_family": "DejaVu Sans",
                "font_size_pt": 9,
                "axis_line_width_pt": 0.8,
                "data_line_width_pt": 1.3,
                "marker_size_pt": 4,
                "palette": ["#0072B2", "#D55E00"],
                "background": "white",
                "width_mm": 90,
                "height_mm": 60,
                "dpi": 300,
                "grayscale_preview": True,
            },
        }

        styled, report = apply_style(spec, profile)

        accounted = set(report["applied_keys"]) | set(report["compatibility_mapped_keys"]) | set(report["unsupported_keys"])
        self.assertEqual(accounted, set(profile["settings"]))
        self.assertEqual(styled["figure"]["size_mm"], [90.0, 60.0])
        self.assertEqual(styled["figure"]["dpi"], 300)

    def test_release_acceptance_covers_profile_and_unified_cli_tests(self):
        source = (ROOT / "scripts" / "release_acceptance.py").read_text(encoding="utf-8")
        self.assertIn('("execution_profiles"', source)
        self.assertIn('("unified_cli"', source)

    def test_preflight_rejects_blank_and_accepts_inked_rasters(self):
        self.assertEqual(inspect_raster(3, 2, 0)["status"], "failed")
        report = inspect_raster(300, 200, 17)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["canvas_px"], [300, 200])


if __name__ == "__main__":
    unittest.main()
