from __future__ import annotations

from common import *


class FastValidationTests(ScientificFigureReproductionTestBase):
    def test_manifest_report_preserves_relative_root(self) -> None:
        validator = load_module("validate_reproduction_manifest_relative_root", SCRIPTS / "validate_reproduction_manifest.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manifest.json").write_text("{}", encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(root)
                result = validator.validate_manifest(Path("manifest.json"), root=Path("."))
            finally:
                os.chdir(previous)

            self.assertEqual(".", result["root"])

    def test_skill_text_has_no_proprietary_project_terms(self) -> None:
        allowed_suffixes = {".md", ".py", ".json", ".yaml", ".yml", ".r"}
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in ROOT.rglob("*")
            if path.is_file() and path.suffix.lower() in allowed_suffixes
        )
        forbidden = [
            "".join(map(chr, [79, 80, 74, 85])),
            "".join(map(chr, [111, 112, 106, 117])),
            "".join(map(chr, [71, 114, 97, 112, 104, 32, 71, 97, 108, 108, 101, 114, 121])),
            "".join(map(chr, [79, 114, 105, 103, 105, 110, 76, 97, 98])),
            "".join(map(chr, [111, 114, 105, 103, 105, 110, 112, 114, 111])),
            "".join(map(chr, [67, 79, 77, 32, 97, 117, 116, 111, 109, 97, 116, 105, 111, 110])),
        ]
        for term in forbidden:
            self.assertNotIn(term, text)

    def test_demo_visualspec_validates(self) -> None:
        spec = json.loads((ROOT / "references" / "visualspec_v1_line_demo.json").read_text(encoding="utf-8"))
        self.assertEqual([], visualspec.validate_visualspec(spec))

    def test_skill_requires_per_figure_scripts(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("dedicated runnable script", text)
        self.assertIn("per_figure_scripts", text)

    def test_validate_reproduction_manifest_requires_per_figure_scripts(self) -> None:
        validator = load_module("validate_reproduction_manifest", SCRIPTS / "validate_reproduction_manifest.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ["source.png", "render.png", "render.svg", "render.pdf", "fig1.py"]:
                (root / name).write_text("x", encoding="utf-8")
            manifest = {
                "schema": "scientificfigure.manifest.v2",
                "status": "semantic_strict_pass",
                "overall_status": "pass",
                "source_strategy": "raw_data",
                "representation": "semantic_vector",
                "source_code_status": "pass",
                "render_status": "pass",
                "export_status": "pass",
                "qa_status": "pass",
                "qa_execution_status": "completed",
                "quality_status": "strict_pass",
                "semantic_audit": {"overall": "pass"},
                "vector_validation": {"status": "pass"},
                "per_figure_scripts": {"fig1": "fig1.py"},
                "figures": {
                    "fig1": {
                        "source": "source.png",
                        "exports": {"png": "render.png", "svg": "render.svg", "pdf": "render.pdf"},
                        "qa": {"execution_status": "completed", "result": "strict_pass"},
                        "status": "semantic_strict_pass",
                        "source_strategy": "raw_data",
                        "representation": "semantic_vector",
                        "panels": {"A": {"bbox_normalized": [0, 0, 1, 1], "qa": {"execution_status": "completed", "result": "strict_pass"}}},
                        "score": {"exact_pixel_match": True, "mae_0_1": 0.0, "rmse_0_1": 0.0, "score_0_1": 0.0, "canvas_size_match": True, "content_bbox_error": 0.0},
                    }
                },
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = validator.validate_manifest(manifest_path, root=root, require_strict=True)
            self.assertEqual("ok", result["status"])
            del manifest["per_figure_scripts"]["fig1"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = validator.validate_manifest(manifest_path, root=root, require_strict=True)
            self.assertEqual("failed", result["status"])

    def test_source_free_semantic_validation_does_not_require_visual_score(self) -> None:
        validator = load_module("validate_reproduction_manifest_source_free", SCRIPTS / "validate_reproduction_manifest.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ["render.png", "render.svg", "render.pdf", "fig1.py"]:
                (root / name).write_text("x", encoding="utf-8")
            manifest = {
                "schema": "scientificfigure.manifest.v2",
                "status": "semantic_validated_pass",
                "overall_status": "pass",
                "source_strategy": "raw_data",
                "representation": "semantic_vector",
                "source_code_status": "pass",
                "render_status": "pass",
                "export_status": "pass",
                "qa_status": "completed",
                "qa_execution_status": "completed",
                "quality_status": "validated_pass",
                "visual_qa_status": "not_applicable",
                "semantic_audit": {"overall": "pass"},
                "vector_validation": {"status": "pass"},
                "per_figure_scripts": {"fig1": "fig1.py"},
                "figures": {
                    "fig1": {
                        "source": None,
                        "exports": {"png": "render.png", "svg": "render.svg", "pdf": "render.pdf"},
                        "qa": {"execution_status": "completed", "result": "validated_pass"},
                        "status": "semantic_validated_pass",
                        "source_strategy": "raw_data",
                        "representation": "semantic_vector",
                        "panels": {"A": {"bbox_normalized": [0, 0, 1, 1], "qa": {"execution_status": "not_run", "result": "not_applicable"}}},
                    }
                },
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual("ok", validator.validate_manifest(manifest_path, root=root)["status"])
            strict = validator.validate_manifest(manifest_path, root=root, require_strict=True)
            self.assertEqual("failed", strict["status"])
            self.assertIn("strict_requires_reference_score", {item["code"] for item in strict["failures"]})

    def test_pixel_trace_cannot_claim_semantic_strict(self) -> None:
        validator = load_module("validate_reproduction_manifest", SCRIPTS / "validate_reproduction_manifest.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ["source.png", "render.png", "render.svg", "render.pdf", "fig1.py"]:
                (root / name).write_text("x", encoding="utf-8")
            manifest = {
                "schema": "scientificfigure.manifest.v2",
                "status": "semantic_strict_pass",
                "overall_status": "pass",
                "source_strategy": "pixel_trace",
                "representation": "pixel_primitives",
                "qa_status": "pass",
                "per_figure_scripts": {"fig1": "fig1.py"},
                "figures": {
                    "fig1": {
                        "source": "source.png",
                        "exports": {"png": "render.png", "svg": "render.svg", "pdf": "render.pdf"},
                        "reconstruction_mode": "pixel_trace",
                        "source_strategy": "pixel_trace",
                        "representation": "pixel_primitives",
                        "status": "semantic_strict_pass",
                        "qa": {"execution_status": "completed", "result": "strict_pass", "profile": "trace"},
                        "score": {"exact_pixel_match": True, "mae_0_1": 0.0, "rmse_0_1": 0.0},
                    }
                },
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = validator.validate_manifest(manifest_path, root=root, require_strict=True)
            self.assertEqual("failed", result["status"])

    def test_validator_and_renderer_capabilities_match(self) -> None:
        capabilities = load_module("capabilities", SCRIPTS / "capabilities.py")
        self.assertEqual(set(capabilities.SUPPORTED_PLOT_TYPES), set(capabilities.PLOT_RENDERERS))
        self.assertEqual(set(capabilities.SUPPORTED_ANNOTATION_TYPES), set(capabilities.ANNOTATION_RENDERERS))

    def test_region_fill_is_rejected_before_render(self) -> None:
        spec = self._line_spec()
        spec["panels"][0]["annotations"] = [{"type": "region_fill", "coordinates": []}]
        errors = visualspec.validate_visualspec(spec)
        self.assertTrue(any("region_fill" in error for error in errors))

    def test_empty_line_data_and_unknown_style_are_rejected(self) -> None:
        spec = self._line_spec()
        spec["panels"][0]["plots"] = [
            {"type": "line", "data": {}, "style": {"linewidht_pt": 99}}
        ]
        errors = visualspec.validate_visualspec(spec)
        self.assertTrue(any("data.x" in error or "data.y" in error for error in errors), errors)
        self.assertTrue(any("linewidht_pt" in error for error in errors), errors)

    def test_inline_errorbar_rejects_negative_and_copied_uncertainty(self) -> None:
        for yerr, code in [([-0.1, 0.2], "uncertainty_negative"), ([1.0, 2.0], "uncertainty_duplicates_measurement")]:
            with self.subTest(code=code):
                spec = self._line_spec()
                spec["panels"][0]["plots"] = [{"type": "errorbar", "data": {"x": [0, 1], "y": [1.0, 2.0], "yerr": yerr}, "style": {}}]
                errors = visualspec.validate_visualspec(spec)
                self.assertTrue(any(code in error for error in errors), errors)

    def test_source_mapping_rejects_same_y_and_yerr_without_override(self) -> None:
        spec = self._line_spec()
        spec["panels"][0]["plots"] = [{"type": "errorbar", "data": {"source": "data.csv", "mapping": {"x": "temperature", "y": "response", "yerr": "response"}}, "style": {}}]
        errors = visualspec.validate_visualspec(spec)
        self.assertTrue(any("uncertainty_same_as_measurement" in error for error in errors), errors)
        spec["panels"][0]["plots"] = [{"type": "errorbar", "data": {"source": "data.csv", "mapping": {"x": "temperature", "y": "response", "yerr": "response_sd", "xerr": "temperature"}, "uncertainty": {"source": "explicit", "semantics": "standard deviation"}}, "style": {}}]
        errors = visualspec.validate_visualspec(spec)
        self.assertTrue(any("uncertainty_xerr_unsupported" in error for error in errors), errors)

    def test_source_error_band_requires_uncertainty_evidence(self) -> None:
        spec = self._line_spec()
        spec["panels"][0]["plots"] = [{"type": "fill_between", "data": {"source": "data.csv", "mapping": {"x": "temperature", "y1": "lower", "y2": "upper"}}, "style": {}}]
        errors = visualspec.validate_visualspec(spec)
        self.assertTrue(any("uncertainty_evidence_missing" in error for error in errors), errors)

    def test_grouped_bar_uncertainty_fails_closed(self) -> None:
        for yerr, code in [([-0.1, 0.2], "uncertainty_negative"), ([1.0, 2.0], "uncertainty_duplicates_measurement")]:
            with self.subTest(code=code):
                spec = self._line_spec()
                spec["panels"][0]["plots"] = [{"type": "grouped_bar", "data": {"x": [0, 1], "groups": [{"y": [1.0, 2.0], "yerr": yerr, "uncertainty": {"source": "explicit", "semantics": "standard deviation"}}]}, "style": {}}]
                errors = visualspec.validate_visualspec(spec)
                self.assertTrue(any(code in error for error in errors), errors)

    def test_score_reads_qa_regions_from_spec_and_masks_ignore(self) -> None:
        scorer = load_module("score_iteration", SCRIPTS / "score_iteration.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            actual = root / "actual.png"
            spec_path = root / "visualspec.json"
            src = Image.new("RGB", (40, 30), "white")
            act = Image.new("RGB", (40, 30), "white")
            act.putpixel((2, 2), (0, 0, 0))
            src.save(source)
            act.save(actual)
            spec = self._line_spec()
            spec["qa_regions"] = {
                "plot_area": {"bbox_normalized": [0.25, 0.25, 0.5, 0.5]},
                "ignore": {"bbox_normalized": [0, 0, 0.2, 0.2]},
            }
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            unmasked = scorer.score_images(source, actual)
            masked = scorer.score_images(source, actual, spec_path=spec_path)
            self.assertIn("plot_area", masked["region_scores"])
            self.assertLess(masked["score_0_1"], unmasked["score_0_1"])

    def test_plot_typo_and_bad_annotation_style_are_rejected(self) -> None:
        spec = self._line_spec()
        spec["panels"][0]["plots"][0]["lable"] = "typo"
        spec["panels"][0]["annotations"] = [{"type": "rectangle", "coordinates": [0.1, 0.1, -0.2, 0.2], "style": {"font_szie_pt": 9}}]
        errors = visualspec.validate_visualspec(spec)
        self.assertTrue(any("lable" in error for error in errors), errors)
        self.assertTrue(any("width and height" in error for error in errors), errors)
        self.assertTrue(any("font_szie_pt" in error for error in errors), errors)

    def test_missing_external_data_writes_structured_run_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["panels"][0]["plots"][0]["data"] = {"source": "missing.csv", "mapping": {"x": "x", "y": "y"}}
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--out-dir", str(out_dir)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MPLCONFIGDIR": str(root / "mplconfig")},
            )
            self.assertEqual(2, completed.returncode, completed.stdout + completed.stderr)
            report = json.loads((out_dir / "run_report.json").read_text(encoding="utf-8"))
            self.assertEqual("input_preflight", report["stage"])
            self.assertEqual("missing_external_data", report["failure_type"])

    def test_visual_optimization_loop_propagates_render_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = {
                "schema": "scientificfigure.visualspec.v2",
                "figure": {"size_mm": [40, 30], "dpi": 100, "crop_mode": "fixed_canvas"},
                "panels": [
                    {
                        "id": "fig1",
                        "bbox_normalized": [0.2, 0.2, 0.7, 0.7],
                        "plots": [{"type": "unsupported_plot", "data": {"x": [0], "y": [0]}}],
                        "annotations": [],
                    }
                ],
            }
            spec_path = root / "bad_visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out_dir = root / "loop"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_visual_optimization_loop.py"), "--spec", str(spec_path), "--out-dir", str(out_dir), "--max-iterations", "1"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            manifest = json.loads((out_dir / "visual_loop_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("failed", manifest["status"])
            self.assertEqual("accepted_render_failed", manifest["iterations"][0]["decision"]["reason"])


if __name__ == "__main__":
    unittest.main()
