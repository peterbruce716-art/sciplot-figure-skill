from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from advisor_common import load_json, write_json


def build_context(visualspec: dict[str, Any], *, qa: dict[str, Any] | None = None, semantics: dict[str, Any] | None = None) -> dict[str, Any]:
    panels = visualspec.get("panels", [])
    artists = visualspec.get("artists", [])
    themes = visualspec.get("theme", {})
    y_axes = {str(a.get("y_axis", "left")) for a in artists if isinstance(a, dict)}
    text = [a for a in artists if isinstance(a, dict) and a.get("kind") in {"text", "title", "legend"}]
    panel_labels_present = all(bool(panel.get("label") or panel.get("panel_label")) for panel in panels) if len(panels) > 1 else True
    chart = {
        "artist_count": len(artists),
        "dual_y": len(y_axes) > 1,
        "is_3d": any(isinstance(a, dict) and a.get("projection") == "3d" for a in artists),
        "has_uncertainty": bool((semantics or {}).get("uncertainty_semantics")),
    }
    layout = {
        "panel_count": len(panels),
        "text_artist_count": len(text),
        "panel_labels_present": panel_labels_present,
        "text_clipped": bool((qa or {}).get("text_clipped", False)),
        "tick_labels_overlap": bool((qa or {}).get("tick_labels_overlap", False)),
    }
    style = {
        "font_family": themes.get("font", {}).get("family") if isinstance(themes.get("font"), dict) else None,
        "font_size": themes.get("font", {}).get("size") if isinstance(themes.get("font"), dict) else None,
        "missing_glyphs": int((qa or {}).get("missing_glyphs", 0)),
    }
    return {
        "schema": "scientificfigure.policy_context.v1",
        "schema_version": "1.0",
        "source": "rendered_visualspec",
        "chart": chart,
        "data": {},
        "statistics": {"uncertainty_semantics": (semantics or {}).get("uncertainty_semantics")},
        "layout": layout,
        "style": style,
        "export": {"deterministic_qa": qa or {}},
        "panel_count": len(panels),
        "artist_count": len(artists),
        "has_dual_y": chart["dual_y"],
        "y_axes": sorted(y_axes),
        "has_3d": chart["is_3d"],
        "text_artist_count": len(text),
        "font_family": style["font_family"],
        "font_size": style["font_size"],
        "uncertainty_semantics": (semantics or {}).get("uncertainty_semantics"),
        "deterministic_qa": qa or {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build policy context from actual VisualSpec render objects and QA evidence.")
    parser.add_argument("--visualspec", required=True, type=Path)
    parser.add_argument("--qa", type=Path)
    parser.add_argument("--semantics", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = build_context(load_json(args.visualspec), qa=load_json(args.qa) if args.qa else None, semantics=load_json(args.semantics) if args.semantics else None)
    write_json(args.output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
