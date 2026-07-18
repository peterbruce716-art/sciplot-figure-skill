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

    def test_same_measurement_and_uncertainty_column_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data.csv"
            data.write_text("temperature,response\n300,1.2\n350,1.8\n", encoding="utf-8")
            decision = {"recommended_type": "line_with_error_bars", "data_columns": {"error": "response"}, "uncertainty_source": "response", "uncertainty_evidence": {"column": "response", "source": "explicit", "semantics": "standard deviation"}}
            with self.assertRaisesRegex(ValueError, "uncertainty_same_as_measurement"):
                materialize_chart_decision(decision, data_path=data, output_dir=root, x="temperature", y="response")

    def test_invalid_uncertainty_values_fail_closed(self):
        cases = {
            "negative": "temperature,response,response_sd\n300,1.2,-0.1\n350,1.8,0.2\n",
            "nonnumeric": "temperature,response,response_sd\n300,1.2,bad\n350,1.8,0.2\n",
            "copied": "temperature,response,response_sd\n300,1.2,1.2\n350,1.8,1.8\n",
        }
        decision = {"recommended_type": "line_with_error_bars", "data_columns": {"error": "response_sd"}, "uncertainty_source": "response_sd", "uncertainty_evidence": {"column": "response_sd", "source": "explicit", "match_type": "token", "matched_token": "sd", "confidence": 1.0, "semantics": "standard deviation"}}
        for label, csv_text in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                data = root / "data.csv"
                data.write_text(csv_text, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "uncertainty_(negative|non_numeric|duplicates_measurement)"):
                    materialize_chart_decision(decision, data_path=data, output_dir=root, x="temperature", y="response")

    def test_valid_explicit_uncertainty_records_mapping_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data.csv"
            data.write_text("temperature,response,response_sd\n300,1.2,0.1\n350,1.8,0.2\n", encoding="utf-8")
            decision = {"recommended_type": "line_with_error_bars", "data_columns": {"error": "response_sd"}, "uncertainty_source": "response_sd", "uncertainty_evidence": {"column": "response_sd", "source": "explicit", "match_type": "token", "matched_token": "sd", "confidence": 1.0, "semantics": "standard deviation"}}
            spec, report = materialize_chart_decision(decision, data_path=data, output_dir=root / "visualspec", x="temperature", y="response")
            self.assertEqual("pass", report["mapping_validity"]["status"])
            self.assertEqual("response_sd", spec["delivery"]["mapping_validity"]["uncertainty_column"])

    def test_uncertainty_without_traceable_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data.csv"
            data.write_text("temperature,response,response_sd\n300,1.2,0.1\n350,1.8,0.2\n", encoding="utf-8")
            decision = {"recommended_type": "line_with_error_bars", "data_columns": {"error": "response_sd"}, "uncertainty_source": "response_sd"}
            with self.assertRaisesRegex(ValueError, "uncertainty_evidence_missing"):
                materialize_chart_decision(decision, data_path=data, output_dir=root, x="temperature", y="response")

    def test_materializer_rejects_decision_mapping_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data.csv"
            data.write_text("temperature,response\n300,1.2\n", encoding="utf-8")
            decision = {"recommended_type": "line_with_markers", "data_columns": {"x": "wrong_x", "y": "response"}}
            with self.assertRaisesRegex(ValueError, "source_mapping_mismatch"):
                materialize_chart_decision(decision, data_path=data, output_dir=root, x="temperature", y="response")

    def test_materializer_rejects_unconfirmed_or_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data.csv"
            data.write_text("temperature,response\n300,1.2\n", encoding="utf-8")
            spec, _ = materialize_chart_decision({"recommended_type": "line_with_markers", "requires_user_confirmation": True}, data_path=data, output_dir=root, x="temperature", y="response")
            self.assertEqual("line", spec["panels"][0]["plots"][0]["type"])
            with self.assertRaisesRegex(ValueError, "uncertainty_confirmation_required"):
                materialize_chart_decision({"recommended_type": "line_with_error_bars", "requires_user_confirmation": True}, data_path=data, output_dir=root, x="temperature", y="response")
            with self.assertRaisesRegex(ValueError, "data_source_mismatch"):
                materialize_chart_decision({"recommended_type": "line_with_markers", "data_source": {"sha256": "sha256:wrong"}}, data_path=data, output_dir=root, x="temperature", y="response")

    def test_standard_error_band_uses_standard_error_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data.csv"
            data.write_text("x,y\n0,1\n0,3\n1,2\n1,4\n", encoding="utf-8")
            decision = {"recommended_type": "line_with_error_band", "uncertainty_source": "repeated_observations", "uncertainty_evidence": {"source": "metadata", "match_type": "repeated_observations", "confidence": 1.0, "semantics": "standard error"}}
            spec, report = materialize_chart_decision(decision, data_path=data, output_dir=root / "out", x="x", y="y")
            self.assertEqual("pass", report["mapping_validity"]["status"])
            derived = root / "out" / report["derived_data"]
            rows = derived.read_text(encoding="utf-8").splitlines()
            self.assertIn("lower", rows[0])
            self.assertEqual(3, len(rows))
            self.assertIn("source_hashes", spec["delivery"])

    def test_unsupported_automatic_ci_band_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data.csv"
            data.write_text("x,y\n0,1\n0,3\n", encoding="utf-8")
            decision = {"recommended_type": "line_with_error_band", "uncertainty_source": "repeated_observations", "uncertainty_evidence": {"source": "metadata", "match_type": "repeated_observations", "confidence": 1.0, "semantics": "95% confidence interval"}}
            with self.assertRaisesRegex(ValueError, "uncertainty_band_requires_declared_bounds"):
                materialize_chart_decision(decision, data_path=data, output_dir=root / "out", x="x", y="y")

    def test_name_inference_requires_auditable_match_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data.csv"
            data.write_text("x,y,spread\n0,1,0.1\n1,2,0.2\n", encoding="utf-8")
            decision = {"recommended_type": "line_with_error_bars", "data_columns": {"error": "spread"}, "uncertainty_source": "spread", "uncertainty_evidence": {"column": "spread", "source": "name_inference", "semantics": "standard deviation"}}
            with self.assertRaisesRegex(ValueError, "uncertainty_evidence_missing"):
                materialize_chart_decision(decision, data_path=data, output_dir=root / "out", x="x", y="y")


if __name__ == "__main__":
    unittest.main()
