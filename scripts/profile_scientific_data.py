from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from advisor_common import sha256_file, validate_payload, write_json


ID_NAME = re.compile(r"(^id$|_id$|^id_|identifier|uuid|编号$|序号$)", re.IGNORECASE)


def read_table(path: Path, *, sheet: str | int | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"input data file does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path)
    elif suffix in {".tsv", ".txt"}:
        frame = pd.read_csv(path, sep="\t")
    elif suffix in {".xlsx", ".xlsm", ".xls"}:
        try:
            frame = pd.read_excel(path, sheet_name=sheet if sheet is not None else 0)
        except ImportError as exc:
            raise RuntimeError("Excel input requires openpyxl or a compatible pandas engine") from exc
    else:
        raise ValueError(f"unsupported input format: {suffix}; use CSV, TSV, XLSX, XLSM, or XLS")
    if not isinstance(frame, pd.DataFrame):
        raise ValueError("sheet selection produced multiple tables; select exactly one sheet")
    if len(frame.columns) == 0:
        raise ValueError("input table has no columns")
    return frame


def infer_type(series: pd.Series) -> tuple[str, list[str]]:
    non_null = series.dropna()
    notes: list[str] = []
    if non_null.empty:
        return "unknown", ["all_values_missing"]
    if pd.api.types.is_bool_dtype(series.dtype):
        return "boolean", notes
    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        return "datetime", notes
    if pd.api.types.is_numeric_dtype(series.dtype):
        unique = int(non_null.nunique(dropna=True))
        if pd.api.types.is_integer_dtype(series.dtype) and unique <= max(12, int(math.sqrt(len(non_null))) + 1):
            notes.append("numeric_low_cardinality")
            return "ordinal", notes
        return "continuous", notes
    if pd.api.types.is_object_dtype(series.dtype) or isinstance(series.dtype, pd.CategoricalDtype):
        parsed = pd.to_datetime(non_null.astype(str), errors="coerce", format="mixed")
        parse_ratio = float(parsed.notna().mean())
        if parse_ratio >= 0.9:
            if parse_ratio < 1:
                notes.append("datetime_parse_ambiguous")
            return "datetime", notes
        unique = int(non_null.nunique(dropna=True))
        threshold = max(20, int(len(non_null) * 0.2))
        if unique <= threshold:
            return "categorical", notes
        return "text", notes
    return "unknown", notes


def _number(value: Any) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    value = value.item() if hasattr(value, "item") else value
    return int(value) if isinstance(value, (int, np.integer)) else float(value)


def profile_dataframe(
    frame: pd.DataFrame,
    *,
    source_path: Path,
    sheet: str | int | None = None,
    groups: list[str] | None = None,
    x: str | None = None,
    y: str | None = None,
) -> dict[str, Any]:
    groups = groups or []
    missing_columns = [name for name in [*groups, x, y] if name and name not in frame.columns]
    if missing_columns:
        raise ValueError(f"requested columns are missing: {', '.join(sorted(set(missing_columns)))}")
    warnings: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    skewness: dict[str, float | None] = {}
    outliers: dict[str, int] = {}
    inferred_by_name: dict[str, str] = {}

    for name in frame.columns:
        series = frame[name]
        inferred, notes = infer_type(series)
        inferred_by_name[str(name)] = inferred
        non_null = series.dropna()
        unique = int(non_null.nunique(dropna=True))
        suspected_id = bool(
            len(non_null) > 1
            and unique == len(non_null)
            and (ID_NAME.search(str(name)) or inferred in {"text", "ordinal"})
        )
        record: dict[str, Any] = {
            "name": str(name),
            "inferred_type": inferred,
            "missing_count": int(series.isna().sum()),
            "unique_count": unique,
            "suspected_id": suspected_id,
        }
        if pd.api.types.is_numeric_dtype(series.dtype) and not non_null.empty:
            numeric = pd.to_numeric(non_null, errors="coerce").dropna()
            q1 = numeric.quantile(0.25)
            q3 = numeric.quantile(0.75)
            iqr = q3 - q1
            outlier_count = int(((numeric < q1 - 1.5 * iqr) | (numeric > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
            skew = _number(numeric.skew())
            record.update(
                {
                    "min": _number(numeric.min()),
                    "max": _number(numeric.max()),
                    "mean": _number(numeric.mean()),
                    "median": _number(numeric.median()),
                    "std": _number(numeric.std(ddof=1)) if len(numeric) > 1 else None,
                    "q1": _number(q1),
                    "q3": _number(q3),
                    "outlier_count_iqr": outlier_count,
                }
            )
            skewness[str(name)] = skew
            outliers[str(name)] = outlier_count
        if suspected_id:
            warnings.append({"code": "suspected_id_column", "severity": "info", "message": f"Column '{name}' appears identifier-like and should not be treated as a measure.", "columns": [str(name)]})
        for note in notes:
            warnings.append({"code": note, "severity": "warning", "message": f"Type inference for '{name}' is ambiguous; review before plotting.", "columns": [str(name)]})
        if inferred == "categorical" and unique > 12:
            warnings.append({"code": "high_category_count", "severity": "warning", "message": f"Column '{name}' has {unique} categories; a single legend or axis may be crowded.", "columns": [str(name)]})
        columns.append(record)

    group_statistics: list[dict[str, Any]] = []
    if groups:
        grouped = frame.groupby(groups, dropna=False, sort=True).size().reset_index(name="sample_count")
        for row in grouped.to_dict(orient="records"):
            group_statistics.append({str(key): (_number(value) if isinstance(value, (np.number,)) else value) for key, value in row.items()})
        min_group = int(grouped["sample_count"].min()) if len(grouped) else 0
        if min_group < 10:
            warnings.append({"code": "small_group_sample", "severity": "warning", "message": f"At least one group has n={min_group}; show individual observations rather than means alone.", "columns": groups})

    if x and inferred_by_name.get(x) == "ordinal" and pd.api.types.is_numeric_dtype(frame[x].dtype):
        warnings.append({"code": "continuous_axis_discretized", "severity": "warning", "message": f"Numeric x column '{x}' has low cardinality; confirm whether it is continuous or an ordered factor.", "columns": [x]})
    if len(frame) == 0:
        warnings.append({"code": "empty_table", "severity": "error", "message": "The input table has no data rows.", "columns": []})
    elif len(frame) == 1:
        warnings.append({"code": "single_row", "severity": "warning", "message": "A single row cannot support distribution or uncertainty summaries.", "columns": []})

    recommended_tasks: list[str] = []
    if x and y:
        recommended_tasks.append("trend_comparison" if inferred_by_name.get(x) in {"continuous", "datetime", "ordinal"} else "group_comparison")
    if groups and y:
        recommended_tasks.append("group_comparison")
    if y and inferred_by_name.get(y) == "continuous":
        recommended_tasks.append("distribution_comparison")

    payload = {
        "schema": "scientificfigure.data_profile.v1",
        "schema_version": "1.0",
        "source": {"path": source_path.name, "sha256": sha256_file(source_path), "sheet": sheet},
        "row_count": int(len(frame)),
        "columns": columns,
        "group_statistics": group_statistics,
        "distribution": {"skewness": skewness, "outliers": outliers},
        "warnings": warnings,
        "recommended_tasks": sorted(set(recommended_tasks)),
    }
    validate_payload(payload, "data-profile-v1.schema.json")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministically profile scientific tabular data without modifying it.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sheet")
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--x")
    parser.add_argument("--y")
    args = parser.parse_args()
    try:
        frame = read_table(args.input, sheet=args.sheet)
        payload = profile_dataframe(frame, source_path=args.input, sheet=args.sheet, groups=args.group, x=args.x, y=args.y)
        write_json(args.output, payload)
    except Exception as exc:
        parser.exit(2, f"profile_scientific_data: {exc}\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
