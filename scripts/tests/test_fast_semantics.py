from __future__ import annotations

from common import *


class FastSemanticsTests(ScientificFigureReproductionTestBase):
    def test_semantic_audit_catches_axis_scale_mismatch(self) -> None:
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["panels"][0]["axes"]["x"]["scale"] = "log"
            semantics = auditor.expected_semantics(spec)
            semantics["figures"]["figure_1"]["panels"]["A"]["axes"]["x"]["scale"] = "linear"
            spec_path = root / "visualspec.json"
            sem_path = root / "render_semantics.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            sem_path.write_text(json.dumps(semantics), encoding="utf-8")
            result = auditor.audit_semantics(spec_path, sem_path)
            self.assertEqual("failed", result["overall"])
            self.assertEqual("failed", result["checks"]["axes"])

    def test_vector_validation_rejects_raster_only_svg_for_semantic_vector(self) -> None:
        checker = load_module("check_vector_output", SCRIPTS / "check_vector_output.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            svg = root / "render.svg"
            pdf = root / "render.pdf"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><image href="x.png" width="10" height="10"/></svg>',
                encoding="utf-8",
            )
            pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Page /Resources << /XObject << /Im0 << /Subtype /Image >> >> >> >> endobj\n%%EOF")
            result = checker.check_vector_outputs(svg, pdf, representation="semantic_vector")
            self.assertEqual("failed", result["status"])

    def test_render_semantics_are_extracted_from_actual_matplotlib_objects(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["panels"][0]["plots"][0]["style"] = {"color": "#336699", "line_width_pt": 2.5, "line_style": "dashed", "marker": "o", "alpha": 0.4}
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = root / "out"
            renderer.render_file(spec_path, out)
            semantics = json.loads((out / "render_semantics.json").read_text(encoding="utf-8"))
            plot = semantics["figures"]["figure_1"]["panels"]["A"]["plots"][0]
            self.assertEqual("o", plot["style"]["marker"])
            self.assertEqual("dashed", plot["style"]["line_style"])
            self.assertAlmostEqual(0.4, plot["style"]["alpha"])
            self.assertEqual("pass", auditor.audit_semantics(spec_path, out / "render_semantics.json")["overall"])

    def test_scatter_style_fields_affect_actual_semantics(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["panels"][0]["plots"] = [
                {"type": "scatter", "data": {"x": [0, 1], "y": [1, 0]}, "style": {"color": "#aa0000", "marker": "x", "alpha": 0.25, "marker_size_pt2": 44}}
            ]
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = root / "out"
            renderer.render_file(spec_path, out)
            plot = json.loads((out / "render_semantics.json").read_text(encoding="utf-8"))["figures"]["figure_1"]["panels"]["A"]["plots"][0]
            self.assertEqual("scatter", plot["type"])
            self.assertEqual("x", plot["style"]["marker"])
            self.assertAlmostEqual(0.25, plot["style"]["alpha"])

    def test_vector_validation_rejects_full_page_raster_with_tiny_vector_spoof(self) -> None:
        checker = load_module("check_vector_output", SCRIPTS / "check_vector_output.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            svg = root / "render.svg"
            pdf = root / "render.pdf"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><image href="data:image/png;base64,AA==" width="100" height="100"/><path d="M0 0 L1 1"/></svg>',
                encoding="utf-8",
            )
            pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Page /Resources << /Font << /F1 2 0 R >> /XObject << /Im0 << /Subtype /Image >> >> >> >> endobj\n%%EOF")
            result = checker.check_vector_outputs(svg, pdf, representation="semantic_vector")
            self.assertEqual("failed", result["status"])
            self.assertGreater(result["svg"]["raster_coverage_ratio"], 0.05)

    def test_v24_errorbar_yerr_is_derived_from_artist_geometry(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._single_plot_spec({"type": "errorbar", "data": {"x": [0, 1], "y": [0.5, 0.5], "yerr": [0.1, 0.2]}})
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = root / "out"
            renderer.render_file(spec_path, out)
            semantics = json.loads((out / "render_semantics.json").read_text(encoding="utf-8"))
            plot = semantics["figures"]["figure_1"]["panels"]["A"]["plots"][0]
            self.assertEqual("derived", plot["provenance"]["yerr_hash"])
            plot["yerr_hash"] = "sha256:wrong"
            bad = root / "bad_semantics.json"
            bad.write_text(json.dumps(semantics), encoding="utf-8")
            self.assertEqual("failed", auditor.audit_semantics(spec_path, bad)["overall"])

    def test_v24_scatter_marker_uses_observed_path_not_declared_tag(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._single_plot_spec({"type": "scatter", "data": {"x": [0, 1], "y": [0, 1]}, "style": {"marker": "o"}})
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = root / "out"
            original_draw = renderer._draw_plot
            def spoofed_draw(ax, plot, *, base_dir=None, plot_index=0):
                altered = dict(plot)
                altered["style"] = dict(plot.get("style") or {})
                altered["style"]["marker"] = "s"
                return original_draw(ax, altered, base_dir=base_dir, plot_index=plot_index)
            renderer._draw_plot = spoofed_draw
            try:
                renderer.render_file(spec_path, out)
            finally:
                renderer._draw_plot = original_draw
            semantics = json.loads((out / "render_semantics.json").read_text(encoding="utf-8"))
            plot = semantics["figures"]["figure_1"]["panels"]["A"]["plots"][0]
            self.assertEqual("s", plot["style"]["marker"])
            self.assertEqual("observed", plot["provenance"]["style.marker"])
            self.assertEqual("failed", auditor.audit_semantics(spec_path, out / "render_semantics.json")["overall"])

    def test_v24_annotation_geometry_is_audited(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["panels"][0]["annotations"] = [
                {"type": "rectangle", "coordinate_space": "axes_fraction", "coordinates": [0.1, 0.2, 0.3, 0.2], "style": {"edgecolor": "#000000", "line_width_pt": 1.0}},
                {"type": "polygon", "coordinate_space": "axes_fraction", "coordinates": [[0.5, 0.5], [0.7, 0.5], [0.6, 0.7]], "style": {"edgecolor": "#000000"}},
            ]
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = root / "out"
            renderer.render_file(spec_path, out)
            self.assertEqual("pass", auditor.audit_semantics(spec_path, out / "render_semantics.json")["overall"])
            semantics = json.loads((out / "render_semantics.json").read_text(encoding="utf-8"))
            semantics["figures"]["figure_1"]["panels"]["A"]["annotations"][0]["geometry"]["width"] = 0.9
            bad = root / "bad_semantics.json"
            bad.write_text(json.dumps(semantics), encoding="utf-8")
            self.assertEqual("failed", auditor.audit_semantics(spec_path, bad)["overall"])

    def test_v25_contour_data_and_levels_are_audited(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        plot = {"type": "contour", "data": {"x": [0, 1, 2], "y": [0, 1, 2], "z": [[0, 1, 0], [1, 2, 1], [0, 1, 0]]}, "style": {"levels": 4, "cmap": "viridis"}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(self._single_plot_spec(plot)), encoding="utf-8")
            out = root / "out"
            renderer.render_file(spec_path, out)
            self.assertEqual("pass", auditor.audit_semantics(spec_path, out / "render_semantics.json")["overall"])
            semantics = json.loads((out / "render_semantics.json").read_text(encoding="utf-8"))
            contour = semantics["figures"]["figure_1"]["panels"]["A"]["plots"][0]
            self.assertIn("z_hash", contour)
            self.assertIn("levels_hash", contour)
            contour["z_hash"] = "sha256:wrong"
            bad = root / "bad_contour.json"
            bad.write_text(json.dumps(semantics), encoding="utf-8")
            self.assertEqual("failed", auditor.audit_semantics(spec_path, bad)["overall"])

    def test_v25_heatmap_aspect_and_bar_group_colors_are_audited(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heatmap_spec = self._single_plot_spec({"type": "heatmap", "data": {"z": [[1, 2], [3, 4]]}, "style": {"aspect": "equal", "cmap": "viridis"}})
            heatmap_path = root / "heatmap.json"
            heatmap_path.write_text(json.dumps(heatmap_spec), encoding="utf-8")
            heatmap_out = root / "heatmap"
            renderer.render_file(heatmap_path, heatmap_out)
            heatmap = json.loads((heatmap_out / "render_semantics.json").read_text(encoding="utf-8"))["figures"]["figure_1"]["panels"]["A"]["plots"][0]
            self.assertEqual("equal", heatmap["style"]["aspect"])
            self.assertEqual("pass", auditor.audit_semantics(heatmap_path, heatmap_out / "render_semantics.json")["overall"])

            bar_spec = self._single_plot_spec({"type": "grouped_bar", "data": {"x": [0, 1], "groups": [{"label": "A", "y": [1, 2], "color": "#cc0000"}, {"label": "B", "y": [2, 1], "color": "#0000cc"}]}, "style": {"bar_width": 0.25, "alpha": 0.8}})
            bar_path = root / "bar.json"
            bar_path.write_text(json.dumps(bar_spec), encoding="utf-8")
            bar_out = root / "bar"
            renderer.render_file(bar_path, bar_out)
            semantics = json.loads((bar_out / "render_semantics.json").read_text(encoding="utf-8"))
            groups = semantics["figures"]["figure_1"]["panels"]["A"]["plots"][0]["groups"]
            groups[0]["color"], groups[1]["color"] = groups[1]["color"], groups[0]["color"]
            bad = root / "bad_bar.json"
            bad.write_text(json.dumps(semantics), encoding="utf-8")
            self.assertEqual("failed", auditor.audit_semantics(bar_path, bad)["overall"])

    def test_v26_grouped_bar_supports_nested_widths_and_explicit_offsets(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        plot = {
            "type": "grouped_bar",
            "data": {"x": [1, 2], "groups": [{"label": "wide", "y": [4, 5]}, {"label": "left", "y": [2, 3]}, {"label": "right", "y": [1, 2]}]},
            "style": {"bar_width": 0.7, "bar_widths": [0.7, 0.25, 0.18], "group_mode": "overlap", "group_offset": 0.0, "group_offsets": [0.0, -0.12, 0.12], "alpha": 1.0},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "offset_bar.json"
            spec_path.write_text(json.dumps(self._single_plot_spec(plot)), encoding="utf-8")
            out = root / "offset_bar"
            renderer.render_file(spec_path, out)
            result = auditor.audit_semantics(spec_path, out / "render_semantics.json")
            self.assertEqual("pass", result["overall"])
            semantics = json.loads((out / "render_semantics.json").read_text(encoding="utf-8"))
            style = semantics["figures"]["figure_1"]["panels"]["A"]["plots"][0]["style"]
            self.assertEqual([0.7, 0.25, 0.18], [round(value, 6) for value in style["bar_widths"]])
            self.assertEqual([0.0, -0.12, 0.12], [round(value, 6) for value in style["group_offsets"]])

    def test_grouped_bar_errorbars_can_disable_connecting_line_and_configure_legend(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._single_plot_spec({
                "type": "grouped_bar",
                "data": {"x": [1, 2], "groups": [{"label": "B", "y": [4, 5], "yerr": [0.2, 0.3], "color": "#cc9966"}]},
                "style": {"bar_width": 0.25, "errorbar_color": "#444444", "errorbar_line_width_pt": 0.5, "errorbar_capsize": 1.5},
            })
            spec["panels"][0]["plots"].append({
                "type": "errorbar",
                "data": {"x": [1, 2], "y": [4, 5], "yerr": [0.2, 0.2]},
                "style": {"color": "#444444", "line_width_pt": 0.5, "line_style": "none", "capsize": 1.5},
            })
            spec["panels"][0]["legend"] = {
                "loc": "upper center", "ncol": 1, "font_size_pt": 6,
                "bbox_to_anchor": [0.5, 1.0], "handle_length": 1.0,
            }
            spec_path = root / "bar_errorbar.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = root / "rendered"
            renderer.render_file(spec_path, out)
            self.assertEqual("pass", auditor.audit_semantics(spec_path, out / "render_semantics.json")["overall"])
            semantics = json.loads((out / "render_semantics.json").read_text(encoding="utf-8"))
            bar = semantics["figures"]["figure_1"]["panels"]["A"]["plots"][0]
            self.assertIn("yerr_hash", bar["groups"][0])
            errorbar = semantics["figures"]["figure_1"]["panels"]["A"]["plots"][1]
            self.assertEqual("none", errorbar["style"]["line_style"])

    def test_v25_crossing_fill_between_preserves_y1_y2_identity(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._single_plot_spec({"type": "fill_between", "data": {"x": [0, 1, 2], "y1": [0.8, 0.2, 0.8], "y2": [0.2, 0.8, 0.2]}, "style": {"color": "#6699cc", "alpha": 0.5}})
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = root / "out"
            renderer.render_file(spec_path, out)
            self.assertEqual("pass", auditor.audit_semantics(spec_path, out / "render_semantics.json")["overall"])

    def test_v25_text_and_arrow_annotation_semantics_are_audited(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["panels"][0]["annotations"] = [
                {"type": "text", "coordinate_space": "axes_fraction", "coordinates": [0.2, 0.8], "text": "Peak", "style": {"font_size_pt": 10, "color": "#111111", "ha": "left", "va": "top", "rotation": 30, "fontweight": "bold", "fontstyle": "italic"}},
                {"type": "arrow", "coordinate_space": "axes_fraction", "coordinates": [0.2, 0.7, 0.45, 0.55], "style": {"arrowstyle": "->", "color": "#111111", "line_width_pt": 1.5}},
            ]
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = root / "out"
            renderer.render_file(spec_path, out)
            self.assertEqual("pass", auditor.audit_semantics(spec_path, out / "render_semantics.json")["overall"])
            semantics = json.loads((out / "render_semantics.json").read_text(encoding="utf-8"))
            annotations = semantics["figures"]["figure_1"]["panels"]["A"]["annotations"]
            self.assertEqual("left", annotations[0]["style"]["ha"])
            self.assertNotIn("declared", set(annotations[1]["provenance"].values()))
            annotations[1]["geometry"]["x1"] = 0.9
            bad = root / "bad_annotations.json"
            bad.write_text(json.dumps(semantics), encoding="utf-8")
            self.assertEqual("failed", auditor.audit_semantics(spec_path, bad)["overall"])

    def test_v25_declared_or_unavailable_provenance_blocks_strict_audit(self) -> None:
        renderer = load_module("render_visualspec_matplotlib", SCRIPTS / "render_visualspec_matplotlib.py")
        auditor = load_module("audit_semantics", SCRIPTS / "audit_semantics.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(self._line_spec()), encoding="utf-8")
            out = root / "out"
            renderer.render_file(spec_path, out)
            semantics = json.loads((out / "render_semantics.json").read_text(encoding="utf-8"))
            plot = semantics["figures"]["figure_1"]["panels"]["A"]["plots"][0]
            plot["provenance"]["x_hash"] = "declared"
            bad = root / "bad_provenance.json"
            bad.write_text(json.dumps(semantics), encoding="utf-8")
            result = auditor.audit_semantics(spec_path, bad)
            self.assertEqual("failed", result["overall"])
            self.assertEqual("failed", result["checks"]["provenance"])

    def test_v25_semantic_failure_and_missing_panel_score_are_not_near_pass(self) -> None:
        finalizer = load_module("finalize_manifest", SCRIPTS / "finalize_manifest.py")
        score = {"canvas_size_match": True, "score_0_1": 0.0, "content_bbox_error": 0.0}
        self.assertEqual(
            "not_strict",
            finalizer.classify_status(score, profile="semantic", source_strategy="raw_data", representation="semantic_vector", semantic_audit={"overall": "failed"}, vector_validation={"status": "pass"}, panel_scores={"A": score}, required_panel_ids={"A"}),
        )
        self.assertEqual(
            "not_strict",
            finalizer.classify_status(score, profile="semantic", source_strategy="raw_data", representation="semantic_vector", semantic_audit={"overall": "pass"}, vector_validation={"status": "pass"}, panel_scores={}, required_panel_ids={"A"}),
        )
