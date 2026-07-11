from __future__ import annotations

import argparse
import json
from pathlib import Path

from portable_paths import portable_path
from visualspec import load_json, validate_visualspec


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a scientificfigure.visualspec.v1/v2 file.")
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()

    spec = load_json(args.path)
    errors = validate_visualspec(spec)
    root = (args.project_root or args.path.parent).resolve()
    result = {
        "schema": "scientificfigure.visualspec_validation.v2",
        "path": portable_path(args.path, root),
        "status": "ok" if not errors else "failed",
        "errors": errors,
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
