from __future__ import annotations

from common import *


class GroupedBarDigitizerTests(ScientificFigureReproductionTestBase):
    def test_digitizes_calibrated_bar_tops_and_records_pixel_uncertainty(self) -> None:
        digitizer = load_module("digitize_grouped_bar_raster", SCRIPTS / "digitize_grouped_bar_raster.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bars.png"
            image = Image.new("RGB", (80, 70), "white")
            pixels = image.load()
            for y in range(40, 59):
                for x in range(17, 22):
                    pixels[x, y] = (240, 160, 120)
            for y in range(20, 59):
                for x in range(27, 32):
                    pixels[x, y] = (120, 180, 220)
            image.save(source)
            config = {
                "schema": "scientificfigure.grouped_bar_digitization.v1",
                "color_tolerance": 4,
                "min_row_coverage": 0.8,
                "baseline_tolerance_px": 3,
                "panels": [{
                    "id": "A",
                    "plot_bbox_px": [10, 10, 70, 60],
                    "category_centers_px": [25],
                    "category_labels": ["1"],
                    "y_axis": {"pixel_baseline": 60, "pixel_top": 10, "value_min": 0, "value_max": 50},
                    "groups": [
                        {"label": "B", "color_rgb": [240, 160, 120], "offset_px": -6, "width_px": 5},
                        {"label": "D", "color_rgb": [120, 180, 220], "offset_px": 4, "width_px": 5},
                    ],
                }],
            }
            rows, audit = digitizer.digitize(source, config)
            self.assertEqual("pass", audit["status"])
            self.assertEqual(2, len(rows))
            by_group = {row["group"]: row for row in rows}
            self.assertEqual(20.0, by_group["B"]["value"])
            self.assertEqual(40.0, by_group["D"]["value"])
            self.assertEqual(1.0, by_group["B"]["value_uncertainty_from_pixels"])
            self.assertEqual("digitized_raster", by_group["D"]["source_strategy"])


if __name__ == "__main__":
    unittest.main()
