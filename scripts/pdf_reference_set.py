"""Validate provenance for PDF-derived raster figure references.

The validator intentionally does not render a PDF.  It checks the immutable
inputs and clip contract before a project-specific renderer or digitizer runs.
This keeps stale reference PNGs from being mistaken for a fresh extraction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(root: Path, raw: Any, failures: list[dict[str, str]], check: str) -> Path | None:
    if not isinstance(raw, str) or not raw:
        failures.append({"check": check, "message": "relative path required"})
        return None
    path = Path(raw.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        failures.append({"check": check, "path": raw, "message": "path escape is not allowed"})
        return None
    return root / path


def validate_pdf_reference_set(*, root: Path, manifest_path: Path) -> dict[str, Any]:
    root = root.resolve()
    failures: list[dict[str, str]] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"schema": "scientificfigure.pdf-reference-validation.v1", "status": "failed", "failures": [{"check": "manifest", "message": str(exc)}]}
    if not isinstance(manifest, dict):
        return {"schema": "scientificfigure.pdf-reference-validation.v1", "status": "failed", "failures": [{"check": "manifest", "message": "JSON object required"}]}

    pdf_meta = manifest.get("pdf")
    if not isinstance(pdf_meta, dict):
        failures.append({"check": "pdf", "message": "pdf object required"})
        pdf_meta = {}
    raw_pdf = pdf_meta.get("path")
    if pdf_meta.get("external") is True and isinstance(raw_pdf, str) and raw_pdf:
        pdf_path = Path(raw_pdf.replace("\\", "/"))
        if not pdf_path.is_absolute():
            pdf_path = (root / pdf_path).resolve()
    else:
        pdf_path = _relative_path(root, raw_pdf, failures, "pdf_path")
    if pdf_path is not None:
        if not pdf_path.is_file():
            failures.append({"check": "pdf_exists", "path": str(pdf_path)})
        elif pdf_meta.get("sha256") != _sha256(pdf_path):
            failures.append({"check": "pdf_hash", "path": str(pdf_path)})

    figures = manifest.get("figures")
    if not isinstance(figures, dict) or not figures:
        failures.append({"check": "figures", "message": "non-empty figures object required"})
        figures = {}
    checked: list[str] = []
    for figure, entry in figures.items():
        checked.append(str(figure))
        if not isinstance(entry, dict):
            failures.append({"check": "figure_entry", "figure": str(figure)})
            continue
        source_path = _relative_path(root, entry.get("source"), failures, "source_path")
        if source_path is not None:
            if not source_path.is_file():
                failures.append({"check": "source_exists", "figure": str(figure)})
            elif entry.get("sha256") != _sha256(source_path):
                failures.append({"check": "source_hash", "figure": str(figure)})
        clip = entry.get("clip_pdf_points")
        valid_clip = isinstance(clip, list) and len(clip) == 4
        if valid_clip:
            try:
                left, top, right, bottom = (float(value) for value in clip)
                valid_clip = 0 <= left < right and 0 <= top < bottom
            except (TypeError, ValueError):
                valid_clip = False
        if not valid_clip:
            failures.append({"check": "clip_box", "figure": str(figure), "message": "expected [left, top, right, bottom] with positive area"})
        if not isinstance(entry.get("page"), int) or entry["page"] < 1:
            failures.append({"check": "page", "figure": str(figure)})
        if not isinstance(entry.get("dpi"), (int, float)) or float(entry["dpi"]) <= 0:
            failures.append({"check": "dpi", "figure": str(figure)})

    return {
        "schema": "scientificfigure.pdf-reference-validation.v1",
        "status": "pass" if not failures else "failed",
        "root": ".",
        "checked_figures": sorted(checked),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = validate_pdf_reference_set(root=args.root, manifest_path=args.manifest)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
