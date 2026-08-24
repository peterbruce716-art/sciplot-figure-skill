from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SEMVER = r"(2\.\d+\.\d+)"


def _match(path: Path, pattern: str) -> str | None:
    text = path.read_text(encoding="utf-8-sig")
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else None


def find_versions(root: Path) -> dict[str, str]:
    """Return canonical release-version declarations only.

    Narrative files such as README.md, SKILL.md, and CHANGELOG.md may contain
    historical protocol versions and are intentionally not release-version
    authorities.
    """
    sources = {
        "VERSION": rf"^v?{SEMVER}\s*$",
        "pyproject.toml": rf'^version\s*=\s*["\']{SEMVER}["\']\s*$',
        "agents/openai.yaml": rf'^\s*version:\s*["\']?{SEMVER}["\']?\s*$',
    }
    result: dict[str, str] = {}
    for rel, pattern in sources.items():
        path = root / rel
        if not path.exists():
            continue
        version = _match(path, pattern)
        if version:
            result[rel] = version
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Check canonical package version declarations for consistency.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--expected", help="Require every canonical declaration to match this release version.")
    args = parser.parse_args()
    versions = find_versions(args.root)
    unique = sorted(set(versions.values()))
    required = {"VERSION", "pyproject.toml", "agents/openai.yaml"}
    complete = set(versions) == required
    consistent = len(unique) == 1
    expected_match = args.expected is None or unique == [args.expected]
    payload = {
        "status": "pass" if complete and consistent and expected_match else "failed",
        "versions": versions,
        "missing_sources": sorted(required - set(versions)),
        "unique_versions": unique,
        "expected_version": args.expected,
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
