from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from typing import Any


REQUIRED_PACKAGES = ["matplotlib", "numpy", "pillow", "scikit-image", "pandas", "openpyxl", "pypdf"]
POLICY_SCHEMA = "scientificfigure.environment_policy.v1"


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def capture_environment() -> dict[str, Any]:
    packages = {name: package_version(name) for name in REQUIRED_PACKAGES}
    try:
        import matplotlib
        from matplotlib import ft2font

        freetype = getattr(ft2font, "__freetype_version__", None)
        matplotlib_version = matplotlib.__version__
    except Exception:
        freetype = None
        matplotlib_version = packages.get("matplotlib")
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "matplotlib": matplotlib_version,
        "freetype": freetype,
        "packages": packages,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_environment_policy(path: Path, *, mode: str = "exact") -> dict[str, Any]:
    payload = {"schema": POLICY_SCHEMA, "mode": mode, "environment": capture_environment()}
    write_json(path, payload)
    return payload


def verify_environment_policy(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": "scientificfigure.environment_policy_verification.v1", "status": "failed", "failures": [{"field": "policy", "reason": "missing"}]}
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    mode = str(policy.get("mode", "exact"))
    expected = policy.get("environment") or {}
    actual = capture_environment()
    failures: list[dict[str, str]] = []
    if mode == "record_only":
        return {"schema": "scientificfigure.environment_policy_verification.v1", "status": "pass", "mode": mode, "failures": [], "actual": actual}
    if mode not in {"exact", "compatible"}:
        failures.append({"field": "mode", "reason": "unsupported", "expected": mode, "actual": ""})
    if mode == "exact" and expected.get("python") != actual.get("python"):
        failures.append({"field": "python", "reason": "version_mismatch", "expected": str(expected.get("python")), "actual": str(actual.get("python"))})
    if mode == "compatible":
        expected_py = ".".join(str(expected.get("python", "")).split(".")[:2])
        actual_py = ".".join(str(actual.get("python", "")).split(".")[:2])
        if expected_py != actual_py:
            failures.append({"field": "python", "reason": "minor_version_mismatch", "expected": expected_py, "actual": actual_py})
    expected_packages = expected.get("packages") or {}
    actual_packages = actual.get("packages") or {}
    for name in REQUIRED_PACKAGES:
        expected_version = expected_packages.get(name)
        actual_version = actual_packages.get(name)
        if actual_version is None:
            failures.append({"field": f"packages.{name}", "reason": "missing", "expected": str(expected_version), "actual": ""})
        elif mode == "exact" and expected_version != actual_version:
            failures.append({"field": f"packages.{name}", "reason": "version_mismatch", "expected": str(expected_version), "actual": str(actual_version)})
    return {
        "schema": "scientificfigure.environment_policy_verification.v1",
        "status": "pass" if not failures else "failed",
        "mode": mode,
        "failures": failures,
        "actual": actual,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write or verify scientific figure reproduction environment policy.")
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--mode", choices=["exact", "compatible", "record_only"], default="exact")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    payload = write_environment_policy(args.policy, mode=args.mode) if args.write else verify_environment_policy(args.policy)
    if args.json_out:
        write_json(args.json_out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if args.write:
        return 0
    return 0 if payload["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
