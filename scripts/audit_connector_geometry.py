from __future__ import annotations
import argparse, json
from pathlib import Path
from object_reconstruction import load_json, audit_connectors, write_json

def main() -> int:
    parser = argparse.ArgumentParser(description="Audit connector anchors and endpoint geometry.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--tolerance", type=float, default=12.0)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit_connectors(load_json(args.manifest), endpoint_tolerance_px=args.tolerance)
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"pass", "not_applicable"} else 2

if __name__ == "__main__":
    raise SystemExit(main())
