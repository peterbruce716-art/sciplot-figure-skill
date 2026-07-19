from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np


MODULE_PATH = Path(__file__).resolve().parents[1] / "shared_geometry.py"
SPEC = importlib.util.spec_from_file_location("sciplot_shared_geometry_smooth", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SmoothCurveGeometryTests(unittest.TestCase):
    def test_smoothing_preserves_endpoints_and_monotonic_x(self) -> None:
        x = np.array([0.0, 0.1, 0.2, 0.4, 0.7, 1.0])
        y = np.array([0.0, 0.8, 0.9, 0.92, 0.94, 0.95])
        dense_x, dense_y = MODULE.smooth_curve_points(x, y, samples_per_interval=20, smoothing_window=3, clip=(0.0, 1.0))
        self.assertEqual(len(dense_x), 101)
        self.assertTrue(np.all(np.diff(dense_x) > 0))
        self.assertAlmostEqual(float(dense_y[0]), y[0])
        self.assertAlmostEqual(float(dense_y[-1]), y[-1])
        self.assertTrue(np.all((dense_y >= 0.0) & (dense_y <= 1.0)))

    def test_constant_series_remains_constant(self) -> None:
        dense_x, dense_y = MODULE.smooth_curve_points([0.0, 1.0, 2.0], [3.0, 3.0, 3.0], smoothing_window=5)
        self.assertEqual(len(dense_x), 33)
        self.assertTrue(np.allclose(dense_y, 3.0))


if __name__ == "__main__":
    unittest.main()
