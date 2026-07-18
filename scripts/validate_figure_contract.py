from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from advisor_common import load_json, validate_payload, write_json
from portable_paths import portable_path


ARCHETYPE_MIN_PANELS = {
    "quantitative_grid": 1,
    "schematic_led": 2,
    "image_quant": 2,
    "asymmetric_mixed": 1,
}


def validate_contract_payload(contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        validate_payload(contract, "figure-contract-v1.schema.json")
    except Exception as exc:
        failures.append({"code": "schema_error", "message": str(exc)})
        return {
            "schema": "scientificfigure.figure_contract_validation.v1",
            "status": "failed",
            "failures": failures,
            "warnings": warnings,
        }

    panels = contract.get("panel_plan") or []
    evidence = contract.get("evidence_chain") or []
    evidence_ids = {str(item.get("id")) for item in evidence if isinstance(item, dict)}
    panel_ids: list[str] = []
    hero_roles: list[str] = []
    for panel in panels:
        panel_id = str(panel.get("panel_id"))
        if panel_id in panel_ids:
            failures.append({"code": "duplicate_panel_id", "panel_id": panel_id})
        panel_ids.append(panel_id)
        if panel.get("scientific_role") == "hero":
            hero_roles.append(panel_id)
        for evidence_id in panel.get("evidence_ids", []):
            if evidence_id not in evidence_ids:
                failures.append({"code": "missing_evidence_reference", "panel_id": panel_id, "evidence_id": evidence_id})

    hero_panel_id = contract.get("hero_panel_id")
    if hero_panel_id and hero_panel_id not in panel_ids:
        failures.append({"code": "invalid_hero_panel_id", "hero_panel_id": hero_panel_id})
    if len(hero_roles) > 1:
        failures.append({"code": "multiple_hero_panels", "panel_ids": hero_roles})
    if hero_panel_id and hero_roles and hero_panel_id not in hero_roles:
        warnings.append({"code": "hero_id_role_mismatch", "severity": "warning", "message": "hero_panel_id does not match the panel marked with scientific_role=hero."})

    archetype = str(contract.get("archetype"))
    min_panels = ARCHETYPE_MIN_PANELS.get(archetype, 1)
    if len(panels) < min_panels:
        warnings.append({"code": "archetype_panel_count_low", "severity": "warning", "message": f"{archetype} usually needs at least {min_panels} panel(s)."})
    if archetype == "quantitative_grid" and hero_panel_id:
        warnings.append({"code": "quantitative_grid_has_hero", "severity": "warning", "message": "quantitative_grid normally uses equal panel weights and no hero panel."})
    if archetype in {"schematic_led", "image_quant", "asymmetric_mixed"} and len(panels) > 1 and not hero_panel_id and not hero_roles:
        warnings.append({"code": "missing_hero_for_asymmetric_layout", "severity": "warning", "message": "Asymmetric layouts should declare a hero panel or record why none exists."})

    assumptions = contract.get("assumptions") or []
    assumption_text = " ".join(str(item.get("statement", "")) for item in assumptions if isinstance(item, dict)).lower()
    for item in evidence:
        if item.get("status") == "inferred" and str(item.get("id", "")).lower() not in assumption_text:
            warnings.append({"code": "inferred_evidence_without_assumption_link", "severity": "warning", "message": f"Evidence {item.get('id')} is inferred; record the inference in assumptions or provenance."})

    approval = contract.get("approval") or {}
    if approval.get("mode") == "strict" and approval.get("status") != "approved":
        failures.append({"code": "strict_approval_not_approved", "message": "strict approval mode requires approval.status=approved"})

    return {
        "schema": "scientificfigure.figure_contract_validation.v1",
        "status": "pass" if not failures else "failed",
        "failures": failures,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a scientific figure contract.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()

    result = validate_contract_payload(load_json(args.input))
    root = (args.project_root or args.input.parent).resolve()
    result["input"] = portable_path(args.input, root)
    if args.report:
        write_json(args.report, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
