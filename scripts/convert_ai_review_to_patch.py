from __future__ import annotations

import argparse
import json
from pathlib import Path

from advisor_common import load_json, sha256_file, validate_payload, write_json


def convert(review: dict, visualspec: Path) -> dict:
    patches = []
    for index, issue in enumerate(review.get("issues", []), start=1):
        patches.append({
            "id": f"review-{index}",
            "target": str(issue.get("panel") or issue.get("category", "figure")),
            "operation": "set",
            "value": None,
            "reason": str(issue.get("recommended_change", issue.get("description", ""))),
            "approved": False,
            "review_issue": str(issue.get("category", "")),
        })
    payload = {
        "schema": "scientificfigure.visual_patch.v1",
        "schema_version": "1.0",
        "status": "draft",
        "base_visualspec_sha256": sha256_file(visualspec),
        "patches": patches,
        "approval": {"approved_by_user": False, "approval_note": "Explicit user approval is required before applying any patch.", "approved_patch_ids": []},
        "deterministic_rerun": None,
    }
    validate_payload(payload, "visual-patch-v1.schema.json")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert advisory review issues into an unapproved patch proposal.")
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--visualspec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        review = load_json(args.review)
        validate_payload(review, "ai-visual-review-v1.schema.json")
        payload = convert(review, args.visualspec)
        write_json(args.output, payload)
    except Exception as exc:
        parser.exit(2, f"convert_ai_review_to_patch: {exc}\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
