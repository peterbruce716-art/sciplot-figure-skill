from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def find_versions(root: Path) -> dict[str, str]:
    result = {}
    for rel in ["VERSION", "pyproject.toml", "README.md", "SKILL.md", "agents/openai.yaml", "CHANGELOG.md"]:
        path = root / rel
        text = path.read_text(encoding="utf-8-sig")
        match = re.search(r"(?<![0-9])v?(2\.\d+\.\d+)(?![0-9])", text)
        if match:
            result[rel] = match.group(1)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Check package version declarations for consistency.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--expected", help="Require every declaration to match this release version.")
    args = parser.parse_args()
    versions = find_versions(args.root)
    unique = sorted(set(versions.values()))
    consistent = len(unique) == 1
    expected_match = args.expected is None or unique == [args.expected]
    payload = {
        "status": "pass" if consistent and expected_match else "failed",
        "versions": versions,
        "unique_versions": unique,
        "expected_version": args.expected,
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
