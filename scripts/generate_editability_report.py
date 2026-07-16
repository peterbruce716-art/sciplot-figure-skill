from __future__ import annotations
import argparse, json
from pathlib import Path
from object_reconstruction import load_json, editability_report, write_json

def main() -> int:
    parser = argparse.ArgumentParser(description="Report which manifest objects remain editable.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--classification", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = editability_report(load_json(args.manifest), load_json(args.classification) if args.classification else None)
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] != "failed" else 2

if __name__ == "__main__":
    raise SystemExit(main())
