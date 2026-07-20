from __future__ import annotations

from common import *


class BundleWorkflowTests(ScientificFigureReproductionTestBase):
    def test_run_reproduction_strict_success_checks_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["panels"][0]["bbox_normalized"] = [0.22, 0.18, 0.68, 0.72]
            spec["qa_policy"] = {
                "canvas_safety": {
                    "enabled": True,
                    "margin_px": 5,
                    "background": "#ffffff",
                    "tolerance": 10,
                    "required_edges": ["top", "right", "bottom", "left"],
                }
            }
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            baseline = root / "baseline"
            subprocess.run([sys.executable, str(SCRIPTS / "render_matplotlib.py"), "--spec", str(spec_path), "--out-dir", str(baseline)], check=True)
            source = baseline / "render.png"
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--source", str(source), "--out-dir", str(out_dir), "--require-strict"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertTrue((out_dir / "run_report.json").exists(), completed.stderr)
            self.assertTrue((out_dir / "reproduction_manifest.json").exists(), completed.stderr)
            run_report = json.loads((out_dir / "run_report.json").read_text(encoding="utf-8"))
            self.assertEqual("ok", run_report["status"])
            manifest = json.loads((out_dir / "reproduction_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("semantic_strict_pass", manifest["status"])
            self.assertEqual("strict_pass", manifest["overall_status"])
            self.assertEqual("completed", manifest["qa_execution_status"])
            self.assertEqual("strict_pass", manifest["quality_status"])
            self.assertEqual("pass", manifest["vector_validation_status"])
            self.assertEqual("pass", manifest["semantic_reconstruction_status"])
            self.assertEqual("pass", manifest["canvas_safety_status"])
            self.assertEqual("pass", manifest["canvas_safety"]["status"])
            self.assertTrue((out_dir / "qa" / "canvas_safety.json").exists())
            self.assertIn("figure_1", manifest["per_figure_scripts"])
            self.assertFalse(Path(manifest["per_figure_scripts"]["figure_1"]).is_absolute())
            self.assertFalse(Path(manifest["figures"]["figure_1"]["exports"]["png"]).is_absolute())
            self.assertIn("A", manifest["figures"]["figure_1"]["panels"])
            self.assertEqual("completed", manifest["figures"]["figure_1"]["panels"]["A"]["qa"]["execution_status"])
            self.assertTrue((out_dir / "checksums.json").exists())
            self.assertTrue((out_dir / "runtime" / "sciplot_figure_skill" / "render.py").exists())
            self.assertTrue((out_dir / "runtime" / "sciplot_figure_skill" / "validate_data_swap_template.py").exists())
            self.assertTrue((out_dir / "outputs" / "render.png").exists())
            self.assertTrue((out_dir / "comparison" / "difference.png").exists())

    def test_canvas_safety_fails_bundle_before_manifest_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["qa_policy"] = {
                "canvas_safety": {
                    "enabled": True,
                    "margin_px": 150,
                    "background": "#ffffff",
                    "tolerance": 10,
                    "required_edges": ["top", "right", "bottom", "left"],
                }
            }
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--out-dir", str(out_dir)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            report = json.loads((out_dir / "run_report.json").read_text(encoding="utf-8"))
            canvas_report = json.loads((out_dir / "qa" / "canvas_safety.json").read_text(encoding="utf-8"))
            self.assertEqual("canvas_safety", report["stage"])
            self.assertEqual("required_canvas_margin_not_clear", report["failure_type"])
            self.assertEqual("failed", canvas_report["status"])
            self.assertFalse((out_dir / "reproduction_manifest.json").exists())

    def test_boxed_text_safety_fails_bundle_before_manifest_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["qa_policy"] = {
                "boxed_text_safety": {
                    "enabled": True,
                    "regions": [
                        {
                            "id": "missing_legend_row",
                            "bbox_px": [1, 1, 20, 20],
                            "text_color": "#000000",
                            "color_tolerance": 30,
                            "border_inset_px": 1,
                            "min_ink_height_px": 8,
                        }
                    ],
                }
            }
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--out-dir", str(out_dir)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            report = json.loads((out_dir / "run_report.json").read_text(encoding="utf-8"))
            boxed_report = json.loads((out_dir / "qa" / "boxed_text_safety.json").read_text(encoding="utf-8"))
            self.assertEqual("boxed_text_safety", report["stage"])
            self.assertEqual("boxed_text_ink_or_padding_failed", report["failure_type"])
            self.assertEqual("failed", boxed_report["status"])
            self.assertEqual(["missing_legend_row"], boxed_report["failed_regions"])
            self.assertFalse((out_dir / "reproduction_manifest.json").exists())

    def test_boxed_text_safety_pass_is_recorded_in_final_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["qa_policy"] = {
                "boxed_text_safety": {
                    "enabled": True,
                    "regions": [
                        {
                            "id": "declared_dark_ink",
                            "bbox_px": [40, 30, 560, 370],
                            "text_color": "#000000",
                            "color_tolerance": 100,
                            "border_inset_px": 1,
                            "min_ink_height_px": 1,
                        }
                    ],
                }
            }
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--out-dir", str(out_dir)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            boxed_report = json.loads((out_dir / "qa" / "boxed_text_safety.json").read_text(encoding="utf-8"))
            manifest = json.loads((out_dir / "reproduction_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("pass", boxed_report["status"])
            self.assertEqual("pass", manifest["boxed_text_safety_status"])
            self.assertEqual("pass", manifest["boxed_text_safety"]["status"])

    def test_plot_geometry_safety_fails_bundle_before_manifest_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["qa_policy"] = {
                "plot_geometry_safety": {
                    "enabled": True,
                    "regions": [
                        {
                            "id": "wrong_panel_bbox",
                            "expected_bbox_px": [0, 0, 1, 1],
                            "max_edge_error_px": 1,
                            "selector": {
                                "min_rgb": [0, 0, 0],
                                "max_rgb": [100, 100, 100],
                                "background": "#ffffff",
                                "min_background_distance": 10,
                            },
                        }
                    ],
                }
            }
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--out-dir", str(out_dir)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            report = json.loads((out_dir / "run_report.json").read_text(encoding="utf-8"))
            geometry = json.loads((out_dir / "qa" / "plot_geometry_safety.json").read_text(encoding="utf-8"))
            self.assertEqual("plot_geometry_safety", report["stage"])
            self.assertEqual("plot_region_bbox_mismatch", report["failure_type"])
            self.assertEqual("failed", geometry["status"])
            self.assertFalse((out_dir / "reproduction_manifest.json").exists())

    def test_plot_geometry_safety_pass_is_recorded_in_final_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["qa_policy"] = {
                "plot_geometry_safety": {
                    "enabled": True,
                    "regions": [
                        {
                            "id": "broad_geometry_contract",
                            "expected_bbox_px": [0, 0, 0, 0],
                            "max_edge_error_px": 1000,
                            "selector": {
                                "min_rgb": [0, 0, 0],
                                "max_rgb": [100, 100, 100],
                                "background": "#ffffff",
                                "min_background_distance": 10,
                            },
                        }
                    ],
                }
            }
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--out-dir", str(out_dir)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            geometry = json.loads((out_dir / "qa" / "plot_geometry_safety.json").read_text(encoding="utf-8"))
            manifest = json.loads((out_dir / "reproduction_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("pass", geometry["status"])
            self.assertEqual("pass", manifest["plot_geometry_safety_status"])
            self.assertEqual("pass", manifest["plot_geometry_safety"]["status"])

    def test_incomplete_axis_spines_fail_bundle_before_manifest_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec["qa_policy"] = {
                "plot_geometry_safety": {
                    "enabled": True,
                    "regions": [
                        {
                            "id": "axis_spine_contract",
                            "expected_bbox_px": [0, 0, 0, 0],
                            "max_edge_error_px": 1000,
                            "selector": {
                                "min_rgb": [0, 0, 0],
                                "max_rgb": [100, 100, 100],
                                "background": "#ffffff",
                                "min_background_distance": 10,
                            },
                            "axis_spines": {
                                "expected_origin_px": [0, 0],
                                "expected_horizontal_end_px": 1,
                                "expected_vertical_top_px": 0,
                                "search_radius_px": 0,
                                "max_position_error_px": 0,
                                "max_rgb": [100, 100, 100],
                                "min_horizontal_coverage_ratio": 1.0,
                                "min_vertical_coverage_ratio": 1.0,
                            },
                        }
                    ],
                }
            }
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--out-dir", str(out_dir)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            report = json.loads((out_dir / "run_report.json").read_text(encoding="utf-8"))
            geometry = json.loads((out_dir / "qa" / "plot_geometry_safety.json").read_text(encoding="utf-8"))
            self.assertEqual("plot_geometry_safety", report["stage"])
            self.assertEqual("failed", geometry["status"])
            self.assertIn("axis_spines_failed", geometry["regions"][0]["failure_reasons"])
            self.assertFalse((out_dir / "reproduction_manifest.json").exists())

    def test_run_reproduction_strict_failure_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.new("RGB", (600, 400), "white").save(source)
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(self._line_spec()), encoding="utf-8")
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--source", str(source), "--out-dir", str(out_dir), "--require-strict"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            run_report = json.loads((out_dir / "run_report.json").read_text(encoding="utf-8"))
            self.assertEqual("incomplete", run_report["status"])
            manifest = json.loads((out_dir / "reproduction_manifest.json").read_text(encoding="utf-8"))
            self.assertIn(manifest["status"], {"semantic_near_pass", "not_strict"})

    def test_reproduction_bundle_runs_after_moving_without_skill_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(self._line_spec()), encoding="utf-8")
            baseline = root / "baseline"
            subprocess.run([sys.executable, str(SCRIPTS / "render_matplotlib.py"), "--spec", str(spec_path), "--out-dir", str(baseline)], check=True)
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--source", str(baseline / "render.png"), "--out-dir", str(out_dir), "--require-strict"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            moved = root / "moved_bundle"
            shutil.copytree(out_dir, moved)
            entry_text = (moved / "reproduce.py").read_text(encoding="utf-8")
            self.assertNotIn(str(SCRIPTS), entry_text)
            rerun = subprocess.run([sys.executable, str(moved / "reproduce.py")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(0, rerun.returncode, rerun.stdout + rerun.stderr)
            self.assertTrue((moved / "outputs" / "render.png").exists())

    def test_custom_renderer_is_inherited_by_reproduce_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.new("RGB", (40, 30), "white").save(source)
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(self._line_spec()), encoding="utf-8")
            custom = root / "custom_renderer.py"
            custom.write_text(
                """
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

def _hash(values):
    payload = json.dumps([float(value) for value in values], separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--script")
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 30), "white").save(out / "render.png")
    fig, ax = plt.subplots(figsize=(0.4, 0.3), dpi=100)
    ax.plot([0, 1], [0, 1], color="#ffffff", linewidth=0.5)
    ax.set_axis_off()
    fig.savefig(out / "render.svg", bbox_inches="tight", pad_inches=0)
    fig.savefig(out / "render.pdf", bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    (out / "custom_marker.txt").write_text("custom", encoding="utf-8")
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    plot = spec["panels"][0]["plots"][0]
    data = plot["data"]
    semantics = {
        "schema": "scientificfigure.render_semantics.v1",
        "figures": {"figure_1": {"panels": {"A": {
            "axes": {"x": {"scale": "linear", "limits": [0, 1], "ticks": [], "label": ""}, "y": {"scale": "linear", "limits": [0, 1], "ticks": [], "label": ""}},
            "plots": [{
                "type": "line",
                "label": plot.get("label"),
                "x_hash": _hash(data["x"]),
                "y_hash": _hash(data["y"]),
                "point_count": 2,
                "style": {"color": "#000000"},
                "provenance": {"type": "observed", "x_hash": "observed", "y_hash": "observed", "point_count": "observed", "style.color": "observed"}
            }],
            "legend_labels": [],
            "annotations": []
        }}}}
    }
    (out / "render_semantics.json").write_text(json.dumps(semantics), encoding="utf-8")
    manifest = {
        "schema": "scientificfigure.manifest.v2",
        "project_root": ".",
        "spec_path": str(args.spec),
        "output_dir": str(out),
        "source_code_status": "pass",
        "render_status": "pass",
        "raster_export_status": "pass",
        "vector_export_status": "pass",
        "export_status": "pass",
        "vector_validation_status": "not_run",
        "semantic_reconstruction_status": "not_run",
        "visual_qa_status": "not_run",
        "qa_status": "not_run",
        "qa_execution_status": "not_run",
        "quality_status": "not_applicable",
        "status": "render_only",
        "overall_status": "render_only",
        "source_strategy": "raw_data",
        "representation": "semantic_vector",
        "exports": {"png": str(out / "render.png"), "svg": str(out / "render.svg"), "pdf": str(out / "render.pdf")},
        "figures": {"figure_1": {"source": None, "script": args.script, "spec": str(args.spec), "source_strategy": "raw_data", "representation": "semantic_vector", "status": "render_only", "exports": {"png": str(out / "render.png"), "svg": str(out / "render.svg"), "pdf": str(out / "render.pdf")}, "qa": {"execution_status": "not_run", "result": "not_applicable"}, "panels": {"A": {"bbox_normalized": [0.15, 0.18, 0.75, 0.72], "qa": {"execution_status": "not_run", "result": "not_applicable"}}}}},
        "per_figure_scripts": {"figure_1": args.script},
        "errors": []
    }
    (out / "render_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
""".lstrip(),
                encoding="utf-8",
            )
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--source", str(source), "--out-dir", str(out_dir), "--script", str(custom)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            manifest = json.loads((out_dir / "reproduction_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("semantic_near_pass", manifest["status"])
            moved = root / "custom_moved"
            shutil.copytree(out_dir, moved)
            (moved / "outputs" / "custom_marker.txt").unlink()
            rerun = subprocess.run([sys.executable, str(moved / "reproduce.py")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(0, rerun.returncode, rerun.stdout + rerun.stderr)
            self.assertEqual("custom", (moved / "outputs" / "custom_marker.txt").read_text(encoding="utf-8"))

    def test_bundle_reproduce_verify_and_checksum_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            baseline = root / "baseline"
            subprocess.run([sys.executable, str(SCRIPTS / "render_matplotlib.py"), "--spec", str(spec_path), "--out-dir", str(baseline)], check=True, timeout=180)
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--source", str(baseline / "render.png"), "--out-dir", str(out_dir), "--require-strict"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=180,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MPLCONFIGDIR": str(root / "mplconfig")},
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            for name in ["render.py", "reproduce.py", "verify.py", "checksums.json"]:
                self.assertTrue((out_dir / name).exists(), name)
            for name in ["requirements.txt", "requirements-lock.txt", "environment.json", "fonts.json", "environment_policy.json"]:
                self.assertTrue((out_dir / "environment" / name).exists(), name)
            caches = [path for path in out_dir.rglob("*") if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}]
            self.assertEqual([], caches)
            verify = subprocess.run([sys.executable, str(out_dir / "verify.py")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
            self.assertEqual(0, verify.returncode, verify.stdout + verify.stderr)
            attestation = out_dir / "run_attestation.json"
            original_attestation = attestation.read_text(encoding="utf-8")
            attestation.write_text(original_attestation + "\n", encoding="utf-8")
            verify_after_attestation_tamper = subprocess.run([sys.executable, str(out_dir / "verify.py")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
            self.assertNotEqual(0, verify_after_attestation_tamper.returncode)
            attestation.write_text(original_attestation, encoding="utf-8")
            verify_after_attestation_restore = subprocess.run([sys.executable, str(out_dir / "verify.py")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
            self.assertEqual(0, verify_after_attestation_restore.returncode, verify_after_attestation_restore.stdout + verify_after_attestation_restore.stderr)
            with (out_dir / "outputs" / "render.svg").open("a", encoding="utf-8") as handle:
                handle.write("\n<!--tamper-->\n")
            verify_after_tamper = subprocess.run([sys.executable, str(out_dir / "verify.py")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
            self.assertNotEqual(0, verify_after_tamper.returncode)

    def _single_plot_spec(self, plot: dict[str, object]) -> dict[str, object]:
        spec = self._line_spec()
        spec["figure"] = {"size_mm": [50.8, 33.8667], "dpi": 120, "crop_mode": "fixed_canvas"}
        spec["panels"][0]["plots"] = [plot]
        return spec

    def test_v24_verify_reports_unexpected_files_and_fake_pdf_fails(self) -> None:
        checker = load_module("check_vector_output", SCRIPTS / "check_vector_output.py")
        verifier = load_module("verify_checksums", SCRIPTS / "verify_checksums.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tracked.txt").write_text("ok", encoding="utf-8")
            checksums = root / "checksums.json"
            verifier.write_json(checksums, verifier.build_checksums(root))
            (root / "untracked.txt").write_text("unexpected", encoding="utf-8")
            result = verifier.verify_checksums(root, checksums)
            self.assertEqual("failed", result["status"])
            self.assertIn("untracked.txt", result["unexpected_files"])
            svg = root / "render.svg"
            pdf = root / "fake.pdf"
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><path d="M0 0 L10 10"/></svg>', encoding="utf-8")
            pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Page /Resources << /Font << /F1 2 0 R >> >> >> endobj\n%%EOF")
            vector = checker.check_vector_outputs(svg, pdf, representation="semantic_vector")
            self.assertEqual("failed", vector["status"])
            self.assertIn("pdf_parse_error", " ".join(vector["pdf"]["failure_reasons"]))

    def test_v24_bundle_lock_blocks_runtime_recertification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            baseline = root / "baseline"
            subprocess.run([sys.executable, str(SCRIPTS / "render_matplotlib.py"), "--spec", str(spec_path), "--out-dir", str(baseline)], check=True, timeout=180)
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--source", str(baseline / "render.png"), "--out-dir", str(out_dir), "--require-strict"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=180,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MPLCONFIGDIR": str(root / "mplconfig")},
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            lock = out_dir / "bundle.lock.json"
            attestation = out_dir / "run_attestation.json"
            self.assertTrue(lock.exists())
            self.assertTrue(attestation.exists())
            runtime_file = out_dir / "runtime" / "sciplot_figure_skill" / "capabilities.py"
            runtime_file.write_text(runtime_file.read_text(encoding="utf-8") + "\nTAMPERED = True\n", encoding="utf-8")
            rerun = subprocess.run([sys.executable, str(out_dir / "reproduce.py")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
            self.assertNotEqual(0, rerun.returncode)
            verify = subprocess.run([sys.executable, str(out_dir / "verify.py")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
            self.assertNotEqual(0, verify.returncode)

    def test_v24_reproduce_outputs_have_stable_canonical_hashes(self) -> None:
        verifier = load_module("verify_checksums", SCRIPTS / "verify_checksums.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = self._line_spec()
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            baseline = root / "baseline"
            subprocess.run([sys.executable, str(SCRIPTS / "render_matplotlib.py"), "--spec", str(spec_path), "--out-dir", str(baseline)], check=True, timeout=180)
            out_dir = root / "out"
            first = subprocess.run([sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--source", str(baseline / "render.png"), "--out-dir", str(out_dir), "--require-strict"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            first_hashes = verifier.build_checksums(out_dir)["files"]
            second = subprocess.run([sys.executable, str(out_dir / "reproduce.py")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
            self.assertEqual(0, second.returncode, second.stdout + second.stderr)
            second_hashes = verifier.build_checksums(out_dir)["files"]
            for name in ["outputs/render.png", "outputs/render.svg", "outputs/render.pdf", "outputs/render_semantics.json"]:
                self.assertEqual(first_hashes[name]["canonical_sha256"], second_hashes[name]["canonical_sha256"], name)

    def test_v25_environment_policy_mismatch_fails_verification(self) -> None:
        env_policy = load_module("environment_policy", SCRIPTS / "environment_policy.py")
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp) / "environment_policy.json"
            payload = env_policy.write_environment_policy(policy, mode="exact")
            payload["environment"]["python"] = "0.0.0"
            policy.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual("failed", env_policy.verify_environment_policy(policy)["status"])
