from __future__ import annotations

from common import Path, tempfile, unittest
from check_vector_output import check_svg, check_vector_outputs
from pypdf import PdfWriter


class VectorValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.svg = self.root / "figure.svg"
        self.pdf = self.root / "figure.pdf"

    def test_non_svg_xml_is_not_a_vector_export(self) -> None:
        for root_tag in ('document', 'html', 'svg xmlns="urn:not-svg"'):
            for mode in ("semantic_vector", "semantic_raster", "mixed"):
                with self.subTest(root=root_tag, mode=mode):
                    closing = root_tag.split()[0]
                    self.svg.write_text(f'<{root_tag}><path d="M0 0L10 10"/></{closing}>')
                    result = check_svg(self.svg, representation=mode)
                    self.assertEqual("failed", result["status"])
                    self.assertIn("svg_root_invalid", result["failure_reasons"])

    def test_empty_pdf_cannot_pass_combined_validation(self) -> None:
        self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L10 10"/></svg>')
        PdfWriter().write(self.pdf)
        for mode in ("semantic_vector", "semantic_raster", "mixed"):
            with self.subTest(mode=mode):
                result = check_vector_outputs(self.svg, self.pdf, representation=mode)
                self.assertIn("pdf_has_no_page_objects", result["pdf"]["failure_reasons"])
                self.assertEqual("failed", result["status"])

    def test_valid_svg_roots_are_supported(self) -> None:
        for attributes in ('', ' xmlns="http://www.w3.org/2000/svg"'):
            with self.subTest(attributes=attributes):
                self.svg.write_text(f'<svg{attributes}><path d="M0 0L10 10"/></svg>')
                self.assertEqual("pass", check_svg(self.svg, representation="semantic_vector")["status"])

    def test_embedded_raster_remains_valid_for_mixed_delivery(self) -> None:
        import base64
        import io
        from PIL import Image

        image = Image.new("RGB", (10, 10), "blue")
        png = io.BytesIO()
        image.save(png, format="PNG")
        data = base64.b64encode(png.getvalue()).decode("ascii")
        self.svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
            f'<image width="10" height="10" href="data:image/png;base64,{data}"/></svg>'
        )
        image.save(self.pdf, format="PDF")
        for mode in ("semantic_raster", "mixed"):
            with self.subTest(mode=mode):
                result = check_vector_outputs(self.svg, self.pdf, representation=mode)
                self.assertEqual("pass", result["svg"]["status"], result)
                self.assertEqual("pass", result["pdf"]["status"], result)
                self.assertEqual("pass", result["status"], result)
        self.assertEqual("failed", check_vector_outputs(self.svg, self.pdf)["status"])


if __name__ == "__main__":
    unittest.main()
