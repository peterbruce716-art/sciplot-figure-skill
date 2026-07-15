from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
from typing import Any, Iterable

from advisor_common import sha256_file, validate_payload, write_json


DEFAULT_CJK = ["Noto Sans CJK SC", "Source Han Sans SC", "SimHei", "Microsoft YaHei", "Arial Unicode MS"]
DEFAULT_LATIN = ["Times New Roman", "Arial", "DejaVu Sans", "Liberation Sans"]


def _available_fonts() -> list[dict[str, Any]]:
    try:
        from matplotlib import font_manager
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("matplotlib is required for font resolution") from exc
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in font_manager.fontManager.ttflist:
        path = Path(entry.fname)
        key = (str(entry.name), path.name)
        if key in seen:
            continue
        seen.add(key)
        record: dict[str, Any] = {"family": str(entry.name), "filename": path.name, "style": str(entry.style), "weight": str(entry.weight)}
        if path.exists():
            record["sha256"] = sha256_file(path)
        records.append(record)
    return sorted(records, key=lambda item: (item["family"].lower(), item["filename"].lower()))


def resolve_fonts(
    *,
    latin: str | None = None,
    cjk: str | None = None,
    available: Iterable[dict[str, Any]] | None = None,
    serif_for_zh: bool = False,
) -> dict[str, Any]:
    available_records = list(available) if available is not None else _available_fonts()
    families = {str(item.get("family")): item for item in available_records}
    latin_candidates = [latin] if latin else []
    latin_candidates.extend(DEFAULT_LATIN)
    cjk_candidates = [cjk] if cjk else []
    cjk_candidates.extend(["Noto Serif CJK SC", "Source Han Serif SC"] if serif_for_zh else DEFAULT_CJK)

    def choose(candidates: list[str]) -> tuple[str | None, dict[str, Any] | None]:
        for candidate in candidates:
            if candidate and candidate in families:
                return candidate, families[candidate]
        return None, None

    latin_family, latin_record = choose(latin_candidates)
    cjk_family, cjk_record = choose(cjk_candidates)
    warnings: list[dict[str, Any]] = []
    if latin_family is None:
        warnings.append({"code": "latin_font_unresolved", "severity": "warning", "message": "No requested or fallback Latin font was found; Matplotlib defaults may vary."})
    if cjk_family is None:
        warnings.append({"code": "cjk_font_unresolved", "severity": "warning", "message": "No CJK font was found; Chinese glyphs may render as missing boxes."})
    payload = {
        "schema": "scientificfigure.font_resolution.v1",
        "schema_version": "1.0",
        "requested": {"latin": latin, "cjk": cjk},
        "resolved": {
            "latin_family": latin_family,
            "cjk_family": cjk_family,
            "latin_file": latin_record,
            "cjk_file": cjk_record,
            "fallback_used": bool((latin and latin_family != latin) or (cjk and cjk_family != cjk)),
        },
        "matplotlib": {"pdf_fonttype": 42, "ps_fonttype": 42, "svg_fonttype": "none", "axes_unicode_minus": False},
        "platform": platform.system().lower(),
        "warnings": warnings,
    }
    validate_payload(payload, "font-resolution-v1.schema.json")
    return payload


def apply_font_config(payload: dict[str, Any]) -> None:
    import matplotlib as mpl
    from matplotlib import rcParams
    resolved = payload.get("resolved", {})
    families = [item for item in [resolved.get("latin_family"), resolved.get("cjk_family")] if item]
    if families:
        rcParams["font.family"] = families
    rcParams["axes.unicode_minus"] = bool(payload.get("matplotlib", {}).get("axes_unicode_minus", False))
    mpl.rcParams["pdf.fonttype"] = 42
    mpl.rcParams["ps.fonttype"] = 42
    mpl.rcParams["svg.fonttype"] = "none"


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve portable Matplotlib Latin/CJK font metadata without bundling fonts.")
    parser.add_argument("--latin")
    parser.add_argument("--cjk")
    parser.add_argument("--serif-for-zh", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--list-fonts", action="store_true")
    args = parser.parse_args()
    try:
        if args.list_fonts:
            print(json.dumps(_available_fonts(), ensure_ascii=False, indent=2))
        payload = resolve_fonts(latin=args.latin, cjk=args.cjk, serif_for_zh=args.serif_for_zh)
        write_json(args.output, payload)
    except Exception as exc:
        parser.exit(2, f"font_resolver: {exc}\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
