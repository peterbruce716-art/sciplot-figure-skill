from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageColor


VALID_EDGES = ("top", "right", "bottom", "left")


def _portable_path(path: Path, project_root: Path | None) -> str:
    if project_root is None:
        return str(path)
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _normalize_edges(required_edges: Iterable[str]) -> tuple[str, ...]:
    edges = tuple(dict.fromkeys(str(edge).strip().lower() for edge in required_edges if str(edge).strip()))
    unknown = sorted(set(edges) - set(VALID_EDGES))
    if unknown:
        raise ValueError(f"Unknown canvas edges: {', '.join(unknown)}")
    return edges


def _ink_count(region: Image.Image, background: tuple[int, int, int], tolerance: int) -> int:
    pixels = region.load()
    return sum(
        1
        for y in range(region.height)
        for x in range(region.width)
        if max(
            abs(pixels[x, y][0] - background[0]),
            abs(pixels[x, y][1] - background[1]),
            abs(pixels[x, y][2] - background[2]),
        )
        > tolerance
    )


def analyze_canvas(
    image_path: Path | str,
    *,
    margin_px: int = 5,
    background: str = "#ffffff",
    tolerance: int = 10,
    required_edges: Iterable[str] = VALID_EDGES,
    project_root: Path | None = None,
) -> dict[str, Any]:
    image_path = Path(image_path)
    if margin_px < 1:
        raise ValueError("margin_px must be at least 1")
    if not 0 <= tolerance <= 255:
        raise ValueError("tolerance must be between 0 and 255")
    edges_required = _normalize_edges(required_edges)
    background_rgb = ImageColor.getrgb(background)

    with Image.open(image_path) as source:
        rgba = source.convert("RGBA")
        backdrop = Image.new("RGBA", rgba.size, (*background_rgb, 255))
        image = Image.alpha_composite(backdrop, rgba).convert("RGB")

    width, height = image.size
    if margin_px * 2 >= min(width, height):
        raise ValueError("margin_px is too large for the image dimensions")

    boxes = {
        "top": (0, 0, width, margin_px),
        "right": (width - margin_px, 0, width, height),
        "bottom": (0, height - margin_px, width, height),
        "left": (0, 0, margin_px, height),
    }
    edge_reports: dict[str, dict[str, Any]] = {}
    failed_edges: list[str] = []
    for edge in VALID_EDGES:
        region = image.crop(boxes[edge])
        ink_pixels = _ink_count(region, background_rgb, tolerance)
        required = edge in edges_required
        clear = ink_pixels == 0
        if required and not clear:
            failed_edges.append(edge)
        edge_reports[edge] = {
            "required": required,
            "clear": clear,
            "ink_pixels": ink_pixels,
            "ink_fraction": round(ink_pixels / (region.width * region.height), 8),
        }

    return {
        "schema": "scientificfigure.canvas_safety.v1",
        "status": "pass" if not failed_edges else "failed",
        "image": _portable_path(image_path, project_root),
        "width_px": width,
        "height_px": height,
        "margin_px": margin_px,
        "background": "#%02x%02x%02x" % background_rgb,
        "tolerance": tolerance,
        "required_edges": list(edges_required),
        "failed_edges": failed_edges,
        "edges": edge_reports,
        "scope": "outer_pixel_band_guard_not_text_semantic_validation",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail when fixed-canvas content enters a required outer safety margin.")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--margin-px", type=int, default=5)
    parser.add_argument("--background", default="#ffffff")
    parser.add_argument("--tolerance", type=int, default=10)
    parser.add_argument(
        "--require-edges",
        default=",".join(VALID_EDGES),
        help="Comma-separated required blank edges. Use an empty value for intentional full bleed.",
    )
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    try:
        report = analyze_canvas(
            args.image,
            margin_px=args.margin_px,
            background=args.background,
            tolerance=args.tolerance,
            required_edges=args.require_edges.split(",") if args.require_edges else (),
            project_root=args.project_root,
        )
    except Exception as exc:
        report = {
            "schema": "scientificfigure.canvas_safety.v1",
            "status": "failed",
            "image": _portable_path(args.image, args.project_root),
            "failure_type": "canvas_safety_input_or_read_error",
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
