from __future__ import annotations
import argparse, json
from pathlib import Path
from object_reconstruction import load_json, crop_preserved_assets, write_json

def main() -> int:
    parser = argparse.ArgumentParser(description="Crop preserved raster elements with exact manifest geometry.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = crop_preserved_assets(args.source, load_json(args.manifest), args.output_dir)
    write_json(args.report, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"pass", "not_applicable"} else 2

if __name__ == "__main__":
    raise SystemExit(main())
