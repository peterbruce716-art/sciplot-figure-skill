from __future__ import annotations

import unittest

import common  # noqa: F401 - adds scripts/ to sys.path for direct discovery
from advisor_common import build_priority_variables
from recommend_scientific_chart import recommend_chart


class AdvisorP0Test(unittest.TestCase):
    def test_priority_variables_non_empty(self):
        self.assertEqual(build_priority_variables("x", "y", "group", ["sd"]), ["x", "y", "group", "sd"])
        with self.assertRaises(ValueError):
            build_priority_variables(None, None)

    def test_trend_without_replicates_does_not_force_band(self):
        profile = {"schema": "scientificfigure.data_profile.v1", "schema_version": "1.0", "source": {"path": "x.csv", "sha256": "sha256:test"}, "row_count": 3, "columns": [{"name": "x", "inferred_role": "independent", "inferred_type": "continuous", "numeric": True}, {"name": "y", "inferred_role": "dependent", "inferred_type": "continuous", "numeric": True}], "numeric_columns": ["x", "y"], "categorical_columns": [], "uncertainty_columns": [], "repeated_x": {"has_repeated_observations": False}}
        intent = {"task_type": "trend_comparison", "uncertainty_semantics": None}
        decision = recommend_chart(profile, intent, x="x", y="y")
        self.assertNotEqual(decision["recommended_type"], "line_with_error_band")


if __name__ == "__main__":
    unittest.main()
