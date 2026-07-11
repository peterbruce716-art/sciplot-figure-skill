from __future__ import annotations

from common import *


class AcceptanceExampleTests(ScientificFigureReproductionTestBase):
    def test_release_acceptance_official_line_plot_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "release_acceptance.json"
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "release_acceptance.py"), "--json-out", str(report)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=240,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual("pass", payload["status"])
            self.assertEqual("semantic_strict_pass", payload["checks"]["official_example"])
