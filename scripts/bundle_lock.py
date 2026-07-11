from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


LOCK_NAME = "bundle.lock.json"
LOCK_SCHEMA = "scientificfigure.bundle_lock.v1"

IMMUTABLE_ROOT_FILES = {
    "visualspec.json",
    "renderer_config.json",
    "render.py",
    "reproduce.py",
    "verify.py",
    "source_pointer.json",
}
IMMUTABLE_DIRS = {"inputs", "runtime", "environment"}
EXCLUDED_DIR_PARTS = {"__pycache__", "mplconfig"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def is_lock_tracked(path: Path, root: Path) -> bool:
    if not path.is_file():
        return False
    relative = path.resolve().relative_to(root.resolve())
    if any(part in EXCLUDED_DIR_PARTS for part in relative.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if len(relative.parts) == 1:
        return relative.parts[0] in IMMUTABLE_ROOT_FILES
    return relative.parts[0] in IMMUTABLE_DIRS


def build_bundle_lock(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files = {
        rel(path, root): {"byte_sha256": sha256_file(path)}
        for path in sorted(root.rglob("*"))
        if is_lock_tracked(path, root)
    }
    return {
        "schema": LOCK_SCHEMA,
        "root": ".",
        "policy": {
            "tracked_root_files": sorted(IMMUTABLE_ROOT_FILES),
            "tracked_dirs": sorted(IMMUTABLE_DIRS),
            "excluded_dir_parts": sorted(EXCLUDED_DIR_PARTS),
            "excluded_suffixes": sorted(EXCLUDED_SUFFIXES),
        },
        "files": files,
    }


def write_bundle_lock(root: Path, lock_path: Path | None = None) -> dict[str, Any]:
    lock_path = lock_path or root / LOCK_NAME
    payload = build_bundle_lock(root)
    write_json(lock_path, payload)
    return payload


def _expected_digest(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("byte_sha256") or value.get("sha256")
    return None


def verify_bundle_lock(root: Path, lock_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    lock_path = lock_path or root / LOCK_NAME
    failures: list[dict[str, str]] = []
    if not lock_path.exists():
        return {
            "schema": "scientificfigure.bundle_lock_verification.v1",
            "status": "failed",
            "root": ".",
            "lock": rel(lock_path, root) if lock_path.is_absolute() else str(lock_path),
            "failures": [{"path": LOCK_NAME, "reason": "missing_lock"}],
            "unexpected_files": [],
        }
    payload = json.loads(lock_path.read_text(encoding="utf-8-sig"))
    expected = payload.get("files") or {}
    for name, value in expected.items():
        digest = _expected_digest(value)
        path = root / name
        if not path.exists():
            failures.append({"path": name, "reason": "missing"})
            continue
        actual = sha256_file(path)
        if digest != actual:
            failures.append({"path": name, "reason": "sha256_mismatch", "expected": digest or "", "actual": actual})
    expected_names = set(expected)
    current_names = {rel(path, root) for path in sorted(root.rglob("*")) if is_lock_tracked(path, root)}
    unexpected = sorted(current_names - expected_names)
    status = "pass" if not failures and not unexpected else "failed"
    return {
        "schema": "scientificfigure.bundle_lock_verification.v1",
        "status": status,
        "root": ".",
        "lock": rel(lock_path, root),
        "checked_files": len(expected),
        "failures": failures,
        "unexpected_files": unexpected,
    }


def fixed_environment(base: dict[str, str] | None = None, *, mplconfig: Path | None = None) -> dict[str, str]:
    env = dict(base or os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["MPLBACKEND"] = "Agg"
    env["SOURCE_DATE_EPOCH"] = env.get("SOURCE_DATE_EPOCH", "0")
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        env[key] = "1"
    if mplconfig is not None:
        env["MPLCONFIGDIR"] = str(mplconfig)
    return env


def write_run_attestation(root: Path, *, status: str, steps: dict[str, Any] | None = None) -> dict[str, Any]:
    lock = verify_bundle_lock(root)
    payload = {
        "schema": "scientificfigure.run_attestation.v1",
        "status": status,
        "root": ".",
        "bundle_lock_status": lock["status"],
        "bundle_lock": lock,
        "environment_policy": {
            "PYTHONDONTWRITEBYTECODE": "1",
            "MPLBACKEND": "Agg",
            "SOURCE_DATE_EPOCH": "0",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
        },
        "steps": steps or {},
    }
    write_json(root / "run_attestation.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Write or verify the immutable scientific figure reproduction bundle lock.")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.write:
        payload = write_bundle_lock(root, args.lock)
        return_code = 0
    else:
        payload = verify_bundle_lock(root, args.lock)
        return_code = 0 if payload["status"] == "pass" else 2
    if args.json_out:
        write_json(args.json_out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
