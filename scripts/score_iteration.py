from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from portable_paths import portable_path

try:
    from skimage.metrics import structural_similarity
except Exception:  # pragma: no cover - dependency is optional at import time.
    structural_similarity = None


def _nonwhite_ratio(img: Image.Image) -> float:
    arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
    return float(np.mean(np.any(arr < 245, axis=2)))


def _content_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
    mask = np.any(rgb < 245, axis=2)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def _bbox_error(source_bbox: tuple[int, int, int, int] | None, actual_bbox: tuple[int, int, int, int] | None, width: int, height: int) -> float | None:
    if source_bbox is None or actual_bbox is None:
        return None
    denom = max(1.0, math.hypot(width, height))
    return float(sum(abs(a - b) for a, b in zip(source_bbox, actual_bbox)) / (4.0 * denom))


def _shift(source_bbox: tuple[int, int, int, int] | None, actual_bbox: tuple[int, int, int, int] | None) -> dict[str, float] | None:
    if source_bbox is None or actual_bbox is None:
        return None
    src_cx = (source_bbox[0] + source_bbox[2]) / 2.0
    src_cy = (source_bbox[1] + source_bbox[3]) / 2.0
    act_cx = (actual_bbox[0] + actual_bbox[2]) / 2.0
    act_cy = (actual_bbox[1] + actual_bbox[3]) / 2.0
    return {"dx_px": float(act_cx - src_cx), "dy_px": float(act_cy - src_cy)}


def _edge_image(img: Image.Image) -> Image.Image:
    return img.convert("L").filter(ImageFilter.FIND_EDGES)


def _similarity_from_error(value: float | None, scale: float = 1.0) -> float:
    if value is None:
        return 0.0
    return float(max(0.0, min(1.0, 1.0 - value / max(scale, 1e-9))))


def _write_comparisons(src_cmp: Image.Image, act_cmp: Image.Image, comparison_dir: Path, *, project_root: Path | None = None) -> dict[str, str]:
    comparison_dir.mkdir(parents=True, exist_ok=True)
    diff = ImageChops.difference(src_cmp, act_cmp)
    overlay = Image.blend(src_cmp, act_cmp, 0.5)
    src_edge = _edge_image(src_cmp).convert("RGB")
    act_edge = _edge_image(act_cmp).convert("RGB")
    edge_diff = ImageChops.difference(src_edge, act_edge)
    outputs = {
        "source_common": comparison_dir / "source_common.png",
        "render_common": comparison_dir / "render_common.png",
        "difference": comparison_dir / "difference.png",
        "overlay_50": comparison_dir / "overlay_50.png",
        "edge_difference": comparison_dir / "edge_difference.png",
    }
    src_cmp.save(outputs["source_common"])
    act_cmp.save(outputs["render_common"])
    diff.save(outputs["difference"])
    overlay.save(outputs["overlay_50"])
    edge_diff.save(outputs["edge_difference"])
    return {key: portable_path(value, project_root) if project_root else str(value) for key, value in outputs.items()}


def _padded_canvases(src: Image.Image, act: Image.Image) -> tuple[Image.Image, Image.Image]:
    canvas_width = max(src.width, act.width)
    canvas_height = max(src.height, act.height)
    src_canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    act_canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    src_canvas.paste(src, (0, 0))
    act_canvas.paste(act, (0, 0))
    return src_canvas, act_canvas


def load_qa_regions_from_spec(spec_path: Path | None) -> dict[str, Any] | None:
    if spec_path is None:
        return None
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    regions = spec.get("qa_regions")
    return regions if isinstance(regions, dict) else None


def _region_bbox(region: dict[str, Any], width: int, height: int) -> tuple[int, int, int, int] | None:
    bbox = region.get("bbox_normalized")
    if not (isinstance(bbox, list) and len(bbox) == 4):
        return None
    coordinate_system = region.get("coordinate_system", "image_fraction_top_left")
    left = max(0, min(width, int(float(bbox[0]) * width)))
    box_width = int(float(bbox[2]) * width)
    box_height = int(float(bbox[3]) * height)
    if coordinate_system in {"figure_fraction_bottom_left", "axes_fraction_bottom_left"}:
        bottom_from_origin = int(float(bbox[1]) * height)
        top = max(0, min(height, height - bottom_from_origin - box_height))
    else:
        top = max(0, min(height, int(float(bbox[1]) * height)))
    right = max(left + 1, min(width, left + box_width))
    bottom = max(top + 1, min(height, top + box_height))
    return (left, top, right, bottom)


def _valid_mask(width: int, height: int, qa_regions: dict[str, Any] | None) -> np.ndarray:
    mask = np.ones((height, width), dtype=bool)
    if not qa_regions:
        return mask
    for name, region in qa_regions.items():
        if not isinstance(region, dict):
            continue
        if name != "ignore" and region.get("role") != "ignore":
            continue
        bbox = _region_bbox(region, width, height)
        if bbox is None:
            continue
        left, top, right, bottom = bbox
        mask[top:bottom, left:right] = False
    return mask


def _masked_images(src_cmp: Image.Image, act_cmp: Image.Image, mask: np.ndarray) -> tuple[Image.Image, Image.Image]:
    src_arr = np.asarray(src_cmp.convert("RGB"), dtype=np.uint8).copy()
    act_arr = np.asarray(act_cmp.convert("RGB"), dtype=np.uint8).copy()
    src_arr[~mask] = 255
    act_arr[~mask] = 255
    return Image.fromarray(src_arr), Image.fromarray(act_arr)


def _masked_mean(values: np.ndarray, mask: np.ndarray) -> float:
    if values.ndim == 3:
        expanded = np.repeat(mask[:, :, None], values.shape[2], axis=2)
        selected = values[expanded]
    else:
        selected = values[mask]
    if selected.size == 0:
        return 0.0
    return float(np.mean(selected))


def _ssim(src_cmp: Image.Image, act_cmp: Image.Image) -> float | None:
    if structural_similarity is None:
        return None
    src_gray = np.asarray(src_cmp.convert("L"), dtype=np.uint8)
    act_gray = np.asarray(act_cmp.convert("L"), dtype=np.uint8)
    min_dim = min(src_gray.shape)
    if min_dim < 3:
        return None
    win_size = min(7, min_dim if min_dim % 2 else min_dim - 1)
    return float(structural_similarity(src_gray, act_gray, data_range=255, win_size=win_size))


def _region_scores(src_cmp: Image.Image, act_cmp: Image.Image, qa_regions: dict[str, Any] | None) -> dict[str, float]:
    if not qa_regions:
        return {}
    scores: dict[str, float] = {}
    width, height = src_cmp.size
    for name, region in qa_regions.items():
        if name == "ignore" or not isinstance(region, dict):
            continue
        bbox = _region_bbox(region, width, height)
        if bbox is None:
            continue
        left, top, right, bottom = bbox
        region_ssim = _ssim(src_cmp.crop((left, top, right, bottom)), act_cmp.crop((left, top, right, bottom)))
        if region_ssim is not None:
            scores[name] = region_ssim
    return scores


def score_images(source: Path, actual: Path, *, comparison_dir: Path | None = None, qa_regions: dict[str, Any] | None = None, spec_path: Path | None = None, project_root: Path | None = None) -> dict[str, object]:
    if qa_regions is None:
        qa_regions = load_qa_regions_from_spec(spec_path)
    src = Image.open(source).convert("RGB")
    act = Image.open(actual).convert("RGB")
    canvas_size_match = src.size == act.size
    aspect_ratio_error = abs((src.width / src.height) - (act.width / act.height)) if src.height and act.height else 1.0
    src_cmp, act_cmp = _padded_canvases(src, act)
    valid_mask = _valid_mask(src_cmp.width, src_cmp.height, qa_regions)
    src_metric, act_metric = _masked_images(src_cmp, act_cmp, valid_mask)
    src_arr = np.asarray(src_cmp, dtype=np.float32)
    act_arr = np.asarray(act_cmp, dtype=np.float32)
    src_metric_arr = np.asarray(src_metric, dtype=np.float32)
    act_metric_arr = np.asarray(act_metric, dtype=np.float32)
    diff = act_metric_arr - src_metric_arr
    mae = float(_masked_mean(np.abs(diff), valid_mask) / 255.0)
    rmse = float(np.sqrt(_masked_mean(diff**2, valid_mask)) / 255.0)
    src_edge = np.asarray(_edge_image(src_metric), dtype=np.float32)
    act_edge = np.asarray(_edge_image(act_metric), dtype=np.float32)
    edge_mae = float(_masked_mean(np.abs(act_edge - src_edge), valid_mask) / 255.0)
    src_flat = src_metric_arr[valid_mask]
    act_flat = act_metric_arr[valid_mask]
    color_mean_delta = float(np.mean(np.abs(src_flat.mean(axis=0) - act_flat.mean(axis=0))) / 255.0) if len(src_flat) else 0.0
    src_bbox = _content_bbox(src_metric)
    act_bbox = _content_bbox(act_metric)
    size_penalty = 0.0 if canvas_size_match else abs(src.width - act.width) / max(src.width, 1) + abs(src.height - act.height) / max(src.height, 1)
    bbox_error = _bbox_error(src_bbox, act_bbox, src.width, src.height)
    comparison_outputs = _write_comparisons(src_cmp, act_cmp, comparison_dir, project_root=project_root) if comparison_dir else {}
    ssim = _ssim(src_metric, act_metric)
    region_scores = _region_scores(src_metric, act_metric, qa_regions)
    return {
        "schema": "scientificfigure.visual_score.v2",
        "source": portable_path(source, project_root) if project_root else str(source),
        "actual": portable_path(actual, project_root) if project_root else str(actual),
        "actual_width": act.width,
        "actual_height": act.height,
        "source_width": src.width,
        "source_height": src.height,
        "canvas_size_match": canvas_size_match,
        "aspect_ratio_error": float(aspect_ratio_error),
        "mae_0_1": mae,
        "rmse_0_1": rmse,
        "edge_mae_0_1": edge_mae,
        "color_mean_delta_0_1": color_mean_delta,
        "size_penalty": float(size_penalty),
        "score_0_1": float(mae + size_penalty + aspect_ratio_error),
        "canvas_score": 1.0 if canvas_size_match else 0.0,
        "layout_score": _similarity_from_error(bbox_error, 0.05),
        "edge_score": _similarity_from_error(edge_mae, 0.2),
        "ssim_score": ssim if ssim is not None else _similarity_from_error(rmse, 0.2),
        "color_score": _similarity_from_error(color_mean_delta, 0.1),
        "text_region_score": region_scores.get("labels"),
        "data_region_score": region_scores.get("plot_area"),
        "region_scores": region_scores,
        "ignored_pixel_ratio": float(1.0 - np.mean(valid_mask)),
        "scientific_fidelity": {
            "axes": "not_applicable",
            "data": "not_applicable",
            "labels": "not_applicable",
            "legend_mapping": "not_applicable",
            "units": "not_applicable",
            "annotations": "not_applicable",
        },
        "visual_fidelity": {
            "canvas": 1.0 if canvas_size_match else 0.0,
            "layout": _similarity_from_error(bbox_error, 0.05),
            "edge": _similarity_from_error(edge_mae, 0.2),
            "color": _similarity_from_error(color_mean_delta, 0.1),
            "ssim": ssim if ssim is not None else _similarity_from_error(rmse, 0.2),
        },
        "source_nonwhite_ratio": _nonwhite_ratio(src_metric),
        "actual_nonwhite_ratio": _nonwhite_ratio(act_metric),
        "nonwhite_delta": abs(_nonwhite_ratio(src_metric) - _nonwhite_ratio(act_metric)),
        "source_content_bbox": list(src_bbox) if src_bbox else None,
        "actual_content_bbox": list(act_bbox) if act_bbox else None,
        "content_bbox_error": bbox_error,
        "registration_shift": _shift(src_bbox, act_bbox),
        "exact_pixel_match": canvas_size_match and ImageChops.difference(src, act).getbbox() is None,
        "comparison_outputs": comparison_outputs,
        "note": "source image is not resized; metrics use max-canvas padding plus explicit size and aspect penalties",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a rendered figure against a source image.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--comparison-dir", type=Path, help="Write source/render/difference/overlay/edge comparison PNGs.")
    parser.add_argument("--qa-regions", type=Path, help="Optional JSON file containing qa_regions definitions.")
    parser.add_argument("--spec", type=Path, help="Optional VisualSpec file; qa_regions are read directly from it.")
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    qa_regions = json.loads(args.qa_regions.read_text(encoding="utf-8-sig")) if args.qa_regions else None
    result = score_images(args.source, args.actual, comparison_dir=args.comparison_dir, qa_regions=qa_regions, spec_path=args.spec, project_root=args.project_root)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
