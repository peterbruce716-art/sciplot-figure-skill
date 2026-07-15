from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from advisor_common import deep_merge, load_json, validate_payload, write_json


def resolve_style(profile: str, *, override: dict[str, Any] | None = None, root: Path | None = None) -> dict[str, Any]:
    root = root or Path(__file__).resolve().parents[1]
    path = root / "styles" / "journal" / f"{profile}.json"
    if not path.exists():
        raise FileNotFoundError(f"unknown style profile: {profile}")
    source = load_json(path)
    merged = deep_merge(source, override or {})
    payload = {
        "schema": "scientificfigure.style_profile.v1",
        "schema_version": "1.0",
        "profile_id": str(merged.get("profile_id", profile)),
        "basis": str(merged.get("basis", "")),
        "checked_date": str(merged.get("checked_date", date.today().isoformat())),
        "scope": str(merged.get("scope", "")),
        "settings": dict(merged.get("settings", {})),
        "user_overrides": override or {},
        "disclaimer": str(merged.get("disclaimer", "Verify current venue requirements.")),
    }
    validate_payload(payload, "style-profile-v1.schema.json")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a journal-like style preset with explicit provenance and overrides.")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--override", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        override = load_json(args.override) if args.override else None
        payload = resolve_style(args.profile, override=override)
        write_json(args.output, payload)
    except Exception as exc:
        parser.exit(2, f"resolve_style_profile: {exc}\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
