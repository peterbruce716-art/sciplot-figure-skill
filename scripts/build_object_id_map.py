from __future__ import annotations
import argparse
from pathlib import Path
from object_reconstruction import load_json, build_object_masks

def main() -> int:
    parser = argparse.ArgumentParser(description="Build a color-coded object ID map.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--masks-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build_object_masks(load_json(args.manifest), args.masks_dir, id_map_path=args.output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
