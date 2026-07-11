from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from visualspec import load_json, write_json


def estimate_patch(spec: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []
    source_width = int(score.get("source_width") or 0)
    source_height = int(score.get("source_height") or 0)
    actual_width = int(score.get("actual_width") or 0)
    actual_height = int(score.get("actual_height") or 0)
    figure = spec.get("figure") or {}
    dpi = float(figure.get("dpi", 300))

    if source_width > 0 and source_height > 0 and (source_width != actual_width or source_height != actual_height):
        target_size_mm = [source_width / dpi * 25.4, source_height / dpi * 25.4]
        operations.append({"op": "replace", "path": "/figure/size_mm", "value": target_size_mm})
        operations.append({"op": "replace", "path": "/figure/crop_mode", "value": "fixed_canvas"})

    patch = {
        "schema": "scientificfigure.visual_patch.v2",
        "strategy": "deterministic_canvas_geometry",
        "operations": operations,
        "expected_effect": "match source canvas size without resizing the source image during scoring",
        "status": "proposed" if operations else "no_patch_available",
    }
    return patch


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate a deterministic VisualSpec patch from a v2 score report.")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--score", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    patch = estimate_patch(load_json(args.spec), load_json(args.score))
    write_json(args.out, patch)
    print(json.dumps(patch, ensure_ascii=False, indent=2))
    return 0 if patch["status"] == "proposed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
