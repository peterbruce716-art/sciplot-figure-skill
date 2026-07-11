from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


VISUALSPEC_SCHEMA = "scientificfigure.visualspec.v1"
VISUALSPEC_SCHEMA_V2 = "scientificfigure.visualspec.v2"
RUN_MANIFEST_SCHEMA = "scientificfigure.manifest.v2"

INCOMPLETE_STATES = {"not_run", "failed", "blocked", "unsupported", "incomplete"}
SUPPORTED_PLOT_TYPES = {
    "line",
    "scatter",
    "errorbar",
    "fill_between",
    "grouped_bar",
    "stacked_bar",
    "heatmap",
    "contour",
}
SUPPORTED_ANNOTATION_TYPES = {
    "text",
    "arrow",
    "rectangle",
    "polygon",
    "region_fill",
    "gradient_fill",
    "masked_image",
    "clip_path",
    "hatch_region",
    "poly_collection",
    "path_patch",
    "circle",
    "ellipse",
    "arc",
    "bezier_path",
    "dimension_arrow",
}
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
    "semantic_near_pass",
    "visual_trace_pass",
    "render_only",
    "not_strict",
    "failed",
}


class VisualSpecError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_visualspec(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if spec.get("schema") not in {VISUALSPEC_SCHEMA, VISUALSPEC_SCHEMA_V2}:
        errors.append(f"schema must be {VISUALSPEC_SCHEMA} or {VISUALSPEC_SCHEMA_V2}")
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
        if isinstance(axes, dict):
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
                    errors.append(f"panels[{index}].plots[{plot_index}].type is not supported: {ptype}")
                data = plot.get("data") or {}
                if not isinstance(data, dict):
                    errors.append(f"panels[{index}].plots[{plot_index}].data must be an object")
                    continue
                if ptype in {"line", "scatter", "errorbar", "fill_between"} and not data.get("source"):
                    x = data.get("x")
                    y = data.get("y")
                    if isinstance(x, list) and isinstance(y, list) and len(x) != len(y):
                        errors.append(f"panels[{index}].plots[{plot_index}].data.x and data.y must have equal length")
                    if ptype == "errorbar" and isinstance(data.get("yerr"), list) and isinstance(y, list) and len(data["yerr"]) != len(y):
                        errors.append(f"panels[{index}].plots[{plot_index}].data.yerr must match data.y length")
                    if ptype == "fill_between":
                        y1 = data.get("y1")
                        y2 = data.get("y2")
                        if isinstance(x, list) and isinstance(y1, list) and len(x) != len(y1):
                            errors.append(f"panels[{index}].plots[{plot_index}].data.x and data.y1 must have equal length")
                        if isinstance(x, list) and isinstance(y2, list) and len(x) != len(y2):
                            errors.append(f"panels[{index}].plots[{plot_index}].data.x and data.y2 must have equal length")
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
                    errors.append(f"panels[{index}].annotations[{ann_index}].type is not supported: {atype}")
                coords = annotation.get("coordinates", [])
                if atype in {"text"} and not (isinstance(coords, list) and len(coords) >= 2):
                    errors.append(f"panels[{index}].annotations[{ann_index}].coordinates must contain x,y")
                if atype in {"arrow"} and not (isinstance(coords, list) and len(coords) >= 4):
                    errors.append(f"panels[{index}].annotations[{ann_index}].coordinates must contain x0,y0,x1,y1")
    return errors


def require_valid_visualspec(spec: dict[str, Any]) -> None:
    errors = validate_visualspec(spec)
    if errors:
        raise VisualSpecError("; ".join(errors))


def manifest_overall_status(manifest: dict[str, Any]) -> str:
    if any(manifest.get(key) == "failed" for key in ["source_code_status", "render_status", "export_status", "qa_status", "visual_qa_status"]):
        return "failed"
    if manifest.get("status") in FINAL_STATUSES - {"render_only"}:
        return "pass" if manifest["status"] in {"semantic_strict_pass", "semantic_near_pass", "visual_trace_pass"} else manifest["status"]
    render_status = manifest.get("render_status", "not_run")
    export_status = manifest.get("export_status", "not_run")
    source_code_status = manifest.get("source_code_status", "not_run")
    qa_status = manifest.get("qa_status", "not_run")
    if source_code_status == "pass" and render_status == "pass" and export_status == "pass" and qa_status == "pass":
        return "pass"
    if render_status == "pass" and export_status == "pass" and qa_status in {"not_run", "render_only"}:
        return "render_only"
    return "incomplete"


def make_manifest(*, spec_path: str, output_dir: str) -> dict[str, Any]:
    manifest = {
        "schema": RUN_MANIFEST_SCHEMA,
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
