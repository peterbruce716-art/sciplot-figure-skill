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
    return {
        "schema": "scientificfigure.policy_context.v1",
        "schema_version": "1.0",
        "source": "rendered_visualspec",
        "panel_count": len(panels),
        "artist_count": len(artists),
        "has_dual_y": len(y_axes) > 1,
        "y_axes": sorted(y_axes),
        "has_3d": any(isinstance(a, dict) and a.get("projection") == "3d" for a in artists),
        "text_artist_count": len(text),
        "font_family": themes.get("font", {}).get("family") if isinstance(themes.get("font"), dict) else None,
        "font_size": themes.get("font", {}).get("size") if isinstance(themes.get("font"), dict) else None,
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
