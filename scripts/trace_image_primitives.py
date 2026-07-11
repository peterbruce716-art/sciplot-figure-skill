from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw


def nonwhite_ratio(img: Image.Image) -> float:
    arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
    return float(np.mean(np.any(arr < 245, axis=2)))


def iter_runs(arr: np.ndarray):
    height, width = arr.shape[:2]
    for y in range(height):
        x0 = 0
        row = arr[y]
        while x0 < width:
            color = tuple(int(v) for v in row[x0])
            x1 = x0 + 1
            while x1 < width and tuple(int(v) for v in row[x1]) == color:
                x1 += 1
            yield x0, y, x1 - x0, color
            x0 = x1


def write_svg_from_runs(source: Image.Image, path: Path) -> int:
    rgb = source.convert("RGB")
    arr = np.asarray(rgb, dtype=np.uint8)
    width, height = rgb.size
    rect_count = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n')
        f.write('<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>\n')
        for x, y, run_width, color in iter_runs(arr):
            if color == (255, 255, 255):
                continue
            fill = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            f.write(f'<rect x="{x}" y="{y}" width="{run_width}" height="1" fill="{fill}"/>\n')
            rect_count += 1
        f.write("</svg>\n")
    return rect_count


def draw_png_from_runs(source: Image.Image, path: Path) -> Image.Image:
    rgb = source.convert("RGB")
    arr = np.asarray(rgb, dtype=np.uint8)
    rebuilt = Image.new("RGB", rgb.size, "white")
    draw = ImageDraw.Draw(rebuilt)
    for x, y, run_width, color in iter_runs(arr):
        if color == (255, 255, 255):
            continue
        draw.rectangle([x, y, x + run_width - 1, y], fill=color)
    rebuilt.save(path)
    return rebuilt


def score_pair(source: Image.Image, actual: Image.Image) -> dict[str, Any]:
    source = source.convert("RGB")
    actual = actual.convert("RGB")
    if actual.size != source.size:
        actual = actual.resize(source.size, Image.Resampling.NEAREST)
    src_arr = np.asarray(source, dtype=np.float32) / 255.0
    act_arr = np.asarray(actual, dtype=np.float32) / 255.0
    diff = src_arr - act_arr
    return {
        "source_width": source.width,
        "source_height": source.height,
        "actual_width": actual.width,
        "actual_height": actual.height,
        "mae_0_1": float(np.mean(np.abs(diff))),
        "rmse_0_1": float(math.sqrt(float(np.mean(diff * diff)))),
        "source_nonwhite_ratio": nonwhite_ratio(source),
        "actual_nonwhite_ratio": nonwhite_ratio(actual),
        "nonwhite_delta": abs(nonwhite_ratio(source) - nonwhite_ratio(actual)),
        "exact_pixel_match": ImageChops.difference(source, actual).getbbox() is None,
    }


def trace_image(source_path: Path, out_dir: Path, stem: str) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(source_path).convert("RGB")
    png_path = out_dir / f"{stem}_trace_primitives.png"
    svg_path = out_dir / f"{stem}_trace_primitives.svg"
    pdf_path = out_dir / f"{stem}_trace_primitives.pdf"
    rebuilt = draw_png_from_runs(source, png_path)
    rect_count = write_svg_from_runs(source, svg_path)
    rebuilt.save(pdf_path, "PDF", resolution=300.0)
    score = score_pair(source, rebuilt)
    return {
        "schema": "scientificfigure.trace_primitives.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "reconstruction_mode": "pixel_trace",
        "source": str(source_path),
        "png": str(png_path),
        "svg": str(svg_path),
        "pdf": str(pdf_path),
        "svg_rect_primitives": rect_count,
        "pixel_source_as_background_used": False,
        "source_trace_primitives_used": True,
        "semantic_data_recovered": False,
        "scientific_objects_editable": False,
        "semantic_scientific_reconstruction": False,
        "visual_exact": bool(score["exact_pixel_match"]),
        "score": score,
        "status": "visual_trace_pass" if score["exact_pixel_match"] else "visual_not_strict",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert a source figure crop to run-length primitive PNG/SVG/PDF.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--stem", default=None)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    stem = args.stem or args.source.stem
    manifest = trace_image(args.source, args.out_dir, stem)
    json_out = args.json_out or args.out_dir / f"{stem}_trace_manifest.json"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "visual_trace_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
