from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from advisor_common import load_json, sha256_file, validate_payload, write_json


PALETTES = {
    "okabe_ito": ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000"],
}


def _resolve_palette(value: object) -> tuple[str | None, list[str]]:
    if isinstance(value, str):
        if value not in PALETTES:
            raise ValueError(f"unknown named palette: {value}")
        return value, list(PALETTES[value])
    if isinstance(value, list) and value and all(isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?", color) for color in value):
        return None, list(value)
    raise ValueError("palette must be a registered name or a non-empty list of hexadecimal colors")


def apply_style(visualspec: dict, profile: dict) -> tuple[dict, dict]:
    settings = profile.get("settings", {})
    theme = visualspec.setdefault("theme", {})
    figure = visualspec.setdefault("figure", {})
    qa_policy = visualspec.setdefault("qa_policy", {})
    applied = {}
    applied_keys: list[str] = []
    compatibility_mapped_keys: dict[str, str] = {}
    if settings.get("font"):
        theme["font"] = dict(settings["font"])
        applied["font"] = theme["font"]
    elif settings.get("font_size_pt") or settings.get("latin_font"):
        current = dict(theme.get("font", {}))
        if settings.get("font_size_pt"):
            current["size_pt"] = float(settings["font_size_pt"])
        if settings.get("latin_font"):
            current["family_candidates"] = [settings["latin_font"], "Liberation Sans", "DejaVu Sans"]
        theme["font"] = current
        applied["font"] = current
    for key in ("axes", "lines", "legend", "colors"):
        if key in settings:
            theme[key] = settings[key]
            applied[key] = settings[key]
    if settings.get("line_width_pt"):
        axes = dict(theme.get("axes", {}))
        axes["line_width_pt"] = float(settings["line_width_pt"])
        theme["axes"] = axes
        applied["axes"] = axes
        compatibility_mapped_keys["line_width_pt"] = "axis_line_width_pt"

    if "font_family" in settings:
        font = dict(theme.get("font", {}))
        family = settings["font_family"]
        font["family_candidates"] = list(family) if isinstance(family, list) else [str(family), "Liberation Sans", "DejaVu Sans"]
        theme["font"] = font
        applied["font_family"] = family
        applied_keys.append("font_family")
    if "font_size_pt" in settings:
        font = dict(theme.get("font", {}))
        font["size_pt"] = float(settings["font_size_pt"])
        theme["font"] = font
        applied["font_size_pt"] = float(settings["font_size_pt"])
        applied_keys.append("font_size_pt")
    for key, section, target in (
        ("axis_line_width_pt", "axes", "line_width_pt"),
        ("data_line_width_pt", "lines", "line_width_pt"),
        ("marker_size_pt", "lines", "marker_size_pt"),
    ):
        if key in settings:
            block = dict(theme.get(section, {}))
            block[target] = float(settings[key])
            theme[section] = block
            applied[key] = float(settings[key])
            applied_keys.append(key)
    if "palette" in settings:
        palette_name, resolved_palette = _resolve_palette(settings["palette"])
        colors = dict(theme.get("colors", {}))
        colors["palette"] = resolved_palette
        if palette_name is not None:
            colors["palette_name"] = palette_name
        theme["colors"] = colors
        applied["palette"] = {"palette_name": palette_name, "palette": resolved_palette}
        applied_keys.append("palette")
    if "column_width_mm" in settings:
        current_size = list(figure.get("size_mm", [90.0, 60.0]))
        current_size[0] = float(settings["column_width_mm"])
        figure["size_mm"] = current_size
        applied["column_width_mm"] = current_size[0]
        applied_keys.append("column_width_mm")
    if "double_column_width_mm" in settings:
        delivery = visualspec.setdefault("delivery", {})
        delivery["double_column_width_mm"] = float(settings["double_column_width_mm"])
        applied["double_column_width_mm"] = float(settings["double_column_width_mm"])
        applied_keys.append("double_column_width_mm")
    if "minimum_font_size_pt" in settings:
        qa_policy["minimum_font_size_pt"] = float(settings["minimum_font_size_pt"])
        applied["minimum_font_size_pt"] = float(settings["minimum_font_size_pt"])
        applied_keys.append("minimum_font_size_pt")
    if "vector_formats" in settings:
        delivery = visualspec.setdefault("delivery", {})
        delivery["vector_formats"] = list(settings["vector_formats"])
        applied["vector_formats"] = list(settings["vector_formats"])
        applied_keys.append("vector_formats")
    if "background" in settings:
        figure["background"] = settings["background"]
        applied["background"] = settings["background"]
        applied_keys.append("background")
    if "width_mm" in settings or "height_mm" in settings:
        current_size = list(figure.get("size_mm", [90.0, 60.0]))
        if "width_mm" in settings:
            current_size[0] = float(settings["width_mm"])
            applied["width_mm"] = current_size[0]
            applied_keys.append("width_mm")
        if "height_mm" in settings:
            current_size[1] = float(settings["height_mm"])
            applied["height_mm"] = current_size[1]
            applied_keys.append("height_mm")
        figure["size_mm"] = current_size
    if "dpi" in settings:
        figure["dpi"] = int(settings["dpi"])
        applied["dpi"] = int(settings["dpi"])
        applied_keys.append("dpi")
    if "grayscale_preview" in settings:
        qa_policy["grayscale_preview"] = bool(settings["grayscale_preview"])
        applied["grayscale_preview"] = bool(settings["grayscale_preview"])
        applied_keys.append("grayscale_preview")

    legacy_keys = {"font", "latin_font", "axes", "lines", "legend", "colors", "line_width_pt"}
    compatibility_mapped_keys.update({key: key for key in settings if key in legacy_keys and key not in compatibility_mapped_keys})
    unsupported_keys = sorted(set(settings) - set(applied_keys) - set(compatibility_mapped_keys))
    report = {
        "schema": "scientificfigure.style_application.v1",
        "schema_version": "1.0",
        "profile_id": profile.get("profile_id"),
        "source_profile_sha256": profile.get("source_profile_sha256") or profile.get("source_sha256"),
        "applied_keys": sorted(set(applied_keys)),
        "compatibility_mapped_keys": compatibility_mapped_keys,
        "unsupported_keys": unsupported_keys,
        "applied": applied,
        "visualspec_hash_before": None,
        "status": "applied" if applied and not unsupported_keys else ("partial" if applied else "no_compatible_settings"),
    }
    return visualspec, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a resolved style profile to a VisualSpec and record the applied settings.")
    parser.add_argument("--visualspec", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    visualspec = load_json(args.visualspec)
    profile = load_json(args.profile)
    before = sha256_file(args.visualspec)
    visualspec, report = apply_style(visualspec, profile)
    report["visualspec_hash_before"] = before
    validate_payload(report, "style-application-v1.schema.json")
    write_json(args.output, visualspec)
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
