from __future__ import annotations

"""Lightweight rendered-figure checks used before packaging a deliverable."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def inspect_raster(width: int, height: int, ink_pixels: int) -> dict[str, Any]:
    """Return deterministic canvas checks without making scientific-validity claims."""
    failures: list[str] = []
    if width < 16 or height < 16:
        failures.append("canvas_too_small")
    if ink_pixels <= 0:
        failures.append("blank_canvas")
    return {
        "schema": "sciplot.figure_preflight.v1",
        "status": "pass" if not failures else "failed",
        "canvas_px": [width, height],
        "ink_pixels": ink_pixels,
        "checks": {
            "minimum_canvas": width >= 16 and height >= 16,
            "non_blank": ink_pixels > 0,
        },
        "failures": failures,
        "scope": "rendered_canvas_only",
        "scientific_data_validated": False,
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pixels(image: Any) -> Any:
    """Use the current Pillow iterator while retaining support for older releases."""
    getter = getattr(image, "get_flattened_data", None)
    return getter() if callable(getter) else image.getdata()


def preflight_png(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - dependency failure is environment-specific
        raise RuntimeError("Pillow is required to preflight PNG output") from exc
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        ink_pixels = sum(1 for red, green, blue in _pixels(rgb) if min(red, green, blue) < 245)
    report = inspect_raster(width, height, ink_pixels)
    report["input"] = {"path": str(path), "sha256": _file_sha256(path)}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a rendered figure canvas before delivery.")
    parser.add_argument("--png", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not args.png.is_file():
        report = {"schema": "sciplot.figure_preflight.v1", "status": "failed", "failures": ["missing_png"]}
    else:
        report = preflight_png(args.png)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
