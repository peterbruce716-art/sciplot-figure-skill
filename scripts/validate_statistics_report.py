from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from advisor_common import load_json, validate_payload, write_json
from portable_paths import portable_path


def _unknown_text(value: Any) -> bool:
    return str(value or "").strip().lower() in {"", "unknown", "not declared", "not_declared"} or "unknown" in str(value or "").strip().lower()


def validate_statistics_payload(report: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        validate_payload(report, "statistics-report-v1.schema.json")
    except Exception as exc:
        failures.append({"code": "schema_error", "message": str(exc)})
        return {
            "schema": "scientificfigure.statistics_report_validation.v1",
            "status": "failed",
            "failures": failures,
            "warnings": warnings,
        }

    seen: set[str] = set()
    unknown_blockers: list[str] = []
    for panel in report.get("panels", []):
        panel_id = str(panel.get("panel_id"))
        if panel_id in seen:
            failures.append({"code": "duplicate_panel_id", "panel_id": panel_id})
        seen.add(panel_id)
        if _unknown_text(panel.get("n_definition")):
            unknown_blockers.append(f"Panel {panel_id} n definition is unknown")
        if panel.get("center") == "unknown":
            unknown_blockers.append(f"Panel {panel_id} center statistic is unknown")
        if panel.get("spread") == "unknown":
            unknown_blockers.append(f"Panel {panel_id} spread statistic is unknown")
        test = panel.get("test") or {}
        if test.get("status") == "unknown":
            unknown_blockers.append(f"Panel {panel_id} statistical test is unknown")
        if not panel.get("source_trace"):
            unknown_blockers.append(f"Panel {panel_id} source trace is missing")
            warnings.append({"code": "missing_source_trace", "severity": "warning", "message": f"Panel {panel_id} has no source trace."})

    readiness = report.get("publication_readiness") or {}
    blocking = set(readiness.get("blocking_reasons") or [])
    missing = [reason for reason in unknown_blockers if reason not in blocking]
    if missing and readiness.get("status") == "ready":
        failures.append({"code": "unknown_statistics_marked_ready", "blocking_reasons": missing})
    elif missing:
        warnings.append({"code": "unknown_statistics_block_publication_ready", "severity": "warning", "message": "; ".join(missing)})

    return {
        "schema": "scientificfigure.statistics_report_validation.v1",
        "status": "pass" if not failures else "failed",
        "failures": failures,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a scientific figure statistics report.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()

    result = validate_statistics_payload(load_json(args.input))
    root = (args.project_root or args.input.parent).resolve()
    result["input"] = portable_path(args.input, root)
    if args.report:
        write_json(args.report, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
