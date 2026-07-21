from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pdf_vector_trace import _edge_ink_report, trace_pdf_clip  # noqa: E402


class EdgeInkReportTests(unittest.TestCase):
    def test_passes_when_canvas_edges_are_clear(self) -> None:
        image = np.full((20, 30, 3), 255, dtype=np.uint8)
        image[5:15, 5:25] = 0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clear.png"
            Image.fromarray(image).save(path)

            report = _edge_ink_report(path, edge_band_px=3)

        self.assertEqual("pass", report["status"])
        self.assertEqual(0, report["edge_ink_pixels"])

    def test_flags_ink_touching_canvas_edge(self) -> None:
        image = np.full((20, 30, 3), 255, dtype=np.uint8)
        image[:, 0] = 0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "touching.png"
            Image.fromarray(image).save(path)

            report = _edge_ink_report(path, edge_band_px=3)

        self.assertEqual("attention", report["status"])
        self.assertGreater(report["edge_ink_pixels"], 0)
        self.assertEqual(3, report["edge_band_px"])

    def test_uniform_colored_background_is_not_treated_as_edge_ink(self) -> None:
        image = np.full((20, 30, 3), [238, 244, 248], dtype=np.uint8)
        image[5:15, 5:25] = 0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "colored-background.png"
            Image.fromarray(image).save(path)

            report = _edge_ink_report(path, edge_band_px=3)

        self.assertEqual("pass", report["status"])
        self.assertEqual([238, 244, 248], report["inferred_background_rgb"])

    def test_uniform_dark_full_bleed_content_requires_attention(self) -> None:
        image = np.zeros((20, 30, 3), dtype=np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "uniform-dark.png"
            Image.fromarray(image).save(path)

            report = _edge_ink_report(path, edge_band_px=3)

        self.assertEqual("attention", report["status"])
        self.assertTrue(report["uniform_edge_attention"])
        self.assertEqual(0, report["edge_ink_pixels"])

    def test_full_bleed_attention_does_not_downgrade_trace_status(self) -> None:
        import fitz

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "full-bleed.pdf"
            document = fitz.open()
            page = document.new_page(width=144, height=72)
            page.draw_rect(fitz.Rect(0, 0, 72, 72), color=(0, 0, 0), fill=(0, 0, 0))
            page.draw_rect(fitz.Rect(72, 0, 144, 72), color=(1, 0, 0), fill=(1, 0, 0))
            document.save(pdf)
            document.close()

            result = trace_pdf_clip(pdf, 1, (0.0, 0.0, 144.0, 72.0), root / "out", "fig", dpi=72)

        self.assertEqual("visual_trace_pass", result["status"])
        self.assertEqual("attention", result["visual_score"]["source_canvas_edge_safety"]["status"])
        self.assertEqual("attention", result["visual_score"]["render_canvas_edge_safety"]["status"])


if __name__ == "__main__":
    unittest.main()
