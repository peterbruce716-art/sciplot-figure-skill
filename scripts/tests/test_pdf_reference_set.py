from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from pdf_reference_set import validate_pdf_reference_set  # noqa: E402


class PdfReferenceSetTests(unittest.TestCase):
    def _fixture(self) -> tuple[Path, Path]:
        root = Path(tempfile.mkdtemp())
        pdf = root / "paper.pdf"
        pdf.write_bytes(b"pdf-bytes")
        inputs = root / "inputs"
        inputs.mkdir()
        (inputs / "fig3_reference.png").write_bytes(b"reference")
        manifest = root / "reference-extraction.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema": "sciplot.fresh-pdf-reference-set.v2",
                    "pdf": {"path": "paper.pdf", "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()},
                    "figures": {
                        "3": {
                            "source": "inputs/fig3_reference.png",
                            "sha256": hashlib.sha256((inputs / "fig3_reference.png").read_bytes()).hexdigest(),
                            "page": 1,
                            "clip_pdf_points": [1, 2, 10, 20],
                            "dpi": 100,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return root, manifest

    def test_accepts_current_pdf_and_reference_hashes(self) -> None:
        root, manifest = self._fixture()
        report = validate_pdf_reference_set(root=root, manifest_path=manifest)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["failures"], [])

    def test_rejects_stale_pdf_hash(self) -> None:
        root, manifest = self._fixture()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["pdf"]["sha256"] = "0" * 64
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        report = validate_pdf_reference_set(root=root, manifest_path=manifest)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any(item["check"] == "pdf_hash" for item in report["failures"]))

    def test_rejects_invalid_clip_box(self) -> None:
        root, manifest = self._fixture()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["figures"]["3"]["clip_pdf_points"] = [10, 20, 1, 2]
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        report = validate_pdf_reference_set(root=root, manifest_path=manifest)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any(item["check"] == "clip_box" for item in report["failures"]))

    def test_accepts_explicit_external_pdf_path(self) -> None:
        root, manifest = self._fixture()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["pdf"]["path"] = str(root / "paper.pdf")
        payload["pdf"]["external"] = True
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        report = validate_pdf_reference_set(root=root, manifest_path=manifest)
        self.assertEqual(report["status"], "pass")


if __name__ == "__main__":
    unittest.main()
