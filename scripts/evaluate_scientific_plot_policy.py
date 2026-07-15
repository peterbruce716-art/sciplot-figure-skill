from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from advisor_common import load_json, validate_payload, write_json


def _get(payload: dict[str, Any], field: str) -> Any:
    current: Any = payload
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _matches(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "missing":
        return (actual is None) is bool(expected)
    if actual is None:
        return False
    if operator == "eq": return actual == expected
    if operator == "ne": return actual != expected
    if operator == "lt": return actual < expected
    if operator == "lte": return actual <= expected
    if operator == "gt": return actual > expected
    if operator == "gte": return actual >= expected
    if operator == "in": return actual in expected
    if operator == "not_in": return actual not in expected
    if operator == "contains": return expected in actual
    return False


def evaluate_policies(
    context: dict[str, Any],
    policy: dict[str, Any],
    *,
    disabled: set[str] | None = None,
    severity_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    disabled = disabled or set()
    severity_overrides = severity_overrides or {}
    findings: list[dict[str, Any]] = []
    for item in policy.get("policies", []):
        policy_id = str(item.get("policy_id"))
        if not item.get("enabled", True) or policy_id in disabled:
            continue
        if not all(_matches(_get(context, str(condition["field"])), str(condition["operator"]), condition.get("value")) for condition in item.get("when", [])):
            continue
        findings.append({
            "policy_id": policy_id,
            "severity": severity_overrides.get(policy_id, item.get("severity", "warning")),
            "message": item.get("message", ""),
            "recommended_actions": list(item.get("recommended_actions", [])),
        })
    counts = {severity: sum(1 for item in findings if item["severity"] == severity) for severity in ["info", "warning", "error"]}
    return {
        "schema": "scientificfigure.plot_policy_report.v1",
        "policy_version": policy.get("policy_version", "unknown"),
        "status": "fail" if counts["error"] else ("pass_with_warnings" if findings else "pass"),
        "counts": counts,
        "disabled_policy_ids": sorted(disabled),
        "findings": findings,
        "context": context,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate configurable scientific plotting policies.")
    parser.add_argument("--policy", type=Path, default=Path(__file__).resolve().parents[1] / "policies" / "scientific-plot-policy-v1.json")
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--disable", action="append", default=[])
    parser.add_argument("--severity", action="append", default=[], help="Override as policy_id=info|warning|error")
    args = parser.parse_args()
    overrides = dict(item.split("=", 1) for item in args.severity if "=" in item)
    try:
        payload = evaluate_policies(load_json(args.context), load_json(args.policy), disabled=set(args.disable), severity_overrides=overrides)
        write_json(args.output, payload)
    except Exception as exc:
        parser.exit(2, f"evaluate_scientific_plot_policy: {exc}\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
