from __future__ import annotations

import copy
import io
import math
from unittest import mock

from common import SCRIPTS, Path, ScientificFigureReproductionTestBase, load_module, visualspec
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure


class FastUncertaintySemanticsTests(ScientificFigureReproductionTestBase):
    def setUp(self) -> None:
        self.auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        self.renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")

    def _uncertainty_spec(self):
        positions = [index * 0.1 for index in range(41)]
        means = [1.0 + 2.0 * (1.0 - math.exp(-position)) for position in positions]
        band = {
            "type": "fill_between",
            "data": {"x": positions, "y1": [mean - 0.2 for mean in means], "y2": [mean + 0.2 for mean in means]},
            "style": {"color": "#0072B2", "alpha": 0.18},
        }
        errorbar = {
            "type": "errorbar",
            "label": "Synthetic mean +/- SD",
            "data": {
                "x": positions[::5], "y": means[::5], "yerr": [0.2] * 9,
                "uncertainty": {"source": "explicit", "semantics": "standard deviation"},
            },
            "style": {"color": "#0072B2", "marker": "o", "capsize": 3},
        }
        spec = self._single_plot_spec(band)
        spec["panels"][0]["plots"].append(errorbar)
        spec["panels"][0]["axes"] = {"x": {"limits": [-0.2, 4.2]}, "y": {"limits": [0.0, 3.7]}}
        spec["panels"][0]["legend"] = {"visible": True, "loc": "lower right"}
        return spec

    def _render(self, spec):
        self.assertEqual([], visualspec.validate_visualspec(spec))
        figure = Figure(figsize=(4, 3), dpi=80)
        FigureCanvasAgg(figure)
        self.addCleanup(figure.clear)
        panel = spec["panels"][0]
        axes = figure.add_axes(panel["bbox_normalized"])
        axes._visualspec_panel_id = panel["id"]
        self.renderer._apply_axes(axes, panel)
        for plot_index, plot in enumerate(panel["plots"]):
            self.renderer._draw_plot(axes, plot, plot_index=plot_index)
        if any(plot.get("label") for plot in panel["plots"]):
            self.renderer._apply_legend(axes, panel)
        return figure, axes

    def _audit(self, spec, semantics):
        with mock.patch.object(self.auditor, "load_json", side_effect=[spec, semantics]):
            return self.auditor.audit_semantics(Path("inline-spec.json"), Path("observed-semantics.json"))

    def _plots(self, semantics):
        return semantics["figures"]["figure_1"]["panels"]["A"]["plots"]

    def test_band_and_labeled_errorbar_render_png_and_pass_audit(self) -> None:
        spec = self._uncertainty_spec()
        figure, _axes = self._render(spec)
        output = io.BytesIO()
        figure.savefig(output, format="png")
        self.assertTrue(output.getvalue().startswith(b"\x89PNG\r\n\x1a\n"))
        semantics = self.auditor.extract_matplotlib_semantics(figure)
        expected = self._plots(self.auditor.expected_semantics(spec))
        observed = self._plots(semantics)
        for wanted, actual in zip(expected, observed):
            for key in wanted:
                if key.endswith("_hash"):
                    self.assertEqual(wanted[key], actual[key], (wanted["type"], key))
        self.assertEqual("pass", self._audit(spec, semantics)["overall"])

    def test_labeled_errorbar_reads_its_container_not_child_line(self) -> None:
        spec = self._uncertainty_spec()
        spec["panels"][0]["plots"] = spec["panels"][0]["plots"][1:]
        figure, axes = self._render(spec)
        container = axes.containers[0]
        self.assertEqual("_nolegend_", container.lines[0].get_label())
        observed = self._plots(self.auditor.extract_matplotlib_semantics(figure))[0]
        self.assertEqual(container.get_label(), observed["label"])
        self.assertEqual("observed", observed["provenance"]["label"])
        self.assertEqual("derived", observed["provenance"]["yerr_hash"])

    def test_fill_between_alone_passes(self) -> None:
        spec = self._uncertainty_spec()
        spec["panels"][0]["plots"] = spec["panels"][0]["plots"][:1]
        figure, _axes = self._render(spec)
        self.assertEqual("pass", self._audit(spec, self.auditor.extract_matplotlib_semantics(figure))["overall"])

    def test_unlabeled_errorbar_still_passes(self) -> None:
        spec = self._uncertainty_spec()
        del spec["panels"][0]["plots"][1]["label"]
        figure, _axes = self._render(spec)
        semantics = self.auditor.extract_matplotlib_semantics(figure)
        self.assertIsNone(self._plots(semantics)[1]["label"])
        self.assertEqual("pass", self._audit(spec, semantics)["overall"])

    def test_multiple_container_labels_follow_their_own_lines(self) -> None:
        spec = self._uncertainty_spec()
        second = copy.deepcopy(spec["panels"][0]["plots"][1])
        second["label"] = "Second mean +/- SD"
        spec["panels"][0]["plots"].append(second)
        figure, axes = self._render(spec)
        semantics = self.auditor.extract_matplotlib_semantics(figure)
        self.assertEqual([container.get_label() for container in axes.containers], [plot["label"] for plot in self._plots(semantics)[1:]])
        self.assertEqual("pass", self._audit(spec, semantics)["overall"])
        labels = [container.get_label() for container in axes.containers]
        for container, label in zip(axes.containers, reversed(labels)):
            container.set_label(label)
        tampered = self._audit(spec, self.auditor.extract_matplotlib_semantics(figure))
        self.assertEqual("failed", tampered["checks"]["data"])
        self.assertEqual("pass", tampered["checks"]["legend_mapping"])

    def test_tampered_errorbar_geometry_still_fails(self) -> None:
        spec = self._uncertainty_spec()
        del spec["panels"][0]["plots"][1]["label"]
        figure, axes = self._render(spec)
        original = self.auditor.extract_matplotlib_semantics(figure)
        self.assertEqual("pass", self._audit(spec, original)["overall"])
        collection = axes.containers[0].lines[2][0]
        segments = collection.get_segments()
        segments[0][0, 1] -= 0.1
        collection.set_segments(segments)
        tampered = self.auditor.extract_matplotlib_semantics(figure)
        self.assertNotEqual(self._plots(original)[1]["yerr_hash"], self._plots(tampered)[1]["yerr_hash"])
        self.assertEqual("failed", self._audit(spec, tampered)["checks"]["data"])

    def test_tampered_band_geometry_still_fails(self) -> None:
        spec = self._uncertainty_spec()
        del spec["panels"][0]["plots"][1]["label"]
        figure, axes = self._render(spec)
        original = self.auditor.extract_matplotlib_semantics(figure)
        self.assertEqual("pass", self._audit(spec, original)["overall"])
        axes.collections[0].get_paths()[0].vertices[5, 1] += 0.1
        tampered = self.auditor.extract_matplotlib_semantics(figure)
        self.assertNotEqual(self._plots(original)[0]["y1_hash"], self._plots(tampered)[0]["y1_hash"])
        self.assertEqual("failed", self._audit(spec, tampered)["checks"]["data"])

    def test_tampered_hash_and_declared_provenance_still_fail(self) -> None:
        spec = self._uncertainty_spec()
        del spec["panels"][0]["plots"][1]["label"]
        figure, _axes = self._render(spec)
        semantics = self.auditor.extract_matplotlib_semantics(figure)
        self.assertEqual("pass", self._audit(spec, semantics)["overall"])
        for plot_index, key in ((0, "y1_hash"), (1, "yerr_hash")):
            with self.subTest(plot_index=plot_index, key=key):
                changed_hash = copy.deepcopy(semantics)
                self._plots(changed_hash)[plot_index][key] = "sha256:tampered"
                self.assertEqual("failed", self._audit(spec, changed_hash)["checks"]["data"])
                declared = copy.deepcopy(semantics)
                self._plots(declared)[plot_index]["provenance"][key] = "declared"
                self.assertEqual("failed", self._audit(spec, declared)["checks"]["provenance"])
