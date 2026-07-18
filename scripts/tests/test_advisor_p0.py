from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

import pandas as pd

import common  # noqa: F401 - adds scripts/ to sys.path for direct discovery
from advisor_common import build_priority_variables
from recommend_scientific_chart import recommend_chart
from profile_scientific_data import profile_dataframe


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

    def test_declared_semantics_without_values_falls_back_with_structured_warning(self):
        profile = {"columns": [{"name": "temperature", "inferred_type": "continuous"}, {"name": "response", "inferred_type": "continuous"}], "uncertainty_columns": [], "repeated_x": {"has_repeated_observations": False}}
        intent = {"task_type": "trend_comparison", "uncertainty_semantics": "standard deviation"}
        decision = recommend_chart(profile, intent, x="temperature", y="response")
        self.assertEqual("line_with_markers", decision["recommended_type"])
        self.assertIn("uncertainty_values_missing", {item["code"] for item in decision["warnings"]})

    def test_name_inferred_uncertainty_requires_confirmation_before_materialization(self):
        profile = {
            "columns": [
                {"name": "temperature", "inferred_type": "continuous"},
                {"name": "response", "inferred_type": "continuous"},
                {"name": "response_sd", "inferred_type": "continuous", "uncertainty_evidence": {"source": "name_inference", "match_type": "token", "matched_token": "sd", "confidence": 0.95}},
            ],
            "uncertainty_columns": ["response_sd"],
            "repeated_x": {"has_repeated_observations": False},
        }
        decision = recommend_chart(profile, {"task_type": "trend_comparison", "uncertainty_semantics": None}, x="temperature", y="response")
        self.assertEqual("line_with_markers", decision["recommended_type"])
        self.assertTrue(decision["requires_user_confirmation"])
        self.assertIn("uncertainty_confirmation_required", {item["code"] for item in decision["warnings"]})

    def test_explicit_column_can_receive_semantics_from_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "data.csv"
            source.write_text("temperature,response,spread\n300,1.2,0.1\n350,1.8,0.2\n", encoding="utf-8")
            profile = profile_dataframe(pd.read_csv(source), source_path=source, x="temperature", y="response", explicit_uncertainty=["spread"])
        evidence = next(item for item in profile["uncertainty_evidence"] if item["column"] == "spread")
        self.assertEqual("pass", evidence["value_validation"]["status"])
        self.assertEqual("pending_confirmation", evidence["value_validation"]["checks"]["definition_known"])
        decision = recommend_chart(profile, {"task_type": "trend_comparison", "uncertainty_semantics": "standard deviation"}, x="temperature", y="response")
        self.assertEqual("line_with_error_bars", decision["recommended_type"])
        self.assertEqual("standard deviation", decision["uncertainty_evidence"]["semantics"])

    def test_explicit_uncertainty_takes_priority_over_name_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "data.csv"
            source.write_text("temperature,response,response_sd,spread\n300,1.2,0.9,0.1\n350,1.8,0.8,0.2\n", encoding="utf-8")
            profile = profile_dataframe(pd.read_csv(source), source_path=source, x="temperature", y="response", explicit_uncertainty=["spread"])
        decision = recommend_chart(profile, {"task_type": "trend_comparison", "uncertainty_semantics": "standard deviation"}, x="temperature", y="response")
        self.assertEqual("spread", decision["uncertainty_source"])
        self.assertEqual("explicit", decision["uncertainty_evidence"]["source"])

    def test_contract_cannot_replace_explicit_error_values_with_derived_band(self):
        profile = {
            "columns": [{"name": "x", "inferred_type": "continuous"}, {"name": "y", "inferred_type": "continuous"}, {"name": "y_sd", "inferred_type": "continuous"}],
            "uncertainty_columns": ["y_sd"],
            "uncertainty_evidence": [{"column": "y_sd", "source": "explicit", "semantics": "standard deviation", "value_validation": {"status": "pass"}}],
            "repeated_x": {"has_repeated_observations": False},
        }
        contract = {"panel_plan": [{"preferred_representation": "line_with_uncertainty"}], "archetype": "single_panel", "hero_panel_id": "A"}
        decision = recommend_chart(profile, {"task_type": "trend_comparison", "uncertainty_semantics": "standard deviation"}, x="x", y="y", figure_contract=contract)
        self.assertEqual("line_with_error_bars", decision["recommended_type"])
        self.assertEqual("y_sd", decision["uncertainty_source"])


if __name__ == "__main__":
    unittest.main()
