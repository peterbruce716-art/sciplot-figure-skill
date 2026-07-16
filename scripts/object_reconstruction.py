from __future__ import annotations

import hashlib
import json
import math
import shutil
from collections import deque
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont


SCHEMA = "scientificfigure.object_manifest.v1"
BUCKETS = {"editable_vector", "preserved_raster", "background"}
PROVENANCE = {"observed", "inferred", "user_confirmed", "generated"}
SIDES = {"left", "right", "top", "bottom", "center", "custom"}
PRIMITIVES = {
    "rectangle", "rounded_rectangle", "ellipse", "circle", "line", "polyline",
    "polygon", "arrow", "connector", "textbox", "image", "group", "path", "unknown",
}
SEMANTIC_ROLES = {
    "panel_label", "title", "subtitle", "axis", "axis_label", "tick_label", "legend",
    "process_box", "material_region", "micrograph", "simulation_result", "annotation_text",
    "connector", "arrow", "dimension_line", "boundary", "sample", "equipment", "grain",
    "particle", "phase", "flow_direction", "callout", "background", "decorative", "unknown",
}


def load_json(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def write_json(path: Path | str, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def canvas_size(manifest: dict[str, Any]) -> tuple[int, int]:
    source = manifest.get("source", {})
    width = int(source.get("width_px", 0))
    height = int(source.get("height_px", 0))
    if width <= 0 or height <= 0:
        raise ValueError("source width_px and height_px must be positive")
    return width, height


def element_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in manifest.get("elements", []) if isinstance(item, dict) and item.get("id")}


def _bbox(element: dict[str, Any]) -> tuple[float, float, float, float] | None:
    value = element.get("bbox_px")
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return tuple(float(part) for part in value)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def _issue(code: str, message: str, *, element_id: str | None = None, severity: str = "error") -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code, "severity": severity, "message": message}
    if element_id is not None:
        issue["element_id"] = element_id
    return issue


def validate_manifest(manifest: dict[str, Any], *, schema_path: Path | None = None, strict: bool = False) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if schema_path is not None:
        try:
            import jsonschema

            schema = load_json(schema_path)
            validator = jsonschema.Draft202012Validator(schema)
            for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.absolute_path)):
                location = "/".join(str(part) for part in error.absolute_path)
                issues.append(_issue("schema_error", f"{location or '<root>'}: {error.message}"))
        except ImportError:
            issues.append(_issue("jsonschema_unavailable", "jsonschema is required for schema validation"))

    if manifest.get("schema") != SCHEMA:
        issues.append(_issue("schema_id", f"schema must be {SCHEMA}"))
    try:
        width, height = canvas_size(manifest)
    except ValueError as exc:
        issues.append(_issue("canvas", str(exc)))
        width, height = 0, 0
    elements = manifest.get("elements")
    if not isinstance(elements, list) or not elements:
        issues.append(_issue("elements_empty", "elements must contain at least one visible object"))
        elements = []
    ids: set[str] = set()
    z_values: dict[int, str] = {}
    for item in elements:
        if not isinstance(item, dict):
            issues.append(_issue("element_type", "each element must be an object"))
            continue
        element_id = str(item.get("id", ""))
        if not element_id:
            issues.append(_issue("missing_id", "element id is required"))
        elif element_id in ids:
            issues.append(_issue("duplicate_id", f"duplicate element id {element_id}", element_id=element_id))
        ids.add(element_id)
        if item.get("bucket") not in BUCKETS:
            issues.append(_issue("bucket", "bucket must be editable_vector, preserved_raster, or background", element_id=element_id))
        if item.get("primitive") not in PRIMITIVES:
            issues.append(_issue("primitive", f"unsupported primitive {item.get('primitive')!r}", element_id=element_id))
        if item.get("semantic_role") not in SEMANTIC_ROLES:
            issues.append(_issue("semantic_role", f"unsupported semantic_role {item.get('semantic_role')!r}", element_id=element_id))
        if item.get("provenance") not in PROVENANCE:
            issues.append(_issue("provenance", "invalid provenance", element_id=element_id))
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            issues.append(_issue("confidence", "confidence must be between 0 and 1", element_id=element_id))
        box = _bbox(item)
        if box is None:
            issues.append(_issue("bbox", "bbox_px must contain x, y, width, height", element_id=element_id))
        else:
            x, y, w, h = box
            if w <= 0 or h <= 0:
                issues.append(_issue("bbox_size", "bbox width and height must be positive", element_id=element_id))
            if width and height and (x < 0 or y < 0 or x + w > width or y + h > height):
                issues.append(_issue("bbox_out_of_bounds", "bbox_px extends outside the source canvas", element_id=element_id))
            norm = item.get("bbox_norm")
            if isinstance(norm, list) and len(norm) == 4 and width and height:
                expected = [x / width, y / height, w / width, h / height]
                if any(abs(float(actual) - exp) > 1e-4 for actual, exp in zip(norm, expected)):
                    issues.append(_issue("bbox_norm_mismatch", "bbox_norm does not match bbox_px", element_id=element_id))
        z_order = item.get("z_order")
        if not isinstance(z_order, int):
            issues.append(_issue("z_order", "z_order must be an integer", element_id=element_id))
        elif z_order in z_values:
            issues.append(_issue("z_order_tie", f"z_order {z_order} is shared with {z_values[z_order]}", element_id=element_id, severity="warning"))
        else:
            z_values[z_order] = element_id
        if item.get("bucket") == "preserved_raster":
            if not item.get("preserve_reason"):
                issues.append(_issue("preserve_reason", "preserved raster requires preserve_reason", element_id=element_id))
            if not item.get("asset_path"):
                issues.append(_issue("asset_path", "preserved raster requires asset_path", element_id=element_id))

    for item in elements:
        if not isinstance(item, dict) or item.get("primitive") not in {"connector", "arrow", "line", "polyline"}:
            continue
        element_id = str(item.get("id", ""))
        for field in ("source_anchor", "target_anchor"):
            anchor = item.get(field)
            if not isinstance(anchor, dict):
                if item.get("primitive") == "connector":
                    issues.append(_issue("anchor_missing", f"{field} is required for connectors", element_id=element_id))
                continue
            target = anchor.get("element_id")
            if target is not None and target not in ids:
                issues.append(_issue("anchor_reference", f"{field} references missing element {target}", element_id=element_id))
            if anchor.get("side") not in SIDES:
                issues.append(_issue("anchor_side", f"invalid {field} side", element_id=element_id))

    completeness = manifest.get("manifest_completeness_status")
    if completeness == "incomplete":
        issues.append(_issue("manifest_incomplete", "final rendering is blocked while manifest is incomplete"))
    elif completeness == "complete_with_warnings":
        issues.append(_issue("manifest_warnings", "manifest is marked complete_with_warnings", severity="warning"))
    if strict:
        for item in elements:
            if isinstance(item, dict) and item.get("primitive") == "unknown":
                issues.append(_issue("unknown_primitive_strict", "unknown primitive is blocked in strict mode", element_id=str(item.get("id", ""))))

    errors = [item for item in issues if item["severity"] == "error"]
    return {
        "schema": "scientificfigure.object_manifest_validation.v1",
        "status": "pass" if not errors else "failed",
        "element_count": len(elements),
        "error_count": len(errors),
        "warning_count": len(issues) - len(errors),
        "issues": issues,
    }


def scaffold_manifest(source: Path, *, source_path: str | None = None) -> dict[str, Any]:
    with Image.open(source) as image:
        width, height = image.size
    return {
        "schema": SCHEMA,
        "schema_version": "1.0",
        "source": {
            "path": source_path or source.name,
            "width_px": width,
            "height_px": height,
            "sha256": sha256_file(source),
        },
        "canvas": {"coordinate_space": "source_pixel", "origin": "top_left"},
        "manifest_completeness_status": "incomplete",
        "elements": [],
    }


def classify_elements(manifest: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    weights = policy.get("weights", {})
    threshold = float(policy.get("preserved_raster_threshold", 0.62))
    hard_roles = set(policy.get("hard_preserve_roles", ["micrograph", "simulation_result"]))
    decisions: list[dict[str, Any]] = []
    for element in manifest.get("elements", []):
        features = element.get("classification_features", {}) if isinstance(element, dict) else {}
        override = element.get("classification_override") if isinstance(element, dict) else None
        role = element.get("semantic_role")
        primitive = element.get("primitive")
        if override in BUCKETS:
            bucket = override
            reason = "user_override"
            score = None
        elif role == "background" or primitive == "group" and element.get("bucket") == "background":
            bucket, reason, score = "background", "background_semantics", 0.0
        else:
            primitive_count = min(float(features.get("estimated_primitive_count", 1)) / float(policy.get("primitive_count_scale", 40)), 1.0)
            values = {
                "primitive_count": primitive_count,
                "texture_entropy": float(features.get("texture_entropy", 0.0)),
                "color_complexity": float(features.get("color_complexity", 0.0)),
                "ocr_density": float(features.get("ocr_density", 0.0)),
                "irregularity": float(features.get("irregularity", 0.0)),
                "edit_value": 1.0 - float(features.get("edit_value", 0.8)),
                "reconstruction_cost": float(features.get("reconstruction_cost", 0.0)),
            }
            score = sum(float(weights.get(key, 0.0)) * value for key, value in values.items())
            if role in hard_roles:
                bucket, reason = "preserved_raster", f"hard_role:{role}"
            elif primitive in {"textbox", "arrow", "connector", "line", "rectangle", "rounded_rectangle", "ellipse", "circle", "polygon"} and score < threshold:
                bucket, reason = "editable_vector", "editable_primitive"
            elif score >= threshold:
                bucket, reason = "preserved_raster", "weighted_complexity"
            else:
                bucket, reason = "editable_vector", "weighted_editability"
        decisions.append({
            "id": element.get("id"),
            "bucket": bucket,
            "classification_score": None if score is None else round(float(score), 6),
            "reason": reason,
            "previous_bucket": element.get("bucket"),
        })
    return {
        "schema": "scientificfigure.reconstruction_classification.v1",
        "policy_version": str(policy.get("version", "1.0")),
        "threshold": threshold,
        "elements": decisions,
    }


def editability_report(manifest: dict[str, Any], classification: dict[str, Any] | None = None) -> dict[str, Any]:
    decisions = {item["id"]: item for item in (classification or {}).get("elements", [])}
    counts = {bucket: 0 for bucket in BUCKETS}
    preserved: list[dict[str, Any]] = []
    structural_not_editable: list[str] = []
    width, height = canvas_size(manifest)
    whole_canvas_rasters: list[str] = []
    for element in manifest.get("elements", []):
        element_id = str(element.get("id"))
        bucket = decisions.get(element_id, {}).get("bucket", element.get("bucket"))
        if bucket in counts:
            counts[bucket] += 1
        if bucket == "preserved_raster":
            preserved.append({"id": element_id, "reason": element.get("preserve_reason") or decisions.get(element_id, {}).get("reason")})
            box = _bbox(element)
            if box and box[2] * box[3] >= width * height * 0.95:
                whole_canvas_rasters.append(element_id)
        if element.get("semantic_role") in {"title", "subtitle", "annotation_text", "arrow", "connector", "process_box"} and bucket != "editable_vector":
            structural_not_editable.append(element_id)
    total = sum(counts.values())
    editable_ratio = counts["editable_vector"] / total if total else 0.0
    blockers = []
    if total == 1 and whole_canvas_rasters:
        blockers.append("whole_source_as_single_raster")
    if structural_not_editable:
        blockers.append("structural_elements_not_editable")
    status = "failed" if blockers else ("pass_with_warnings" if preserved else "pass")
    return {
        "schema": "scientificfigure.editability_report.v1",
        "total_elements": total,
        "editable_vector_count": counts["editable_vector"],
        "preserved_raster_count": counts["preserved_raster"],
        "background_count": counts["background"],
        "editable_ratio": round(editable_ratio, 6),
        "preserved_elements": preserved,
        "structural_not_editable": structural_not_editable,
        "whole_canvas_rasters": whole_canvas_rasters,
        "blockers": blockers,
        "status": status,
    }


def crop_preserved_assets(source: Path, manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    with Image.open(source) as image:
        for element in manifest.get("elements", []):
            if element.get("bucket") != "preserved_raster":
                continue
            element_id = str(element.get("id"))
            box = _bbox(element)
            if box is None or any(abs(value - round(value)) > 1e-9 for value in box):
                records.append({"element_id": element_id, "status": "failed", "reason": "bbox_must_use_integer_pixels"})
                continue
            x, y, w, h = (int(value) for value in box)
            if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > image.width or y + h > image.height:
                records.append({"element_id": element_id, "status": "failed", "reason": "invalid_crop_bbox"})
                continue
            relative = Path(str(element.get("asset_path", f"assets/{element_id}.png")))
            target = output_dir / relative.name
            crop = image.crop((x, y, x + w, y + h))
            if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                crop = crop.convert("RGBA")
            crop.save(target, format="PNG")
            records.append({
                "element_id": element_id,
                "asset_path": target.name,
                "source_bbox_px": [x, y, w, h],
                "crop_size_px": [crop.width, crop.height],
                "alpha_preserved": crop.mode in {"RGBA", "LA"},
                "asset_sha256": sha256_file(target),
                "status": "pass",
            })
    status = "pass" if records and all(item["status"] == "pass" for item in records) else ("not_applicable" if not records else "failed")
    return {"schema": "scientificfigure.preserved_asset_report.v1", "status": status, "assets": records}


def validate_preserved_geometry(manifest: dict[str, Any], assets_dir: Path, *, tolerance: float = 0.02) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for element in manifest.get("elements", []):
        if element.get("bucket") != "preserved_raster":
            continue
        element_id = str(element.get("id"))
        asset = assets_dir / Path(str(element.get("asset_path", f"{element_id}.png"))).name
        box = _bbox(element)
        if not asset.exists() or box is None:
            records.append({"element_id": element_id, "status": "failed", "reason": "asset_or_bbox_missing"})
            continue
        try:
            with Image.open(asset) as image:
                crop_ratio = image.width / image.height
                alpha = image.mode in {"RGBA", "LA"}
                crop_size = [image.width, image.height]
        except Exception as exc:
            records.append({"element_id": element_id, "status": "failed", "reason": f"asset_unreadable:{exc}"})
            continue
        expected_ratio = box[2] / box[3]
        error = abs(crop_ratio - expected_ratio) / expected_ratio
        expected_hash = element.get("asset_sha256")
        actual_hash = sha256_file(asset)
        record = {
            "element_id": element_id,
            "source_bbox_px": [int(value) for value in box],
            "crop_size_px": crop_size,
            "source_aspect_ratio": round(expected_ratio, 6),
            "rendered_aspect_ratio": round(crop_ratio, 6),
            "aspect_ratio_error": round(error, 6),
            "alpha_preserved": alpha,
            "rotation_match": float(element.get("rotation_deg", 0.0)) == 0.0,
            "asset_hash_match": expected_hash in {None, actual_hash},
        }
        record["status"] = "pass" if error <= tolerance and record["rotation_match"] and record["asset_hash_match"] else "failed"
        records.append(record)
    return {
        "schema": "scientificfigure.preserved_geometry_report.v1",
        "tolerance": tolerance,
        "status": "pass" if all(item["status"] == "pass" for item in records) else ("not_applicable" if not records else "failed"),
        "elements": records,
    }


def anchor_point(element: dict[str, Any], anchor: dict[str, Any]) -> tuple[float, float]:
    box = _bbox(element)
    if box is None:
        raise ValueError(f"element {element.get('id')} has no bbox")
    x, y, w, h = box
    side = str(anchor.get("side", "center"))
    offset = float(anchor.get("offset", 0.5))
    if not 0 <= offset <= 1:
        raise ValueError("anchor offset must be between 0 and 1")
    if side == "left":
        return x, y + h * offset
    if side == "right":
        return x + w, y + h * offset
    if side == "top":
        return x + w * offset, y
    if side == "bottom":
        return x + w * offset, y + h
    if side == "custom":
        point = anchor.get("point_px")
        if isinstance(point, list) and len(point) == 2:
            return float(point[0]), float(point[1])
        raise ValueError("custom anchor requires point_px")
    return x + w / 2, y + h / 2


def connector_points(element: dict[str, Any], elements: dict[str, dict[str, Any]]) -> list[tuple[float, float]]:
    observed = element.get("observed_endpoints_px")
    points: list[tuple[float, float]] = []
    for field, index in (("source_anchor", 0), ("target_anchor", 1)):
        anchor = element.get(field)
        if isinstance(anchor, dict) and anchor.get("element_id") in elements:
            points.append(anchor_point(elements[str(anchor["element_id"])], anchor))
        elif isinstance(observed, list) and len(observed) == 2:
            point = observed[index]
            points.append((float(point[0]), float(point[1])))
        else:
            raise ValueError(f"{element.get('id')} has unresolved {field}")
    via = element.get("via_points_px", [])
    return [points[0], *[(float(p[0]), float(p[1])) for p in via], points[1]]


def audit_connectors(manifest: dict[str, Any], *, endpoint_tolerance_px: float = 12.0) -> dict[str, Any]:
    elements = element_map(manifest)
    width, height = canvas_size(manifest)
    records: list[dict[str, Any]] = []
    for connector in manifest.get("elements", []):
        if connector.get("primitive") not in {"connector", "arrow", "line", "polyline"}:
            continue
        element_id = str(connector.get("id"))
        issues: list[str] = []
        anchors: list[tuple[float, float]] = []
        for field in ("source_anchor", "target_anchor"):
            anchor = connector.get(field)
            if not isinstance(anchor, dict):
                if connector.get("primitive") == "connector":
                    issues.append(f"missing_{field}")
                continue
            ref = anchor.get("element_id")
            if ref not in elements:
                issues.append(f"missing_{field}_element")
                continue
            if anchor.get("side") not in SIDES:
                issues.append(f"invalid_{field}_side")
                continue
            try:
                anchors.append(anchor_point(elements[str(ref)], anchor))
            except ValueError:
                issues.append(f"invalid_{field}")
        if len(anchors) == 2 and connector.get("source_anchor", {}).get("element_id") == connector.get("target_anchor", {}).get("element_id") and not connector.get("self_connection_reason"):
            issues.append("unjustified_self_connection")
        observed = connector.get("observed_endpoints_px")
        errors: dict[str, float] = {}
        if isinstance(observed, list) and len(observed) == 2 and len(anchors) == 2:
            for name, expected, actual in zip(("start", "end"), anchors, observed):
                error = math.dist(expected, (float(actual[0]), float(actual[1])))
                errors[name] = round(error, 6)
                if error > endpoint_tolerance_px:
                    issues.append(f"{name}_endpoint_mismatch")
        for point in connector.get("via_points_px", []):
            if not (0 <= float(point[0]) <= width and 0 <= float(point[1]) <= height):
                issues.append("via_point_out_of_bounds")
        records.append({
            "id": element_id,
            "computed_endpoints_px": [[round(p[0], 6), round(p[1], 6)] for p in anchors],
            "endpoint_error_px": errors,
            "recomputable": len(anchors) == 2,
            "issues": sorted(set(issues)),
            "status": "pass" if not issues else "failed",
        })
    return {
        "schema": "scientificfigure.connector_audit.v1",
        "endpoint_tolerance_px": endpoint_tolerance_px,
        "status": "pass" if all(item["status"] == "pass" for item in records) else ("not_applicable" if not records else "failed"),
        "connectors": records,
    }


def geometry_audit(manifest: dict[str, Any], connector_report: dict[str, Any] | None = None) -> dict[str, Any]:
    width, height = canvas_size(manifest)
    issues: list[dict[str, Any]] = []
    elements = manifest.get("elements", [])
    for element in elements:
        element_id = str(element.get("id"))
        box = _bbox(element)
        if box is None:
            issues.append(_issue("bbox_missing", "geometry requires bbox", element_id=element_id))
            continue
        x, y, w, h = box
        if x < 0 or y < 0 or x + w > width or y + h > height:
            issues.append(_issue("clipped", "element is outside canvas", element_id=element_id))
    sorted_elements = sorted((item for item in elements if isinstance(item.get("z_order"), int)), key=lambda item: item["z_order"])
    if len(sorted_elements) != len(elements):
        issues.append(_issue("z_order", "all elements require integer z_order"))
    if connector_report and connector_report.get("status") == "failed":
        issues.append(_issue("connector_geometry", "one or more connectors failed geometry audit"))
    return {
        "schema": "scientificfigure.geometry_audit.v1",
        "canvas_px": [width, height],
        "element_count": len(elements),
        "panel_ids": sorted({str(item.get("panel_id")) for item in elements if item.get("panel_id") is not None}),
        "z_order": [str(item.get("id")) for item in sorted_elements],
        "issues": issues,
        "geometry_status": "pass" if not issues else "failed",
    }


def _color(value: Any, default: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    try:
        rgb = ImageColor.getrgb(str(value or default))
    except ValueError:
        rgb = ImageColor.getrgb(default)
    return int(rgb[0]), int(rgb[1]), int(rgb[2]), int(max(0, min(1, opacity)) * 255)


def _draw_element(draw: ImageDraw.ImageDraw, image: Image.Image, element: dict[str, Any], elements: dict[str, dict[str, Any]], *, geometry: bool, assets_dir: Path | None = None, id_map_color: tuple[int, int, int, int] | None = None) -> None:
    box = _bbox(element)
    if box is None:
        return
    x, y, w, h = box
    xy = (round(x), round(y), round(x + w), round(y + h))
    primitive = element.get("primitive")
    if id_map_color is not None:
        fill, stroke, width = id_map_color, id_map_color, 3
    elif geometry:
        fill, stroke, width = (220, 220, 220, 150), (90, 90, 90, 255), 2
    else:
        style = element.get("style", {})
        opacity = float(style.get("opacity", 1.0))
        fill = _color(style.get("fill"), "#FFFFFF", opacity)
        stroke = _color(style.get("stroke"), "#333333", opacity)
        width = max(1, round(float(style.get("stroke_width_pt", 1.0))))
    if primitive in {"rectangle", "textbox", "image", "group", "path", "unknown"}:
        draw.rectangle(xy, fill=fill, outline=stroke, width=width)
    elif primitive == "rounded_rectangle":
        draw.rounded_rectangle(xy, radius=max(2, round(min(w, h) * 0.12)), fill=fill, outline=stroke, width=width)
    elif primitive in {"ellipse", "circle"}:
        draw.ellipse(xy, fill=fill, outline=stroke, width=width)
    elif primitive == "polygon":
        points = element.get("points_px") or [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
        draw.polygon([(round(p[0]), round(p[1])) for p in points], fill=fill, outline=stroke)
    elif primitive in {"line", "polyline", "arrow", "connector"}:
        try:
            points = connector_points(element, elements)
        except ValueError:
            points = [(x, y + h / 2), (x + w, y + h / 2)]
        draw.line([(round(px), round(py)) for px, py in points], fill=stroke, width=max(width, 2), joint="curve")
        if primitive in {"arrow", "connector"} and element.get("arrowhead", "triangle") != "none" and len(points) >= 2:
            p1, p2 = points[-2], points[-1]
            angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
            size = max(6.0, float(element.get("style", {}).get("arrow_size_px", 9.0)))
            left = (p2[0] - size * math.cos(angle - 0.5), p2[1] - size * math.sin(angle - 0.5))
            right = (p2[0] - size * math.cos(angle + 0.5), p2[1] - size * math.sin(angle + 0.5))
            draw.polygon([(round(p2[0]), round(p2[1])), (round(left[0]), round(left[1])), (round(right[0]), round(right[1]))], fill=stroke)
    if not geometry and element.get("bucket") == "preserved_raster" and assets_dir is not None:
        asset = assets_dir / Path(str(element.get("asset_path", ""))).name
        if asset.exists():
            with Image.open(asset) as source:
                source = source.convert("RGBA")
                scale = min(w / source.width, h / source.height)
                size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
                source = source.resize(size, Image.Resampling.LANCZOS)
                left = round(x + (w - size[0]) / 2)
                top = round(y + (h - size[1]) / 2)
                image.alpha_composite(source, (left, top))
    if id_map_color is None:
        text = str(element.get("id")) if geometry else str((element.get("text") or {}).get("content", ""))
        if text:
            draw.text((round(x + 3), round(y + 3)), text, fill=(30, 30, 30, 255), font=ImageFont.load_default())


def render_manifest(manifest: dict[str, Any], output: Path, *, stage: str, assets_dir: Path | None = None, require_geometry_report: Path | None = None) -> dict[str, Any]:
    if stage not in {"geometry", "final"}:
        raise ValueError("stage must be geometry or final")
    if stage == "final" and require_geometry_report is not None:
        report = load_json(require_geometry_report)
        if report.get("geometry_status") != "pass":
            raise RuntimeError("final stage is blocked until geometry_status is pass")
    width, height = canvas_size(manifest)
    background = (255, 255, 255, 255)
    image = Image.new("RGBA", (width, height), background)
    draw = ImageDraw.Draw(image, "RGBA")
    elements = element_map(manifest)
    for element in sorted(manifest.get("elements", []), key=lambda item: int(item.get("z_order", 0))):
        _draw_element(draw, image, element, elements, geometry=stage == "geometry", assets_dir=assets_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".png":
        image.convert("RGB").save(output, format="PNG")
    else:
        raise ValueError("render_manifest currently writes PNG; use export_vector_manifest for SVG/PDF")
    return {"stage": stage, "output": output.as_posix(), "canvas_px": [width, height], "element_count": len(elements), "status": "pass"}


def export_vector_manifest(manifest: dict[str, Any], output: Path, *, assets_dir: Path | None = None) -> dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

    width, height = canvas_size(manifest)
    fig = plt.figure(figsize=(width / 100, height / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.axis("off")
    elements = element_map(manifest)
    for element in sorted(manifest.get("elements", []), key=lambda item: int(item.get("z_order", 0))):
        box = _bbox(element)
        if box is None:
            continue
        x, y, w, h = box
        style = element.get("style", {})
        face = style.get("fill", "none")
        edge = style.get("stroke", "#333333")
        lw = float(style.get("stroke_width_pt", 1.0))
        alpha = float(style.get("opacity", 1.0))
        primitive = element.get("primitive")
        patch = None
        if primitive in {"rectangle", "textbox", "image", "group", "path", "unknown"}:
            patch = Rectangle((x, y), w, h, facecolor=face, edgecolor=edge, linewidth=lw, alpha=alpha)
        elif primitive == "rounded_rectangle":
            patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=6", facecolor=face, edgecolor=edge, linewidth=lw, alpha=alpha)
        elif primitive == "ellipse":
            patch = Ellipse((x + w / 2, y + h / 2), w, h, facecolor=face, edgecolor=edge, linewidth=lw, alpha=alpha)
        elif primitive == "circle":
            patch = Circle((x + w / 2, y + h / 2), min(w, h) / 2, facecolor=face, edgecolor=edge, linewidth=lw, alpha=alpha)
        elif primitive == "polygon":
            patch = Polygon(element.get("points_px") or [[x, y], [x + w, y], [x + w, y + h], [x, y + h]], closed=True, facecolor=face, edgecolor=edge, linewidth=lw, alpha=alpha)
        if patch is not None:
            ax.add_patch(patch)
        if primitive in {"line", "polyline", "arrow", "connector"}:
            try:
                points = connector_points(element, elements)
            except ValueError:
                points = [(x, y + h / 2), (x + w, y + h / 2)]
            for index in range(len(points) - 1):
                arrowstyle = "-|>" if index == len(points) - 2 and primitive in {"arrow", "connector"} else "-"
                ax.add_patch(FancyArrowPatch(points[index], points[index + 1], arrowstyle=arrowstyle, color=edge, linewidth=lw, mutation_scale=10))
        if element.get("bucket") == "preserved_raster" and assets_dir is not None:
            asset = assets_dir / Path(str(element.get("asset_path", ""))).name
            if asset.exists():
                raster = np.asarray(Image.open(asset).convert("RGBA"))
                ax.imshow(raster, extent=(x, x + w, y + h, y), aspect="equal")
        text = str((element.get("text") or {}).get("content", ""))
        if text:
            ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=float((element.get("text") or {}).get("font_size_pt", 10)), color=(element.get("text") or {}).get("color", "#111111"))
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=100, transparent=False, metadata={"Creator": "SciPlot object reconstruction"})
    plt.close(fig)
    return {"output": output.as_posix(), "status": "pass"}


def build_object_masks(manifest: dict[str, Any], masks_dir: Path, *, id_map_path: Path | None = None) -> dict[str, Any]:
    width, height = canvas_size(manifest)
    masks_dir.mkdir(parents=True, exist_ok=True)
    elements = element_map(manifest)
    id_map = Image.new("RGB", (width, height), "black")
    records: list[dict[str, Any]] = []
    for index, element in enumerate(sorted(manifest.get("elements", []), key=lambda item: int(item.get("z_order", 0))), start=1):
        element_id = str(element.get("id"))
        mask = Image.new("L", (width, height), 0)
        rgba = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(rgba, "RGBA")
        _draw_element(draw, rgba, element, elements, geometry=False, id_map_color=(255, 255, 255, 255))
        mask = rgba.getchannel("A").point(lambda value: 255 if value else 0)
        path = masks_dir / f"{element_id}.png"
        mask.save(path)
        color = ((index & 255), ((index >> 8) & 255), ((index >> 16) & 255))
        id_map.paste(color, mask=mask)
        records.append({"id": element_id, "mask": path.name, "map_color": list(color), "pixel_count": int(np.count_nonzero(np.asarray(mask)))})
    if id_map_path is not None:
        id_map_path.parent.mkdir(parents=True, exist_ok=True)
        id_map.save(id_map_path)
    return {"schema": "scientificfigure.object_masks.v1", "status": "pass", "canvas_px": [width, height], "elements": records}


def _same_canvas_images(source: Path, actual: Path) -> tuple[np.ndarray, np.ndarray]:
    src = np.asarray(Image.open(source).convert("RGB"), dtype=np.float64)
    act = np.asarray(Image.open(actual).convert("RGB"), dtype=np.float64)
    if src.shape != act.shape:
        raise ValueError(f"canvas mismatch: source={src.shape[:2]} actual={act.shape[:2]}; resizing is forbidden")
    return src, act


def _ssim(source: np.ndarray, actual: np.ndarray) -> float | None:
    try:
        from skimage.metrics import structural_similarity

        if min(source.shape[0], source.shape[1]) < 7:
            return None
        return float(structural_similarity(source.astype(np.uint8), actual.astype(np.uint8), channel_axis=2, data_range=255))
    except Exception:
        return None


def score_object_regions(source: Path, actual: Path, manifest: dict[str, Any], masks_dir: Path, *, connector_report: dict[str, Any] | None = None) -> dict[str, Any]:
    src, act = _same_canvas_images(source, actual)
    connector_map = {item["id"]: item for item in (connector_report or {}).get("connectors", [])}
    records: list[dict[str, Any]] = []
    for element in manifest.get("elements", []):
        element_id = str(element.get("id"))
        mask_path = masks_dir / f"{element_id}.png"
        if not mask_path.exists():
            records.append({"id": element_id, "status": "failed", "suspected_issues": ["mask_missing"]})
            continue
        mask = np.asarray(Image.open(mask_path).convert("L")) > 0
        box = _bbox(element)
        if box is None or not np.any(mask):
            records.append({"id": element_id, "status": "failed", "suspected_issues": ["empty_geometry"]})
            continue
        x, y, w, h = (int(round(value)) for value in box)
        x2, y2 = min(src.shape[1], x + w), min(src.shape[0], y + h)
        local_src = src[max(0, y):y2, max(0, x):x2]
        local_act = act[max(0, y):y2, max(0, x):x2]
        local_mask = mask[max(0, y):y2, max(0, x):x2]
        values = (local_src - local_act)[local_mask]
        mae = float(np.mean(np.abs(values))) if values.size else 0.0
        rmse = float(np.sqrt(np.mean(values ** 2))) if values.size else 0.0
        mean_delta = float(np.mean(np.linalg.norm(values.reshape(-1, 3), axis=1))) if values.size else 0.0
        ssim = _ssim(local_src, local_act)
        src_edge = np.asarray(Image.fromarray(local_src.astype(np.uint8)).filter(ImageFilter.FIND_EDGES), dtype=np.float64)
        act_edge = np.asarray(Image.fromarray(local_act.astype(np.uint8)).filter(ImageFilter.FIND_EDGES), dtype=np.float64)
        edge_error = float(np.mean(np.abs(src_edge - act_edge)) / 255.0) if src_edge.size else 0.0
        suspected = []
        if mae > 20:
            suspected.append("local_color_or_content_mismatch")
        if edge_error > 0.18:
            suspected.append("edge_alignment_mismatch")
        endpoint_error = connector_map.get(element_id, {}).get("endpoint_error_px")
        if endpoint_error and max(endpoint_error.values(), default=0) > float((connector_report or {}).get("endpoint_tolerance_px", 12)):
            suspected.append("anchor_endpoint_mismatch")
        records.append({
            "id": element_id,
            "bbox_error_px": 0.0,
            "center_error_px": 0.0,
            "width_error_px": 0.0,
            "height_error_px": 0.0,
            "local_mae": round(mae, 6),
            "local_rmse": round(rmse, 6),
            "local_ssim": None if ssim is None else round(ssim, 6),
            "edge_alignment_score": round(max(0.0, 1.0 - edge_error), 6),
            "mean_color_delta": round(mean_delta, 6),
            "endpoint_error_px": endpoint_error,
            "text_occupancy": round(float(np.count_nonzero(local_mask)) / max(1, local_mask.size), 6) if element.get("primitive") == "textbox" else None,
            "overlap_error": None,
            "z_order_conflict": False,
            "suspected_issues": suspected,
            "status": "pass" if not suspected else "warning",
        })
    worst = sorted(records, key=lambda item: (float(item.get("local_mae", -1)), float(item.get("local_rmse", -1))), reverse=True)
    return {
        "schema": "scientificfigure.object_qa_report.v1",
        "canvas_match": True,
        "status": "pass" if all(item.get("status") == "pass" for item in records) else "pass_with_warnings",
        "elements": records,
        "worst_elements": [item["id"] for item in worst[: min(10, len(worst))]],
    }


def _components(binary: np.ndarray, *, min_pixels: int = 4) -> list[tuple[int, int, int, int, int]]:
    height, width = binary.shape
    seen = np.zeros_like(binary, dtype=bool)
    components: list[tuple[int, int, int, int, int]] = []
    for y, x in zip(*np.nonzero(binary)):
        if seen[y, x]:
            continue
        queue = deque([(int(x), int(y))])
        seen[y, x] = True
        xs: list[int] = []
        ys: list[int] = []
        while queue:
            px, py = queue.popleft()
            xs.append(px)
            ys.append(py)
            for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                if 0 <= nx < width and 0 <= ny < height and binary[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((nx, ny))
        if len(xs) >= min_pixels:
            components.append((min(xs), min(ys), max(xs) + 1, max(ys) + 1, len(xs)))
    return components


def map_diff_to_objects(source: Path, actual: Path, masks_dir: Path, *, threshold: float = 24.0, min_pixels: int = 4) -> dict[str, Any]:
    src, act = _same_canvas_images(source, actual)
    diff = np.mean(np.abs(src - act), axis=2) >= threshold
    masks = {path.stem: np.asarray(Image.open(path).convert("L")) > 0 for path in masks_dir.glob("*.png")}
    regions: list[dict[str, Any]] = []
    for index, (x1, y1, x2, y2, pixels) in enumerate(_components(diff, min_pixels=min_pixels), start=1):
        region = np.zeros_like(diff)
        region[y1:y2, x1:x2] = diff[y1:y2, x1:x2]
        overlaps = []
        for element_id, mask in masks.items():
            overlap = int(np.count_nonzero(region & mask))
            if overlap:
                overlaps.append((element_id, overlap))
        overlaps.sort(key=lambda item: item[1], reverse=True)
        confidence = overlaps[0][1] / pixels if overlaps else 0.0
        regions.append({
            "diff_region_id": f"D{index:03d}",
            "bbox_px": [x1, y1, x2 - x1, y2 - y1],
            "pixel_count": pixels,
            "candidate_elements": [item[0] for item in overlaps],
            "primary_element": overlaps[0][0] if overlaps else None,
            "confidence": round(confidence, 6),
        })
    return {"schema": "scientificfigure.object_diff_map.v1", "status": "pass", "threshold": threshold, "regions": regions}


def create_bundle(source: Path, manifest_path: Path, run_root: Path, bundle_dir: Path) -> dict[str, Any]:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    records: dict[str, str] = {}
    mapping = {
        source: bundle_dir / "input" / source.name,
        manifest_path: bundle_dir / "object_manifest" / "object_manifest.json",
    }
    for directory in ("assets", "outputs", "qa", "editable"):
        root = run_root / directory
        if root.exists():
            for item in root.rglob("*"):
                if item.is_file():
                    mapping[item] = bundle_dir / directory / item.relative_to(root)
    for original, target in mapping.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        if original.resolve() != target.resolve():
            shutil.copyfile(original, target)
        records[target.relative_to(bundle_dir).as_posix()] = sha256_file(target)
    payload = {
        "schema": "scientificfigure.object_reconstruction_bundle.v1",
        "project_root": ".",
        "source_sha256": sha256_file(source),
        "object_manifest_sha256": sha256_file(manifest_path),
        "object_manifest_schema": SCHEMA,
        "policy_version": "1.0",
        "office_runtime_verified": False,
        "files": dict(sorted(records.items())),
        "status": "pass",
    }
    write_json(bundle_dir / "manifest.json", payload)
    return payload
