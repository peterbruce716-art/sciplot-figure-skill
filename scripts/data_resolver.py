from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np


def _coerce_number(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _read_table(path: Path) -> dict[str, list[Any]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter, strict=True)
        try:
            header = next(reader, None)
            if not header:
                raise ValueError(f"{path}: missing table header")
            columns: dict[str, list[Any]] = {}
            for index, name in enumerate(header, start=1):
                if not name.strip():
                    raise ValueError(f"{path}: empty header at column {index}")
                if name in columns:
                    raise ValueError(f"{path}: duplicate header {name!r} at column {index}")
                columns[name] = []
            for row in reader:
                if not row:  # Ignore blank records, not explicitly empty cells.
                    continue
                if len(row) != len(header):
                    raise ValueError(
                        f"{path}: line {reader.line_num}: expected {len(header)} fields, got {len(row)}"
                    )
                for key, value in zip(header, row):
                    columns[key].append(_coerce_number(value))
        except csv.Error as exc:
            raise ValueError(f"{path}: line {reader.line_num}: {exc}") from exc
    return columns


def _read_json(path: Path) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)


def _read_numpy(path: Path) -> Any:
    loaded = np.load(path, allow_pickle=False)
    if isinstance(loaded, np.lib.npyio.NpzFile):
        return {key: loaded[key].tolist() for key in loaded.files}
    return loaded.tolist()


def load_data_source(source: str | Path, *, base_dir: Path | None = None) -> Any:
    path = Path(source)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        return _read_table(path)
    if suffix == ".json":
        return _read_json(path)
    if suffix in {".npy", ".npz"}:
        return _read_numpy(path)
    if suffix in {".xls", ".xlsx"}:
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - depends on optional env
            raise RuntimeError("Excel data sources require pandas in the active Python environment") from exc
        return pd.read_excel(path).to_dict(orient="list")
    raise ValueError(f"unsupported data source format: {path}")


def resolve_series(data: dict[str, Any], key: str, *, base_dir: Path | None = None) -> list[Any]:
    if "source" not in data:
        value = data.get(key, [])
        if isinstance(value, list):
            return value
        raise ValueError(f"inline data field must be a list: {key}")

    table = load_data_source(str(data["source"]), base_dir=base_dir)
    mapping = data.get("mapping") or {}
    column = mapping.get(key, key)
    if isinstance(table, dict) and column in table:
        value = table[column]
        if not isinstance(value, list):
            raise ValueError(f"{data['source']}: mapped column {column!r} for {key} must be a list")
        return value
    raise KeyError(f"data source does not contain mapped column for {key}: {column}")
