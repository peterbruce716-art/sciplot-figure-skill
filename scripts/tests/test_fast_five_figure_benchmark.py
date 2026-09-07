from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import benchmark_five_figures as benchmark
from visualspec import validate_visualspec


class FiveFigureBenchmarkTests(unittest.TestCase):
    def test_five_deterministic_valid_inline_specs(self) -> None:
        cases = benchmark.build_cases()
        self.assertEqual(5, len(cases))
        self.assertEqual(cases, benchmark.build_cases())
        for name, spec in cases.items():
            with self.subTest(name=name):
                self.assertEqual([], validate_visualspec(spec))

    def test_existing_evidence_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "existing.txt"
            marker.write_text("preserve", encoding="utf-8")
            with self.assertRaises(ValueError):
                benchmark.run_benchmark(root, "standard")
            self.assertEqual("preserve", marker.read_text(encoding="utf-8"))

    def test_reviewed_presentation_preserves_all_plot_data(self) -> None:
        baseline = benchmark.build_cases()
        reviewed = benchmark.build_cases(polished=True)
        for name in baseline:
            self.assertEqual(baseline[name]["panels"][0]["plots"], reviewed[name]["panels"][0]["plots"])
            self.assertEqual([], validate_visualspec(reviewed[name]))
        self.assertEqual("upper left", reviewed["04_grouped_bar"]["panels"][0]["legend"]["loc"])
        self.assertEqual("white", reviewed["05_contour"]["panels"][0]["annotations"][0]["style"]["color"])

    def test_case_requires_qa_and_independent_validation(self) -> None:
        outputs = {kind: {} for kind in ("png", "svg", "pdf")}
        evidence = {"status": "pass", "semantic_status": "pass", "vector_status": "pass"}
        self.assertTrue(benchmark.case_passes(0, {"status": "ok"}, evidence, outputs, True))
        self.assertTrue(benchmark.case_passes(0, {"status": "pass"}, evidence, outputs, True))
        self.assertFalse(benchmark.case_passes(0, {"status": "ok"}, {}, outputs, True))
        self.assertFalse(benchmark.case_passes(0, {"status": "ok"}, evidence, outputs, False))
        self.assertFalse(benchmark.case_passes(0, {"status": "ok"}, evidence, {"png": {}}, True))
        self.assertFalse(benchmark.case_passes(1, {"status": "pass"}, evidence, outputs, True))

    def test_audit_and_standard_use_exact_export_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            paths, evidence = benchmark.project_evidence(project, "audit")
            self.assertEqual(project / "outputs" / "render.png", paths["png"])
            self.assertNotEqual("pass", evidence["status"])
            paths, evidence = benchmark.project_evidence(project, "standard")
            self.assertEqual(project / "output" / "figure.png", paths["png"])
            self.assertNotEqual("pass", evidence["status"])


if __name__ == "__main__":
    unittest.main()
