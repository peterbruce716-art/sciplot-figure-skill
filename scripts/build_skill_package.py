from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".git"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def should_include(path: Path) -> bool:
    if any(part in IGNORED_PARTS for part in path.parts):
        return False
    if path.suffix.lower() in IGNORED_SUFFIXES:
        return False
    return path.is_file()


def build_package(root: Path, output: Path | None = None) -> Path:
    root = root.resolve()
    output = (output or root.parent / f"{root.name}.zip").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not should_include(path):
                continue
            relative = path.relative_to(root.parent)
            archive.write(path, relative.as_posix())
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a portable scientific-figure-reproduction skill ZIP.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = build_package(args.root, args.out)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
