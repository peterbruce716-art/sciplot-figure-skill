from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from advisor_common import load_json, validate_payload, write_json
from validate_figure_contract import validate_contract_payload


def _json_arg(value: str | None, *, label: str) -> Any:
    if not value:
        return None
    path = Path(value)
    text = path.read_text(encoding="utf-8-sig") if path.exists() else value
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be JSON text or a path to a JSON file") from exc


def _default_evidence(profile: dict[str, Any]) -> list[dict[str, Any]]:
    source = profile.get("source") or {}
    source_path = str(source.get("path") or "unknown_source")
    sha256 = source.get("sha256")
    return [
        {
            "id": "E1",
            "source": source_path,
            "claim": "Input data source is available; scientific interpretation remains user-declared or unknown.",
            "status": "unknown",
            "provenance": {"sha256": sha256},
        }
    ]


def _default_panel_plan(question: str, evidence_ids: list[str], *, hero_panel_id: str | None) -> list[dict[str, Any]]:
    panel_id = hero_panel_id or "A"
    role = "hero" if hero_panel_id else "evidence"
    return [
        {
            "panel_id": panel_id,
            "scientific_role": role,
            "question": question,
            "preferred_representation": "chart_from_data_profile",
            "evidence_ids": evidence_ids,
            "panel_weight": 1.0 if role != "hero" else 1.5,
            "backend": "matplotlib",
            "required_output": "svg",
        }
    ]


def build_contract(
    data_profile: dict[str, Any],
    *,
    question: str,
    core_claim: str = "unknown",
    target_audience: str = "scientific_readers",
    target_journal: str = "generic_scientific",
    target_width_mm: float = 183.0,
    archetype: str = "quantitative_grid",
    hero_panel_id: str | None = None,
    panel_plan: list[dict[str, Any]] | None = None,
    evidence_chain: list[dict[str, Any]] | None = None,
    approval_mode: str = "auto",
    strict: bool = False,
) -> dict[str, Any]:
    evidence = evidence_chain if evidence_chain is not None else _default_evidence(data_profile)
    evidence_ids = [str(item.get("id")) for item in evidence if isinstance(item, dict) and item.get("id")]
    panels = panel_plan if panel_plan is not None else _default_panel_plan(question, evidence_ids, hero_panel_id=hero_panel_id)
    assumptions: list[dict[str, str]] = []
    if evidence_chain is None:
        assumptions.append({
            "id": "A1",
            "statement": "Evidence source was initialized from the data profile; no scientific result was inferred.",
            "reason": "No explicit evidence JSON was supplied.",
            "status": "defaulted",
        })
    if panel_plan is None:
        assumptions.append({
            "id": "A2",
            "statement": "A single-panel plan was created from the scientific question.",
            "reason": "No explicit panel-plan JSON was supplied.",
            "status": "defaulted",
        })
    if core_claim.strip().lower() in {"", "unknown"}:
        assumptions.append({
            "id": "A3",
            "statement": "The core claim is unknown and must not be upgraded by rendering or advisory review.",
            "reason": "No user-declared core claim was supplied.",
            "status": "unknown",
        })
        core_claim = "unknown"
    approval_status = "pending" if approval_mode in {"interactive", "strict"} else "not_required"
    if strict:
        approval_mode = "strict"
        approval_status = "pending"
    payload = {
        "schema": "scientificfigure.figure_contract.v1",
        "schema_version": "1.0",
        "scientific_question": question,
        "core_claim": core_claim,
        "target_audience": target_audience,
        "target_journal": target_journal,
        "target_width_mm": float(target_width_mm),
        "archetype": archetype,
        "hero_panel_id": hero_panel_id,
        "evidence_chain": evidence,
        "panel_plan": panels,
        "assumptions": assumptions,
        "approval": {"mode": approval_mode, "status": approval_status},
        "provenance": {
            "data_profile_schema": data_profile.get("schema"),
            "builder": "scripts/build_figure_contract.py",
            "import_mode": "concept_and_parameter_adaptation",
        },
    }
    validate_payload(payload, "figure-contract-v1.schema.json")
    validation = validate_contract_payload(payload)
    if validation["status"] != "pass":
        raise ValueError("invalid generated figure contract: " + json.dumps(validation["failures"], ensure_ascii=False))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a FigureContract from a data profile and explicit user intent.")
    parser.add_argument("--data-profile", required=True, type=Path)
    parser.add_argument("--question", required=True)
    parser.add_argument("--core-claim", default="unknown")
    parser.add_argument("--target-audience", default="scientific_readers")
    parser.add_argument("--target-journal", default="generic_scientific")
    parser.add_argument("--target-width-mm", type=float, default=183.0)
    parser.add_argument("--archetype", choices=["quantitative_grid", "schematic_led", "image_quant", "asymmetric_mixed"], default="quantitative_grid")
    parser.add_argument("--hero-panel-id")
    parser.add_argument("--panel-plan-json")
    parser.add_argument("--evidence-json")
    parser.add_argument("--approval-mode", choices=["auto", "interactive", "strict"], default="auto")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        payload = build_contract(
            load_json(args.data_profile),
            question=args.question,
            core_claim=args.core_claim,
            target_audience=args.target_audience,
            target_journal=args.target_journal,
            target_width_mm=args.target_width_mm,
            archetype=args.archetype,
            hero_panel_id=args.hero_panel_id,
            panel_plan=_json_arg(args.panel_plan_json, label="--panel-plan-json"),
            evidence_chain=_json_arg(args.evidence_json, label="--evidence-json"),
            approval_mode=args.approval_mode,
            strict=args.strict,
        )
        write_json(args.output, payload)
    except Exception as exc:
        parser.exit(2, f"build_figure_contract: {exc}\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
