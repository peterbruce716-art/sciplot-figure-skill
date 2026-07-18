from __future__ import annotations

import pandas as pd

from common import *


class AdvisorTests(unittest.TestCase):
    def test_empty_companion_set_preserves_legacy_bundle_layout(self) -> None:
        runner = load_module("run_reproduction_advisor", SCRIPTS / "run_reproduction.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = runner.prepare_companion_artifacts(root, {})
            self.assertEqual({}, artifacts)
            self.assertFalse((root / "companion_artifacts.json").exists())

    def test_profile_is_deterministic_and_warns_on_small_groups(self) -> None:
        profile_mod = load_module("profile_scientific_data", SCRIPTS / "profile_scientific_data.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "data.csv"
            source.write_text("temperature,treatment,response\n300,A,4\n310,A,5\n320,B,20\n330,B,21\n", encoding="utf-8")
            frame = profile_mod.read_table(source)
            payload = profile_mod.profile_dataframe(frame, source_path=source, groups=["treatment"], x="temperature", y="response")
            self.assertEqual("scientificfigure.data_profile.v1", payload["schema"])
            self.assertEqual(4, payload["row_count"])
            self.assertTrue(any(item["code"] == "small_group_sample" for item in payload["warnings"]))
            self.assertEqual(payload, profile_mod.profile_dataframe(frame, source_path=source, groups=["treatment"], x="temperature", y="response"))

    def test_uncertainty_name_detection_uses_tokens_not_substrings(self) -> None:
        profile_mod = load_module("profile_scientific_data_uncertainty_names", SCRIPTS / "profile_scientific_data.py")
        negative = ["response", "dose", "phase", "baseline", "measurement", "stress", "strain", "temperature", "sample_response"]
        positive = ["response_sd", "response_std", "response_sem", "response_se", "y_error", "yerr", "sigma", "ci95", "95_ci", "confidence_interval", "标准差", "标准误", "误差", "置信区间"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "names.csv"
            frame = pd.DataFrame({name: [1.0, 2.0] for name in [*negative, *positive]})
            frame.to_csv(source, index=False)
            profile = profile_mod.profile_dataframe(frame, source_path=source)
        by_name = {item["name"]: item for item in profile["columns"]}
        for name in negative:
            self.assertFalse(by_name[name]["uncertainty_candidate"], name)
        for name in positive:
            self.assertTrue(by_name[name]["uncertainty_candidate"], name)
            evidence = by_name[name]["uncertainty_evidence"]
            self.assertTrue(evidence["matched_token"], name)
            self.assertEqual("name_inference", evidence["source"])

    def test_explicit_physical_x_is_not_suspected_id_but_true_ids_remain_flagged(self) -> None:
        profile_mod = load_module("profile_scientific_data_id_semantics", SCRIPTS / "profile_scientific_data.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "ids.csv"
            frame = pd.DataFrame({
                "temperature": [300, 350, 400, 450],
                "sample_id": [1, 2, 3, 4],
                "specimen_id": [11, 12, 13, 14],
                "编号": [21, 22, 23, 24],
                "response": [1.2, 1.8, 2.7, 3.9],
            })
            frame.to_csv(source, index=False)
            profile = profile_mod.profile_dataframe(frame, source_path=source, x="temperature", y="response")
        by_name = {item["name"]: item for item in profile["columns"]}
        self.assertFalse(by_name["temperature"]["suspected_id"])
        self.assertFalse(any(item["code"] == "suspected_id_column" and item.get("columns") == ["temperature"] for item in profile["warnings"]))
        for name in ["sample_id", "specimen_id", "编号"]:
            self.assertTrue(by_name[name]["suspected_id"], name)

    def test_chart_decision_explains_small_sample_and_user_risk(self) -> None:
        profile_mod = load_module("profile_scientific_data_decision", SCRIPTS / "profile_scientific_data.py")
        decision_mod = load_module("recommend_scientific_chart", SCRIPTS / "recommend_scientific_chart.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "data.csv"
            source.write_text("x,group,y\n1,a,1\n2,a,2\n3,b,3\n4,b,4\n", encoding="utf-8")
            profile = profile_mod.profile_dataframe(profile_mod.read_table(source), source_path=source, groups=["group"], x="x", y="y")
            intent = {"task_type": "group_comparison", "uncertainty_semantics": None}
            decision = decision_mod.recommend_chart(profile, intent, x="x", y="y", group=["group"], requested_type="pie")
            self.assertIn("raw_points", " ".join(decision["required_visual_elements"]))
            self.assertTrue(any(item["code"] == "requested_type_risky" for item in decision["warnings"]))

    def test_policy_can_be_disabled(self) -> None:
        policy_mod = load_module("evaluate_scientific_plot_policy", SCRIPTS / "evaluate_scientific_plot_policy.py")
        policy = json.loads((ROOT / "policies" / "scientific-plot-policy-v1.json").read_text(encoding="utf-8"))
        context = {"sample": {"min_group_n": 5}, "chart": {"type": "bar", "raw_points_visible": False}}
        report = policy_mod.evaluate_policies(context, policy)
        self.assertTrue(any(item["policy_id"] == "small_sample_mean_only" for item in report["findings"]))
        disabled = policy_mod.evaluate_policies(context, policy, disabled={"small_sample_mean_only"})
        self.assertFalse(any(item["policy_id"] == "small_sample_mean_only" for item in disabled["findings"]))

    def test_font_style_and_visual_review_contracts(self) -> None:
        font_mod = load_module("font_resolver", SCRIPTS / "font_resolver.py")
        style_mod = load_module("resolve_style_profile", SCRIPTS / "resolve_style_profile.py")
        review_mod = load_module("prepare_ai_visual_review", SCRIPTS / "prepare_ai_visual_review.py")
        available = [{"family": "Times New Roman", "filename": "times.ttf"}, {"family": "Noto Sans CJK SC", "filename": "noto.ttf"}]
        fonts = font_mod.resolve_fonts(latin="Times New Roman", cjk="Noto Sans CJK SC", available=available)
        self.assertEqual("Times New Roman", fonts["resolved"]["latin_family"])
        style = style_mod.resolve_style("generic_sci")
        self.assertEqual("generic_sci", style["profile_id"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "render.png"
            Image.new("RGB", (20, 10), "white").save(image)
            review = review_mod.prepare_review(image)
            self.assertEqual("pending_advisory", review["status"])
            self.assertEqual("pass", review["deterministic_gate"])


if __name__ == "__main__":
    unittest.main()
