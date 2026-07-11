from __future__ import annotations

import argparse
import json
from pathlib import Path

from visualspec import apply_json_patch, load_json, validate_visualspec, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply JSON add/replace operations to a VisualSpec.")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--patch", required=True, type=Path, help="JSON list or object with operations.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    spec = load_json(args.spec)
    patch_doc = load_json(args.patch)
    operations = patch_doc.get("operations") if isinstance(patch_doc, dict) else patch_doc
    if not isinstance(operations, list):
        raise SystemExit("patch must be a list or contain an operations list")
    patched = apply_json_patch(spec, operations)
    errors = validate_visualspec(patched)
    result = {
        "schema": "scientificfigure.visual_patch_report.v1",
        "status": "ok" if not errors else "failed",
        "operation_count": len(operations),
        "errors": errors,
        "rollback_on_no_improvement": True,
    }
    if not errors:
        write_json(args.out, patched)
    if args.report:
        write_json(args.report, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
