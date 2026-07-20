from __future__ import annotations

"""Run a declared data-swap renderer in an isolated output directory."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from validate_data_swap_template import validate_template
from visualspec import _json_schema_errors


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def run_data_swap(*, root: Path, template_path: Path, figure_id: str, data_path: Path, out_dir: Path, input_mode: str) -> dict[str, Any]:
    validation = validate_template(template_path, root=root)
    if validation["status"] != "pass":
        raise ValueError("template validation failed: " + json.dumps(validation["failures"], ensure_ascii=False))
    template = _load(template_path)
    figures = template["figures"]
    if figure_id not in figures:
        raise ValueError(f"figure is not declared by template: {figure_id}")
    record = figures[figure_id]
    renderer = (root / record["renderer"]).resolve()
    data_schema = (root / record["data_schema"]).resolve()
    data_path = data_path.resolve()
    out_dir = out_dir.resolve()
    if not data_path.is_file():
        raise FileNotFoundError(data_path)
    data_errors = _json_schema_errors(_load(data_path), data_schema)
    if data_errors:
        raise ValueError("replacement data schema validation failed: " + "; ".join(data_errors))
    if data_path == out_dir or data_path in out_dir.parents:
        raise ValueError("output directory must be outside the data file parent")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError(f"output directory must be new or empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(renderer), "--figure", figure_id, "--data", str(data_path), "--out-dir", str(out_dir), "--input-mode", input_mode]
    completed = subprocess.run(command, cwd=root, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"renderer failed with exit code {completed.returncode}")
    manifest_path = out_dir / "data_swap_manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("renderer did not emit data_swap_manifest.json")
    manifest = _load(manifest_path)
    if manifest.get("schema") != "scientificfigure.data-swap-run.v1":
        raise ValueError("renderer manifest has wrong schema")
    if manifest.get("input_mode") != input_mode:
        raise ValueError("renderer manifest input_mode mismatch")
    if manifest.get("historical_data_consumed") is not False:
        raise ValueError("renderer manifest must set historical_data_consumed=false")
    return {"status": "pass", "command": command, "manifest": str(manifest_path), "figure": figure_id}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--input-mode", choices=("user_supplied", "fresh_digitization"), default="user_supplied")
    args = parser.parse_args()
    try:
        result = run_data_swap(root=args.root.resolve(), template_path=args.template.resolve(), figure_id=args.figure, data_path=args.data, out_dir=args.out_dir, input_mode=args.input_mode)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
