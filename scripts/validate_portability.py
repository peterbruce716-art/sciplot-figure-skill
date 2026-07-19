from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "scientificfigure.portability_validation.v1"
EXCLUDED_DIRS = {"logs", "scratch", "__pycache__", "mplconfig"}
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
HOST_PATH_MARKERS = ("/mnt/", "/opt/", "/tmp/", "\\mnt\\", "\\opt\\", "\\tmp\\")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def is_excluded(path: Path, root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return True
    return any(part in EXCLUDED_DIRS for part in relative.parts)


def path_reason(value: str, root: Path) -> str | None:
    if value.startswith("\\\\"):
        return "unc_path"
    if WINDOWS_ABSOLUTE.match(value):
        return "windows_absolute_path"
    if value.startswith("/"):
        return "posix_absolute_path"
    normalized = value.replace("\\", "/")
    root_text = root.resolve().as_posix()
    if root_text and root_text in normalized:
        return "project_root_path"
    if any(marker in normalized for marker in HOST_PATH_MARKERS):
        return "host_path_marker"
    return None


def walk_json(value: Any, *, file: str, pointer: str, root: Path, failures: list[dict[str, str]]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            walk_json(item, file=file, pointer=f"{pointer}/{escaped}", root=root, failures=failures)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            walk_json(item, file=file, pointer=f"{pointer}/{index}", root=root, failures=failures)
    elif isinstance(value, str):
        reason = path_reason(value, root)
        if reason:
            failures.append({"file": file, "json_pointer": pointer or "/", "value": value, "reason": reason})


def validate_portability(root: Path, *, excluded_paths: set[Path] | None = None) -> dict[str, Any]:
    root = root.resolve()
    excluded = {path.resolve() for path in (excluded_paths or set())}
    failures: list[dict[str, str]] = []
    scanned = 0
    for path in sorted(root.rglob("*.json")):
        if path.resolve() in excluded or is_excluded(path, root):
            continue
        scanned += 1
        file = rel(path, root)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            failures.append({"file": file, "json_pointer": "/", "value": "", "reason": f"json_parse_error:{exc}"})
            continue
        walk_json(payload, file=file, pointer="", root=root, failures=failures)
    return {"schema": SCHEMA, "root": ".", "status": "pass" if not failures else "failed", "scanned_json_files": scanned, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate that delivered reproduction JSON contains no host absolute paths.")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    excluded = {args.json_out} if args.json_out else None
    result = validate_portability(args.root, excluded_paths=excluded)
    if args.json_out:
        write_json(args.json_out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
