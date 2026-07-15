from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def validate_payload(payload: dict[str, Any], schema_name: str) -> None:
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - dependency preflight
        raise RuntimeError("jsonschema is required to validate advisor artifacts") from exc
    schema = load_json(SCHEMAS / schema_name)
    validator = jsonschema.Draft202012Validator(schema)
    failures = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if failures:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in item.absolute_path) or '<root>'}: {item.message}"
            for item in failures
        )
        raise ValueError(f"schema validation failed for {schema_name}: {detail}")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
