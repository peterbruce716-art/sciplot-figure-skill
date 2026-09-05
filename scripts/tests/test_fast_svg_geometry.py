from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_vector_output import check_svg


class SvgGeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.svg = Path(self.temp_dir.name) / "figure.svg"

    def check_image(self, attributes: str, image: str) -> dict:
        self.svg.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" {attributes}>'
            f'<path d="M0 0L1 1"/><image href="data:image/png;base64,AA==" {image}/></svg>'
        )
        return check_svg(self.svg, representation="semantic_vector")

    def test_full_raster_coverage_uses_viewbox_coordinates(self) -> None:
        result = self.check_image(
            'width="1000" height="1000" viewBox="0 0 10 10"',
            'width="10" height="10"',
        )
        self.assertEqual(1.0, result["raster_coverage_ratio"])
        self.assertEqual("failed", result["status"])

    def test_offset_viewbox_clips_against_its_actual_origin(self) -> None:
        for x, y in [(100, 200), (-100, -200)]:
            with self.subTest(x=x, y=y):
                result = self.check_image(
                    f'viewBox="{x} {y} 10 10"',
                    f'x="{x}" y="{y}" width="10" height="10"',
                )
                self.assertEqual(1.0, result["raster_coverage_ratio"])
                self.assertEqual("failed", result["status"])

    def test_small_raster_is_not_inflated_by_physical_page_units(self) -> None:
        result = self.check_image(
            'width="10mm" height="10mm" viewBox="0 0 1000 1000"',
            'width="10" height="10"',
        )
        self.assertAlmostEqual(0.0001, result["raster_coverage_ratio"])
        self.assertEqual("pass", result["status"])

    def test_partial_overlap_and_percent_lengths_share_viewbox_units(self) -> None:
        result = self.check_image(
            'width="1000" height="1000" viewBox="100 200 100 100"',
            'x="50" y="200" width="100%" height="100%"',
        )
        self.assertEqual(0.5, result["raster_coverage_ratio"])

    def test_bad_viewbox_reports_failure_without_crashing(self) -> None:
        for viewbox in ["", "bad numbers", "0 0 10", "0 0 10 10 10", "0 0 -10 10", "0 0 0 10", "0 0 NaN 10", "inf 0 10 10", "0 0 1_00 100", "0,,0,100,100", ",0,0,100,100", "0,0,100,100,"]:
            for dimensions in ['', 'width="10" height="10"']:
                with self.subTest(viewbox=viewbox, dimensions=dimensions):
                    result = self.check_image(f'{dimensions} viewBox="{viewbox}"', 'width="10" height="10"')
                    self.assertEqual("failed", result["status"])
                    self.assertIn("svg_viewbox_invalid", result["failure_reasons"])

    def test_absolute_image_units_are_converted_to_user_units(self) -> None:
        for length in ["96px", "1in", "2.54cm", "25.4mm", "72pt", "6pc", "101.6Q"]:
            with self.subTest(length=length):
                result = self.check_image(
                    'width="10mm" height="10mm" viewBox="0 0 100 100"',
                    f'width="{length}" height="{length}"',
                )
                self.assertAlmostEqual(0.9216, result["raster_coverage_ratio"])
                self.assertEqual("failed", result["status"])

    def test_extreme_finite_viewbox_sizes_do_not_underflow_or_overflow_area(self) -> None:
        for size in ["1e-200", "1e200"]:
            with self.subTest(size=size):
                result = self.check_image(f'viewBox="0 0 {size} {size}"', f'width="{size}" height="{size}"')
                self.assertEqual(1.0, result["raster_coverage_ratio"])
                self.assertEqual("failed", result["status"])

    def test_comma_whitespace_and_scientific_notation_are_supported(self) -> None:
        result = self.check_image('viewBox=" +0, 0 ,1e2, 100 "', 'width="100" height="100"')
        self.assertEqual(1.0, result["raster_coverage_ratio"])

    def test_unresolved_image_lengths_do_not_certify_vector_output(self) -> None:
        result = self.check_image('viewBox="0 0 100 100"', 'width="10em" height="10em"')
        self.assertEqual("failed", result["status"])
        self.assertIn("semantic_vector_svg_raster_geometry_unknown", result["failure_reasons"])

    def test_svg_without_viewbox_keeps_existing_dimension_behavior(self) -> None:
        result = self.check_image('width="100" height="100"', 'width="100%" height="100%"')
        self.assertEqual(1.0, result["raster_coverage_ratio"])
        self.assertEqual("failed", result["status"])


if __name__ == "__main__":
    unittest.main()
