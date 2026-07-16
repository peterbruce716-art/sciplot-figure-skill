from __future__ import annotations

import argparse
import json
from pathlib import Path

from advisor_common import load_json, sha256_file, validate_payload, write_json


def apply_style(visualspec: dict, profile: dict) -> tuple[dict, dict]:
    settings = profile.get("settings", {})
    theme = visualspec.setdefault("theme", {})
    applied = {}
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
    report = {
        "schema": "scientificfigure.style_application.v1",
        "schema_version": "1.0",
        "profile_id": profile.get("profile_id"),
        "source_profile_sha256": profile.get("source_sha256"),
        "applied_keys": sorted(applied),
        "applied": applied,
        "visualspec_hash_before": None,
        "status": "applied" if applied else "no_compatible_settings",
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
