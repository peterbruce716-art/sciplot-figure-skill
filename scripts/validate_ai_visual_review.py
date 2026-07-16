from __future__ import annotations

import argparse
import json
from pathlib import Path

from advisor_common import load_json, validate_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an advisory AI visual-review response without calling a model.")
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = load_json(args.input)
        validate_payload(payload, "ai-visual-review-v1.schema.json")
    except Exception as exc:
        parser.exit(2, f"validate_ai_visual_review: {exc}\n")
    print(json.dumps({"status": "valid", "schema": payload["schema"], "issues": len(payload["issues"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
