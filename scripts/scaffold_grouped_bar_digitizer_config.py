from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


SCHEMA = "scientificfigure.grouped_bar_digitization.v1"


def _runs(indices: list[int]) -> list[tuple[int, int]]:
    if not indices:
        return []
    result: list[tuple[int, int]] = []
    start = previous = indices[0]
    for value in indices[1:]:
        if value != previous + 1:
            result.append((start, previous))
            start = value
        previous = value
    result.append((start, previous))
    return result


def _center(run: tuple[int, int]) -> float:
    return (run[0] + run[1]) / 2.0


def _median(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot take the median of an empty list")
    return float(statistics.median(values))


def _dark_mask(image: np.ndarray) -> np.ndarray:
    rgb = image.astype(np.float64)
    return (rgb.mean(axis=2) < 125.0) & ((rgb.max(axis=2) - rgb.min(axis=2)) < 95.0)


def _colored_mask(image: np.ndarray) -> np.ndarray:
    rgb = image.astype(np.float64)
    spread = rgb.max(axis=2) - rgb.min(axis=2)
    mean = rgb.mean(axis=2)
    return (mean > 80.0) & (mean < 248.0) & (spread > 8.0)


def _split_touching_run(
    image: np.ndarray,
    run: tuple[int, int],
    top: int,
    bottom: int,
    group_count: int,
    min_bar_width_px: int,
) -> tuple[list[tuple[int, int]], str]:
    start, end = run
    run_width = end - start + 1
    if group_count < 2 or run_width < group_count * min_bar_width_px:
        return [run], "connected_component"

    band_top = max(top, bottom - 12)
    profiles: list[np.ndarray] = []
    for x in range(start, end + 1):
        column = image[band_top:bottom, x : x + 1]
        mask = _colored_mask(column)
        pixels = column[mask]
        if pixels.size:
            profiles.append(np.median(pixels.astype(np.float64), axis=0))
        else:
            profiles.append(column.reshape(-1, 3).astype(np.float64).mean(axis=0))

    transitions = [
        (float(np.linalg.norm(profiles[index + 1] - profiles[index])), start + index)
        for index in range(run_width - 1)
    ]
    boundaries: list[int] = []
    minimum_transition_distance = 12.0
    for strength, candidate in sorted(transitions, reverse=True):
        if strength < minimum_transition_distance:
            continue
        trial = sorted([*boundaries, candidate])
        segment_starts = [start, *[value + 1 for value in trial]]
        segment_ends = [*trial, end]
        if all(
            segment_end - segment_start + 1 >= min_bar_width_px
            for segment_start, segment_end in zip(segment_starts, segment_ends, strict=True)
        ):
            boundaries = trial
        if len(boundaries) == group_count - 1:
            break

    if len(boundaries) == group_count - 1:
        method = "bottom_color_transitions"
    else:
        boundaries = [
            start + int(round(run_width * index / group_count)) - 1
            for index in range(1, group_count)
        ]
        method = "equal_width_fallback"

    segment_starts = [start, *[value + 1 for value in boundaries]]
    segment_ends = [*boundaries, end]
    segments = list(zip(segment_starts, segment_ends, strict=True))
    if len(segments) != group_count or any(
        segment_end - segment_start + 1 < min_bar_width_px
        for segment_start, segment_end in segments
    ):
        return [run], "connected_component"
    return segments, method


def _dominant_color_prototypes(
    image: np.ndarray,
    bbox: list[int],
    group_count: int,
) -> list[np.ndarray]:
    left, top, right, bottom = bbox
    scan_top = min(bottom - 1, top + 17)
    crop = image[scan_top:bottom, left : right + 1]
    pixels = crop[_colored_mask(crop)]
    if len(pixels) < group_count:
        return []
    quantized = (pixels.astype(np.uint16) // 4 * 4 + 2).astype(np.uint8)
    colors, counts = np.unique(quantized, axis=0, return_counts=True)
    selected: list[np.ndarray] = []
    for index in np.argsort(counts)[::-1]:
        candidate = colors[index].astype(np.float64)
        if all(float(np.linalg.norm(candidate - existing)) >= 28.0 for existing in selected):
            selected.append(candidate)
        if len(selected) == group_count:
            break
    return selected


def _detect_color_layer_bars(
    image: np.ndarray,
    bbox: list[int],
    category_runs: list[tuple[int, int]],
    group_count: int,
    min_bar_width_px: int,
    min_col_pixels: int,
) -> list[dict[str, Any]] | None:
    left, top, right, bottom = bbox
    del left, right
    prototypes = _dominant_color_prototypes(image, bbox, group_count)
    if len(prototypes) != group_count:
        return None

    scan_top = min(bottom - 1, top + 17)
    bars_by_category: list[list[dict[str, Any]]] = []
    for run in category_runs:
        x0, x1 = run
        local = image[scan_top:bottom, x0 : x1 + 1].astype(np.float64)
        colored = _colored_mask(local.astype(np.uint8))
        distances = np.stack(
            [np.linalg.norm(local - prototype, axis=2) for prototype in prototypes],
            axis=2,
        )
        nearest = distances.argmin(axis=2)
        nearest_distance = distances.min(axis=2)
        category_bars: list[dict[str, Any]] = []
        for prototype_index, prototype in enumerate(prototypes):
            color_distance_limit = 24.0
            mask = colored & (nearest == prototype_index) & (nearest_distance <= color_distance_limit)
            col_counts = mask.sum(axis=0)
            minimum_pixels = max(2, min_col_pixels // 2)
            hit_columns = [
                x0 + int(index)
                for index, count in enumerate(col_counts)
                if int(count) >= minimum_pixels
            ]
            if not hit_columns:
                return None
            bar_left = min(hit_columns)
            bar_right = max(hit_columns)
            if bar_right - bar_left + 1 < min_bar_width_px:
                return None
            assigned_pixels = local[mask]
            mean_rgb = assigned_pixels.mean(axis=0) if assigned_pixels.size else prototype
            category_bars.append(
                {
                    "left_px": int(bar_left),
                    "right_px": int(bar_right),
                    "center_px": round((bar_left + bar_right) / 2.0, 3),
                    "width_px": int(bar_right - bar_left + 1),
                    "mean_rgb": [int(round(float(value))) for value in mean_rgb],
                    "prototype_index": prototype_index,
                    "prototype_rgb": [int(round(float(value))) for value in prototype],
                    "color_distance_limit": color_distance_limit,
                    "segmentation_method": "color_layer_component",
                }
            )
        bars_by_category.append(category_bars)

    median_centers = [
        _median(
            [
                float(category[prototype_index]["center_px"] - _center(category_runs[index]))
                for index, category in enumerate(bars_by_category)
            ]
        )
        for prototype_index in range(group_count)
    ]
    median_widths = [
        _median(
            [float(category[prototype_index]["width_px"]) for category in bars_by_category]
        )
        for prototype_index in range(group_count)
    ]
    covered_front_counts: list[int] = []
    for candidate_index in range(group_count):
        candidate_left = median_centers[candidate_index] - median_widths[candidate_index] / 2.0
        candidate_right = median_centers[candidate_index] + median_widths[candidate_index] / 2.0
        covered = 0
        for other_index in range(group_count):
            if other_index == candidate_index or median_widths[candidate_index] <= median_widths[other_index]:
                continue
            other_left = median_centers[other_index] - median_widths[other_index] / 2.0
            other_right = median_centers[other_index] + median_widths[other_index] / 2.0
            overlap = max(0.0, min(candidate_right, other_right) - max(candidate_left, other_left))
            substantially_wider = median_widths[candidate_index] >= 1.25 * median_widths[other_index]
            if substantially_wider and overlap >= 0.5:
                covered += 1
        covered_front_counts.append(covered)
    prototype_order = sorted(
        range(group_count),
        key=lambda prototype_index: (
            -covered_front_counts[prototype_index],
            median_centers[prototype_index],
            -median_widths[prototype_index],
            prototype_index,
        ),
    )
    return [
        category[prototype_index]
        for category in bars_by_category
        for prototype_index in prototype_order
    ]


def _baseline_visibility(groups: list[dict[str, Any]]) -> list[str]:
    visibility = ["visible" for _ in groups]
    intervals = [
        (
            float(group["offset_px"]) - float(group["width_px"]) / 2.0,
            float(group["offset_px"]) + float(group["width_px"]) / 2.0,
        )
        for group in groups
    ]
    for back_index, (back_left, back_right) in enumerate(intervals):
        back_width = back_right - back_left
        for front_left, front_right in intervals[back_index + 1 :]:
            overlap = max(0.0, min(back_right, front_right) - max(back_left, front_left))
            front_width = front_right - front_left
            substantial_width_difference = back_width >= 1.25 * front_width
            if (
                overlap / max(1.0, min(back_width, front_width)) >= 0.25
                or (substantial_width_difference and overlap >= 0.5)
            ):
                visibility[back_index] = "occluded_by_front_groups"
                break
    return visibility


def detect_plot_bboxes(image: np.ndarray, panel_count: int) -> list[list[int]]:
    if panel_count < 1:
        raise ValueError("panel_count must be positive")
    height, width = image.shape[:2]
    dark = _dark_mask(image)
    col_threshold = max(20, int(height * 0.42))
    vertical_runs = _runs([int(x) for x in np.flatnonzero(dark.sum(axis=0) >= col_threshold)])
    vertical_centers = [int(round(_center(run))) for run in vertical_runs]
    if len(vertical_centers) == panel_count * 2 - 1 and panel_count > 1:
        widths = [vertical_centers[index + 1] - vertical_centers[index] for index in range(0, len(vertical_centers) - 1, 2)]
        if widths:
            inferred_right = vertical_centers[-1] + int(round(_median([float(width) for width in widths])))
            if inferred_right < width:
                vertical_centers.append(inferred_right)

    candidates: list[list[int]] = []
    min_panel_width = max(20, int(width / max(panel_count * 4, 4)))
    for left, right in zip(vertical_centers, vertical_centers[1:], strict=False):
        if right - left < min_panel_width:
            continue
        span = dark[:, left : right + 1]
        row_threshold = max(8, int((right - left + 1) * 0.35))
        row_runs = _runs([int(y) for y in np.flatnonzero(span.sum(axis=1) >= row_threshold)])
        if len(row_runs) < 2:
            continue
        top = int(round(_center(row_runs[0])))
        bottom = int(round(_center(row_runs[-1])))
        if bottom - top < 20:
            continue
        candidates.append([left, top, right, bottom])

    if len(candidates) < panel_count:
        raise ValueError(
            f"detected {len(candidates)} plot boxes, fewer than requested panel_count={panel_count}; "
            "provide a cleaner crop or use a manual digitizer config"
        )
    candidates = sorted(candidates, key=lambda bbox: (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]), reverse=True)[:panel_count]
    return sorted(candidates, key=lambda bbox: bbox[0])


def detect_panel_bars(
    image: np.ndarray,
    bbox: list[int],
    category_count: int,
    group_count: int,
    min_bar_width_px: int = 3,
    min_col_pixels: int = 6,
) -> tuple[list[dict[str, Any]], list[float], list[float], list[int], list[list[int]]]:
    if category_count < 1 or group_count < 1:
        raise ValueError("category_count and group_count must be positive")
    left, top, right, bottom = bbox
    colored = _colored_mask(image)
    region = colored[top : bottom + 1, left : right + 1]
    bottom_band = colored[max(top, bottom - 12) : bottom + 1, left : right + 1]
    col_counts = region.sum(axis=0)
    bottom_counts = bottom_band.sum(axis=0)
    column_hits = [
        left + int(index)
        for index, (count, base_count) in enumerate(zip(col_counts, bottom_counts, strict=True))
        if int(count) >= min_col_pixels and int(base_count) > 0
    ]
    runs = [run for run in _runs(column_hits) if run[1] - run[0] + 1 >= min_bar_width_px]
    expected = category_count * group_count
    bars: list[dict[str, Any]] = []
    layered_bars = None
    if len(runs) == category_count and group_count > 1:
        layered_bars = _detect_color_layer_bars(
            image,
            bbox,
            runs,
            group_count,
            min_bar_width_px,
            min_col_pixels,
        )
    segmentation_methods: dict[tuple[int, int], str] = {run: "connected_component" for run in runs}
    if layered_bars is not None:
        bars = layered_bars
    elif len(runs) == category_count and group_count > 1:
        split_runs: list[tuple[int, int]] = []
        split_methods: dict[tuple[int, int], str] = {}
        for run in runs:
            segments, method = _split_touching_run(
                image,
                run,
                top,
                bottom,
                group_count,
                min_bar_width_px,
            )
            split_runs.extend(segments)
            split_methods.update({segment: method for segment in segments})
        if len(split_runs) == expected:
            runs = split_runs
            segmentation_methods = split_methods
    if not bars and len(runs) < expected:
        raise ValueError(f"detected {len(runs)} bar runs in bbox {bbox}, fewer than expected {expected}")
    if not bars and len(runs) > expected:
        runs = sorted(runs, key=lambda run: run[1] - run[0] + 1, reverse=True)[:expected]
        runs = sorted(runs, key=_center)

    if not bars:
        for run in runs:
            x0, x1 = run
            local = image[top : bottom + 1, x0 : x1 + 1]
            local_mask = _colored_mask(local)
            pixels = local[local_mask]
            mean_rgb = pixels.mean(axis=0) if pixels.size else local.reshape(-1, 3).mean(axis=0)
            bars.append(
                {
                    "left_px": int(x0),
                    "right_px": int(x1),
                    "center_px": round(_center(run), 3),
                    "width_px": int(x1 - x0 + 1),
                    "mean_rgb": [int(round(float(value))) for value in mean_rgb],
                    "segmentation_method": segmentation_methods.get(run, "connected_component"),
                }
            )

    category_centers: list[float] = []
    offsets_by_group: list[list[float]] = [[] for _ in range(group_count)]
    widths_by_group: list[list[float]] = [[] for _ in range(group_count)]
    rgb_by_group: list[list[list[int]]] = [[] for _ in range(group_count)]
    for category_index in range(category_count):
        chunk = bars[category_index * group_count : (category_index + 1) * group_count]
        category_center = sum(float(bar["center_px"]) for bar in chunk) / len(chunk)
        category_centers.append(category_center)
        for group_index, bar in enumerate(chunk):
            offsets_by_group[group_index].append(float(bar["center_px"]) - category_center)
            widths_by_group[group_index].append(float(bar["width_px"]))
            rgb_by_group[group_index].append(list(bar["mean_rgb"]))

    group_offsets = [_median(values) for values in offsets_by_group]
    group_widths = [max(1, int(round(_median(values)))) for values in widths_by_group]
    group_colors = [
        [int(round(_median([float(rgb[channel]) for rgb in values]))) for channel in range(3)]
        for values in rgb_by_group
    ]
    return bars, category_centers, group_offsets, group_widths, group_colors


def scaffold_config(
    source: Path,
    panel_count: int,
    category_count: int,
    group_labels: list[str],
    panel_ids: list[str] | None = None,
    y_min: float = 0.0,
    y_max: float = 80.0,
    color_tolerance: float = 34.0,
    min_row_coverage: float = 0.45,
    baseline_tolerance_px: int = 4,
) -> tuple[dict[str, Any], dict[str, Any]]:
    image = np.asarray(Image.open(source).convert("RGB"))
    if panel_ids is None:
        panel_ids = [chr(ord("A") + index) for index in range(panel_count)]
    if len(panel_ids) != panel_count:
        raise ValueError("panel_ids must match panel_count")
    if not group_labels:
        raise ValueError("group_labels must not be empty")
    bboxes = detect_plot_bboxes(image, panel_count)
    panels: list[dict[str, Any]] = []
    detection: list[dict[str, Any]] = []
    for panel_id, bbox in zip(panel_ids, bboxes, strict=True):
        bars, centers, offsets, widths, colors = detect_panel_bars(image, bbox, category_count, len(group_labels))
        groups = [
            {
                "label": label,
                "color_rgb": colors[index],
                "offset_px": round(offsets[index], 3),
                "width_px": widths[index],
            }
            for index, label in enumerate(group_labels)
        ]
        for group, baseline_visibility in zip(groups, _baseline_visibility(groups), strict=True):
            group["baseline_visibility"] = baseline_visibility
        left, top, right, bottom = bbox
        panels.append(
            {
                "id": panel_id,
                "plot_bbox_px": [left, top, right, bottom],
                "category_centers_px": [round(value, 3) for value in centers],
                "category_labels": [str(index + 1) for index in range(category_count)],
                "y_axis": {"pixel_baseline": bottom, "pixel_top": top, "value_min": y_min, "value_max": y_max},
                "groups": groups,
            }
        )
        detection.append({"panel": panel_id, "plot_bbox_px": bbox, "bars": bars})

    config = {
        "schema": SCHEMA,
        "color_tolerance": color_tolerance,
        "min_row_coverage": min_row_coverage,
        "baseline_tolerance_px": baseline_tolerance_px,
        "panels": panels,
    }
    fallback_segments = [
        {
            "panel": item["panel"],
            "left_px": bar["left_px"],
            "right_px": bar["right_px"],
        }
        for item in detection
        for bar in item["bars"]
        if bar.get("segmentation_method") == "equal_width_fallback"
    ]
    audit_status = "review_required" if fallback_segments else "pass"
    config["calibration_status"] = audit_status
    config["unresolved_segments"] = fallback_segments
    audit = {
        "schema": "scientificfigure.grouped_bar_config_scaffold.v1",
        "source": {"path": source.name, "width_px": int(image.shape[1]), "height_px": int(image.shape[0])},
        "status": audit_status,
        "detected_panel_count": len(bboxes),
        "category_count": category_count,
        "group_labels": group_labels,
        "detection": detection,
        "fallback_segments": fallback_segments,
        "notes": [
            "Plot boxes are inferred from dark frame/spine pixels.",
            "Bar offsets, widths, and colors are inferred independently for every panel.",
            "Equal-width fallback segments require manual review and prevent a passing scaffold audit.",
            "Review and adjust the JSON before treating digitized values as quantitative evidence.",
        ],
    }
    return config, audit


def _parse_csv_labels(value: str, name: str) -> list[str]:
    labels = [item.strip() for item in value.split(",") if item.strip()]
    if not labels:
        raise argparse.ArgumentTypeError(f"{name} must contain at least one label")
    return labels


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold panel-specific grouped-bar digitizer JSON from a raster chart or small multiple.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--audit-out", type=Path, required=True)
    parser.add_argument("--panel-count", type=int, default=1)
    parser.add_argument("--panel-ids", type=lambda value: _parse_csv_labels(value, "panel_ids"))
    parser.add_argument("--category-count", type=int, required=True)
    parser.add_argument("--group-labels", type=lambda value: _parse_csv_labels(value, "group_labels"), required=True)
    parser.add_argument("--y-min", type=float, default=0.0)
    parser.add_argument("--y-max", type=float, default=80.0)
    parser.add_argument("--color-tolerance", type=float, default=34.0)
    parser.add_argument("--min-row-coverage", type=float, default=0.45)
    parser.add_argument("--baseline-tolerance-px", type=int, default=4)
    args = parser.parse_args()

    config, audit = scaffold_config(
        source=args.source,
        panel_count=args.panel_count,
        category_count=args.category_count,
        group_labels=args.group_labels,
        panel_ids=args.panel_ids,
        y_min=args.y_min,
        y_max=args.y_max,
        color_tolerance=args.color_tolerance,
        min_row_coverage=args.min_row_coverage,
        baseline_tolerance_px=args.baseline_tolerance_px,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.audit_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.audit_out.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": audit["status"], "json": str(args.json_out), "audit": str(args.audit_out)}, ensure_ascii=False, indent=2))
    return 0 if audit["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
