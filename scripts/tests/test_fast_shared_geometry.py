from __future__ import annotations

from common import *

import importlib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


class SharedGeometryTests(ScientificFigureReproductionTestBase):
    def test_segments_and_fill_reuse_one_immutable_curve_source(self) -> None:
        module = importlib.import_module("shared_geometry")
        x = np.linspace(0.0, 1.0, 9)
        source = module.SharedSeries("curve-a", x, x**2)
        baseline = module.SharedSeries("baseline-a", x, np.zeros_like(x))
        fig, ax = plt.subplots()
        source.plot_segments(ax, [(0, 5), (4, 9)], color="black")
        source.fill_between(ax, baseline, color="grey", alpha=0.2)
        report = module.audit_shared_geometry(fig)
        plt.close(fig)
        self.assertEqual("pass", report["status"])
        self.assertEqual(2, report["source_count"])
        self.assertEqual(3, report["sources"]["curve-a"]["artist_count"])
        self.assertIn("fill_between", report["sources"]["curve-a"]["roles"])

    def test_same_source_id_with_different_data_fails_audit(self) -> None:
        module = importlib.import_module("shared_geometry")
        fig, ax = plt.subplots()
        module.SharedSeries("curve-a", [0, 1], [0, 1]).plot(ax)
        module.SharedSeries("curve-a", [0, 1], [1, 0]).plot(ax)
        report = module.audit_shared_geometry(fig)
        plt.close(fig)
        self.assertEqual("failed", report["status"])
        self.assertTrue(any("multiple geometry hashes" in item for item in report["failures"]))

    def test_pdf_vector_trace_exports_shared_path_audit(self) -> None:
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is not installed")
        tracer = load_module("pdf_vector_trace", SCRIPTS / "pdf_vector_trace.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            document = fitz.open()
            page = document.new_page(width=144, height=72)
            shape = page.new_shape()
            shape.draw_line((10, 60), (70, 12))
            shape.draw_rect((80, 20, 130, 60))
            shape.finish(color=(0, 0, 1), fill=(0.8, 0.9, 1.0), width=1)
            shape.commit()
            document.save(source)
            document.close()
            result = tracer.trace_pdf_clip(source, 1, (0, 0, 144, 72), root / "out", "demo", dpi=100)
            self.assertEqual("visual_trace_pass", result["status"])
            self.assertEqual("native_pdf_clip", result["render_method"])
            self.assertTrue(result["visual_score"]["independent_render"])
            self.assertTrue(result["visual_score"]["comparison_valid"])
            self.assertEqual("source_clip_pixel_dimensions", result["visual_score"]["output_canvas_basis"])
            self.assertEqual(
                "source_page_clip_vs_exported_pdf_raster",
                result["visual_score"]["comparison_pipeline"],
            )
            self.assertFalse(Path(result["outputs"]["png"]).is_absolute())
            self.assertTrue((root / "out" / "demo.svg").exists())
            audit = json.loads((root / "out" / "demo_geometry_audit.json").read_text(encoding="utf-8"))
            self.assertEqual("pass", audit["status"])
            self.assertEqual("pdf_compound_path", audit["source_identity_scope"])
            second = tracer.trace_pdf_clip(source, 1, (0, 0, 144, 72), root / "out_second", "demo", dpi=100)
            self.assertEqual(result["output_sha256"]["pdf"], second["output_sha256"]["pdf"])
