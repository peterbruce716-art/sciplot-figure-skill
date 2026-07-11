from __future__ import annotations

from common import *


class FastCoreTests(ScientificFigureReproductionTestBase):
    def test_manifest_pass_requires_all_python_gates(self) -> None:
        manifest = visualspec.make_manifest(spec_path="spec.json", output_dir="out")
        self.assertEqual("incomplete", manifest["overall_status"])
        manifest.update(
            {
                "source_code_status": "pass",
                "render_status": "pass",
                "export_status": "pass",
                "qa_execution_status": "not_run",
            }
        )
        self.assertEqual("render_only", visualspec.manifest_overall_status(manifest))
        manifest["qa_execution_status"] = "completed"
        manifest["quality_status"] = "near_pass"
        manifest["status"] = "semantic_near_pass"
        self.assertEqual("near_pass", visualspec.manifest_overall_status(manifest))

    def test_scaffold_uses_open_delivery_fields(self) -> None:
        scaffold = load_module("scaffold_figurespec", SCRIPTS / "scaffold_figurespec.py")
        spec = scaffold.build_spec(["fig1"], "outputs/figures", "outputs/source")
        panel = spec["panels"][0]
        self.assertIn("delivery", spec)
        self.assertNotIn("editable" + "_delivery", panel)
        self.assertNotIn("op" + "ju_delivery", panel)
        self.assertEqual("fixed_canvas", spec["figure"]["crop_mode"])

    def test_trace_image_primitives_module_loads(self) -> None:
        trace = load_module("trace_image_primitives", SCRIPTS / "trace_image_primitives.py")
        self.assertTrue(callable(trace.trace_image))

    def test_create_trace_figure_script_writes_wrapper(self) -> None:
        creator = load_module("create_trace_figure_scripts", SCRIPTS / "create_trace_figure_scripts.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "fig.png"
            source.parent.mkdir()
            source.write_text("x", encoding="utf-8")
            script = root / "scripts" / "fig_trace.py"
            trace_script = SCRIPTS / "trace_image_primitives.py"
            creator.create_script(
                source=source,
                script_path=script,
                root=root,
                out_dir=root / "outputs",
                stem="fig",
                trace_script=trace_script,
            )
            text = script.read_text(encoding="utf-8")
            self.assertIn("per_figure_script", text)
            self.assertIn("trace_image", text)

    def test_score_does_not_resize_source_to_hide_canvas_error(self) -> None:
        scorer = load_module("score_iteration", SCRIPTS / "score_iteration.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            actual = root / "actual.png"
            Image.new("RGB", (120, 80), "white").save(source)
            Image.new("RGB", (60, 40), "white").save(actual)
            score = scorer.score_images(source, actual)
            self.assertFalse(score["canvas_size_match"])
            self.assertGreater(score["size_penalty"], 0)

    def test_data_resolver_reads_external_csv_mapping(self) -> None:
        resolver = load_module("data_resolver", SCRIPTS / "data_resolver.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "points.csv"
            csv_path.write_text("time,response\n0,1\n1,3\n", encoding="utf-8")
            data = {"source": "points.csv", "mapping": {"x": "time", "y": "response"}}
            self.assertEqual([0.0, 1.0], resolver.resolve_series(data, "x", base_dir=root))
            self.assertEqual([1.0, 3.0], resolver.resolve_series(data, "y", base_dir=root))

    def test_score_writes_comparison_artifacts(self) -> None:
        scorer = load_module("score_iteration", SCRIPTS / "score_iteration.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            actual = root / "actual.png"
            Image.new("RGB", (40, 30), "white").save(source)
            Image.new("RGB", (40, 30), "white").save(actual)
            score = scorer.score_images(source, actual, comparison_dir=root / "comparison")
            self.assertIn("edge_score", score)
            self.assertIn("ssim_score", score)
            self.assertIn("visual_fidelity", score)
            self.assertTrue((root / "comparison" / "overlay_50.png").exists())

    def test_build_skill_package_writes_portable_zip(self) -> None:
        builder = load_module("build_skill_package", SCRIPTS / "build_skill_package.py")
        validator = load_module("validate_skill_package", SCRIPTS / "validate_skill_package.py")
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "skill.zip"
            built = builder.build_package(ROOT, zip_path)
            result = validator.scan_zip(built)
            self.assertEqual("ok", result["status"], result)
            with zipfile.ZipFile(built, "r") as archive:
                names = archive.namelist()
            self.assertTrue(all("\\" not in name for name in names))
            self.assertTrue(all("__pycache__" not in name and not name.endswith(".pyc") for name in names))

    def test_check_environment_reports_fonts_and_required_modules(self) -> None:
        env = load_module("check_environment", SCRIPTS / "check_environment.py")
        result = env.check_environment()
        self.assertIn("matplotlib", result["required_modules"])
        self.assertIn("fonts_available", result)

