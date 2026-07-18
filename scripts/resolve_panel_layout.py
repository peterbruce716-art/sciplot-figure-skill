from __future__ import annotations

from typing import Any


ARCHETYPES = {"quantitative_grid", "schematic_led", "image_quant", "asymmetric_mixed"}


def resolve_layout(contract: dict[str, Any] | None, *, panel_ids: list[str] | None = None) -> dict[str, Any]:
    contract = contract or {}
    panels = list(contract.get("panel_plan") or [])
    inference_log: list[dict[str, Any]] = []
    ids = panel_ids or [str(panel.get("panel_id")) for panel in panels if panel.get("panel_id")]
    if not ids:
        ids = ["A"]
        inference_log.append({
            "field": "layout.narrative_order",
            "value": ids,
            "source": "default",
            "status": "defaulted",
            "reason": "No panel IDs were supplied by FigureContract or the caller.",
        })
    archetype = str(contract.get("archetype") or "quantitative_grid")
    if archetype not in ARCHETYPES:
        inference_log.append({
            "field": "layout.archetype",
            "value": "quantitative_grid",
            "source": "default",
            "status": "defaulted",
            "reason": f"Unsupported archetype {archetype!r}; using quantitative_grid.",
        })
        archetype = "quantitative_grid"
    hero_panel_id = contract.get("hero_panel_id")
    hero_source = "contract.hero_panel_id" if hero_panel_id else None
    if not hero_panel_id:
        hero_panels = [panel for panel in panels if panel.get("scientific_role") == "hero"]
        if len(hero_panels) == 1:
            hero_panel_id = hero_panels[0].get("panel_id")
            hero_source = "panel_plan.scientific_role"
            inference_log.append({
                "field": "layout.hero_panel_id",
                "value": hero_panel_id,
                "source": hero_source,
                "status": "inferred",
                "reason": "Exactly one panel declares scientific_role=hero.",
            })
    weights: dict[str, float] = {panel_id: 1.0 for panel_id in ids}
    for panel in panels:
        panel_id = str(panel.get("panel_id") or "")
        if panel_id in weights:
            weights[panel_id] = float(panel.get("panel_weight", 1.0))
    if hero_panel_id in weights and archetype != "quantitative_grid":
        before = weights[str(hero_panel_id)]
        weights[str(hero_panel_id)] = max(weights[str(hero_panel_id)], 1.5)
        if weights[str(hero_panel_id)] != before:
            inference_log.append({
                "field": f"layout.panel_weights.{hero_panel_id}",
                "value": weights[str(hero_panel_id)],
                "source": hero_source or "layout.hero_panel_id",
                "status": "derived",
                "reason": "Hero panels in asymmetric layouts require at least 1.5 visual weight.",
            })
    target_width_mm = float(contract.get("target_width_mm") or 183.0)
    gutter_mm = 3.0 if target_width_mm >= 120 else 2.0
    layout = {
        "archetype": archetype,
        "hero_panel_id": hero_panel_id,
        "narrative_order": ids,
        "panel_weights": weights,
        "gutter_mm": gutter_mm,
        "alignment": "baseline",
        "target_width_mm": target_width_mm,
        "min_panel_width_mm": 35.0,
        "min_readable_font_size_pt": 6.0,
    }
    if inference_log:
        layout["inference_log"] = inference_log
    return layout


def panel_semantics(contract: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    semantics: dict[str, dict[str, Any]] = {}
    for panel in (contract or {}).get("panel_plan", []) or []:
        panel_id = str(panel.get("panel_id") or "")
        if not panel_id:
            continue
        semantics[panel_id] = {
            "semantic_role": panel.get("scientific_role"),
            "answers_question": panel.get("question"),
            "evidence_ids": list(panel.get("evidence_ids") or []),
            "panel_weight": float(panel.get("panel_weight", 1.0)),
            "backend": panel.get("backend", "matplotlib"),
            "required_output": panel.get("required_output", "svg"),
        }
    return semantics
