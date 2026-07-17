from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFont


def _portable_path(path: Path, project_root: Path | None) -> str:
    if project_root is None:
        return str(path)
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _pixel_box(region: dict[str, Any], width: int, height: int) -> tuple[int, int, int, int]:
    if "bbox_px" in region:
        values = region["bbox_px"]
        if not isinstance(values, list) or len(values) != 4:
            raise ValueError("bbox_px must contain [left, top, right, bottom]")
        left, top, right, bottom = (int(round(float(value))) for value in values)
    else:
        values = region.get("bbox_normalized")
        if not isinstance(values, list) or len(values) != 4:
            raise ValueError("region requires bbox_px or bbox_normalized")
        x, y, box_width, box_height = (float(value) for value in values)
        left = int(round(x * width))
        top = int(round(y * height))
        right = int(round((x + box_width) * width))
        bottom = int(round((y + box_height) * height))
    left, top = max(0, left), max(0, top)
    right, bottom = min(width, right), min(height, bottom)
    if right - left < 3 or bottom - top < 3:
        raise ValueError("boxed-text region is outside the image or too small")
    return left, top, right, bottom


def _matches_color(pixel: tuple[int, int, int], target: tuple[int, int, int], tolerance: int) -> bool:
    return max(abs(pixel[index] - target[index]) for index in range(3)) <= tolerance


def _upper_ink_fraction(points: list[tuple[int, int]]) -> float:
    top = min(y for _, y in points)
    bottom = max(y for _, y in points)
    midpoint = top + (bottom - top + 1) / 2
    return sum(1 for _, y in points if y < midpoint) / len(points)


def _reference_glyph_metrics(region: dict[str, Any]) -> dict[str, Any]:
    from matplotlib.font_manager import FontProperties, findfont

    text = str(region.get("text", ""))
    family = str(region.get("font_family", ""))
    size_px = int(region.get("font_size_px", 0))
    if not text or not family or size_px < 1:
        raise ValueError("reference glyph check requires text, font_family, and font_size_px")
    weight = str(region.get("font_weight", "normal"))
    font_path = findfont(FontProperties(family=family, weight=weight), fallback_to_default=False)
    font = ImageFont.truetype(font_path, size_px)
    probe = Image.new("L", (max(64, size_px * max(4, len(text) * 2)), max(64, size_px * 4)), 0)
    draw = ImageDraw.Draw(probe)
    bbox = draw.textbbox((0, 0), text, font=font)
    origin = (4 - bbox[0], 4 - bbox[1])
    draw.text(origin, text, fill=255, font=font)
    pixels = probe.load()
    points = [(x, y) for y in range(probe.height) for x in range(probe.width) if pixels[x, y] > 24]
    if not points:
        raise ValueError("reference glyph rendered no ink")
    return {
        "reference_font_file": Path(font_path).name,
        "reference_ink_height_px": max(y for _, y in points) - min(y for _, y in points) + 1,
        "reference_upper_ink_fraction": round(_upper_ink_fraction(points), 6),
    }


def _analyze_region(image: Image.Image, region: dict[str, Any]) -> dict[str, Any]:
    left, top, right, bottom = _pixel_box(region, image.width, image.height)
    inset = int(region.get("border_inset_px", 3))
    if inset < 1 or right - left <= inset * 2 or bottom - top <= inset * 2:
        raise ValueError("border_inset_px leaves no text-search area")
    tolerance = int(region.get("color_tolerance", 60))
    if not 0 <= tolerance <= 255:
        raise ValueError("color_tolerance must be between 0 and 255")
    target = ImageColor.getrgb(str(region.get("text_color", "#000000")))
    pixels = image.load()
    ink = [
        (x, y)
        for y in range(top + inset, bottom - inset)
        for x in range(left + inset, right - inset)
        if _matches_color(pixels[x, y], target, tolerance)
    ]

    failure_reasons: list[str] = []
    if not ink:
        metrics = {"ink_height_px": 0, "ink_width_px": 0, "top_padding_px": 0, "bottom_padding_px": 0}
        failure_reasons.append("no_matching_text_ink")
    else:
        ink_left = min(x for x, _ in ink)
        ink_right = max(x for x, _ in ink)
        ink_top = min(y for _, y in ink)
        ink_bottom = max(y for _, y in ink)
        metrics = {
            "ink_height_px": ink_bottom - ink_top + 1,
            "ink_width_px": ink_right - ink_left + 1,
            "top_padding_px": ink_top - top,
            "bottom_padding_px": bottom - 1 - ink_bottom,
            "upper_ink_fraction": round(_upper_ink_fraction(ink), 6),
        }
        if metrics["ink_height_px"] < int(region.get("min_ink_height_px", 1)):
            failure_reasons.append("ink_height_below_minimum")
        if metrics["top_padding_px"] < int(region.get("min_top_padding_px", 0)):
            failure_reasons.append("top_padding_below_minimum")
        if metrics["bottom_padding_px"] < int(region.get("min_bottom_padding_px", 0)):
            failure_reasons.append("bottom_padding_below_minimum")

        if region.get("reference_glyph_check", False):
            try:
                reference = _reference_glyph_metrics(region)
                height_ratio = metrics["ink_height_px"] / reference["reference_ink_height_px"]
                upper_ratio = metrics["upper_ink_fraction"] / max(reference["reference_upper_ink_fraction"], 1e-9)
                metrics.update(reference)
                metrics["reference_height_ratio"] = round(height_ratio, 6)
                metrics["upper_ink_profile_ratio"] = round(upper_ratio, 6)
                if height_ratio < float(region.get("min_reference_height_ratio", 0.85)):
                    failure_reasons.append("reference_height_ratio_below_minimum")
                if upper_ratio < float(region.get("min_upper_ink_profile_ratio", 0.65)):
                    failure_reasons.append("upper_ink_profile_below_minimum")
            except Exception as exc:
                metrics["reference_error"] = f"{type(exc).__name__}: {exc}"
                failure_reasons.append("font_reference_unavailable")

    return {
        "id": str(region.get("id", "boxed_text")),
        "status": "pass" if not failure_reasons else "failed",
        "bbox_px": [left, top, right, bottom],
        **metrics,
        "failure_reasons": failure_reasons,
    }


def analyze_boxed_text(
    image_path: Path | str,
    regions: list[dict[str, Any]],
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    image_path = Path(image_path)
    if not regions:
        raise ValueError("boxed-text safety requires at least one region")
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    reports = [_analyze_region(image, region) for region in regions]
    failed = [report["id"] for report in reports if report["status"] != "pass"]
    return {
        "schema": "scientificfigure.boxed_text_safety.v1",
        "status": "pass" if not failed else "failed",
        "image": _portable_path(image_path, project_root),
        "width_px": image.width,
        "height_px": image.height,
        "failed_regions": failed,
        "regions": reports,
        "scope": "declared_box_text_ink_height_and_vertical_padding_guard",
    }


def _regions_from_spec(path: Path) -> list[dict[str, Any]]:
    spec = json.loads(path.read_text(encoding="utf-8-sig"))
    policy = spec.get("qa_policy", {}).get("boxed_text_safety", {})
    regions = policy.get("regions", []) if isinstance(policy, dict) else []
    if not isinstance(regions, list):
        raise ValueError("qa_policy.boxed_text_safety.regions must be an array")
    return regions


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate declared text ink inside annotation boxes.")
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
        report = analyze_boxed_text(args.image, regions, project_root=args.project_root)
    except Exception as exc:
        report = {
            "schema": "scientificfigure.boxed_text_safety.v1",
            "status": "failed",
            "image": _portable_path(args.image, args.project_root),
            "failure_type": "boxed_text_input_or_read_error",
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
