from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageColor


def _portable_path(path: Path, project_root: Path | None) -> str:
    if project_root is None:
        return str(path)
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _quad(value: Any, name: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{name} must contain four pixel coordinates")
    return [int(round(float(item))) for item in value]


def _pair(value: Any, name: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must contain two pixel coordinates")
    return [int(round(float(item))) for item in value]


def _rgb_triplet(value: Any, name: str) -> np.ndarray:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{name} must contain three RGB values")
    result = np.asarray([int(item) for item in value], dtype=np.int16)
    if bool(np.any(result < 0)) or bool(np.any(result > 255)):
        raise ValueError(f"{name} RGB values must be between 0 and 255")
    return result


def _analyze_axis_spines(pixels: np.ndarray, config: dict[str, Any]) -> dict[str, Any]:
    expected_origin = _pair(config.get("expected_origin_px"), "axis_spines.expected_origin_px")
    expected_right = int(config.get("expected_horizontal_end_px"))
    expected_top = int(config.get("expected_vertical_top_px"))
    search_radius = int(config.get("search_radius_px", 2))
    max_position_error = int(config.get("max_position_error_px", 1))
    maximum = _rgb_triplet(config.get("max_rgb", [200, 200, 200]), "axis_spines.max_rgb")
    min_horizontal = float(config.get("min_horizontal_coverage_ratio", 0.95))
    min_vertical = float(config.get("min_vertical_coverage_ratio", 0.95))
    if search_radius < 0 or max_position_error < 0:
        raise ValueError("axis_spines search and position tolerances must be non-negative")
    if not 0 <= min_horizontal <= 1 or not 0 <= min_vertical <= 1:
        raise ValueError("axis_spines coverage ratios must be between zero and one")

    height, width, _ = pixels.shape
    expected_x, expected_y = expected_origin
    if not (0 <= expected_top <= expected_y < height and 0 <= expected_x <= expected_right < width):
        raise ValueError("axis_spines expected coordinates are outside the image")
    dark = np.all(pixels <= maximum, axis=2)

    horizontal_candidates: list[tuple[float, int]] = []
    for y in range(max(0, expected_y - search_radius), min(height - 1, expected_y + search_radius) + 1):
        coverage = float(np.mean(dark[y, expected_x : expected_right + 1]))
        horizontal_candidates.append((coverage, y))
    vertical_candidates: list[tuple[float, int]] = []
    for x in range(max(0, expected_x - search_radius), min(width - 1, expected_x + search_radius) + 1):
        coverage = float(np.mean(dark[expected_top : expected_y + 1, x]))
        vertical_candidates.append((coverage, x))

    horizontal_coverage, actual_y = max(
        horizontal_candidates,
        key=lambda item: (item[0], -abs(item[1] - expected_y)),
    )
    vertical_coverage, actual_x = max(
        vertical_candidates,
        key=lambda item: (item[0], -abs(item[1] - expected_x)),
    )
    failures: list[str] = []
    if horizontal_coverage < min_horizontal:
        failures.append("horizontal_axis_coverage_below_minimum")
    if vertical_coverage < min_vertical:
        failures.append("vertical_axis_coverage_below_minimum")
    if abs(actual_x - expected_x) > max_position_error or abs(actual_y - expected_y) > max_position_error:
        failures.append("axis_origin_position_error_exceeds_tolerance")

    return {
        "status": "pass" if not failures else "failed",
        "expected_origin_px": expected_origin,
        "actual_origin_px": [int(actual_x), int(actual_y)],
        "origin_delta_px": [int(actual_x - expected_x), int(actual_y - expected_y)],
        "expected_horizontal_extent_px": [expected_x, expected_right],
        "expected_vertical_extent_px": [expected_top, expected_y],
        "horizontal_coverage_ratio": round(horizontal_coverage, 6),
        "vertical_coverage_ratio": round(vertical_coverage, 6),
        "min_horizontal_coverage_ratio": min_horizontal,
        "min_vertical_coverage_ratio": min_vertical,
        "max_position_error_px": max_position_error,
        "failure_reasons": failures,
    }


def _analyze_region(pixels: np.ndarray, region: dict[str, Any]) -> dict[str, Any]:
    expected = _quad(region.get("expected_bbox_px"), "expected_bbox_px")
    selector = region.get("selector")
    if not isinstance(selector, dict):
        raise ValueError("plot-geometry region requires a selector object")

    minimum = _rgb_triplet(selector.get("min_rgb", [0, 0, 0]), "selector.min_rgb")
    maximum = _rgb_triplet(selector.get("max_rgb", [255, 255, 255]), "selector.max_rgb")
    if bool(np.any(minimum > maximum)):
        raise ValueError("selector.min_rgb cannot exceed selector.max_rgb")
    background = np.asarray(ImageColor.getrgb(str(selector.get("background", "#ffffff"))), dtype=np.int16)
    min_background_distance = int(selector.get("min_background_distance", 1))
    min_channel_spread = int(selector.get("min_channel_spread", 0))
    if min_background_distance < 0 or min_channel_spread < 0:
        raise ValueError("selector distance and channel spread must be non-negative")

    height, width, _ = pixels.shape
    search = region.get("search_bbox_px", [0, 0, width - 1, height - 1])
    left, top, right, bottom = _quad(search, "search_bbox_px")
    left, top = max(0, left), max(0, top)
    right, bottom = min(width - 1, right), min(height - 1, bottom)
    if right < left or bottom < top:
        raise ValueError("search_bbox_px is outside the image")

    crop = pixels[top : bottom + 1, left : right + 1]
    within_range = np.all((crop >= minimum) & (crop <= maximum), axis=2)
    channel_spread = crop.max(axis=2) - crop.min(axis=2)
    background_distance = np.max(np.abs(crop - background), axis=2)
    mask = within_range & (channel_spread >= min_channel_spread) & (background_distance >= min_background_distance)
    min_column_matches = int(selector.get("min_column_matches", 1))
    min_row_matches = int(selector.get("min_row_matches", 1))
    if min_column_matches < 1 or min_row_matches < 1:
        raise ValueError("selector row and column match thresholds must be positive")
    columns = np.where(mask.sum(axis=0) >= min_column_matches)[0]
    rows = np.where(mask.sum(axis=1) >= min_row_matches)[0]

    failures: list[str] = []
    if not len(columns) or not len(rows):
        actual = None
        deltas = None
        failures.append("no_matching_plot_region_pixels")
    else:
        actual = [
            int(columns.min()) + left,
            int(rows.min()) + top,
            int(columns.max()) + left,
            int(rows.max()) + top,
        ]
        deltas = [actual[index] - expected[index] for index in range(4)]
        tolerance = int(region.get("max_edge_error_px", 1))
        if tolerance < 0:
            raise ValueError("max_edge_error_px must be non-negative")
        if any(abs(delta) > tolerance for delta in deltas):
            failures.append("plot_bbox_edge_error_exceeds_tolerance")

    axis_report = None
    axis_config = region.get("axis_spines")
    if axis_config is not None:
        if not isinstance(axis_config, dict):
            raise ValueError("axis_spines must be an object")
        axis_report = _analyze_axis_spines(pixels, axis_config)
        if axis_report["status"] != "pass":
            failures.append("axis_spines_failed")

    result = {
        "id": str(region.get("id", "plot_region")),
        "status": "pass" if not failures else "failed",
        "expected_bbox_px": expected,
        "actual_bbox_px": actual,
        "edge_deltas_px": deltas,
        "expected_origin_px": [expected[0], expected[3]],
        "actual_origin_px": [actual[0], actual[3]] if actual else None,
        "max_edge_error_px": int(region.get("max_edge_error_px", 1)),
        "matching_pixel_count": int(mask.sum()),
        "qualified_column_count": int(len(columns)),
        "qualified_row_count": int(len(rows)),
        "failure_reasons": failures,
    }
    if axis_report is not None:
        result["axis_spines"] = axis_report
    return result


def analyze_plot_geometry(
    image_path: Path | str,
    regions: list[dict[str, Any]],
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    image_path = Path(image_path)
    if not regions:
        raise ValueError("plot-geometry safety requires at least one region")
    with Image.open(image_path) as source:
        pixels = np.asarray(source.convert("RGB"), dtype=np.int16)
    reports = [_analyze_region(pixels, region) for region in regions]
    failed = [report["id"] for report in reports if report["status"] != "pass"]
    return {
        "schema": "scientificfigure.plot_geometry_safety.v1",
        "status": "pass" if not failed else "failed",
        "image": _portable_path(image_path, project_root),
        "width_px": int(pixels.shape[1]),
        "height_px": int(pixels.shape[0]),
        "failed_regions": failed,
        "regions": reports,
        "scope": "declared_plot_region_pixel_bbox_guard",
    }


def _regions_from_spec(path: Path) -> list[dict[str, Any]]:
    spec = json.loads(path.read_text(encoding="utf-8-sig"))
    policy = spec.get("qa_policy", {}).get("plot_geometry_safety", {})
    regions = policy.get("regions", []) if isinstance(policy, dict) else []
    if not isinstance(regions, list):
        raise ValueError("qa_policy.plot_geometry_safety.regions must be an array")
    return regions


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate plot-region position on a fixed raster canvas.")
    parser.add_argument("--image", required=True, type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--spec", type=Path)
    source.add_argument("--regions-json", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    try:
        if args.spec:
            regions = _regions_from_spec(args.spec)
        else:
            payload = json.loads(args.regions_json.read_text(encoding="utf-8-sig"))
            regions = payload.get("regions", payload) if isinstance(payload, dict) else payload
        report = analyze_plot_geometry(args.image, regions, project_root=args.project_root)
    except Exception as exc:
        report = {
            "schema": "scientificfigure.plot_geometry_safety.v1",
            "status": "failed",
            "image": _portable_path(args.image, args.project_root),
            "failure_type": "plot_geometry_input_or_read_error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
