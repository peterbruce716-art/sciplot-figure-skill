from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from common import ScientificFigureReproductionTestBase
from benchmark_five_figures import build_cases
from render_visualspec_matplotlib import render_visualspec
from sciplot import _build_visualspec, _prepare_visualspec, build_parser
from visualspec import validate_visualspec


class ReadabilityTests(ScientificFigureReproductionTestBase):
    def _render(self, spec):
        with tempfile.TemporaryDirectory() as tmp:
            return render_visualspec(spec, Path(tmp), output_formats=("png",))

    def test_baseline_bar_warns_about_overlap_and_fractional_group_ticks(self):
        spec = build_cases()["04_grouped_bar"]
        original = copy.deepcopy(spec)
        report = self._render(spec)["readability"]
        codes = {item["code"] for item in report["warnings"]}
        self.assertIn("legend_data_overlap", codes)
        self.assertIn("group_ticks_between_categories", codes)
        self.assertEqual(original, spec)

    def test_dark_contour_annotation_warns_but_white_annotation_does_not(self):
        baseline = self._render(build_cases()["05_contour"])["readability"]
        polished = self._render(build_cases(polished=True)["05_contour"])["readability"]
        self.assertIn("annotation_low_contrast", {x["code"] for x in baseline["warnings"]})
        self.assertNotIn("annotation_low_contrast", {x["code"] for x in polished["warnings"]})

    def test_polished_bar_has_no_readability_warnings(self):
        self.assertEqual([], self._render(build_cases(polished=True)["04_grouped_bar"])["readability"]["warnings"])

    def test_readability_error_policy_rejects_bad_layout(self):
        spec = build_cases()["04_grouped_bar"]
        spec["qa_policy"] = {"readability": "error"}
        with self.assertRaisesRegex(ValueError, "readability_violation"):
            self._render(spec)

    def test_benign_line_has_no_warnings(self):
        self.assertEqual([], self._render(build_cases()["01_line"])["readability"]["warnings"])

    def test_annotation_outline_is_not_a_data_mark(self):
        spec = build_cases()["01_line"]
        spec["qa_policy"] = {"readability": "error"}
        spec["panels"][0]["annotations"].append({"type": "rectangle", "coordinate_space": "axes_fraction", "coordinates": [0, 0, 1, 1], "style": {"fill": False}})
        self.assertNotIn("legend_data_overlap", {x["code"] for x in self._render(spec)["readability"]["warnings"]})

    def test_transparent_line_does_not_obscure_legend(self):
        spec = build_cases()["01_line"]
        spec["qa_policy"] = {"readability": "error"}
        spec["panels"][0]["plots"] = [{"type": "line", "label": "Hidden", "data": {"x": [0, 4], "y": [0.2, 0.2]}, "style": {"color": "#00000000"}}]
        self.assertNotIn("legend_data_overlap", {x["code"] for x in self._render(spec)["readability"]["warnings"]})

    def test_transparent_scatter_does_not_obscure_legend(self):
        spec = build_cases()["01_line"]
        spec["qa_policy"] = {"readability": "error"}
        spec["panels"][0]["plots"] = [{"type": "scatter", "label": "Hidden", "data": {"x": [3.5], "y": [0.2]}, "style": {"color": "#00000000"}}]
        self.assertNotIn("legend_data_overlap", {x["code"] for x in self._render(spec)["readability"]["warnings"]})

    def test_unknown_readability_policy_is_rejected(self):
        spec = build_cases()["01_line"]
        spec["qa_policy"] = {"readability": "erorr"}
        self.assertTrue(any("readability" in error for error in validate_visualspec(spec)))

    def test_csv_unit_label_does_not_change_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "data.csv"
            source.write_text("strain,stress_MPa\n0,100\n0.1,200\n")
            spec = _build_visualspec(source, "input/data.csv", x="strain", y="stress_MPa", yerr=None, uncertainty_semantics=None, plot_type=None)
        panel = spec["panels"][0]
        self.assertEqual("Stress (MPa)", panel["axes"]["y"]["label"])
        self.assertEqual("stress_MPa", panel["plots"][0]["data"]["mapping"]["y"])

    def test_explicit_csv_labels_are_preserved_in_prepared_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "data.csv"
            source.write_text("strain,stress_MPa\n0,100\n0.1,200\n")
            project = root / "project"
            project.mkdir()
            args = build_parser().parse_args(["run", "--input", str(source), "--out-dir", str(project), "--x-label", "True strain", "--y-label", "Flow stress (MPa)"])
            path, _ = _prepare_visualspec(args, project)
            panel = json.loads(path.read_text())["panels"][0]
        self.assertEqual("True strain", panel["axes"]["x"]["label"])
        self.assertEqual("Flow stress (MPa)", panel["axes"]["y"]["label"])

    def test_unknown_column_suffix_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "data.csv"
            source.write_text("strain,SSD_initial\n0,100\n0.1,200\n")
            spec = _build_visualspec(source, "input/data.csv", x=None, y=None, yerr=None, uncertainty_semantics=None, plot_type=None)
        self.assertEqual("SSD_initial", spec["panels"][0]["axes"]["y"]["label"])


if __name__ == "__main__":
    unittest.main()
