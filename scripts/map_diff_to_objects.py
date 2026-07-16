from __future__ import annotations
import argparse, json
from pathlib import Path
from object_reconstruction import map_diff_to_objects, write_json

def main() -> int:
    parser = argparse.ArgumentParser(description="Map fixed-canvas visual diff regions to manifest object IDs.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--masks-dir", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=24.0)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = map_diff_to_objects(args.source, args.actual, args.masks_dir, threshold=args.threshold)
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
