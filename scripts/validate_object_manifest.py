from __future__ import annotations
import argparse, json
from pathlib import Path
from object_reconstruction import load_json, validate_manifest

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an Object Manifest and semantic references.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = validate_manifest(load_json(args.manifest), schema_path=Path(__file__).resolve().parents[1] / "schemas" / "object-manifest-v1.schema.json", strict=args.strict)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2

if __name__ == "__main__":
    raise SystemExit(main())
