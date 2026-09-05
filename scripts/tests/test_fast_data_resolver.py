from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

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

    def test_duplicate_json_columns_are_rejected_before_data_loss(self) -> None:
        path = self.write_table('{"x":[0,1],"y":[10,20],"y":[90,80]}', ".json")
        with self.assertRaisesRegex(ValueError, r"measurements.*duplicate.*y"):
            load_data_source(path)

    def test_external_json_columns_must_be_lists(self) -> None:
        for value in ["42", {"3": 100, "4": 200}, 42, 1.5, True, None]:
            with self.subTest(value=value):
                path = self.write_table(json.dumps({"time": [0, 1], "response": value}), ".json")
                data = {"source": str(path), "mapping": {"y": "response"}}
                with self.assertRaisesRegex(ValueError, r"measurements.*response.*y.*list"):
                    resolve_series(data, "y")

    def test_scalar_numpy_columns_are_not_split_into_samples(self) -> None:
        path = self.root / "measurements.npz"
        for value in ["42", 42]:
            with self.subTest(value=value):
                np.savez(path, x=[0, 1], response=np.array(value))
                with self.assertRaisesRegex(ValueError, r"measurements.*response.*y.*list"):
                    resolve_series({"source": str(path), "mapping": {"y": "response"}}, "y")

    def test_json_and_numpy_list_columns_preserve_mapping_and_values(self) -> None:
        table = {"time": [0, 1], "response": [10.0, 20.0]}
        json_path = self.write_table(json.dumps(table), ".json")
        npz_path = self.root / "measurements.npz"
        np.savez(npz_path, **table)
        for path in [json_path, npz_path]:
            with self.subTest(path=path):
                data = {"source": path.name, "mapping": {"x": "time", "y": "response"}}
                self.assertEqual([0, 1], resolve_series(data, "x", base_dir=self.root))
                self.assertEqual([10.0, 20.0], resolve_series(data, "y", base_dir=self.root))


if __name__ == "__main__":
    unittest.main()
