from __future__ import annotations

from common import *


class IntegrationPlotTests(ScientificFigureReproductionTestBase):
    def test_renderer_manifest_is_render_only_without_script(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = {
                "schema": "scientificfigure.visualspec.v2",
                "figure": {"size_mm": [40, 30], "dpi": 100, "crop_mode": "fixed_canvas"},
                "panels": [{"id": "fig1", "bbox_normalized": [0.2, 0.2, 0.7, 0.7], "plots": [], "annotations": []}],
            }
            manifest = renderer.render_visualspec(spec, root / "out", spec_path=str(root / "spec.json"))
            self.assertEqual("incomplete", manifest["source_code_status"])
            self.assertEqual("not_run", manifest["semantic_reconstruction_status"])
            self.assertEqual("render_only", manifest["status"])
            self.assertIn("figure_1", manifest["figures"])
            self.assertIn("fig1", manifest["figures"]["figure_1"]["panels"])

    def test_v24_all_declared_plots_render_extract_and_audit(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        plots = {
            "line": {"type": "line", "data": {"x": [0, 1, 2], "y": [0, 1, 0]}, "style": {"color": "#111111", "marker": "o"}},
            "scatter": {"type": "scatter", "data": {"x": [0, 1, 2], "y": [2, 1, 0]}, "style": {"color": "#aa0000", "marker": "s", "alpha": 0.7}},
            "errorbar": {"type": "errorbar", "data": {"x": [0, 1, 2], "y": [1, 1.5, 1], "yerr": [0.1, 0.2, 0.3], "uncertainty": {"source": "explicit", "semantics": "standard deviation"}}, "style": {"color": "#0033aa", "capsize": 2}},
            "fill_between": {"type": "fill_between", "data": {"x": [0, 1, 2], "y1": [0.2, 0.3, 0.2], "y2": [0.7, 0.8, 0.7]}, "style": {"color": "#6699cc", "alpha": 0.45}},
            "grouped_bar": {"type": "grouped_bar", "data": {"x": [0, 1], "groups": [{"label": "a", "y": [1, 2], "color": "#cc0000"}, {"label": "b", "y": [2, 1], "color": "#0000cc"}]}, "style": {"bar_width": 0.25, "alpha": 0.8}},
            "stacked_bar": {"type": "stacked_bar", "data": {"x": [0, 1], "groups": [{"label": "a", "y": [1, 2], "color": "#cc0000"}, {"label": "b", "y": [2, 1], "color": "#0000cc"}]}, "style": {"bar_width": 0.5, "alpha": 0.8}},
            "heatmap": {"type": "heatmap", "data": {"z": [[1, 2], [3, 4]]}, "style": {"cmap": "viridis", "vmin": 1, "vmax": 4}},
            "contour": {"type": "contour", "data": {"x": [0, 1, 2], "y": [0, 1, 2], "z": [[0, 1, 0], [1, 2, 1], [0, 1, 0]]}, "style": {"levels": 3, "cmap": "viridis", "alpha": 0.9}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, plot in plots.items():
                spec = self._single_plot_spec(plot)
                spec_path = root / f"{name}.json"
                out = root / name
                spec_path.write_text(json.dumps(spec), encoding="utf-8")
                renderer.render_file(spec_path, out)
                semantics = json.loads((out / "render_semantics.json").read_text(encoding="utf-8"))
                actual_plot = semantics["figures"]["figure_1"]["panels"]["A"]["plots"][0]
                self.assertEqual(name, actual_plot["type"])
                self.assertEqual("pass", auditor.audit_semantics(spec_path, out / "render_semantics.json")["overall"], name)
                provenance = actual_plot.get("provenance", {})
                self.assertTrue(provenance, name)
                self.assertNotIn("declared", set(provenance.values()), name)
