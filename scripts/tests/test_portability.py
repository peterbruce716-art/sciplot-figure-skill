from __future__ import annotations

from common import *


class PortabilityTests(ScientificFigureReproductionTestBase):
    def test_portability_excludes_its_output_report(self) -> None:
        portability = load_module("validate_portability_self_output", SCRIPTS / "validate_portability.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "portability.json"
            report.write_text(json.dumps({"stale_host_path": str(root.resolve())}), encoding="utf-8")

            self.assertEqual("failed", portability.validate_portability(root)["status"])
            result = portability.validate_portability(root, excluded_paths={report})
            self.assertEqual("pass", result["status"])
            self.assertEqual(0, result["scanned_json_files"])

    def test_portable_command_removes_host_absolute_paths(self) -> None:
        portable = load_module("portable_paths", SCRIPTS / "portable_paths.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "runtime" / "scientific_figure_reproduction" / "audit_semantics.py"
            command = portable.portable_command(
                [sys.executable, str(script), "--spec", str(root / "visualspec.json"), "--external", str(root.parent / "outside.dat")],
                root,
            )
            self.assertEqual("python", command["executable_role"])
            self.assertEqual("runtime/scientific_figure_reproduction/audit_semantics.py", command["script"])
            self.assertIn("visualspec.json", command["arguments"])
            self.assertIn("outside.dat", command["arguments"])

    def test_delivery_json_has_no_absolute_paths(self) -> None:
        portability = load_module("validate_portability", SCRIPTS / "validate_portability.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(self._line_spec()), encoding="utf-8")
            baseline = root / "baseline"
            subprocess.run([sys.executable, str(SCRIPTS / "render_matplotlib.py"), "--spec", str(spec_path), "--out-dir", str(baseline)], check=True)
            bundle = root / "bundle"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--source", str(baseline / "render.png"), "--out-dir", str(bundle), "--require-strict"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            result = portability.validate_portability(bundle)
            self.assertEqual("pass", result["status"], json.dumps(result["failures"], indent=2))

    def test_same_bundle_in_two_directories_has_same_canonical_reports(self) -> None:
        checksums = load_module("verify_checksums", SCRIPTS / "verify_checksums.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(self._line_spec()), encoding="utf-8")
            baseline = root / "baseline"
            subprocess.run([sys.executable, str(SCRIPTS / "render_matplotlib.py"), "--spec", str(spec_path), "--out-dir", str(baseline)], check=True)
            bundles = []
            for name in ("bundle_one", "bundle_two"):
                bundle = root / name
                completed = subprocess.run(
                    [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--source", str(baseline / "render.png"), "--out-dir", str(bundle), "--require-strict"],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
                bundles.append(bundle)
            for relative in ("reproduction_manifest.json", "outputs/render_manifest.json", "visual_score.json"):
                first = checksums.sha256_bytes(checksums.canonical_bytes(bundles[0] / relative))
                second = checksums.sha256_bytes(checksums.canonical_bytes(bundles[1] / relative))
                self.assertEqual(first, second, relative)
