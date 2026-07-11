from __future__ import annotations

from common import *


class SourceFreeBundleTests(ScientificFigureReproductionTestBase):
    def test_source_free_bundle_closes_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(self._line_spec()), encoding="utf-8")
            out_dir = root / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--out-dir", str(out_dir)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=180,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MPLCONFIGDIR": str(root / "mplconfig")},
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            manifest = json.loads((out_dir / "reproduction_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("semantic_validated_pass", manifest["status"])
            self.assertEqual("pass", manifest["overall_status"])
            self.assertEqual("validated_pass", manifest["quality_status"])
            self.assertNotIn("score", manifest["figures"]["figure_1"])
            verify = subprocess.run(
                [sys.executable, str(out_dir / "verify.py")],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=90,
            )
            self.assertEqual(0, verify.returncode, verify.stdout + verify.stderr)

    def test_strict_without_source_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "visualspec.json"
            spec_path.write_text(json.dumps(self._line_spec()), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec_path), "--out-dir", str(root / "out"), "--require-strict"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=20,
            )
            self.assertEqual(2, completed.returncode)
            self.assertIn("--require-strict requires --source", completed.stderr)


if __name__ == "__main__":
    unittest.main()
