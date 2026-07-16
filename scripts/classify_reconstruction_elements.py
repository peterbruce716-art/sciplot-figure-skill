from __future__ import annotations
import argparse, json
from pathlib import Path
from object_reconstruction import load_json, classify_elements, write_json

def main() -> int:
    parser = argparse.ArgumentParser(description="Classify manifest objects as editable vector, preserved raster, or background.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--policy", type=Path, default=Path(__file__).resolve().parents[1] / "policies" / "hybrid-reconstruction-policy-v1.json")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = classify_elements(load_json(args.manifest), load_json(args.policy))
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
