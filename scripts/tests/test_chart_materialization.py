from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import common  # noqa: F401
from chart_decision_to_visualspec import materialize_chart_decision


class ChartMaterializationTest(unittest.TestCase):
    def test_line_decision_becomes_line_visualspec(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data.csv"
            data.write_text("x,y\n0,1\n1,2\n", encoding="utf-8")
            decision = {"recommended_type": "line_with_markers"}
            spec, report = materialize_chart_decision(decision, data_path=data, output_dir=root, x="x", y="y")
            self.assertEqual(spec["panels"][0]["plots"][0]["type"], "line")
            self.assertEqual(report["materialized_as"], ["line"])

    def test_unsupported_decision_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data.csv"
            data.write_text("x,y\n0,1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported chart decision"):
                materialize_chart_decision({"recommended_type": "pie"}, data_path=data, output_dir=root, x="x", y="y")


if __name__ == "__main__":
    unittest.main()
