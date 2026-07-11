from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback a candidate VisualSpec to the last accepted spec.")
    parser.add_argument("--accepted", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    if not args.accepted.exists():
        raise SystemExit(f"accepted spec not found: {args.accepted}")
    args.candidate.parent.mkdir(parents=True, exist_ok=True)
    args.candidate.write_text(args.accepted.read_text(encoding="utf-8-sig"), encoding="utf-8")
    result = {
        "schema": "scientificfigure.rollback_report.v1",
        "status": "ok",
        "accepted": str(args.accepted),
        "candidate": str(args.candidate),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
