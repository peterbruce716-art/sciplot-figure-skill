from __future__ import annotations

try:
    from common import *
except ModuleNotFoundError:
    from scripts.tests.common import *


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

    def test_scaffolds_three_panel_grouped_bars_without_short_bar_outlier(self) -> None:
        scaffolder = load_module(
            "scaffold_grouped_bar_digitizer_config",
            SCRIPTS / "scaffold_grouped_bar_digitizer_config.py",
        )
        digitizer = load_module(
            "digitize_grouped_bar_raster",
            SCRIPTS / "digitize_grouped_bar_raster.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "triptych.png"
            image = Image.new("RGB", (647, 179), "white")
            pixels = image.load()
            panel_boxes = [(39, 8, 209, 148), (250, 8, 420, 148), (461, 8, 632, 148)]
            panel_colors = [
                [(246, 195, 142), (137, 201, 145), (201, 194, 219)],
                [(232, 201, 251), (201, 135, 232), (148, 68, 173)],
                [(232, 201, 251), (201, 135, 232), (148, 68, 173)],
            ]
            values = [
                [55, 25, 10],
                [63, 35, 12],
                [42, 28, 8],
                [68, 21, 7],
                [67, 30, 15],
            ]
            for panel_index, (left, top, right, bottom) in enumerate(panel_boxes):
                for x in range(left, right + 1):
                    pixels[x, top] = (35, 35, 35)
                    pixels[x, bottom] = (35, 35, 35)
                for y in range(top, bottom + 1):
                    pixels[left, y] = (35, 35, 35)
                    pixels[right, y] = (35, 35, 35)
                centers = [56, 90, 124, 158, 192]
                for category_index, center in enumerate(centers):
                    if panel_index == 0:
                        offsets, widths = (-8, 0, 8), (8, 8, 8)
                    elif panel_index == 1:
                        offsets, widths = (0, 0, 0), (24, 16, 8)
                    else:
                        offsets, widths = (0, -4, 4), (24, 10, 10)
                    for group_index, (offset, bar_width) in enumerate(zip(offsets, widths, strict=True)):
                        value = values[category_index][group_index]
                        bar_top = bottom - round(value / 80 * (bottom - top))
                        bar_center = left + center - 39 + offset
                        # Side-by-side bars may share a boundary; nested bars share
                        # a center and hide the lower part of wider background bars.
                        x_start = bar_center - bar_width // 2
                        for x in range(x_start, x_start + bar_width):
                            for y in range(bar_top, bottom):
                                base_color = panel_colors[panel_index][group_index]
                                jitter = (x + y) % 3 - 1
                                pixels[x, y] = tuple(
                                    max(0, min(255, channel + jitter))
                                    for channel in base_color
                                )
                if panel_index > 0:
                    for x in range(right - 31, right - 6):
                        for y in range(top + 3, top + 7):
                            pixels[x, y] = panel_colors[panel_index][0]
            image.save(source)

            config, scaffold_audit = scaffolder.scaffold_config(
                source,
                panel_count=3,
                panel_ids=["P1", "P2", "P3"],
                category_count=5,
                group_labels=["B", "D", "F"],
                y_min=0,
                y_max=80,
                color_tolerance=8,
                min_row_coverage=0.75,
            )
            rows, digitize_audit = digitizer.digitize(source, config)

            self.assertEqual("pass", scaffold_audit["status"])
            self.assertEqual("pass", digitize_audit["status"], digitize_audit["failures"])
            self.assertEqual(45, len(rows))
            short_bar = next(
                row
                for row in rows
                if row["panel"] == "P3" and row["category"] == "5" and row["group"] == "F"
            )
            background_bar = next(
                row
                for row in rows
                if row["panel"] == "P3" and row["category"] == "5" and row["group"] == "B"
            )
            self.assertLess(short_bar["value"], 25.0)
            self.assertGreaterEqual(short_bar["confidence"], 0.6)
            self.assertGreater(background_bar["value"], 60.0)
            self.assertLess(background_bar["value"], 75.0)
            panel_2_groups = config["panels"][1]["groups"]
            panel_3_groups = config["panels"][2]["groups"]
            self.assertAlmostEqual(0.0, panel_2_groups[1]["offset_px"], delta=1.0)
            self.assertGreater(panel_2_groups[0]["width_px"], panel_2_groups[1]["width_px"])
            self.assertGreater(panel_2_groups[1]["width_px"], panel_2_groups[2]["width_px"])
            self.assertLess(panel_3_groups[1]["offset_px"], -2.0)
            self.assertGreater(panel_3_groups[2]["offset_px"], 2.0)
            self.assertGreaterEqual(panel_3_groups[0]["width_px"], 2 * panel_3_groups[1]["width_px"])
            self.assertEqual("occluded_by_front_groups", panel_2_groups[0]["baseline_visibility"])
            self.assertEqual("occluded_by_front_groups", panel_2_groups[1]["baseline_visibility"])
            self.assertEqual("occluded_by_front_groups", panel_3_groups[0]["baseline_visibility"])
            panel_3_background = next(
                row
                for row in rows
                if row["panel"] == "P3" and row["category"] == "5" and row["group"] == "B"
            )
            self.assertIn("D", panel_3_background["occlusion_evidence_groups"])

    def test_rejects_disconnected_swatch_without_front_occlusion_evidence(self) -> None:
        digitizer = load_module("digitize_grouped_bar_raster", SCRIPTS / "digitize_grouped_bar_raster.py")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "missing_background_bar.png"
            image = Image.new("RGB", (100, 100), "white")
            pixels = image.load()
            background_color = (230, 200, 250)
            foreground_color = (150, 70, 175)
            for x in range(39, 63):
                for y in range(20, 25):
                    pixels[x, y] = background_color
            for x in range(46, 56):
                for y in range(60, 91):
                    pixels[x, y] = foreground_color
            image.save(source)
            config = {
                "schema": "scientificfigure.grouped_bar_digitization.v1",
                "color_tolerance": 4,
                "min_row_coverage": 0.6,
                "baseline_tolerance_px": 3,
                "panels": [
                    {
                        "id": "A",
                        "plot_bbox_px": [10, 10, 90, 90],
                        "category_centers_px": [50.5],
                        "category_labels": ["1"],
                        "y_axis": {
                            "pixel_baseline": 90,
                            "pixel_top": 10,
                            "value_min": 0,
                            "value_max": 80,
                        },
                        "groups": [
                            {
                                "label": "B",
                                "color_rgb": list(background_color),
                                "offset_px": 0,
                                "width_px": 24,
                                "baseline_visibility": "occluded_by_front_groups",
                            },
                            {
                                "label": "F",
                                "color_rgb": list(foreground_color),
                                "offset_px": 0,
                                "width_px": 10,
                                "baseline_visibility": "visible",
                            },
                        ],
                    }
                ],
            }

            rows, audit = digitizer.digitize(source, config)

            self.assertEqual("partial", audit["status"])
            self.assertEqual(["F"], [row["group"] for row in rows])
            self.assertEqual(
                "unverified_front_group_occlusion",
                audit["failures"][0]["reason"],
            )

    def test_scaffold_marks_unresolved_equal_width_split_for_review(self) -> None:
        scaffolder = load_module(
            "scaffold_grouped_bar_digitizer_config_review",
            SCRIPTS / "scaffold_grouped_bar_digitizer_config.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "ambiguous_groups.png"
            image = Image.new("RGB", (100, 100), "white")
            pixels = image.load()
            for x in range(10, 91):
                pixels[x, 10] = (35, 35, 35)
                pixels[x, 90] = (35, 35, 35)
            for y in range(10, 91):
                pixels[10, y] = (35, 35, 35)
                pixels[90, y] = (35, 35, 35)
            for x in range(35, 66):
                for y in range(30, 90):
                    pixels[x, y] = (180, 120, 210)
            image.save(source)

            _, audit = scaffolder.scaffold_config(
                source,
                panel_count=1,
                panel_ids=["A"],
                category_count=1,
                group_labels=["B", "D", "F"],
                y_min=0,
                y_max=80,
            )

            self.assertEqual("review_required", audit["status"])
            self.assertEqual(3, len(audit["fallback_segments"]))


if __name__ == "__main__":
    unittest.main()
