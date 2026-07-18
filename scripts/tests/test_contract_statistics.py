from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import common  # noqa: F401
from advisor_common import ROOT, load_json, sha256_file
from build_figure_contract import build_contract
from build_statistics_report import build_statistics_report
from chart_decision_to_visualspec import materialize_chart_decision
from finalize_manifest import finalize_manifest
from recommend_scientific_chart import recommend_chart
from resolve_panel_layout import resolve_layout
from validate_figure_contract import validate_contract_payload
from validate_statistics_report import validate_statistics_payload


PROFILE = {
    "schema": "scientificfigure.data_profile.v1",
    "schema_version": "1.0",
    "source": {"path": "data.csv", "sha256": "sha256:" + "0" * 64, "sheet": None},
    "row_count": 3,
    "columns": [
        {"name": "x", "inferred_type": "continuous", "missing_count": 0, "unique_count": 3, "suspected_id": False},
        {"name": "y", "inferred_type": "continuous", "missing_count": 0, "unique_count": 3, "suspected_id": False},
    ],
    "group_statistics": [],
    "distribution": {"skewness": {}, "outliers": {}},
    "warnings": [],
    "recommended_tasks": ["trend_comparison"],
    "uncertainty_columns": [],
    "repeated_x": {"x": "x", "unique_x": 3, "max_replicates_per_x": 1, "repeated_x_count": 0, "has_repeated_observations": False},
}

INTENT = {
    "schema": "scientificfigure.figure_intent.v1",
    "schema_version": "1.0",
    "claim": "unknown",
    "task_type": "trend_comparison",
    "primary_message": "Does y change with x?",
    "audience": "scientific_readers",
    "priority_variables": ["x", "y"],
    "uncertainty_semantics": None,
}


class ContractStatisticsTests(unittest.TestCase):
    def test_default_panel_plan_honors_custom_hero_panel_id(self) -> None:
        contract = build_contract(
            PROFILE,
            question="Does y change with x?",
            core_claim="unknown",
            archetype="asymmetric_mixed",
            hero_panel_id="b",
        )
        result = validate_contract_payload(contract)
        self.assertEqual("pass", result["status"])
        self.assertEqual("b", contract["panel_plan"][0]["panel_id"])
        self.assertEqual("hero", contract["panel_plan"][0]["scientific_role"])
        self.assertEqual(1.5, contract["panel_plan"][0]["panel_weight"])

    def test_build_contract_and_validate_references(self) -> None:
        contract = build_contract(PROFILE, question="Does y change with x?", core_claim="unknown")
        result = validate_contract_payload(contract)
        self.assertEqual("pass", result["status"])
        broken = json.loads(json.dumps(contract))
        broken["hero_panel_id"] = "missing"
        result = validate_contract_payload(broken)
        self.assertEqual("failed", result["status"])
        self.assertIn("invalid_hero_panel_id", {item["code"] for item in result["failures"]})

    def test_statistics_unknown_blocks_publication_ready_not_reproduction(self) -> None:
        contract = build_contract(PROFILE, question="Does y change with x?", core_claim="unknown")
        report = build_statistics_report(PROFILE, figure_contract=contract)
        result = validate_statistics_payload(report)
        self.assertEqual("pass", result["status"])
        self.assertEqual("conditional", report["publication_readiness"]["status"])
        self.assertTrue(report["publication_readiness"]["blocking_reasons"])
        self.assertIn("Panel A n definition is unknown", report["publication_readiness"]["blocking_reasons"])

    def test_declared_statistics_can_mark_publication_ready_with_trace(self) -> None:
        contract = build_contract(PROFILE, question="Does y change with x?", core_claim="unknown")
        report = build_statistics_report(
            PROFILE,
            figure_contract=contract,
            declared_statistics={
                "panels": [
                    {
                        "panel_id": "A",
                        "n_definition": "three independent specimens per condition",
                        "center": "mean",
                        "spread": "standard_deviation",
                        "test": {"name": "one_way_anova", "status": "declared", "multiple_comparison": "tukey_hsd"},
                        "source_trace": [
                            {
                                "file": "data.csv",
                                "sheet": None,
                                "columns": ["x", "y"],
                                "filters": [],
                                "aggregation": "mean_by_condition",
                                "sample_definition": "independent specimens",
                                "random_seed": None,
                                "split": None,
                                "metric_definition": "y response by x condition",
                                "sha256": "sha256:" + "0" * 64,
                            }
                        ],
                    }
                ]
            },
        )
        result = validate_statistics_payload(report)
        self.assertEqual("pass", result["status"])
        self.assertEqual("ready", report["publication_readiness"]["status"])
        self.assertFalse(report["publication_readiness"]["blocking_reasons"])
        self.assertEqual("declared_statistics", report["panels"][0]["test"]["provenance"]["status_source"])

    def test_validator_rejects_unknown_n_definition_marked_ready(self) -> None:
        report = {
            "schema": "scientificfigure.statistics_report.v1",
            "schema_version": "1.0",
            "panels": [
                {
                    "panel_id": "A",
                    "n_definition": "unknown",
                    "center": "mean",
                    "spread": "standard_deviation",
                    "test": {"name": "not_applicable", "status": "not_applicable", "multiple_comparison": None},
                    "source_trace": [{"file": "data.csv", "columns": ["x", "y"]}],
                }
            ],
            "publication_readiness": {"status": "ready", "blocking_reasons": []},
        }
        result = validate_statistics_payload(report)
        self.assertEqual("failed", result["status"])
        self.assertIn("unknown_statistics_marked_ready", {item["code"] for item in result["failures"]})

    def test_contract_flows_into_decision_and_visualspec_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data.csv"
            data.write_text("x,y\n0,1\n1,2\n2,3\n", encoding="utf-8")
            contract = build_contract(
                PROFILE,
                question="Does y change with x?",
                core_claim="unknown",
                archetype="asymmetric_mixed",
                hero_panel_id="A",
                panel_plan=[{"panel_id": "A", "scientific_role": "hero", "question": "Does y change with x?", "preferred_representation": "line_with_uncertainty", "evidence_ids": ["E1"], "panel_weight": 1.8}],
                evidence_chain=[{"id": "E1", "source": "data.csv", "claim": "unknown", "status": "unknown"}],
            )
            decision = recommend_chart(PROFILE, INTENT, x="x", y="y", figure_contract=contract)
            self.assertEqual("line_with_markers", decision["recommended_type"])
            self.assertIn("uncertainty_values_missing", {item["code"] for item in decision["warnings"]})
            decision["data_source"]["sha256"] = sha256_file(data)
            spec, materialization = materialize_chart_decision(decision, data_path=data, output_dir=root / "out", x="x", y="y", figure_contract=contract)
            self.assertEqual("asymmetric_mixed", spec["layout"]["archetype"])
            self.assertEqual("A", spec["layout"]["hero_panel_id"])
            self.assertEqual("hero", spec["panels"][0]["semantic_role"])
            self.assertEqual("A", list(materialization["panel_semantics"].keys())[0])

    def test_layout_records_inferred_hero_panel_provenance(self) -> None:
        contract = build_contract(
            PROFILE,
            question="Does y change with x?",
            core_claim="unknown",
            archetype="asymmetric_mixed",
            panel_plan=[{"panel_id": "A", "scientific_role": "hero", "question": "Does y change with x?", "preferred_representation": "line", "evidence_ids": ["E1"], "panel_weight": 1.0}],
            evidence_chain=[{"id": "E1", "source": "data.csv", "claim": "unknown", "status": "unknown"}],
        )
        layout = resolve_layout(contract, panel_ids=["A"])
        self.assertEqual("A", layout["hero_panel_id"])
        self.assertGreaterEqual(layout["panel_weights"]["A"], 1.5)
        inference_codes = {(item["field"], item["status"], item["source"]) for item in layout["inference_log"]}
        self.assertIn(("layout.hero_panel_id", "inferred", "panel_plan.scientific_role"), inference_codes)
        self.assertIn(("layout.panel_weights.A", "derived", "panel_plan.scientific_role"), inference_codes)

    def test_finalize_manifest_records_contract_and_statistics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ["render.png", "render.svg", "render.pdf", "render.py"]:
                (root / name).write_text("x", encoding="utf-8")
            manifest = {
                "schema": "scientificfigure.manifest.v2",
                "status": "render_only",
                "figures": {"fig1": {"exports": {"png": "render.png", "svg": "render.svg", "pdf": "render.pdf"}, "qa": {"execution_status": "not_run", "result": "not_applicable"}, "status": "render_only"}},
                "per_figure_scripts": {"fig1": "render.py"},
            }
            manifest_path = root / "render_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            contract = build_contract(PROFILE, question="Does y change with x?", core_claim="unknown")
            stats = build_statistics_report(PROFILE, figure_contract=contract)
            contract_path = root / "figure_contract.json"
            stats_path = root / "statistics_report.json"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            stats_path.write_text(json.dumps(stats), encoding="utf-8")
            result = finalize_manifest(
                manifest_path,
                score_path=None,
                script_path=root / "render.py",
                source_path=None,
                output_path=root / "final.json",
                project_root=root,
                figure_contract_path=contract_path,
                statistics_report_path=stats_path,
            )
            self.assertEqual("figure_contract.json", result["figure_contract"])
            self.assertEqual("statistics_report.json", result["statistics_report"])
            self.assertEqual("conditional", result["publication_readiness"]["status"])

    def test_bundled_contract_examples_validate(self) -> None:
        paths = [ROOT / "examples" / "figure_contract" / "figure_contract.json"]
        paths.extend(sorted((ROOT / "examples" / "layout_archetypes").glob("*/figure_contract.json")))
        self.assertGreaterEqual(len(paths), 5)
        for path in paths:
            result = validate_contract_payload(load_json(path))
            self.assertEqual("pass", result["status"], path.as_posix())

    def test_bundled_statistics_example_validates(self) -> None:
        report = load_json(ROOT / "examples" / "statistics_report" / "statistics_report.json")
        result = validate_statistics_payload(report)
        self.assertEqual("pass", result["status"])
        self.assertEqual("conditional", report["publication_readiness"]["status"])


if __name__ == "__main__":
    unittest.main()
