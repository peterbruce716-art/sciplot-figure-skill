from __future__ import annotations

"""Validate the reusable data-swap contract for any figure template."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from visualspec import _json_schema_errors, schema_path


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_relative(root: Path, raw: Any, *, field: str, failures: list[dict[str, str]]) -> Path | None:
    if not isinstance(raw, str) or not raw:
        failures.append({"check": field, "message": "relative path required"})
        return None
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        failures.append({"check": field, "path": raw, "message": "absolute or parent path is forbidden"})
        return None
    candidate = root / path
    if not candidate.is_file():
        failures.append({"check": field, "path": raw, "message": "file does not exist"})
        return None
    return candidate


def validate_template(template_path: Path, *, root: Path | None = None) -> dict[str, Any]:
    root = (root or template_path.parent).resolve()
    failures: list[dict[str, str]] = []
    try:
        template = _load(template_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"schema": "scientificfigure.data-swap-template-validation.v1", "status": "failed", "failures": [{"check": "template_json", "message": str(exc)}]}

    failures.extend({"check": "schema", "message": error} for error in _json_schema_errors(template, schema_path("data-swap-template-v1.schema.json")))
    if template.get("historical_data_consumed") is not False:
        failures.append({"check": "historical_data_consumed", "message": "must be false"})
    entrypoint = _safe_relative(root, template.get("renderer_entrypoint"), field="renderer_entrypoint", failures=failures)
    if entrypoint is not None and entrypoint.suffix.lower() != ".py":
        failures.append({"check": "renderer_entrypoint", "message": "renderer entrypoint must be a Python file"})

    figures = template.get("figures")
    if not isinstance(figures, dict) or not figures:
        failures.append({"check": "figures", "message": "non-empty figures object required"})
        figures = {}
    checked: dict[str, Any] = {}
    for figure_id, record in figures.items():
        if not isinstance(record, dict):
            failures.append({"check": "figure_record", "figure": str(figure_id), "message": "object required"})
            continue
        data_schema = _safe_relative(root, record.get("data_schema"), field=f"{figure_id}.data_schema", failures=failures)
        example_data = _safe_relative(root, record.get("example_data"), field=f"{figure_id}.example_data", failures=failures)
        renderer = _safe_relative(root, record.get("renderer"), field=f"{figure_id}.renderer", failures=failures)
        outputs = record.get("outputs")
        if not isinstance(outputs, list) or not outputs or any(value not in {"png", "svg", "pdf"} for value in outputs):
            failures.append({"check": "outputs", "figure": str(figure_id), "message": "outputs must contain png, svg, and/or pdf"})
        if renderer is not None and renderer.suffix.lower() != ".py":
            failures.append({"check": "renderer", "figure": str(figure_id), "message": "renderer must be a Python file"})
        observed_hash = _sha256(example_data) if example_data is not None else None
        schema_hash = _sha256(data_schema) if data_schema is not None else None
        if data_schema is not None and example_data is not None:
            try:
                example_payload = _load(example_data)
                failures.extend(
                    {"check": "example_data_schema", "figure": str(figure_id), "message": error}
                    for error in _json_schema_errors(example_payload, data_schema)
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                failures.append({"check": "example_data_json", "figure": str(figure_id), "message": str(exc)})
        declared_hash = record.get("data_sha256")
        if declared_hash is not None and declared_hash != observed_hash:
            failures.append({"check": "data_sha256", "figure": str(figure_id), "message": "example data hash mismatch"})
        checked[str(figure_id)] = {"data_schema": str(record.get("data_schema", "")), "data_schema_sha256": schema_hash, "example_data": str(record.get("example_data", "")), "renderer": str(record.get("renderer", "")), "example_data_sha256": observed_hash}

    return {
        "schema": "scientificfigure.data-swap-template-validation.v1",
        "status": "pass" if not failures else "failed",
        "template": str(template_path),
        "template_id": template.get("template_id"),
        "template_version": template.get("template_version"),
        "figures": checked,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = validate_template(args.template, root=args.root)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
