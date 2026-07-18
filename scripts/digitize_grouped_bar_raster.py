from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


SCHEMA = "scientificfigure.grouped_bar_digitization.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runs(values: list[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    result: list[tuple[int, int]] = []
    start = previous = values[0]
    for value in values[1:]:
        if value != previous + 1:
            result.append((start, previous))
            start = value
        previous = value
    result.append((start, previous))
    return result


def _require_number(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _validate_config(config: dict[str, Any]) -> None:
    if config.get("schema") != SCHEMA:
        raise ValueError(f"config.schema must be {SCHEMA}")
    calibration_status = config.get("calibration_status")
    unresolved_segments = config.get("unresolved_segments", [])
    if calibration_status is not None and calibration_status != "pass":
        raise ValueError(
            f"config requires manual review before digitization: calibration_status={calibration_status}"
        )
    if not isinstance(unresolved_segments, list):
        raise ValueError("config.unresolved_segments must be a list when provided")
    if unresolved_segments:
        raise ValueError("config requires manual review before digitization: unresolved_segments is not empty")
    panels = config.get("panels")
    if not isinstance(panels, list) or not panels:
        raise ValueError("config.panels must be a non-empty list")
    for panel_index, panel in enumerate(panels):
        prefix = f"panels[{panel_index}]"
        if not isinstance(panel, dict) or not panel.get("id"):
            raise ValueError(f"{prefix}.id must be a non-empty string")
        bbox = panel.get("plot_bbox_px")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"{prefix}.plot_bbox_px must contain left, top, right, bottom")
        left, top, right, bottom = [_require_number(value, f"{prefix}.plot_bbox_px") for value in bbox]
        if not (left < right and top < bottom):
            raise ValueError(f"{prefix}.plot_bbox_px must have positive width and height")
        centers = panel.get("category_centers_px")
        if not isinstance(centers, list) or not centers:
            raise ValueError(f"{prefix}.category_centers_px must be a non-empty list")
        for value in centers:
            _require_number(value, f"{prefix}.category_centers_px")
        axis = panel.get("y_axis")
        if not isinstance(axis, dict):
            raise ValueError(f"{prefix}.y_axis must be an object")
        baseline = _require_number(axis.get("pixel_baseline"), f"{prefix}.y_axis.pixel_baseline")
        pixel_top = _require_number(axis.get("pixel_top"), f"{prefix}.y_axis.pixel_top")
        value_min = _require_number(axis.get("value_min"), f"{prefix}.y_axis.value_min")
        value_max = _require_number(axis.get("value_max"), f"{prefix}.y_axis.value_max")
        if not (pixel_top < baseline and value_min < value_max):
            raise ValueError(f"{prefix}.y_axis calibration must be increasing")
        groups = panel.get("groups")
        if not isinstance(groups, list) or not groups:
            raise ValueError(f"{prefix}.groups must be a non-empty list")
        for group_index, group in enumerate(groups):
            group_prefix = f"{prefix}.groups[{group_index}]"
            if not isinstance(group, dict) or not group.get("label"):
                raise ValueError(f"{group_prefix}.label must be a non-empty string")
            color = group.get("color_rgb")
            if not isinstance(color, list) or len(color) != 3 or not all(isinstance(item, int) and 0 <= item <= 255 for item in color):
                raise ValueError(f"{group_prefix}.color_rgb must contain three integers in [0, 255]")
            _require_number(group.get("offset_px"), f"{group_prefix}.offset_px")
            width = _require_number(group.get("width_px"), f"{group_prefix}.width_px")
            if width < 1:
                raise ValueError(f"{group_prefix}.width_px must be at least 1")
            baseline_visibility = group.get("baseline_visibility", "visible")
            if baseline_visibility not in {"visible", "occluded_by_front_groups"}:
                raise ValueError(
                    f"{group_prefix}.baseline_visibility must be visible or occluded_by_front_groups"
                )
            allow_front_group_bridge = group.get("allow_front_group_bridge", False)
            if not isinstance(allow_front_group_bridge, bool):
                raise ValueError(f"{group_prefix}.allow_front_group_bridge must be a boolean")


def _bar_window(category_center: float, group: dict[str, Any]) -> tuple[int, int]:
    bar_width = max(1, int(round(float(group["width_px"]))))
    bar_center = float(category_center) + float(group["offset_px"])
    x0 = int(round(bar_center - (bar_width - 1) / 2.0))
    return x0, x0 + bar_width - 1


def _detect_upper_errorbar(
    image: np.ndarray,
    *,
    bar_center: float,
    bar_width: int,
    bar_top: int,
    plot_top: int,
    plot_height: int,
) -> dict[str, Any] | None:
    """Detect the achromatic cap/stem immediately above a raster bar top."""
    half_window = max(2, min(4, int(math.ceil(bar_width * 0.25))))
    center = int(round(bar_center))
    left = max(0, center - half_window)
    right = min(image.shape[1] - 1, center + half_window)
    search_height = max(4, min(12, int(math.ceil(plot_height * 0.08))))
    top = max(plot_top, bar_top - search_height)
    bottom = min(image.shape[0] - 1, bar_top + 1)
    if top >= bottom:
        return None

    crop = image[top : bottom + 1, left : right + 1]
    spread = crop.max(axis=2) - crop.min(axis=2)
    intensity = crop.mean(axis=2)
    row_median = np.median(intensity, axis=1, keepdims=True)
    achromatic = (spread <= 18.0) & (intensity >= 45.0) & (intensity <= 225.0)
    local_contrast = (row_median - intensity >= 18.0) & (intensity >= 35.0) & (intensity <= 235.0)
    candidate = achromatic | local_contrast

    seen = np.zeros(candidate.shape, dtype=bool)
    components: list[list[tuple[int, int]]] = []
    for local_y, local_x in zip(*np.nonzero(candidate), strict=True):
        if seen[local_y, local_x]:
            continue
        stack = [(int(local_y), int(local_x))]
        seen[local_y, local_x] = True
        component: list[tuple[int, int]] = []
        while stack:
            current_y, current_x = stack.pop()
            component.append((current_y, current_x))
            for delta_y in (-1, 0, 1):
                for delta_x in (-1, 0, 1):
                    if delta_y == 0 and delta_x == 0:
                        continue
                    next_y = current_y + delta_y
                    next_x = current_x + delta_x
                    if (
                        0 <= next_y < candidate.shape[0]
                        and 0 <= next_x < candidate.shape[1]
                        and candidate[next_y, next_x]
                        and not seen[next_y, next_x]
                    ):
                        seen[next_y, next_x] = True
                        stack.append((next_y, next_x))
        components.append(component)

    eligible: list[tuple[int, int, int, list[tuple[int, int]]]] = []
    for component in components:
        ys = [top + point[0] for point in component]
        xs = [left + point[1] for point in component]
        upper_extent = bar_top - min(ys)
        if (
            len(component) >= 3
            and max(ys) >= bar_top - 2
            and upper_extent >= 1
            and max(xs) - min(xs) >= 1
        ):
            eligible.append((upper_extent, len(component), -min(ys), component))
    if not eligible:
        return None

    upper_extent, _, _, selected = max(eligible)
    ys = [top + point[0] for point in selected]
    xs = [left + point[1] for point in selected]
    return {
        "upper_extent_px": int(upper_extent),
        "top_y_px": int(min(ys)),
        "bottom_y_px": int(max(ys)),
        "left_x_px": int(min(xs)),
        "right_x_px": int(max(xs)),
        "detection_method": "achromatic_or_contrast_component_above_fill",
    }


def _front_occlusion_evidence(
    image: np.ndarray,
    panel: dict[str, Any],
    group_index: int,
    category_center: float,
    run_bottom: int,
    baseline: float,
    tolerance: float,
    baseline_tolerance: int,
) -> list[dict[str, Any]]:
    groups = panel["groups"]
    current_left, current_right = _bar_window(category_center, groups[group_index])
    current_width = current_right - current_left + 1
    baseline_floor = int(round(baseline)) - baseline_tolerance
    bridge_limit = run_bottom + max(2, baseline_tolerance)
    current_prototype = np.asarray(groups[group_index]["color_rgb"], dtype=np.float64)
    current_crop = image[: int(round(baseline)) + 1, current_left : current_right + 1]
    current_mask = np.linalg.norm(current_crop - current_prototype, axis=2) <= tolerance
    current_contact_run: tuple[int, int] | None = None
    for column in range(current_width):
        column_rows = [int(y) for y in np.flatnonzero(current_mask[:, column])]
        matching_run = next(
            (
                run
                for run in _runs(column_rows)
                if run[0] <= bridge_limit and run[1] >= baseline_floor
            ),
            None,
        )
        if matching_run is not None:
            current_contact_run = matching_run
            break
    evidence: list[dict[str, Any]] = []
    for front_group in groups[group_index + 1 :]:
        front_left, front_right = _bar_window(category_center, front_group)
        overlap_left = max(current_left, front_left)
        overlap_right = min(current_right, front_right)
        overlap_width = overlap_right - overlap_left + 1
        front_width = front_right - front_left + 1
        if overlap_width <= 0 or overlap_width / min(current_width, front_width) < 0.25:
            continue
        if current_contact_run is not None:
            evidence.append(
                {
                    "group": str(front_group["label"]),
                    "evidence_type": "current_color_edge_to_baseline",
                    "candidate_bottom_y_px": run_bottom,
                    "bridge_top_y_px": current_contact_run[0],
                    "bridge_bottom_y_px": current_contact_run[1],
                    "overlap_left_px": overlap_left,
                    "overlap_right_px": overlap_right,
                }
            )
            continue
        prototype = np.asarray(front_group["color_rgb"], dtype=np.float64)
        crop = image[: int(round(baseline)) + 1, overlap_left : overlap_right + 1]
        mask = np.linalg.norm(crop - prototype, axis=2) <= tolerance
        # A still-deeper group can cover most of this foreground bar at the
        # baseline, so continuity needs only a narrow color-consistent edge.
        minimum_count = max(1, int(math.ceil(overlap_width * 0.2)))
        qualifying = [int(y) for y, count in enumerate(mask.sum(axis=1)) if int(count) >= minimum_count]
        touching_runs = [run for run in _runs(qualifying) if run[1] >= baseline_floor]
        bridge_run = next(
            (run for run in touching_runs if run_bottom < run[0] <= bridge_limit),
            None,
        )
        if bridge_run is not None:
            evidence.append(
                {
                    "group": str(front_group["label"]),
                    "evidence_type": "front_group_vertical_bridge",
                    "candidate_bottom_y_px": run_bottom,
                    "bridge_top_y_px": bridge_run[0],
                    "bridge_bottom_y_px": bridge_run[1],
                    "overlap_left_px": overlap_left,
                    "overlap_right_px": overlap_right,
                }
            )
    return evidence


def digitize(source: Path, config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _validate_config(config)
    image = np.asarray(Image.open(source).convert("RGB"), dtype=np.float64)
    height, width = image.shape[:2]
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    default_tolerance = float(config.get("color_tolerance", 28.0))
    default_coverage = float(config.get("min_row_coverage", 0.45))
    default_baseline_tolerance = int(config.get("baseline_tolerance_px", 4))
    detect_errorbars = bool(config.get("detect_errorbars", True))
    if default_tolerance <= 0 or not 0 < default_coverage <= 1 or default_baseline_tolerance < 0:
        raise ValueError("color_tolerance, min_row_coverage, and baseline_tolerance_px are invalid")

    for panel in config["panels"]:
        panel_id = str(panel["id"])
        left, top, right, bottom = [int(round(value)) for value in panel["plot_bbox_px"]]
        if left < 0 or top < 0 or right >= width or bottom >= height:
            raise ValueError(f"panel {panel_id} plot_bbox_px is outside the source image")
        axis = panel["y_axis"]
        baseline = float(axis["pixel_baseline"])
        pixel_top = float(axis["pixel_top"])
        value_min = float(axis["value_min"])
        value_max = float(axis["value_max"])
        units_per_pixel = (value_max - value_min) / (baseline - pixel_top)
        category_labels = panel.get("category_labels") or [str(index + 1) for index in range(len(panel["category_centers_px"]))]
        if len(category_labels) != len(panel["category_centers_px"]):
            raise ValueError(f"panel {panel_id} category_labels must match category_centers_px")
        tolerance = float(panel.get("color_tolerance", default_tolerance))
        coverage = float(panel.get("min_row_coverage", default_coverage))
        baseline_tolerance = int(panel.get("baseline_tolerance_px", default_baseline_tolerance))

        for category_index, (category_label, category_center) in enumerate(zip(category_labels, panel["category_centers_px"], strict=True), start=1):
            for group_index, group in enumerate(panel["groups"]):
                bar_width = max(1, int(round(float(group["width_px"]))))
                bar_center = float(category_center) + float(group["offset_px"])
                x0, x1 = _bar_window(float(category_center), group)
                if x0 < left or x1 > right:
                    raise ValueError(f"panel {panel_id} category {category_label} group {group['label']} window is outside plot_bbox_px")
                prototype = np.asarray(group["color_rgb"], dtype=np.float64)
                crop = image[top : int(round(baseline)) + 1, x0 : x1 + 1]
                distance = np.linalg.norm(crop - prototype, axis=2)
                mask = distance <= tolerance
                row_counts = mask.sum(axis=1)
                group_coverage = float(group.get("min_row_coverage", coverage))
                if not 0 < group_coverage <= 1:
                    raise ValueError(f"group {group['label']} min_row_coverage must be in (0, 1]")
                minimum_count = max(1, int(math.ceil(bar_width * group_coverage)))
                qualifying = [top + index for index, count in enumerate(row_counts) if int(count) >= minimum_count]
                candidate_runs = _runs(qualifying)
                baseline_floor = int(round(baseline)) - baseline_tolerance
                touching = [run for run in candidate_runs if run[1] >= baseline_floor]
                baseline_visibility = str(group.get("baseline_visibility", "visible"))
                baseline_contact_observed = bool(touching)
                occlusion_evidence: list[dict[str, Any]] = []
                minimum_occluded_component_height = max(
                    2 * baseline_tolerance + 1,
                    int(math.ceil((baseline - pixel_top) * 0.04)),
                )
                minimum_occluded_component_height = int(
                    group.get(
                        "min_occluded_component_height_px",
                        minimum_occluded_component_height,
                    )
                )
                if minimum_occluded_component_height < 1:
                    raise ValueError(
                        f"group {group['label']} min_occluded_component_height_px must be at least 1"
                    )
                if touching:
                    run_top, run_bottom = max(
                        touching,
                        key=lambda item: (item[1] - item[0] + 1, item[1]),
                    )
                elif baseline_visibility == "occluded_by_front_groups" and candidate_runs:
                    candidate_top, candidate_bottom = max(
                        candidate_runs,
                        key=lambda item: (item[1] - item[0] + 1, -item[0]),
                    )
                    candidate_height = candidate_bottom - candidate_top + 1
                    occlusion_evidence = _front_occlusion_evidence(
                        image,
                        panel,
                        group_index,
                        float(category_center),
                        candidate_bottom,
                        baseline,
                        tolerance,
                        baseline_tolerance,
                    )
                    if (
                        candidate_height < minimum_occluded_component_height
                        or not bool(group.get("allow_front_group_bridge", False))
                    ):
                        occlusion_evidence = [
                            item
                            for item in occlusion_evidence
                            if item["evidence_type"] == "current_color_edge_to_baseline"
                        ]
                    if not occlusion_evidence:
                        failures.append(
                            {
                                "panel": panel_id,
                                "category": str(category_label),
                                "group": str(group["label"]),
                                "reason": "unverified_front_group_occlusion",
                                "candidate_height_px": candidate_height,
                                "minimum_occluded_component_height_px": minimum_occluded_component_height,
                            }
                        )
                        continue
                    run_top, run_bottom = candidate_top, candidate_bottom
                else:
                    failures.append({"panel": panel_id, "category": str(category_label), "group": str(group["label"]), "reason": "no_color_component_near_baseline"})
                    continue
                value = value_min + (baseline - run_top) * units_per_pixel
                errorbar = (
                    _detect_upper_errorbar(
                        image,
                        bar_center=bar_center,
                        bar_width=bar_width,
                        bar_top=run_top,
                        plot_top=top,
                        plot_height=int(round(baseline)) - top,
                    )
                    if detect_errorbars
                    else None
                )
                run_mask = mask[run_top - top : run_bottom - top + 1]
                run_pixels = crop[run_top - top : run_bottom - top + 1][run_mask]
                mean_rgb = [round(float(item), 3) for item in run_pixels.mean(axis=0)] if run_pixels.size else [float(item) for item in prototype]
                median_coverage = float(np.median(row_counts[run_top - top : run_bottom - top + 1]) / bar_width)
                bottom_contact = max(0.0, 1.0 - max(0.0, baseline - run_bottom) / max(1.0, baseline_tolerance + 1.0))
                confidence = round(max(0.0, min(1.0, 0.7 * median_coverage + 0.3 * bottom_contact)), 4)
                rows.append(
                    {
                        "panel": panel_id,
                        "category": str(category_label),
                        "category_index": category_index,
                        "group": str(group["label"]),
                        "category_center_px": round(float(category_center), 3),
                        "bar_center_px": round(bar_center, 3),
                        "bar_left_px": x0,
                        "bar_right_px": x1,
                        "top_y_px": run_top,
                        "bottom_y_px": run_bottom,
                        "baseline_y_px": baseline,
                        "value": round(value, 6),
                        "pixel_uncertainty": 1.0,
                        "value_uncertainty_from_pixels": round(units_per_pixel, 6),
                        "errorbar_upper_px": errorbar["upper_extent_px"] if errorbar else "",
                        "errorbar_value_from_pixels": round(errorbar["upper_extent_px"] * units_per_pixel, 6) if errorbar else "",
                        "errorbar_detection": json.dumps(errorbar, ensure_ascii=True, separators=(",", ":")) if errorbar else "",
                        "mean_r": mean_rgb[0],
                        "mean_g": mean_rgb[1],
                        "mean_b": mean_rgb[2],
                        "confidence": confidence,
                        "baseline_visibility": baseline_visibility,
                        "baseline_contact_observed": baseline_contact_observed,
                        "occlusion_evidence_groups": "|".join(
                            str(item["group"]) for item in occlusion_evidence
                        ),
                        "occlusion_evidence": json.dumps(
                            occlusion_evidence,
                            ensure_ascii=True,
                            separators=(",", ":"),
                        ),
                        "source_strategy": "digitized_raster",
                    }
                )

    audit = {
        "schema": SCHEMA,
        "source": {"path": source.name, "sha256": _sha256(source), "width_px": width, "height_px": height},
        "status": "pass" if rows and not failures else "partial" if rows else "failed",
        "row_count": len(rows),
        "detected_errorbar_count": sum(1 for row in rows if row.get("errorbar_upper_px") != ""),
        "failures": failures,
        "calibration": config,
        "uncertainty_note": "Central values use the detected fill top; value_uncertainty_from_pixels is the mapped magnitude of plus/minus one source pixel. errorbar_value_from_pixels records only the visible upper raster extent and does not infer SD, SEM, CI, or another statistical definition.",
    }
    return rows, audit


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else ["panel", "category", "group", "value", "source_strategy"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Digitize calibrated grouped bars from a raster image.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--csv-out", type=Path, required=True)
    parser.add_argument("--audit-out", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    rows, audit = digitize(args.source, config)
    write_csv(args.csv_out, rows)
    args.audit_out.parent.mkdir(parents=True, exist_ok=True)
    args.audit_out.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": audit["status"], "rows": len(rows), "csv": str(args.csv_out), "audit": str(args.audit_out)}, ensure_ascii=False, indent=2))
    return 0 if audit["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
