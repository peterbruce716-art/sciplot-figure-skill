from __future__ import annotations

import re
from pathlib import Path
from typing import Any


POSIX_ABSOLUTE_PREFIXES = ("/",)
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def portable_path(value: str | Path | None, root: Path) -> str | None:
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute() and not WINDOWS_DRIVE_RE.match(str(value)):
        return path.as_posix()
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.name


def portable_command(cmd: list[str], root: Path) -> dict[str, Any]:
    if not cmd:
        return {"executable_role": None, "script": None, "arguments": []}

    executable = Path(cmd[0]).name
    executable_role = "python" if executable.lower().startswith("python") else executable
    script: str | None = None
    arguments: list[str] = []

    for index, argument in enumerate(cmd[1:]):
        text = str(argument)
        path = Path(text)
        if index == 0 and path.suffix.lower() == ".py":
            script = portable_path(path, root)
        elif path.is_absolute() or WINDOWS_DRIVE_RE.match(text):
            arguments.append(portable_path(path, root) or Path(text).name)
        else:
            arguments.append(text.replace("\\", "/"))

    return {"executable_role": executable_role, "script": script, "arguments": arguments}


def portable_json(value: Any, root: Path, *, keys: set[str] | None = None) -> Any:
    path_keys = keys or {
        "path",
        "spec",
        "render_semantics",
        "source",
        "actual",
        "log",
        "script",
        "runner",
        "output_dir",
        "spec_path",
        "semantics",
        "png",
        "svg",
        "pdf",
        "score_report",
        "checksums",
    }
    if isinstance(value, dict):
        return {
            key: portable_json(portable_path(item, root) if key in path_keys and isinstance(item, str) else item, root, keys=path_keys)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [portable_json(item, root, keys=path_keys) for item in value]
    if isinstance(value, str):
        text = value.replace("\\", "/")
        if value.startswith("\\\\") or WINDOWS_DRIVE_RE.match(value) or text.startswith("/"):
            return portable_path(value, root)
    return value
