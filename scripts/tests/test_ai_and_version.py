from __future__ import annotations

import unittest
import tempfile
import json
from pathlib import Path

from common import ROOT
from check_version_consistency import find_versions
from build_policy_context_from_render import build_context
from apply_style_profile import apply_style
from font_resolver import resolve_fonts
from resolve_style_profile import resolve_style
import render_visualspec_matplotlib as renderer
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

    def test_named_palette_and_journal_delivery_settings_are_resolved(self):
        styled, report = apply_style(
            {"figure": {}, "theme": {}},
            {"profile_id": "nature_like", "source_sha256": "sha256:" + "a" * 64, "settings": {
                "column_width_mm": 89, "double_column_width_mm": 183, "minimum_font_size_pt": 6,
                "vector_formats": ["pdf", "svg"], "palette": "okabe_ito",
            }},
        )
        self.assertEqual(styled["figure"]["size_mm"][0], 89.0)
        self.assertEqual(styled["theme"]["colors"]["palette_name"], "okabe_ito")
        self.assertTrue(all(color.startswith("#") for color in styled["theme"]["colors"]["palette"]))
        self.assertEqual(styled["delivery"]["vector_formats"], ["pdf", "svg"])
        self.assertEqual(report["status"], "applied")

    def test_style_rejects_malformed_custom_palette_and_reports_partial_application(self):
        with self.assertRaises(ValueError):
            apply_style({"figure": {}, "theme": {}}, {"profile_id": "bad", "settings": {"palette": ["#not-a-color"]}})
        _, report = apply_style({"figure": {}, "theme": {}}, {"profile_id": "mixed", "settings": {"dpi": 300, "future_key": True}})
        self.assertEqual(report["status"], "partial")

    def test_release_acceptance_covers_profile_and_unified_cli_tests(self):
        source = (ROOT / "scripts" / "release_acceptance.py").read_text(encoding="utf-8")
        self.assertIn('("execution_profiles"', source)
        self.assertIn('("unified_cli"', source)
        self.assertIn('("object_reconstruction"', source)
        self.assertIn('("pdf_trace"', source)

    def test_resolved_style_has_source_hash_and_cjk_font_records_are_concrete(self):
        profile = resolve_style("nature_like", root=ROOT)
        self.assertRegex(profile["source_profile_sha256"], r"^sha256:[0-9a-f]{64}$")
        font = resolve_fonts(available=[{"family": "Microsoft YaHei", "filename": "msyh.ttc", "style": "normal", "weight": "400", "sha256": "sha256:" + "b" * 64}])
        self.assertEqual("Microsoft YaHei", font["resolved"]["cjk_family"])
        self.assertEqual("sha256:" + "b" * 64, font["resolved"]["cjk_file"]["sha256"])

    def test_minimum_font_size_is_an_export_gate(self):
        spec = {
            "schema": "scientificfigure.visualspec.v2", "figure": {"size_mm": [50, 40], "dpi": 100},
            "qa_policy": {"minimum_font_size_pt": 6},
            "panels": [{"id": "A", "bbox_normalized": [0.15, 0.15, 0.75, 0.75], "axes": {"x": {}, "y": {}}, "plots": [], "annotations": [{"type": "text", "coordinates": [0.5, 0.5], "text": "small", "style": {"font_size_pt": 5}}]}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "minimum_font_size_violation"):
                renderer.render_visualspec(spec, Path(tmp) / "out")

    def test_cjk_text_fails_closed_when_no_cjk_font_can_be_resolved(self):
        spec = {"panels": [{"axes": {"x": {"label": "温度"}, "y": {}}, "plots": [], "annotations": []}], "theme": {"font": {"family_candidates": ["DejaVu Sans"]}}}
        original = renderer.font_manager.findfont
        renderer.font_manager.findfont = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("not installed"))
        try:
            with self.assertRaisesRegex(ValueError, "cjk_font_unresolved"):
                renderer._lock_rcparams(spec)
        finally:
            renderer.font_manager.findfont = original

    def test_named_palette_changes_multiseries_rendering(self):
        spec = {
            "schema": "scientificfigure.visualspec.v2", "figure": {"size_mm": [50, 40], "dpi": 100},
            "theme": {"colors": {"palette": ["#0072B2", "#D55E00"]}},
            "panels": [{"id": "A", "bbox_normalized": [0.15, 0.15, 0.75, 0.75], "axes": {"x": {}, "y": {}}, "plots": [{"type": "line", "data": {"x": [0, 1], "y": [0, 1]}, "style": {}}, {"type": "line", "data": {"x": [0, 1], "y": [1, 0]}, "style": {}}], "annotations": []}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            renderer.render_file(spec_path, root / "out")
            semantics = json.loads((root / "out" / "render_semantics.json").read_text(encoding="utf-8"))
            colors = [plot["style"]["color"] for plot in semantics["figures"]["figure_1"]["panels"]["A"]["plots"]]
            self.assertEqual(["#0072b2", "#d55e00"], colors)

    def test_preflight_rejects_blank_and_accepts_inked_rasters(self):
        self.assertEqual(inspect_raster(3, 2, 0)["status"], "failed")
        report = inspect_raster(300, 200, 17)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["canvas_px"], [300, 200])


if __name__ == "__main__":
    unittest.main()
