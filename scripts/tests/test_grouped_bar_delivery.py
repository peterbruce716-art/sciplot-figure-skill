from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from common import SCRIPTS
import sys

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from validate_grouped_bar_delivery import validate_grouped_bar_delivery


class GroupedBarDeliveryTests(unittest.TestCase):
    def _image(self, *, baseline: bool, clipped_legend: bool, missing_bottom: bool = False) -> Path:
        root = Path(tempfile.mkdtemp())
        image = np.full((40, 80, 3), 255, dtype=np.uint8)
        image[10:30, 10:25] = (255, 153, 51)
        image[10:30, 25:40] = (0, 255, 153)
        image[10:30, 45:55] = (204, 153, 255)
        if not missing_bottom:
            image[30, 10:40] = 0
            image[30, 45:55] = 0
        if not clipped_legend:
            image[0, 60:72] = 255
            image[1:5, 60:72] = (255, 153, 51)
        else:
            image[0:5, 60:72] = (255, 153, 51)
        if baseline:
            image[30, 5:60] = 0
        path = root / "fig16.png"
        Image.fromarray(image).save(path)
        return path

    def _kwargs(self) -> dict[str, object]:
        return {
            "panel_regions": [[5, 5, 60, 35]],
            "baseline_rows": [30],
            "required_baseline_regions": [[5, 30, 10, 31], [40, 30, 45, 31], [55, 30, 60, 31]],
            "min_required_baseline_black": 5,
            "required_bottom_regions": [[10, 30, 40, 31], [45, 30, 55, 31]],
            "legend_rows": [
                {
                    "y": 2,
                    "x0": 60,
                    "x1": 72,
                    "fill_rgb": [255, 153, 51],
                    "top_clear": {"y": 0, "x0": 60, "x1": 72},
                }
            ],
        }

    def test_accepts_continuous_baseline_and_complete_legend(self) -> None:
        report = validate_grouped_bar_delivery(self._image(baseline=True, clipped_legend=False), **self._kwargs())
        self.assertEqual(report["status"], "pass")

    def test_rejects_missing_panel_baseline_and_clipped_legend(self) -> None:
        report = validate_grouped_bar_delivery(self._image(baseline=False, clipped_legend=True), **self._kwargs())
        self.assertEqual(report["status"], "failed")
        checks = {failure["check"] for failure in report["failures"]}
        self.assertIn("panel_baseline_missing", checks)
        self.assertIn("legend_top_clipped", checks)

    def test_rejects_missing_individual_bar_bottom(self) -> None:
        report = validate_grouped_bar_delivery(
            self._image(baseline=False, clipped_legend=False, missing_bottom=True), **self._kwargs()
        )
        self.assertEqual(report["status"], "failed")
        self.assertIn("bar_bottom_missing", {failure["check"] for failure in report["failures"]})


if __name__ == "__main__":
    unittest.main()
