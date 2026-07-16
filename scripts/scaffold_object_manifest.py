from __future__ import annotations
import argparse
from pathlib import Path
from object_reconstruction import scaffold_manifest, write_json

def main() -> int:
    parser = argparse.ArgumentParser(description="Create a reviewable Object Manifest scaffold from an image.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    write_json(args.output, scaffold_manifest(args.source))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
