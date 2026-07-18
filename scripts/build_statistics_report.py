from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from advisor_common import load_json, validate_payload, write_json
from validate_statistics_report import validate_statistics_payload


def _columns(profile: dict[str, Any]) -> list[str]:
    return [str(item.get("name")) for item in profile.get("columns", []) if item.get("name") is not None]


def _panel_ids(contract: dict[str, Any] | None) -> list[str]:
    if not contract:
        return ["A"]
    ids = [str(item.get("panel_id")) for item in contract.get("panel_plan", []) if item.get("panel_id")]
    return ids or ["A"]


def _json_arg(value: str | None, *, label: str) -> dict[str, Any] | None:
    if not value:
        return None
    path = Path(value)
    text = path.read_text(encoding="utf-8-sig") if path.exists() else value
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be JSON text or a path to a JSON file") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def _declared_panel_map(declared_statistics: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not declared_statistics:
        return {}
    raw_panels = declared_statistics.get("panels", declared_statistics.get("panel_statistics"))
    if isinstance(raw_panels, list):
        return {str(item.get("panel_id")): item for item in raw_panels if isinstance(item, dict) and item.get("panel_id")}
    return {str(key): value for key, value in declared_statistics.items() if isinstance(value, dict)}


def _default_source_trace(profile: dict[str, Any]) -> dict[str, Any]:
    source = profile.get("source") or {}
    return {
        "file": str(source.get("path") or "unknown_source"),
        "sheet": source.get("sheet"),
        "columns": _columns(profile),
        "filters": [],
        "aggregation": None,
        "sample_definition": "unknown",
        "random_seed": None,
        "split": None,
        "metric_definition": None,
        "sha256": source.get("sha256"),
    }


def _unknown_text(value: Any) -> bool:
    return str(value or "").strip().lower() in {"", "unknown", "not declared", "not_declared"} or "unknown" in str(value or "").strip().lower()


def _panel_blockers(panel: dict[str, Any]) -> list[str]:
    panel_id = panel["panel_id"]
    blockers: list[str] = []
    if _unknown_text(panel.get("n_definition")):
        blockers.append(f"Panel {panel_id} n definition is unknown")
    if panel.get("center") == "unknown":
        blockers.append(f"Panel {panel_id} center statistic is unknown")
    if panel.get("spread") == "unknown":
        blockers.append(f"Panel {panel_id} spread statistic is unknown")
    if (panel.get("test") or {}).get("status") == "unknown":
        blockers.append(f"Panel {panel_id} statistical test is unknown")
    if not panel.get("source_trace"):
        blockers.append(f"Panel {panel_id} source trace is missing")
    return blockers


def _build_panel_statistics(profile: dict[str, Any], panel_id: str, declared: dict[str, Any] | None) -> dict[str, Any]:
    if declared:
        test = dict(declared.get("test") or {"name": "unknown", "status": "unknown", "multiple_comparison": None})
        test.setdefault("multiple_comparison", None)
        if test.get("status") == "declared":
            provenance = dict(test.get("provenance") or {})
            provenance.setdefault("status_source", "declared_statistics")
            test["provenance"] = provenance
        return {
            "panel_id": panel_id,
            "n_definition": str(declared.get("n_definition") or "unknown"),
            "center": declared.get("center", "unknown"),
            "spread": declared.get("spread", "unknown"),
            "test": test,
            "source_trace": declared.get("source_trace") or [_default_source_trace(profile)],
            "advisory": declared.get("advisory") or [
                {
                    "code": "statistics_declared_not_recomputed",
                    "severity": "info",
                    "message": "Statistics were imported from user-declared JSON and were not recomputed by the figure pipeline.",
                }
            ],
        }

    return {
        "panel_id": panel_id,
        "n_definition": f"row_count={profile.get('row_count', 'unknown')}; biological/technical replicate definition unknown",
        "center": "unknown",
        "spread": "unknown",
        "test": {"name": "unknown", "status": "unknown", "multiple_comparison": None},
        "source_trace": [_default_source_trace(profile)],
        "advisory": [
            {
                "code": "statistics_not_declared",
                "severity": "warning",
                "message": "Center, spread, and statistical test are unknown until declared by the user or a traceable analysis script.",
            }
        ],
    }


def build_statistics_report(
    profile: dict[str, Any],
    *,
    figure_contract: dict[str, Any] | None = None,
    declared_statistics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    declared_by_panel = _declared_panel_map(declared_statistics)
    panels: list[dict[str, Any]] = []
    blocking: list[str] = []
    for panel_id in _panel_ids(figure_contract):
        panel = _build_panel_statistics(profile, panel_id, declared_by_panel.get(panel_id))
        panels.append(panel)
        blocking.extend(_panel_blockers(panel))
    payload = {
        "schema": "scientificfigure.statistics_report.v1",
        "schema_version": "1.0",
        "panels": panels,
        "publication_readiness": {
            "status": "conditional" if blocking else "ready",
            "blocking_reasons": blocking,
            "advisory": [
                {
                    "code": "reproduction_allowed_publication_conditional",
                    "severity": "warning",
                    "message": "Unknown statistics do not block deterministic reproduction but do block publication-ready attestation.",
                }
            ] if blocking else [],
        },
        "provenance": {
            "data_profile_schema": profile.get("schema"),
            "figure_contract_schema": (figure_contract or {}).get("schema"),
            "builder": "scripts/build_statistics_report.py",
            "declared_statistics": bool(declared_statistics),
        },
    }
    validate_payload(payload, "statistics-report-v1.schema.json")
    validation = validate_statistics_payload(payload)
    if validation["status"] != "pass":
        raise ValueError("invalid generated statistics report: " + json.dumps(validation["failures"], ensure_ascii=False))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a statistics transparency report without inventing tests or significance.")
    parser.add_argument("--data-profile", required=True, type=Path)
    parser.add_argument("--figure-contract", type=Path)
    parser.add_argument("--statistics-json", help="User-declared statistics JSON text or path. Values are imported as declarations, not recomputed.")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = build_statistics_report(
            load_json(args.data_profile),
            figure_contract=load_json(args.figure_contract) if args.figure_contract else None,
            declared_statistics=_json_arg(args.statistics_json, label="--statistics-json"),
        )
        write_json(args.output, payload)
    except Exception as exc:
        parser.exit(2, f"build_statistics_report: {exc}\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
