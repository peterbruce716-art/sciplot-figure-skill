from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from object_reconstruction import (
    audit_connectors,
    build_object_masks,
    classify_elements,
    create_bundle,
    crop_preserved_assets,
    editability_report,
    export_vector_manifest,
    geometry_audit,
    load_json,
    map_diff_to_objects,
    render_manifest,
    score_object_regions,
    sha256_file,
    validate_manifest,
    validate_preserved_geometry,
    write_json,
)


def _apply_classification(manifest: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(manifest)
    decisions = {str(item["id"]): item for item in classification.get("elements", [])}
    for element in result.get("elements", []):
        decision = decisions.get(str(element.get("id")))
        if decision and not element.get("classification_override"):
            element["bucket"] = decision["bucket"]
        if element.get("bucket") == "preserved_raster":
            element.setdefault("asset_path", f"assets/{element.get('id')}.png")
    return result


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = load_json(args.manifest)
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "object-manifest-v1.schema.json"
    initial_validation = validate_manifest(manifest, schema_path=schema_path, strict=args.strict)
    report: dict[str, Any] = {"schema": "scientificfigure.object_reconstruction_run.v1", "status": "failed", "steps": {"manifest_validation": initial_validation}}
    if initial_validation["status"] != "pass":
        write_json(output / "run_report.json", report)
        if args.strict or not args.dry_run:
            raise ValueError("object manifest validation failed")
        return report

    policy_path = args.policy.resolve()
    classification = classify_elements(manifest, load_json(policy_path))
    write_json(output / "object_manifest" / "reconstruction_classification.json", classification)
    render_manifest_payload = _apply_classification(manifest, classification)
    write_json(output / "object_manifest" / "object_manifest.json", render_manifest_payload)
    report["steps"]["classification"] = classification
    editability = editability_report(render_manifest_payload, classification)
    write_json(output / "qa" / "editability_report.json", editability)
    report["steps"]["editability"] = editability
    if args.manifest_only:
        report["status"] = "manifest_only"
        write_json(output / "run_report.json", report)
        return report

    assets_dir = output / "assets"
    crops = crop_preserved_assets(args.source.resolve(), render_manifest_payload, assets_dir)
    write_json(output / "qa" / "preserved_asset_report.json", crops)
    geometry_assets = validate_preserved_geometry(render_manifest_payload, assets_dir, tolerance=args.aspect_ratio_tolerance)
    write_json(output / "qa" / "preserved_geometry_report.json", geometry_assets)
    report["steps"]["preserved_geometry"] = geometry_assets
    connector = audit_connectors(render_manifest_payload, endpoint_tolerance_px=args.endpoint_tolerance_px)
    write_json(output / "qa" / "connector_audit.json", connector)
    geometry = geometry_audit(render_manifest_payload, connector)
    write_json(output / "qa" / "geometry_audit.json", geometry)
    report["steps"]["connector"] = connector
    report["steps"]["geometry"] = geometry
    render_manifest(render_manifest_payload, output / "outputs" / "geometry_skeleton.png", stage="geometry", assets_dir=assets_dir)
    if args.dry_run:
        report["status"] = "dry_run"
        write_json(output / "run_report.json", report)
        return report
    if geometry.get("geometry_status") != "pass":
        report["status"] = "geometry_failed_final_blocked"
        write_json(output / "run_report.json", report)
        raise ValueError("geometry audit failed; final stage is blocked")
    if geometry_assets.get("status") not in {"pass", "not_applicable"}:
        report["status"] = "preserved_geometry_failed_final_blocked"
        write_json(output / "run_report.json", report)
        raise ValueError("preserved raster geometry audit failed; final stage is blocked")

    render_manifest(render_manifest_payload, output / "outputs" / "final.png", stage="final", assets_dir=assets_dir, require_geometry_report=output / "qa" / "geometry_audit.json")
    export_vector_manifest(render_manifest_payload, output / "outputs" / "final.svg", assets_dir=assets_dir)
    export_vector_manifest(render_manifest_payload, output / "outputs" / "final.pdf", assets_dir=assets_dir)
    masks = build_object_masks(render_manifest_payload, output / "qa" / "object_masks", id_map_path=output / "qa" / "object_id_map.png")
    write_json(output / "qa" / "object_masks.json", masks)
    object_qa = score_object_regions(args.source.resolve(), output / "outputs" / "final.png", render_manifest_payload, output / "qa" / "object_masks", connector_report=connector)
    write_json(output / "qa" / "object_qa_report.json", object_qa)
    diff_map = map_diff_to_objects(args.source.resolve(), output / "outputs" / "final.png", output / "qa" / "object_masks")
    write_json(output / "qa" / "object_diff_map.json", diff_map)
    report["steps"]["object_qa"] = object_qa
    if args.export_office:
        from export_office_shapes import export
        office = export(render_manifest_payload, output / "editable", backend=args.office_backend, create_pptx=args.create_pptx)
        write_json(output / "qa" / "office_export_report.json", office)
        report["steps"]["office"] = office
    if args.create_bundle:
        bundle = create_bundle(args.source.resolve(), output / "object_manifest" / "object_manifest.json", output, output / "bundle")
        report["steps"]["bundle"] = bundle
    report["status"] = "pass_with_warnings" if object_qa.get("status") != "pass" else "pass"
    report["output_hashes"] = {str(path.relative_to(output)).replace("\\", "/"): sha256_file(path) for path in output.glob("outputs/*") if path.is_file()}
    write_json(output / "run_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Object Manifest classification, geometry, final render, object QA, optional Office export, and bundle creation.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--policy", type=Path, default=Path(__file__).resolve().parents[1] / "policies" / "hybrid-reconstruction-policy-v1.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--run-geometry-stage", action="store_true")
    parser.add_argument("--run-final-stage", action="store_true")
    parser.add_argument("--run-object-qa", action="store_true")
    parser.add_argument("--export-office", action="store_true")
    parser.add_argument("--create-pptx", action="store_true")
    parser.add_argument("--office-backend", default="powerpoint_vba")
    parser.add_argument("--skip-office", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--min-improvement", type=float, default=0.01)
    parser.add_argument("--create-bundle", action="store_true")
    parser.add_argument("--aspect-ratio-tolerance", type=float, default=0.02)
    parser.add_argument("--endpoint-tolerance-px", type=float, default=12.0)
    args = parser.parse_args()
    if args.skip_office:
        args.export_office = False
    try:
        result = run(args)
    except Exception as exc:
        print(json.dumps({"schema": "scientificfigure.object_reconstruction_run.v1", "status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"pass", "pass_with_warnings", "dry_run", "manifest_only"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
