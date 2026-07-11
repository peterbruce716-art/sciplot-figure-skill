from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_spec(figures: list[str], output_dir: str, source_dir: str) -> dict[str, Any]:
    return {
        "schema": "scientificfigure.visualspec.v2",
        "figure": {
            "size_mm": [180, 120],
            "dpi": 300,
            "background": "white",
            "crop_mode": "fixed_canvas",
            "output_dir": output_dir,
            "source_dir": source_dir,
        },
        "delivery": {
            "source_code": {"required": True},
            "raster": {"formats": ["png"]},
            "vector": {
                "formats": ["svg", "pdf"],
                "preserve_text_as_text": True,
                "forbid_embedded_full_canvas_raster": True,
            },
        },
        "panels": [
            {
                "id": figure,
                "source_crop": str(Path(source_dir) / f"{figure}_source.png"),
                "bbox_normalized": [0.12, 0.14, 0.78, 0.76],
                "axes": {
                    "x": {"scale": "linear", "limits": [0, 1], "label": "TODO x"},
                    "y": {"scale": "linear", "limits": [0, 1], "label": "TODO y"},
                },
                "plots": [],
                "annotations": [],
                "reconstruction_mode": "semantic_reconstruction",
            }
            for figure in figures
        ],
        "qa_policy": {
            "visual_backend": "python_matplotlib",
            "completion_without_visual_pass": "forbidden",
            "pixel_trace_default": "forbidden",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Scientific Figure VisualSpec v1 skeleton.")
    parser.add_argument("--figures", nargs="+", required=True, help="Figure ids, for example fig12 fig15 fig16.")
    parser.add_argument("--output-dir", default="outputs/figure_reproduction", help="Output directory recorded in the spec.")
    parser.add_argument("--source-dir", default="outputs/source_refs/crops", help="Directory containing source crops.")
    parser.add_argument("--json-out", type=Path, help="Optional output path. Prints to stdout when omitted.")
    args = parser.parse_args()

    spec = build_spec(args.figures, args.output_dir, args.source_dir)
    payload = json.dumps(spec, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
