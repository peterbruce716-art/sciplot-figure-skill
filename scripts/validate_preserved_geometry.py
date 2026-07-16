from __future__ import annotations
import argparse, json
from pathlib import Path
from object_reconstruction import load_json, validate_preserved_geometry, write_json

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate preserved raster crop geometry, alpha, orientation, and hash.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--assets-dir", required=True, type=Path)
    parser.add_argument("--tolerance", type=float, default=0.02)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = validate_preserved_geometry(load_json(args.manifest), args.assets_dir, tolerance=args.tolerance)
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"pass", "not_applicable"} else 2

if __name__ == "__main__":
    raise SystemExit(main())
