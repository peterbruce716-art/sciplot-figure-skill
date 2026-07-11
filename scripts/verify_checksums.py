from __future__ import annotations

import argparse
import io
import hashlib
import json
import re
from pathlib import Path
from typing import Any


EXCLUDED_DIRS = {"logs", "__pycache__", "mplconfig"}
EXCLUDED_NAMES = {
    "run_report.json",
    "checksums.json",
    "checksum_verification.json",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
ALLOWED_UNTRACKED_ROOTS = {"logs"}
ALLOWED_UNTRACKED_PARTS = {"__pycache__", "mplconfig"}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _canonical_json(data: bytes) -> bytes:
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except Exception:
        return data
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _canonical_svg(data: bytes) -> bytes:
    text = data.decode("utf-8", errors="replace")
    text = re.sub(r"<metadata>.*?</metadata>", "<metadata/>", text, flags=re.DOTALL)
    text = re.sub(r"<dc:date>.*?</dc:date>", "", text, flags=re.DOTALL)
    id_map: dict[str, str] = {}

    def mapped_id(original: str) -> str:
        if original not in id_map:
            id_map[original] = f"id{len(id_map) + 1}"
        return id_map[original]

    def replace_id(match: re.Match[str]) -> str:
        return f'id="{mapped_id(match.group(1))}"'

    text = re.sub(r'id="([^"]+)"', replace_id, text)
    for original, mapped in sorted(id_map.items(), key=lambda item: len(item[0]), reverse=True):
        escaped = re.escape(original)
        text = re.sub(rf"url\(\#{escaped}\)", f"url(#{mapped})", text)
        text = re.sub(rf"href=\"\#{escaped}\"", f'href="#{mapped}"', text)
        text = re.sub(rf"xlink:href=\"\#{escaped}\"", f'xlink:href="#{mapped}"', text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.encode("utf-8")


def _canonical_pdf(data: bytes) -> bytes:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data), strict=True)
        pages: list[dict[str, Any]] = []
        for page in reader.pages:
            resources = page.get("/Resources") or {}
            fonts = sorted(str(key) for key in (resources.get("/Font") or {}).keys())
            xobjects = resources.get("/XObject") or {}
            images = 0
            for obj in xobjects.values():
                try:
                    if obj.get_object().get("/Subtype") == "/Image":
                        images += 1
                except Exception:
                    continue
            pages.append({"mediabox": [float(value) for value in page.mediabox], "fonts": fonts, "images": images})
        payload = {"pages": pages}
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except Exception:
        pass
    text = data.decode("latin-1", errors="ignore")
    text = re.sub(r"/CreationDate\s*\([^)]*\)", "", text)
    text = re.sub(r"/ModDate\s*\([^)]*\)", "", text)
    text = re.sub(r"/Producer\s*\([^)]*\)", "", text)
    text = re.sub(r"/ID\s*\[[^\]]+\]", "", text, flags=re.DOTALL)
    return text.encode("latin-1", errors="ignore")


def canonical_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _canonical_json(data)
    if suffix == ".svg":
        return _canonical_svg(data)
    if suffix == ".pdf":
        return _canonical_pdf(data)
    return data


def file_hashes(path: Path) -> dict[str, str]:
    return {
        "byte_sha256": sha256_file(path),
        "canonical_sha256": sha256_bytes(canonical_bytes(path)),
    }


def is_cache_file(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix.lower() in EXCLUDED_SUFFIXES


def should_track(path: Path, root: Path) -> bool:
    relative = path.resolve().relative_to(root.resolve())
    if path.name in EXCLUDED_NAMES:
        return False
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def is_allowed_untracked(path: Path, root: Path) -> bool:
    relative = path.resolve().relative_to(root.resolve())
    if any(part in ALLOWED_UNTRACKED_PARTS for part in relative.parts):
        return True
    if relative.parts and relative.parts[0] in ALLOWED_UNTRACKED_ROOTS:
        return True
    if path.name in EXCLUDED_NAMES:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    return False


def build_checksums(root: Path) -> dict[str, Any]:
    files = {
        rel(path, root): file_hashes(path)
        for path in sorted(root.rglob("*"))
        if should_track(path, root)
    }
    return {"schema": "scientificfigure.checksums.v3", "root": ".", "files": files}


def _expected_hashes(value: Any) -> dict[str, str]:
    if isinstance(value, str):
        return {"byte_sha256": value}
    if isinstance(value, dict):
        result: dict[str, str] = {}
        if value.get("byte_sha256"):
            result["byte_sha256"] = str(value["byte_sha256"])
        elif value.get("sha256"):
            result["byte_sha256"] = str(value["sha256"])
        if value.get("canonical_sha256"):
            result["canonical_sha256"] = str(value["canonical_sha256"])
        return result
    return {}


def verify_checksums(root: Path, checksums_path: Path) -> dict[str, Any]:
    root = root.resolve()
    payload = json.loads(checksums_path.read_text(encoding="utf-8-sig"))
    expected = payload.get("files") or {}
    failures: list[dict[str, str]] = []
    for name, digest_payload in expected.items():
        path = root / name
        if not path.exists():
            failures.append({"path": name, "reason": "missing"})
            continue
        expected_hashes = _expected_hashes(digest_payload)
        actual_hashes = file_hashes(path)
        for key, expected_digest in expected_hashes.items():
            actual_digest = actual_hashes.get(key)
            if actual_digest != expected_digest:
                failures.append({"path": name, "reason": f"{key}_mismatch", "expected": expected_digest, "actual": actual_digest or ""})
    expected_names = set(expected)
    current_trackable = {
        rel(path, root)
        for path in sorted(root.rglob("*"))
        if path.is_file() and should_track(path, root)
    }
    unexpected_files = sorted(name for name in current_trackable - expected_names if not is_allowed_untracked(root / name, root))
    unexpected_cache = [rel(path, root) for path in sorted(root.rglob("*")) if path.is_file() and is_cache_file(path)]
    status = "pass" if not failures and not unexpected_files and not unexpected_cache else "failed"
    return {
        "schema": "scientificfigure.checksum_verification.v2",
        "status": status,
        "root": ".",
        "checksums": rel(checksums_path, root) if checksums_path.is_absolute() else str(checksums_path),
        "checked_files": len(expected),
        "failures": failures,
        "unexpected_files": unexpected_files,
        "unexpected_python_cache": unexpected_cache,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write or verify deterministic reproduction bundle checksums.")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--checksums", type=Path)
    parser.add_argument("--write", action="store_true", help="Write checksums instead of verifying them.")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    checksums = args.checksums or root / "checksums.json"
    if args.write:
        result = build_checksums(root)
        write_json(checksums, result)
        verification = verify_checksums(root, checksums)
        result["verification"] = verification
        payload = result
        return_code = 0 if verification["status"] == "pass" else 2
    else:
        payload = verify_checksums(root, checksums)
        return_code = 0 if payload["status"] == "pass" else 2
    if args.json_out:
        write_json(args.json_out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
