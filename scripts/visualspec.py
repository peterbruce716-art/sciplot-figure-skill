from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from capability_model import PLOT_CAPABILITIES, SUPPORTED_ANNOTATION_TYPES, SUPPORTED_PLOT_TYPES, plot_style_keys


VISUALSPEC_SCHEMA = "scientificfigure.visualspec.v1"
VISUALSPEC_SCHEMA_V2 = "scientificfigure.visualspec.v2"
RUN_MANIFEST_SCHEMA = "scientificfigure.manifest.v2"

SOURCE_STRATEGIES = {
    "raw_data",
    "digitized_raster",
    "manual_measurement",
    "vector_redraw",
    "color_region_extraction",
    "pixel_trace",
}
REPRESENTATIONS = {"semantic_vector", "semantic_raster", "mixed", "pixel_primitives"}
FINAL_STATUSES = {
    "semantic_strict_pass",
    "semantic_validated_pass",
    "semantic_near_pass",
    "visual_trace_pass",
    "render_only",
    "not_strict",
    "failed",
}
QA_EXECUTION_STATUSES = {"not_run", "completed", "failed"}
QA_RESULTS = {"strict_pass", "validated_pass", "near_pass", "not_strict", "not_applicable"}
QUALITY_STATUSES = {"strict_pass", "validated_pass", "near_pass", "render_only", "not_strict", "not_applicable", "failed"}

PLOT_STYLE_KEYS = {name: set(capability.style_fields) for name, capability in PLOT_CAPABILITIES.items()}
PLOT_TOP_LEVEL_KEYS = {"id", "type", "label", "data", "style", "allow_empty", "colorbar"}
ANNOTATION_STYLE_KEYS = {
    "text": {"font_size_pt", "color", "ha", "va", "rotation", "fontweight", "fontstyle"},
    "arrow": {"arrowstyle", "color", "line_width_pt", "alpha"},
    "rectangle": {"fill", "facecolor", "edgecolor", "line_width_pt", "line_style", "alpha", "hatch", "zorder"},
    "polygon": {"fill", "facecolor", "edgecolor", "line_width_pt", "line_style", "alpha", "hatch", "zorder"},
}


class VisualSpecError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def portable_path(path: Path | str | None, root: Path, *, allow_outside: bool = False) -> str | None:
    if path is None:
        return None
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()
    if allow_outside:
        return str(candidate)
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path is outside project root: {candidate}") from exc


def schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "schemas" / name


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _resolve_ref(schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        return {}
    current: Any = schema
    for part in ref[2:].split("/"):
        current = current.get(part, {}) if isinstance(current, dict) else {}
    return current if isinstance(current, dict) else {}


def _basic_schema_errors(value: Any, schema_node: dict[str, Any], root_schema: dict[str, Any], path: str = "<root>") -> list[str]:
    if "$ref" in schema_node:
        return _basic_schema_errors(value, _resolve_ref(root_schema, str(schema_node["$ref"])), root_schema, path)
    errors: list[str] = []
    if "oneOf" in schema_node:
        branches = schema_node.get("oneOf") or []
        branch_errors = [_basic_schema_errors(value, branch, root_schema, path) for branch in branches if isinstance(branch, dict)]
        passing = [items for items in branch_errors if not items]
        if len(passing) != 1:
            flat = "; ".join(item for items in branch_errors for item in items[:2])
            errors.append(f"{path}: must match exactly one schema branch" + (f" ({flat})" if flat else ""))
        return errors
    if "allOf" in schema_node:
        for branch in schema_node.get("allOf") or []:
            if isinstance(branch, dict):
                errors.extend(_basic_schema_errors(value, branch, root_schema, path))
    expected_type = schema_node.get("type")
    if isinstance(expected_type, list):
        if not any(_type_ok(value, item) for item in expected_type):
            errors.append(f"{path}: {value!r} is not of type {expected_type}")
            return errors
    elif isinstance(expected_type, str) and not _type_ok(value, expected_type):
        errors.append(f"{path}: {value!r} is not of type {expected_type}")
        return errors
    if "const" in schema_node and value != schema_node["const"]:
        errors.append(f"{path}: {value!r} does not match const {schema_node['const']!r}")
    if "enum" in schema_node and value not in schema_node["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema_node['enum']!r}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "exclusiveMinimum" in schema_node and not value > float(schema_node["exclusiveMinimum"]):
            errors.append(f"{path}: {value!r} must be > {schema_node['exclusiveMinimum']}")
        if "minimum" in schema_node and not value >= float(schema_node["minimum"]):
            errors.append(f"{path}: {value!r} must be >= {schema_node['minimum']}")
        if "maximum" in schema_node and not value <= float(schema_node["maximum"]):
            errors.append(f"{path}: {value!r} must be <= {schema_node['maximum']}")
    if isinstance(value, dict):
        properties = schema_node.get("properties") or {}
        for required in schema_node.get("required", []):
            if required not in value:
                errors.append(f"{path}: required property {required!r} is missing")
        additional = schema_node.get("additionalProperties", True)
        for key, child in value.items():
            child_path = f"{path}.{key}" if path != "<root>" else key
            if key in properties:
                errors.extend(_basic_schema_errors(child, properties[key], root_schema, child_path))
            elif additional is False:
                errors.append(f"{child_path}: additional property is not allowed")
            elif isinstance(additional, dict):
                errors.extend(_basic_schema_errors(child, additional, root_schema, child_path))
    if isinstance(value, list):
        if "minItems" in schema_node and len(value) < int(schema_node["minItems"]):
            errors.append(f"{path}: array has fewer than {schema_node['minItems']} items")
        if "maxItems" in schema_node and len(value) > int(schema_node["maxItems"]):
            errors.append(f"{path}: array has more than {schema_node['maxItems']} items")
        item_schema = schema_node.get("items")
        if isinstance(item_schema, dict):
            for index, child in enumerate(value):
                errors.extend(_basic_schema_errors(child, item_schema, root_schema, f"{path}[{index}]"))
    return errors


def _json_schema_errors(payload: dict[str, Any], schema_file: Path) -> list[str]:
    schema = load_json(schema_file)
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:
        return _basic_schema_errors(payload, schema, schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.absolute_path))
    result: list[str] = []
    for error in errors:
        path = ".".join(str(part) for part in error.absolute_path)
        result.append(f"{path or '<root>'}: {error.message}")
    return result


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _number_list(value: Any) -> bool:
    return isinstance(value, list) and all(_is_finite_number(item) for item in value)


def _nonempty_number_list(value: Any) -> bool:
    return _number_list(value) and len(value) > 0


def _matrix(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_nonempty_number_list(row) for row in value)


def _style_errors(style: Any, ptype: str, prefix: str) -> list[str]:
    if style is None:
        return []
    if not isinstance(style, dict):
        return [f"{prefix}.style must be an object"]
    allowed = set(plot_style_keys(ptype))
    errors = [f"{prefix}.style.{key}: additional property is not allowed" for key in style if key not in allowed]
    if "line_width_pt" in style and (not _is_finite_number(style["line_width_pt"]) or float(style["line_width_pt"]) <= 0):
        errors.append(f"{prefix}.style.line_width_pt must be a positive number")
    if "marker_size_pt2" in style and (not _is_finite_number(style["marker_size_pt2"]) or float(style["marker_size_pt2"]) <= 0):
        errors.append(f"{prefix}.style.marker_size_pt2 must be a positive number")
    if "capsize" in style and (not _is_finite_number(style["capsize"]) or float(style["capsize"]) < 0):
        errors.append(f"{prefix}.style.capsize must be a non-negative number")
    if "bar_width" in style and (not _is_finite_number(style["bar_width"]) or float(style["bar_width"]) <= 0):
        errors.append(f"{prefix}.style.bar_width must be a positive number")
    if "alpha" in style and (not _is_finite_number(style["alpha"]) or not 0 <= float(style["alpha"]) <= 1):
        errors.append(f"{prefix}.style.alpha must be in [0, 1]")
    if "line_style" in style and style["line_style"] not in {"solid", "dashed", "dashdot", "dotted"}:
        errors.append(f"{prefix}.style.line_style is not supported: {style['line_style']}")
    return errors


def _annotation_style_errors(style: Any, atype: str, prefix: str) -> list[str]:
    if style is None:
        return []
    if not isinstance(style, dict):
        return [f"{prefix}.style must be an object"]
    allowed = ANNOTATION_STYLE_KEYS.get(atype, set())
    errors = [f"{prefix}.style.{key}: additional property is not allowed" for key in style if key not in allowed]
    if "line_width_pt" in style and (not _is_finite_number(style["line_width_pt"]) or float(style["line_width_pt"]) <= 0):
        errors.append(f"{prefix}.style.line_width_pt must be a positive number")
    if "font_size_pt" in style and (not _is_finite_number(style["font_size_pt"]) or float(style["font_size_pt"]) <= 0):
        errors.append(f"{prefix}.style.font_size_pt must be a positive number")
    if "alpha" in style and (not _is_finite_number(style["alpha"]) or not 0 <= float(style["alpha"]) <= 1):
        errors.append(f"{prefix}.style.alpha must be in [0, 1]")
    if "rotation" in style and not _is_finite_number(style["rotation"]):
        errors.append(f"{prefix}.style.rotation must be a finite number")
    if "zorder" in style and not _is_finite_number(style["zorder"]):
        errors.append(f"{prefix}.style.zorder must be a finite number")
    if "line_style" in style and style["line_style"] not in {"solid", "dashed", "dashdot", "dotted"}:
        errors.append(f"{prefix}.style.line_style is not supported: {style['line_style']}")
    return errors


def _plot_data_errors(data: Any, ptype: str, prefix: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(data, dict):
        return [f"{prefix}.data must be an object"]
    if allow_empty:
        return []
    if data.get("source"):
        return []
    errors: list[str] = []
    if ptype in {"line", "scatter", "errorbar"}:
        if not _nonempty_number_list(data.get("x")):
            errors.append(f"{prefix}.data.x must be a non-empty finite number array")
        if not _nonempty_number_list(data.get("y")):
            errors.append(f"{prefix}.data.y must be a non-empty finite number array")
        if _number_list(data.get("x")) and _number_list(data.get("y")) and len(data["x"]) != len(data["y"]):
            errors.append(f"{prefix}.data.x and data.y must have equal length")
        if ptype == "errorbar":
            if not _nonempty_number_list(data.get("yerr")):
                errors.append(f"{prefix}.data.yerr must be a non-empty finite number array")
            elif _number_list(data.get("y")) and len(data["yerr"]) != len(data["y"]):
                errors.append(f"{prefix}.data.yerr must match data.y length")
    elif ptype == "fill_between":
        for key in ("x", "y1", "y2"):
            if not _nonempty_number_list(data.get(key)):
                errors.append(f"{prefix}.data.{key} must be a non-empty finite number array")
        if _number_list(data.get("x")):
            for key in ("y1", "y2"):
                if _number_list(data.get(key)) and len(data["x"]) != len(data[key]):
                    errors.append(f"{prefix}.data.x and data.{key} must have equal length")
    elif ptype in {"grouped_bar", "stacked_bar"}:
        if not _nonempty_number_list(data.get("x")):
            errors.append(f"{prefix}.data.x must be a non-empty finite number array")
        groups = data.get("groups")
        if not isinstance(groups, list) or not groups:
            errors.append(f"{prefix}.data.groups must be a non-empty array")
        else:
            x_len = len(data.get("x") or [])
            for group_index, group in enumerate(groups):
                if not isinstance(group, dict):
                    errors.append(f"{prefix}.data.groups[{group_index}] must be an object")
                    continue
                if not _nonempty_number_list(group.get("y")):
                    errors.append(f"{prefix}.data.groups[{group_index}].y must be a non-empty finite number array")
                elif x_len and len(group["y"]) != x_len:
                    errors.append(f"{prefix}.data.groups[{group_index}].y must match data.x length")
    elif ptype == "heatmap":
        if not _matrix(data.get("z")):
            errors.append(f"{prefix}.data.z must be a non-empty finite 2D matrix")
    elif ptype == "contour":
        if not _nonempty_number_list(data.get("x")):
            errors.append(f"{prefix}.data.x must be a non-empty finite number array")
        if not _nonempty_number_list(data.get("y")):
            errors.append(f"{prefix}.data.y must be a non-empty finite number array")
        if not _matrix(data.get("z")):
            errors.append(f"{prefix}.data.z must be a non-empty finite 2D matrix")
        elif _number_list(data.get("x")) and _number_list(data.get("y")):
            z = data["z"]
            if len(z) != len(data["y"]) or any(len(row) != len(data["x"]) for row in z):
                errors.append(f"{prefix}.data.z shape must be (len(y), len(x))")
    return errors


def validate_visualspec(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = spec.get("schema")
    if schema not in {VISUALSPEC_SCHEMA, VISUALSPEC_SCHEMA_V2}:
        errors.append(f"schema must be {VISUALSPEC_SCHEMA} or {VISUALSPEC_SCHEMA_V2}")
    elif schema == VISUALSPEC_SCHEMA_V2:
        errors.extend(_json_schema_errors(spec, schema_path("visualspec-v2.schema.json")))

    figure = spec.get("figure")
    if not isinstance(figure, dict):
        errors.append("figure must be an object")
    else:
        size_mm = figure.get("size_mm")
        if not (isinstance(size_mm, list) and len(size_mm) == 2 and all(float(v) > 0 for v in size_mm)):
            errors.append("figure.size_mm must be two positive numbers")
        if int(figure.get("dpi", 0)) <= 0:
            errors.append("figure.dpi must be positive")
        crop_mode = figure.get("crop_mode", "fixed_canvas")
        if crop_mode not in {"fixed_canvas", "content_tight"}:
            errors.append("figure.crop_mode must be fixed_canvas or content_tight")

    panels = spec.get("panels")
    if not isinstance(panels, list) or not panels:
        errors.append("panels must be a non-empty list")
        return errors

    seen: set[str] = set()
    for index, panel in enumerate(panels):
        if not isinstance(panel, dict):
            errors.append(f"panels[{index}] must be an object")
            continue
        panel_id = panel.get("id")
        if not isinstance(panel_id, str) or not panel_id:
            errors.append(f"panels[{index}].id must be a non-empty string")
        elif panel_id in seen:
            errors.append(f"duplicate panel id: {panel_id}")
        else:
            seen.add(panel_id)

        bbox = panel.get("bbox_normalized")
        if not (isinstance(bbox, list) and len(bbox) == 4):
            errors.append(f"panels[{index}].bbox_normalized must have four values")
        elif not all(0 <= float(v) <= 1 for v in bbox):
            errors.append(f"panels[{index}].bbox_normalized values must be in [0, 1]")
        elif float(bbox[0]) + float(bbox[2]) > 1 or float(bbox[1]) + float(bbox[3]) > 1:
            errors.append(f"panels[{index}].bbox_normalized left+width and bottom+height must be <= 1")

        source_strategy = panel.get("source_strategy")
        if source_strategy is not None and source_strategy not in SOURCE_STRATEGIES:
            errors.append(f"panels[{index}].source_strategy is not supported: {source_strategy}")
        representation = panel.get("representation")
        if representation is not None and representation not in REPRESENTATIONS:
            errors.append(f"panels[{index}].representation is not supported: {representation}")

        axes = panel.get("axes") or {}
        if not isinstance(axes, dict):
            errors.append(f"panels[{index}].axes must be an object")
        else:
            for axis_name in ("x", "y"):
                axis = axes.get(axis_name) or {}
                if not isinstance(axis, dict):
                    errors.append(f"panels[{index}].axes.{axis_name} must be an object")
                    continue
                limits = axis.get("limits")
                if limits is not None and not (isinstance(limits, list) and len(limits) == 2):
                    errors.append(f"panels[{index}].axes.{axis_name}.limits must have two values")
                elif limits is not None and float(limits[0]) >= float(limits[1]):
                    errors.append(f"panels[{index}].axes.{axis_name}.limits must be increasing")
                if axis.get("scale") == "log" and limits is not None and (float(limits[0]) <= 0 or float(limits[1]) <= 0):
                    errors.append(f"panels[{index}].axes.{axis_name}.limits must be positive for log scale")

        plots = panel.get("plots", [])
        if not isinstance(plots, list):
            errors.append(f"panels[{index}].plots must be a list")
        else:
            for plot_index, plot in enumerate(plots):
                if not isinstance(plot, dict):
                    errors.append(f"panels[{index}].plots[{plot_index}] must be an object")
                    continue
                ptype = plot.get("type")
                if ptype not in SUPPORTED_PLOT_TYPES:
                    errors.append(f"panels[{index}].plots[{plot_index}].type is not supported by the generic renderer: {ptype}")
                data = plot.get("data") or {}
                prefix = f"panels[{index}].plots[{plot_index}]"
                for key in plot:
                    if key not in PLOT_TOP_LEVEL_KEYS:
                        errors.append(f"{prefix}.{key}: additional property is not allowed")
                if ptype in SUPPORTED_PLOT_TYPES:
                    errors.extend(_plot_data_errors(data, ptype, prefix, allow_empty=plot.get("allow_empty") is True))
                    errors.extend(_style_errors(plot.get("style") or {}, ptype, prefix))

        annotations = panel.get("annotations", [])
        if not isinstance(annotations, list):
            errors.append(f"panels[{index}].annotations must be a list")
        else:
            for ann_index, annotation in enumerate(annotations):
                if not isinstance(annotation, dict):
                    errors.append(f"panels[{index}].annotations[{ann_index}] must be an object")
                    continue
                atype = annotation.get("type")
                if atype not in SUPPORTED_ANNOTATION_TYPES:
                    errors.append(f"panels[{index}].annotations[{ann_index}].type is not supported by the generic renderer: {atype}")
                coords = annotation.get("coordinates", [])
                if atype == "text" and not (isinstance(coords, list) and len(coords) >= 2):
                    errors.append(f"panels[{index}].annotations[{ann_index}].coordinates must contain x,y")
                if atype == "arrow" and not (isinstance(coords, list) and len(coords) >= 4):
                    errors.append(f"panels[{index}].annotations[{ann_index}].coordinates must contain x0,y0,x1,y1")
                if atype == "rectangle":
                    if not (isinstance(coords, list) and len(coords) == 4 and all(_is_finite_number(value) for value in coords)):
                        errors.append(f"panels[{index}].annotations[{ann_index}].coordinates must contain x,y,width,height")
                    elif float(coords[2]) <= 0 or float(coords[3]) <= 0:
                        errors.append(f"panels[{index}].annotations[{ann_index}].coordinates width and height must be positive")
                if atype == "polygon":
                    if not (isinstance(coords, list) and len(coords) >= 3 and all(isinstance(point, list) and len(point) == 2 and all(_is_finite_number(value) for value in point) for point in coords)):
                        errors.append(f"panels[{index}].annotations[{ann_index}].coordinates must contain at least three x,y points")
                if atype in SUPPORTED_ANNOTATION_TYPES:
                    errors.extend(_annotation_style_errors(annotation.get("style") or {}, atype, f"panels[{index}].annotations[{ann_index}]"))

    return errors


def require_valid_visualspec(spec: dict[str, Any]) -> None:
    errors = validate_visualspec(spec)
    if errors:
        raise VisualSpecError("; ".join(errors))


def status_to_qa_result(status: str) -> str:
    if status in {"semantic_strict_pass", "visual_trace_pass"}:
        return "strict_pass"
    if status == "semantic_validated_pass":
        return "validated_pass"
    if status == "semantic_near_pass":
        return "near_pass"
    if status == "not_strict":
        return "not_strict"
    return "not_applicable"


def manifest_overall_status(manifest: dict[str, Any]) -> str:
    if any(manifest.get(key) == "failed" for key in ["run_status", "source_code_status", "render_status", "export_status", "qa_execution_status", "visual_qa_status"]):
        return "failed"
    if manifest.get("quality_status") == "validated_pass":
        return "pass"
    if manifest.get("quality_status") in QUALITY_STATUSES - {"not_applicable"}:
        return str(manifest["quality_status"])
    status = manifest.get("status")
    if status in {"semantic_strict_pass", "visual_trace_pass"}:
        return "strict_pass"
    if status == "semantic_validated_pass":
        return "pass"
    if status == "semantic_near_pass":
        return "near_pass"
    if status in {"not_strict", "failed"}:
        return str(status)
    render_status = manifest.get("render_status", "not_run")
    export_status = manifest.get("export_status", "not_run")
    qa_execution_status = manifest.get("qa_execution_status", manifest.get("qa_status", "not_run"))
    if render_status == "pass" and export_status == "pass" and qa_execution_status in {"not_run", "render_only"}:
        return "render_only"
    return "incomplete"


def make_manifest(*, spec_path: str, output_dir: str, project_root: str = ".") -> dict[str, Any]:
    manifest = {
        "schema": RUN_MANIFEST_SCHEMA,
        "project_root": project_root,
        "spec_path": spec_path,
        "output_dir": output_dir,
        "source_code_status": "incomplete",
        "render_status": "not_run",
        "raster_export_status": "not_run",
        "vector_export_status": "not_run",
        "export_status": "not_run",
        "vector_validation_status": "not_run",
        "semantic_reconstruction_status": "not_run",
        "visual_qa_status": "not_run",
        "qa_status": "not_run",
        "run_status": "not_run",
        "qa_execution_status": "not_run",
        "quality_status": "not_applicable",
        "status": "render_only",
        "source_strategy": "raw_data",
        "representation": "semantic_vector",
        "overall_status": "incomplete",
        "figures": {},
        "per_figure_scripts": {},
        "errors": [],
    }
    manifest["overall_status"] = manifest_overall_status(manifest)
    return manifest


def apply_json_patch(doc: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    result = deepcopy(doc)
    for operation in operations:
        if operation.get("op") not in {"add", "replace"}:
            raise VisualSpecError(f"unsupported patch op: {operation.get('op')}")
        path = str(operation.get("path", ""))
        if not path.startswith("/"):
            raise VisualSpecError(f"patch path must start with /: {path}")
        parts = [part for part in path.strip("/").split("/") if part]
        if not parts:
            raise VisualSpecError("patch path cannot target the document root")
        target: Any = result
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        last = parts[-1]
        value = operation.get("value")
        if isinstance(target, list):
            index = int(last)
            if operation["op"] == "add" and index == len(target):
                target.append(value)
            else:
                target[index] = value
        else:
            target[last] = value
    return result
