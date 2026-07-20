"""Validate a fresh-digitization source policy and its consumed-input record.

The check is intentionally independent from rendering.  It prevents a fresh
pixel measurement run from silently consuming historical tables, arrays,
projects, or stale QA artifacts while still allowing the project to keep its
own domain-specific extraction logic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_relative(value: str) -> str:
    return value.replace("\\", "/")


def _validate_fresh_outputs(
    *, root: Path, policy: dict[str, Any], allowed_set: set[str], failures: list[dict[str, str]]
) -> list[str]:
    """Validate fresh measurement artifacts against the current reference hashes.

    A source-only check can pass while a renderer still consumes stale JSON.  When
    the policy declares ``fresh_outputs_required``, each artifact must exist, be a
    project-relative JSON object, identify an allowed reference, and carry the
    current reference SHA-256 plus ``historical_data_consumed: false``.
    """
    declared = policy.get("fresh_outputs_required", [])
    if declared is None:
        return []
    if not isinstance(declared, list) or any(not isinstance(item, str) for item in declared):
        failures.append({"check": "fresh_outputs_required", "message": "list of relative paths required"})
        return []
    outputs: list[str] = []
    for raw_path in declared:
        relative = _normalise_relative(raw_path)
        outputs.append(relative)
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            failures.append({"check": "fresh_output_path_escape", "path": relative})
            continue
        candidate = root / path
        if not candidate.is_file():
            failures.append({"check": "fresh_output_exists", "path": relative})
            continue
        if candidate.suffix.lower() != ".json":
            failures.append({"check": "fresh_output_format", "path": relative, "message": "fresh outputs must be JSON"})
            continue
        try:
            payload = _load(candidate)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append({"check": "fresh_output_json", "path": relative, "message": str(exc)})
            continue
        source = payload.get("source")
        source = _normalise_relative(source) if isinstance(source, str) else ""
        if source not in allowed_set:
            failures.append({"check": "fresh_output_source", "path": relative, "message": f"source={source!r}"})
            continue
        source_path = root / Path(source)
        if not source_path.is_file():
            failures.append({"check": "fresh_output_source_exists", "path": relative})
            continue
        expected_hash = _sha256(source_path)
        if payload.get("source_sha256") != expected_hash:
            failures.append({"check": "fresh_output_source_hash", "path": relative})
        if payload.get("historical_data_consumed") is not False:
            failures.append({"check": "fresh_output_historical_data", "path": relative})
    return outputs


def validate_source_policy(
    *, root: Path, policy_path: Path, consumed_path: Path, source_pdf_path: Path | None = None
) -> dict[str, Any]:
    policy = _load(policy_path)
    consumed = _load(consumed_path)
    failures: list[dict[str, str]] = []

    # PDF pixel traces use the source PDF itself as the immutable reference;
    # they do not have project-relative PNG inputs or digitized JSON outputs.
    # Validate the source identity directly and keep this path separate from
    # the fresh-digitization contract below.
    if policy.get("data_policy") == "fresh_pdf_trace":
        policy_hash = policy.get("source_pdf_sha256")
        consumed_source = consumed.get("source_pdf")
        consumed_hash = consumed_source.get("sha256") if isinstance(consumed_source, dict) else None
        if not isinstance(policy_hash, str) or not policy_hash:
            failures.append({"check": "source_pdf_sha256", "message": "non-empty source PDF hash required"})
        if consumed_hash != policy_hash:
            failures.append({"check": "source_pdf_hash", "message": "consumed source PDF hash does not match policy"})
        if source_pdf_path is not None:
            if not source_pdf_path.is_file():
                failures.append({"check": "source_pdf_exists", "path": str(source_pdf_path)})
            elif _sha256(source_pdf_path) != policy_hash:
                failures.append({"check": "source_pdf_current_hash", "message": "source PDF hash mismatch"})
        if policy.get("historical_data_allowed") is not False:
            failures.append({"check": "historical_data_allowed", "message": "historical inputs must be disabled"})
        if consumed.get("historical_data_consumed") is not False:
            failures.append({"check": "historical_data_consumed", "message": "must be false"})
        policy_figures = policy.get("figures")
        consumed_figures = consumed.get("figure_order")
        if isinstance(policy_figures, list) and isinstance(consumed_figures, list) and policy_figures != consumed_figures:
            failures.append({"check": "figure_order", "message": "policy and consumed figure declarations differ"})
        return {
            "schema": "scientificfigure.source-policy-validation.v1",
            "status": "pass" if not failures else "failed",
            "root": ".",
            "policy": policy_path.name,
            "consumed_inputs": consumed_path.name,
            "checked_inputs": [],
            "checked_fresh_outputs": [],
            "failures": failures,
        }

    if policy.get("data_policy") != "fresh_digitization":
        failures.append({"check": "data_policy", "message": "data_policy must be fresh_digitization"})
    if policy.get("historical_data_allowed") is not False:
        failures.append({"check": "historical_data_allowed", "message": "historical inputs must be disabled"})

    allowed = policy.get("allowed_reference_inputs")
    if not isinstance(allowed, list) or not allowed or any(not isinstance(item, str) for item in allowed):
        failures.append({"check": "allowed_reference_inputs", "message": "non-empty string list required"})
        allowed = []
    allowed_set = {item.replace("\\", "/") for item in allowed}

    consumed_items = consumed.get("inputs")
    if not isinstance(consumed_items, list):
        failures.append({"check": "consumed_inputs", "message": "inputs list required"})
        consumed_items = []
    consumed_paths: set[str] = set()
    forbidden_tokens = consumed.get("forbidden_path_tokens", [])
    if not isinstance(forbidden_tokens, list):
        forbidden_tokens = []
        failures.append({"check": "forbidden_path_tokens", "message": "list required"})

    for item in consumed_items:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            failures.append({"check": "consumed_inputs", "message": "each input needs a string path"})
            continue
        relative = item["path"].replace("\\", "/")
        consumed_paths.add(relative)
        lowered = relative.lower()
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            failures.append({"check": "path_escape", "path": relative})
            continue
        for token in forbidden_tokens:
            if isinstance(token, str) and token.lower() in lowered:
                failures.append({"check": "forbidden_path", "path": relative, "token": token})
        candidate = root / Path(relative)
        if not candidate.is_file():
            failures.append({"check": "input_exists", "path": relative})
            continue
        expected_hash = item.get("sha256")
        if expected_hash is not None and expected_hash != _sha256(candidate):
            failures.append({"check": "input_hash", "path": relative})

    if consumed_paths != allowed_set:
        failures.append(
            {
                "check": "input_set",
                "message": f"consumed={sorted(consumed_paths)!r}; allowed={sorted(allowed_set)!r}",
            }
        )
    if any(not path.lower().endswith(".png") for path in consumed_paths):
        failures.append({"check": "reference_format", "message": "fresh references must be PNG files"})
    if "historical_data_consumed" in consumed and consumed.get("historical_data_consumed") is not False:
        failures.append({"check": "historical_data_consumed", "message": "must be false"})

    fresh_outputs = _validate_fresh_outputs(
        root=root,
        policy=policy,
        allowed_set=allowed_set,
        failures=failures,
    )

    return {
        "schema": "scientificfigure.source-policy-validation.v1",
        "status": "pass" if not failures else "failed",
        "root": ".",
        "policy": policy_path.name,
        "consumed_inputs": consumed_path.name,
        "checked_inputs": sorted(consumed_paths),
        "checked_fresh_outputs": fresh_outputs,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--consumed", type=Path, required=True)
    parser.add_argument("--source-pdf", type=Path, help="Optional current PDF to hash-check for fresh_pdf_trace policies")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = validate_source_policy(root=args.root, policy_path=args.policy, consumed_path=args.consumed, source_pdf_path=args.source_pdf)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
