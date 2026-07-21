from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "sciplot.py"


class SciPlotCliTests(unittest.TestCase):
    def _write_csv(self, root: Path) -> Path:
        path = root / "data.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["time", "response"])
            writer.writerows([[0, 0], [1, 2], [2, 4], [3, 7]])
        return path

    def _run(self, *args: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        completed = subprocess.run(
            [sys.executable, str(CLI), *args, "--json"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=180,
        )
        payload = json.loads(completed.stdout)
        return completed, payload

    def test_quick_input_run_writes_small_project_without_pdf_or_data_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._write_csv(root)
            project = root / "quick"
            completed, payload = self._run("run", "--input", str(source), "--profile", "quick", "--out-dir", str(project), "--outputs", "auto")

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("quick", payload["selected_profile"])
            self.assertEqual("ok", payload["status"])
            self.assertTrue((project / "output" / "figure.png").is_file())
            self.assertTrue((project / "output" / "figure.svg").is_file())
            self.assertFalse((project / "output" / "figure.pdf").exists())
            self.assertTrue((project / "quick_report.json").is_file())
            self.assertTrue((project / "src" / "render.py").is_file())
            self.assertFalse((project / "output" / "render_semantics.json").exists())
            self.assertFalse((project / "output" / "render_manifest.json").exists())
            self.assertFalse((project / "data_swap_template.json").exists())
            self.assertEqual("sha256:", str(payload["input_hash"])[:7])
            self.assertIn("visualspec.json", payload["input_hashes"])
            quick_report = json.loads((project / "quick_report.json").read_text(encoding="utf-8"))
            self.assertNotIn("checksums", quick_report)
            self.assertNotIn("environment_summary", quick_report)

    def test_standard_run_keeps_semantic_and_vector_qa_without_data_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._write_csv(root)
            project = root / "standard"
            completed, payload = self._run("run", "--input", str(source), "--profile", "standard", "--out-dir", str(project), "--outputs", "auto")

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("standard", payload["selected_profile"])
            self.assertEqual("ok", payload["status"])
            self.assertTrue((project / "output" / "figure.png").is_file())
            self.assertTrue((project / "output" / "figure.svg").is_file())
            self.assertTrue((project / "output" / "figure.pdf").is_file())
            self.assertTrue((project / "qa" / "report.json").is_file())
            report = json.loads((project / "qa" / "report.json").read_text(encoding="utf-8"))
            self.assertEqual("pass", report["semantic_audit"]["overall"])
            self.assertEqual("pass", report["vector_validation"]["status"])
            self.assertEqual("not_applicable", report["plot_geometry_safety"]["status"])
            self.assertEqual("not_applicable", report["boxed_text_safety"]["status"])
            self.assertEqual("pass", report["manifest_validation"]["status"])
            self.assertNotIn("data_swap_template", report["enabled_gates"])

    def test_validate_reports_structured_failure_for_missing_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            completed, payload = self._run("validate", "--project", str(Path(tmp) / "missing"), "--profile", "standard")
            self.assertNotEqual(0, completed.returncode)
            self.assertEqual("failed", payload["status"])
            self.assertEqual("missing_project", payload["failure_type"])

    def test_validate_audit_rejects_a_lightweight_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._write_csv(root)
            project = root / "standard"
            completed, _ = self._run("run", "--input", str(source), "--profile", "standard", "--out-dir", str(project))
            self.assertEqual(0, completed.returncode, completed.stderr)
            completed, payload = self._run("validate", "--project", str(project), "--profile", "audit")
            self.assertNotEqual(0, completed.returncode)
            self.assertEqual("invalid_audit_bundle", payload["failure_type"])

    def test_standard_data_swap_is_explicit_and_fail_closed_without_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._write_csv(root)
            completed, payload = self._run(
                "run",
                "--input",
                str(source),
                "--profile",
                "standard",
                "--enable-data-swap",
                "--out-dir",
                str(root / "project"),
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertEqual("missing_data_swap_template", payload["failure_type"])

    def test_standard_data_swap_with_template_requires_audit_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._write_csv(root)
            completed, payload = self._run(
                "run",
                "--input",
                str(source),
                "--profile",
                "standard",
                "--enable-data-swap",
                "--template",
                str(source),
                "--out-dir",
                str(root / "project"),
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertEqual("data_swap_requires_audit", payload["failure_type"])

    def test_standard_create_bundle_requires_audit_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._write_csv(root)
            completed, payload = self._run(
                "run",
                "--input",
                str(source),
                "--profile",
                "standard",
                "--create-bundle",
                "--out-dir",
                str(root / "project"),
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertEqual("PlannerError", payload["failure_type"])

    def test_finalize_upgrades_standard_project_to_existing_audit_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._write_csv(root)
            project = root / "standard"
            completed, _ = self._run("run", "--input", str(source), "--profile", "standard", "--out-dir", str(project))
            self.assertEqual(0, completed.returncode, completed.stderr)
            completed, payload = self._run("finalize", "--project", str(project), "--profile", "audit", "--bundle", str(root / "bundle"))
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("pass", payload["status"])
            self.assertTrue((root / "bundle" / "bundle.lock.json").is_file())
            self.assertTrue((root / "bundle" / "reproduction_manifest.json").is_file())
            self.assertEqual("audit", payload["profile"])
            completed, payload = self._run("validate", "--project", str(root / "bundle"), "--profile", "audit")
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("pass", payload["status"])
            completed, payload = self._run("validate", "--project", str(root / "bundle"), "--profile", "audit")
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("pass", payload["status"])
            verify = subprocess.run([sys.executable, str(root / "bundle" / "verify.py")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
            self.assertEqual(0, verify.returncode, verify.stdout + verify.stderr)

    def test_run_audit_uses_the_same_bundle_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._write_csv(root)
            completed, payload = self._run("run", "--input", str(source), "--profile", "audit", "--out-dir", str(root / "audit"))
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("pass", payload["status"])
            self.assertEqual("audit", payload["profile"])
            self.assertTrue((root / "audit" / "reproduction_manifest.json").is_file())
            self.assertTrue((root / "audit" / "qa" / "execution_plan.json").is_file())
            self.assertEqual(str(root / "audit"), payload["project"])
            self.assertEqual("audit", payload["selected_profile"])

    def test_reusable_finalize_fails_before_creating_bundle_when_proof_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._write_csv(root)
            project = root / "standard"
            completed, _ = self._run("run", "--input", str(source), "--profile", "standard", "--out-dir", str(project))
            self.assertEqual(0, completed.returncode, completed.stderr)
            bundle = root / "bundle"
            completed, payload = self._run(
                "finalize",
                "--project",
                str(project),
                "--profile",
                "audit",
                "--claim",
                "reusable",
                "--template",
                str(source),
                "--figure",
                "figure_1",
                "--baseline-data",
                str(source),
                "--changed-data",
                str(source),
                "--bundle",
                str(bundle),
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertEqual("data_swap_proof_failed", payload["failure_type"])
            self.assertFalse(bundle.exists())

    def test_trace_pdf_delegates_to_fresh_pdf_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "source.pdf"
            with PdfPages(pdf) as pages:
                figure, axis = plt.subplots(figsize=(3, 2))
                axis.plot([0, 1], [0, 1])
                pages.savefig(figure)
                plt.close(figure)
            clips = root / "clips.json"
            clips.write_text(
                json.dumps(
                    {
                        "schema": "scientificfigure.pdf-clip-manifest.v1",
                        "figures": {"1": {"page": 1, "clip_pdf_points": [0, 0, 216, 144]}},
                    }
                ),
                encoding="utf-8",
            )
            completed, payload = self._run("trace-pdf", "--pdf", str(pdf), "--clip-manifest", str(clips), "--out-dir", str(root / "trace"))
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("pass", payload["status"])
            self.assertTrue((root / "trace" / "fresh_pdf_batch_manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
