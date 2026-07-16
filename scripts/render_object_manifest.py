from __future__ import annotations
import argparse, json
from pathlib import Path
from object_reconstruction import load_json, render_manifest, export_vector_manifest, geometry_audit, audit_connectors, write_json

def main() -> int:
    parser = argparse.ArgumentParser(description="Render Object Manifest geometry or final style stage.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--stage", choices=["geometry", "final"], required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--assets-dir", type=Path)
    parser.add_argument("--geometry-report", type=Path)
    parser.add_argument("--vector-output", type=Path)
    parser.add_argument("--qa-output", type=Path)
    args = parser.parse_args()
    manifest = load_json(args.manifest)
    connector = audit_connectors(manifest)
    audit = geometry_audit(manifest, connector)
    if args.qa_output:
        write_json(args.qa_output, audit)
    result = render_manifest(manifest, args.output, stage=args.stage, assets_dir=args.assets_dir, require_geometry_report=args.geometry_report)
    if args.vector_output and args.stage == "final":
        export_vector_manifest(manifest, args.vector_output, assets_dir=args.assets_dir)
    print(json.dumps({"geometry": audit, "render": result}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
