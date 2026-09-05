from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_resolver import load_data_source, resolve_series


class TabularDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def write_table(self, text: str, suffix: str = ".csv") -> Path:
        path = self.root / f"measurements{suffix}"
        path.write_text(text, encoding="utf-8")
        return path

    def test_duplicate_headers_fail_before_overwriting_values(self) -> None:
        for suffix, delimiter in [(".csv", ","), (".tsv", "\t")]:
            with self.subTest(suffix=suffix):
                path = self.write_table(
                    f"x{delimiter}y{delimiter}y\n0{delimiter}10{delimiter}99\n", suffix
                )
                with self.assertRaisesRegex(ValueError, r"measurements.*duplicate.*y"):
                    load_data_source(path)

    def test_blank_headers_are_rejected(self) -> None:
        for header in ["x,", "x,   "]:
            with self.subTest(header=header):
                path = self.write_table(f"{header}\n0,10\n")
                with self.assertRaisesRegex(ValueError, r"measurements.*empty.*column 2"):
                    load_data_source(path)

    def test_empty_file_is_rejected(self) -> None:
        path = self.write_table("")
        with self.assertRaisesRegex(ValueError, r"measurements.*header"):
            load_data_source(path)

    def test_row_width_mismatch_reports_source_and_line(self) -> None:
        for row, count in [("1,20,99", 3), ("1", 1)]:
            with self.subTest(row=row):
                path = self.write_table(f"x,y\n0,10\n{row}\n")
                with self.assertRaisesRegex(
                    ValueError, rf"measurements.*line 3.*expected 2.*got {count}"
                ):
                    load_data_source(path)

    def test_malformed_quoted_record_is_rejected_with_location(self) -> None:
        path = self.write_table('x,y\n0,"10\n')
        with self.assertRaisesRegex(ValueError, r"measurements.*line 2"):
            load_data_source(path)

    def test_bom_unicode_and_relative_column_mapping(self) -> None:
        self.write_table("\ufeff时间,响应\n0,1.5\n1,3e-2\n")
        data = {"source": "measurements.csv", "mapping": {"x": "时间", "y": "响应"}}
        self.assertEqual([0.0, 1.0], resolve_series(data, "x", base_dir=self.root))
        self.assertEqual([1.5, 0.03], resolve_series(data, "y", base_dir=self.root))

    def test_quoted_delimiters_newlines_and_escaped_quotes_are_preserved(self) -> None:
        path = self.write_table('x,label\n0,"alpha,beta"\n1,"two\nlines"\n2,"say ""hi"""\n')
        self.assertEqual(
            {"x": [0.0, 1.0, 2.0], "label": ["alpha,beta", "two\nlines", 'say "hi"']},
            load_data_source(path),
        )

    def test_tsv_blank_lines_and_empty_cells_keep_row_alignment(self) -> None:
        path = self.write_table("x\ty\tnote\n\n0\t10\t\n\n1\t\tlabel\n", ".TSV")
        self.assertEqual(
            {"x": [0.0, 1.0], "y": [10.0, ""], "note": ["", "label"]},
            load_data_source(path),
        )

    def test_column_names_are_not_silently_normalized(self) -> None:
        path = self.write_table("x, y,y\n0,10,20\n")
        self.assertEqual({"x": [0.0], " y": [10.0], "y": [20.0]}, load_data_source(path))

    def test_header_only_table_keeps_named_empty_columns(self) -> None:
        path = self.write_table("x,y\n")
        self.assertEqual({"x": [], "y": []}, load_data_source(path))


if __name__ == "__main__":
    unittest.main()
