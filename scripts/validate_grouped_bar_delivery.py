"""Validate final grouped-bar pixels for baseline and legend contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _region(region: list[int]) -> tuple[int, int, int, int]:
    if len(region) != 4 or any(not isinstance(value, int) for value in region):
        raise ValueError("regions must be [x0, y0, x1, y1] integer lists")
    x0, y0, x1, y1 = region
    if not (0 <= x0 < x1 and 0 <= y0 < y1):
        raise ValueError(f"invalid region: {region!r}")
    return x0, y0, x1, y1


def validate_grouped_bar_delivery(
    image_path: Path,
    *,
    panel_regions: list[list[int]],
    baseline_rows: list[int],
    legend_rows: list[dict[str, Any]],
    max_panel_baseline_black: int | None = None,
    max_panel_baseline_run: int | None = None,
    baseline_gap_regions: list[list[int]] | None = None,
    max_baseline_gap_black: int = 0,
    required_baseline_regions: list[list[int]] | None = None,
    min_required_baseline_black: int = 20,
    required_bottom_regions: list[list[int]] | None = None,
    min_required_bottom_black: int = 8,
) -> dict[str, Any]:
    """Check an exported PNG, not an intermediate artist tree.

    ``panel_regions`` are [x0, y0, x1, y1] regions whose baseline rows must
    not contain an independent black line. Counting all black pixels and
    limiting run length are optional because legitimate bar bottom edges can
    be long. ``baseline_gap_regions`` are [x0, y0, x1, y1] gaps between bar
    groups that must remain disconnected; this is the preferred check when
    individual bar bottoms are required. ``required_baseline_regions`` require
    a continuous panel baseline when the reference contains one.
    ``required_bottom_regions`` require black bottom-frame evidence within
    each declared bar-group interval.
    ``legend_rows`` each declare a
    y coordinate, x interval, and expected RGB fill. A separate ``top_clear``
    interval can require the row above a legend swatch to remain white, which
    catches clipped legend frames caused by a negative or zero canvas position.
    """
    image = np.asarray(Image.open(image_path).convert("RGB"))
    failures: list[dict[str, Any]] = []
    for panel in panel_regions:
        x0, y0, x1, y1 = _region(panel)
        for row in baseline_rows:
            if not (y0 <= row < y1 and row < image.shape[0]):
                failures.append({"check": "baseline_row_bounds", "panel": panel, "row": row})
                continue
            pixels = image[row, x0:x1]
            black = np.all(pixels < 30, axis=1)
            black_count = int(np.sum(black))
            transitions = np.diff(np.concatenate(([False], black, [False])).astype(np.int8))
            starts = np.flatnonzero(transitions == 1)
            ends = np.flatnonzero(transitions == -1)
            longest_run = int(np.max(ends - starts)) if len(starts) else 0
            if (max_panel_baseline_run is not None and longest_run > max_panel_baseline_run) or (
                max_panel_baseline_black is not None and black_count > max_panel_baseline_black
            ):
                failures.append(
                    {
                        "check": "panel_baseline",
                        "panel": panel,
                        "row": row,
                        "black_pixels": black_count,
                        "longest_black_run": longest_run,
                        "max_black_run": max_panel_baseline_run,
                        "max_black_pixels": max_panel_baseline_black,
                    }
                )
    for gap in baseline_gap_regions or []:
        x0, y0, x1, y1 = _region(gap)
        if x1 > image.shape[1] or y1 > image.shape[0]:
            failures.append({"check": "baseline_gap_bounds", "region": gap})
            continue
        region = image[y0:y1, x0:x1]
        black_count = int(np.sum(np.all(region < 30, axis=2)))
        if black_count > max_baseline_gap_black:
            failures.append(
                {
                    "check": "panel_baseline_gap",
                    "region": gap,
                    "black_pixels": black_count,
                    "max_black_pixels": max_baseline_gap_black,
                }
            )
    for baseline in required_baseline_regions or []:
        x0, y0, x1, y1 = _region(baseline)
        if x1 > image.shape[1] or y1 > image.shape[0]:
            failures.append({"check": "required_baseline_bounds", "region": baseline})
            continue
        region = image[y0:y1, x0:x1]
        black_count = int(np.sum(np.all(region < 30, axis=2)))
        if black_count < min_required_baseline_black:
            failures.append(
                {"check": "panel_baseline_missing", "region": baseline,
                 "black_pixels": black_count, "min_black_pixels": min_required_baseline_black}
            )
    for bottom in required_bottom_regions or []:
        x0, y0, x1, y1 = _region(bottom)
        if x1 > image.shape[1] or y1 > image.shape[0]:
            failures.append({"check": "required_bottom_bounds", "region": bottom})
            continue
        region = image[y0:y1, x0:x1]
        black_count = int(np.sum(np.all(region < 30, axis=2)))
        if black_count < min_required_bottom_black:
            failures.append(
                {
                    "check": "bar_bottom_missing",
                    "region": bottom,
                    "black_pixels": black_count,
                    "min_black_pixels": min_required_bottom_black,
                }
            )
    for legend in legend_rows:
        y = int(legend["y"])
        x0, x1 = (int(legend["x0"]), int(legend["x1"]))
        color = tuple(int(channel) for channel in legend["fill_rgb"])
        if not (0 <= y < image.shape[0] and 0 <= x0 < x1 <= image.shape[1]):
            failures.append({"check": "legend_row_bounds", "legend": legend})
            continue
        row = image[y, x0:x1]
        if not np.any(np.all(row == color, axis=1)):
            failures.append({"check": "legend_fill_missing", "legend": legend})
        top_clear = legend.get("top_clear")
        if top_clear is not None:
            clear_y = int(top_clear.get("y", y - 1))
            clear_x0, clear_x1 = int(top_clear["x0"]), int(top_clear["x1"])
            if not (0 <= clear_y < image.shape[0] and 0 <= clear_x0 < clear_x1 <= image.shape[1]):
                failures.append({"check": "legend_top_bounds", "legend": legend})
            elif not np.all(image[clear_y, clear_x0:clear_x1] == 255):
                failures.append({"check": "legend_top_clipped", "legend": legend})
    return {
        "schema": "scientificfigure.grouped-bar-delivery-validation.v1",
        "status": "pass" if not failures else "failed",
        "image": str(image_path),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    report = validate_grouped_bar_delivery(args.image, **contract)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
