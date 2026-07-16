from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from advisor_common import load_json, validate_payload, write_json


def apply_approved_patch(patch: dict, visualspec: dict) -> dict:
    if patch.get("status") != "approved" or not patch.get("approval", {}).get("approved_by_user"):
        raise ValueError("patch is advisory only; set status=approved and approval.approved_by_user=true after review")
    allowed = set(patch.get("approval", {}).get("approved_patch_ids", []))
    applied = []
    for item in patch.get("patches", []):
        if item["id"] not in allowed or not item.get("approved"):
            continue
        target = item["target"]
        if item["operation"] == "set":
            cursor = visualspec
            parts = target.split(".")
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[parts[-1]] = item.get("value")
            applied.append(item["id"])
        else:
            raise ValueError(f"unsupported approved patch operation: {item['operation']}")
    return {"visualspec": visualspec, "applied_patch_ids": applied, "requires_deterministic_rerun": bool(applied)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an AI review and optionally apply explicitly approved patches.")
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--visualspec", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rerun", nargs=argparse.REMAINDER, help="optional deterministic command, executed only after approved patch application")
    args = parser.parse_args()
    try:
        review = load_json(args.review)
        validate_payload(review, "ai-visual-review-v1.schema.json")
        result = {"review_valid": True, "review_status": review["status"], "applied_patch_ids": [], "requires_deterministic_rerun": False}
        if args.patch:
            if not args.visualspec:
                raise ValueError("--visualspec is required with --patch")
            patch = load_json(args.patch)
            validate_payload(patch, "visual-patch-v1.schema.json")
            result = apply_approved_patch(patch, load_json(args.visualspec))
            if result["applied_patch_ids"]:
                write_json(args.visualspec, result.pop("visualspec"))
                if args.rerun:
                    subprocess.run(args.rerun, check=True)
                    result["deterministic_rerun"] = "completed"
                else:
                    result["deterministic_rerun"] = "required"
        write_json(args.output, result)
    except Exception as exc:
        parser.exit(2, f"run_ai_visual_review: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
