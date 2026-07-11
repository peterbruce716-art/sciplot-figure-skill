from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any


FORBIDDEN_TERMS = [
    "".join(map(chr, [79, 80, 74, 85])),
    "".join(map(chr, [111, 112, 106, 117])),
    "".join(map(chr, [111, 114, 105, 103, 105, 110, 112, 114, 111])),
    "".join(map(chr, [79, 114, 105, 103, 105, 110, 76, 97, 98])),
    "".join(map(chr, [71, 114, 97, 112, 104, 32, 71, 97, 108, 108, 101, 114, 121])),
    "".join(map(chr, [67, 79, 77, 32, 97, 117, 116, 111, 109, 97, 116, 105, 111, 110])),
]

IGNORED_DIRS = {"__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".r", ".toml", ".txt"}


def scan_skill(root: Path) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            failures.append({"code": "bytecode_present", "path": str(path)})
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for term in FORBIDDEN_TERMS:
                if term in text:
                    failures.append({"code": "forbidden_term", "term": term, "path": str(path)})
    return {
        "schema": "scientificfigure.skill_package_validation.v1",
        "root": str(root),
        "status": "ok" if not failures else "failed",
        "failures": failures,
    }


def scan_zip(path: Path) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    with zipfile.ZipFile(path, "r") as archive:
        for name in archive.namelist():
            if "\\" in name:
                failures.append({"code": "windows_separator_in_zip", "path": name})
            if "__pycache__" in name or name.endswith((".pyc", ".pyo")):
                failures.append({"code": "cache_in_zip", "path": name})
            try:
                with archive.open(name) as handle:
                    while handle.read(1024 * 64):
                        pass
            except Exception as exc:
                failures.append({"code": "zip_entry_unreadable", "path": name, "message": str(exc)})
    return {
        "schema": "scientificfigure.zip_package_validation.v1",
        "zip": str(path),
        "status": "ok" if not failures else "failed",
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the scientific figure reproduction skill package.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = scan_skill(args.root)
    if args.zip:
        result["zip_validation"] = scan_zip(args.zip)
        if result["zip_validation"]["status"] != "ok":
            result["status"] = "failed"
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
