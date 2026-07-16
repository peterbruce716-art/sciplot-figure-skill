from __future__ import annotations
import argparse, json
from pathlib import Path
from object_reconstruction import load_json, build_object_masks, write_json

def main() -> int:
    parser = argparse.ArgumentParser(description="Build one deterministic mask per manifest object.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--masks-dir", required=True, type=Path)
    parser.add_argument("--id-map", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build_object_masks(load_json(args.manifest), args.masks_dir, id_map_path=args.id_map)
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
