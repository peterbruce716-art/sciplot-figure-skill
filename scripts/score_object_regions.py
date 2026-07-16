from __future__ import annotations
import argparse, json
from pathlib import Path
from object_reconstruction import load_json, load_json as _load, score_object_regions, write_json

def main() -> int:
    parser = argparse.ArgumentParser(description="Score fixed-canvas local object regions without resizing.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--masks-dir", required=True, type=Path)
    parser.add_argument("--connector-report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = score_object_regions(args.source, args.actual, load_json(args.manifest), args.masks_dir, connector_report=load_json(args.connector_report) if args.connector_report else None)
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
