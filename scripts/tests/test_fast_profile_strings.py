from __future__ import annotations

from common import Path, tempfile, unittest
import pandas as pd

from profile_scientific_data import infer_type, profile_dataframe, read_table


class StringProfileTests(unittest.TestCase):
    def test_string_storage_preserves_semantic_types(self) -> None:
        cases = [
            (["control", "treated", None], "categorical", []),
            (["2026-01-01", "2026-01-02", None], "datetime", []),
            ([f"observation label {i}" for i in range(30)], "text", []),
            ([None, None], "unknown", ["all_values_missing"]),
            (["2026-01-01"] * 9 + ["not a date"], "datetime", ["datetime_parse_ambiguous"]),
        ]
        for dtype in ["object", "string", "category"]:
            for values, expected, notes in cases:
                with self.subTest(dtype=dtype, expected=expected, notes=notes):
                    self.assertEqual((expected, notes), infer_type(pd.Series(values, dtype=dtype)))

    def test_csv_dates_recommend_trend_and_group_labels_are_categorical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "data.csv"
            source.write_text(
                "date,group,response\n2026-01-01,control,1.2\n2026-01-02,treated,2.3\n",
                encoding="utf-8",
            )
            profile = profile_dataframe(read_table(source), source_path=source, x="date", y="response")
        inferred = {column["name"]: column["inferred_type"] for column in profile["columns"]}
        self.assertEqual("datetime", inferred["date"])
        self.assertEqual("categorical", inferred["group"])
        self.assertIn("trend_comparison", profile["recommended_tasks"])


if __name__ == "__main__":
    unittest.main()
