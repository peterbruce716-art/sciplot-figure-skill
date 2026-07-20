from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "fresh_pdf_batch.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fresh_pdf_batch_test_module", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FreshPdfBatchTests(unittest.TestCase):
    def test_installed_skill_has_no_paper_specific_default_clips(self) -> None:
        module = load_module()
        self.assertEqual({}, module.FIGURE_CLIPS)

    def test_caption_locator_prefers_anchored_caption_over_body_reference(self) -> None:
        module = load_module()
        body = (0, 0, 10, 10, "As shown in Fig. 12, the map changes.")
        caption = (0, 20, 10, 30, "Fig. 12. Grain refinement mechanisms maps.")
        self.assertIs(caption, module.select_anchored_caption_block([body, caption], "12"))
        self.assertFalse(module.is_anchored_figure_caption(body[4], "12"))
        self.assertTrue(module.is_anchored_figure_caption(caption[4], "12"))

    def test_clip_manifest_is_generic_and_validated(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clips.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "scientificfigure.pdf-clip-manifest.v1",
                        "figures": {"alpha": {"page": 2, "clip_pdf_points": [1, 2, 30, 40]}},
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                {"alpha": {"page": 2, "clip_pdf_points": [1.0, 2.0, 30.0, 40.0]}},
                module.load_clip_manifest(path),
            )

    def test_rejects_inherited_output_path(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "paper.pdf"
            source.write_bytes(b"pdf")
            with self.assertRaisesRegex(ValueError, "E124_HISTORICAL_PATH_REJECTED"):
                module.run_batch(
                    source,
                    root / "validated_reuse_run",
                    figures=["x"],
                    dpi=72,
                    figure_clips={"x": {"page": 1, "clip_pdf_points": [0, 0, 10, 10]}},
                )

    def test_rejects_nonempty_output_before_work(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "paper.pdf"
            source.write_bytes(b"pdf")
            output = root / "out"
            output.mkdir()
            (output / "prior.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "E126_FRESH_OUTPUT_NOT_EMPTY"):
                module.run_batch(
                    source,
                    output,
                    figures=["x"],
                    dpi=72,
                    figure_clips={"x": {"page": 1, "clip_pdf_points": [0, 0, 10, 10]}},
                )

    def test_trace_manifest_records_fresh_identity(self) -> None:
        module = load_module()
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "paper.pdf"
            document = fitz.open()
            page = document.new_page(width=144, height=72)
            page.draw_rect((10, 10, 60, 50), color=(0, 0, 1), fill=(0.8, 0.9, 1.0))
            document.save(source)
            document.close()
            result = module.run_batch(
                source,
                root / "out",
                figures=["3"],
                dpi=72,
                figure_clips={"3": {"page": 1, "clip_pdf_points": [0.0, 0.0, 144.0, 72.0]}},
            )
            self.assertTrue(result["fresh_extraction"])
            self.assertFalse(result["historical_data_consumed"])
            self.assertEqual("pass", result["status"])
            self.assertEqual("visual_trace_pass", result["figures"]["3"]["status"])
            self.assertEqual("scripts/fig3_trace.py", result["per_figure_scripts"]["3"])
            script_path = root / "out" / "scripts" / "fig3_trace.py"
            self.assertTrue(script_path.is_file())
            script_text = script_path.read_text(encoding="utf-8")
            self.assertIn("source PDF SHA-256 mismatch", script_text)
            self.assertIn("historical_data_consumed", script_text)
            saved = json.loads((root / "out" / "fresh_pdf_batch_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(result["source_pdf"]["sha256"], saved["source_pdf"]["sha256"])
            self.assertEqual(result["per_figure_scripts"], saved["per_figure_scripts"])
            rerun_path = root / "out" / "trace_rerun_manifest.json"
            self.assertTrue(rerun_path.is_file())
            rerun = json.loads(rerun_path.read_text(encoding="utf-8"))
            self.assertEqual("sciplot.pdf_trace_rerun.v1", rerun["schema"])
            self.assertFalse(rerun["historical_data_consumed"])
            self.assertEqual("scripts/fig3_trace.py", rerun["figures"]["3"]["per_figure_script"])
            self.assertEqual("trace_rerun_manifest.json", saved["trace_rerun_manifest"])


if __name__ == "__main__":
    unittest.main()
