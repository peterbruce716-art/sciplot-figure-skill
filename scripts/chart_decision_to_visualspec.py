from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from advisor_common import load_json, validate_payload, write_json
from resolve_panel_layout import panel_semantics, resolve_layout


SUPPORTED = {
    "line", "line_with_markers", "line_with_error_bars", "line_with_error_band",
    "scatter", "grouped_bar", "stacked_bar", "heatmap", "contour",
}


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _source_ref(path: Path, root: Path) -> str:
    return Path(os.path.relpath(path.resolve(), root.resolve())).as_posix()


def _style(theme: dict[str, Any] | None = None) -> dict[str, Any]:
    theme = theme or {}
    settings = theme.get("settings", theme)
    return {
        "line_width_pt": float(settings.get("line_width_pt", settings.get("line_width", 1.2))),
        "marker_size_pt2": float(settings.get("marker_size_pt2", settings.get("marker_size", 18))),
        "color": settings.get("primary_color", "#0072B2"),
        "alpha": float(settings.get("alpha", 1.0)),
    }


def _typed_style(style: dict[str, Any], kind: str) -> dict[str, Any]:
    allowed = {
        "line": {"line_width_pt", "color", "alpha", "marker", "line_style"},
        "scatter": {"marker_size_pt2", "color", "alpha", "marker"},
        "errorbar": {"line_width_pt", "color", "alpha", "marker", "line_style", "capsize"},
    }[kind]
    return {key: value for key, value in style.items() if key in allowed}


def materialize_chart_decision(
    decision: dict[str, Any],
    *,
    data_path: Path,
    output_dir: Path,
    x: str,
    y: str,
    style_profile: dict[str, Any] | None = None,
    figure_intent: dict[str, Any] | None = None,
    figure_contract: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    recommended = str(decision.get("recommended_type", ""))
    if recommended not in SUPPORTED:
        raise ValueError(f"unsupported chart decision '{recommended}'; use a project-level renderer instead of silently drawing a line")
    output_dir.mkdir(parents=True, exist_ok=True)
    source = data_path.resolve()
    root = output_dir.resolve()
    derived_path: Path | None = None
    plot_style = _style(style_profile)
    plots: list[dict[str, Any]] = []
    mapping: dict[str, Any] = {"x": x, "y": y}
    source_ref = _source_ref(source, root)
    contract_panels = list((figure_contract or {}).get("panel_plan") or [])
    panel_id = str(contract_panels[0].get("panel_id")) if contract_panels and contract_panels[0].get("panel_id") else "A"
    layout = resolve_layout(figure_contract, panel_ids=[panel_id])
    semantics = panel_semantics(figure_contract).get(panel_id, {})

    if recommended in {"line", "line_with_markers", "scatter"}:
        plot_type = "scatter" if recommended == "scatter" else "line"
        style = _typed_style(plot_style, plot_type)
        if recommended == "line_with_markers":
            style["marker"] = "o"
        plots.append({"type": plot_type, "data": {"source": source_ref, "mapping": {"x": x, "y": y}}, "style": style})
    elif recommended == "line_with_error_bars":
        error_column = decision.get("data_columns", {}).get("error") or decision.get("uncertainty_source")
        if not error_column:
            raise ValueError("line_with_error_bars requires a declared uncertainty column")
        plots.append({"type": "errorbar", "data": {"source": source_ref, "mapping": {"x": x, "y": y, "yerr": error_column}}, "style": _typed_style(plot_style, "errorbar")})
        mapping["yerr"] = error_column
    elif recommended == "line_with_error_band":
        frame = pd.read_csv(source)
        if x not in frame or y not in frame:
            raise ValueError(f"data columns not found: {x}, {y}")
        lower = decision.get("data_columns", {}).get("lower")
        upper = decision.get("data_columns", {}).get("upper")
        if lower and upper and lower in frame and upper in frame:
            derived = frame[[x, y, lower, upper]].copy()
            mapping.update({"lower": lower, "upper": upper})
        else:
            grouped = frame.groupby([x], sort=True, dropna=False)[y]
            derived = grouped.agg(["mean", "std"]).reset_index().rename(columns={"mean": y})
            derived["std"] = derived["std"].fillna(0.0)
            derived["lower"] = derived[y] - derived["std"]
            derived["upper"] = derived[y] + derived["std"]
            mapping.update({"lower": "lower", "upper": "upper", "uncertainty": "std"})
        derived_path = output_dir / "derived" / f"{source.stem}_error_band.csv"
        derived_path.parent.mkdir(parents=True, exist_ok=True)
        derived.to_csv(derived_path, index=False)
        derived_ref = _source_ref(derived_path, root)
        plots.extend([
            {"type": "fill_between", "data": {"source": derived_ref, "mapping": {"x": x, "y1": mapping["lower"], "y2": mapping["upper"]}}, "style": {"color": plot_style["color"], "alpha": 0.18}},
            {"type": "line", "data": {"source": derived_ref, "mapping": {"x": x, "y": y}}, "style": _typed_style(plot_style, "line")},
        ])
    elif recommended in {"grouped_bar", "stacked_bar"}:
        raise ValueError(f"{recommended} requires an explicit grouped-bar data mapping; no silent reduction is allowed")
    else:
        raise ValueError(f"{recommended} requires a project-level matrix mapping")

    style_settings = (style_profile or {}).get("settings", {})
    size_width = float((figure_contract or {}).get("target_width_mm") or 85)
    size_height = max(45.0, min(120.0, size_width * 60.0 / 85.0))
    panel = {
            "id": panel_id,
            "bbox_normalized": [0.15, 0.16, 0.78, 0.75],
            "source_strategy": "raw_data",
            "representation": "semantic_vector",
            "axes": {"x": {"label": x}, "y": {"label": y}},
            "plots": plots,
            "annotations": [],
        }
    panel.update({key: value for key, value in semantics.items() if value is not None})
    spec: dict[str, Any] = {
        "schema": "scientificfigure.visualspec.v2",
        "figure": {"size_mm": [size_width, size_height], "dpi": int(style_settings.get("dpi", 300)), "crop_mode": "fixed_canvas"},
        "theme": {
            "font": {"family_candidates": [style_settings.get("font_family"), "Liberation Sans", "DejaVu Sans"], "size_pt": float(style_settings.get("font_size_pt", 8)), "mathtext_fontset": "stix"},
            "axes": {"line_width_pt": float(style_settings.get("axis_line_width_pt", style_settings.get("line_width_pt", 0.8)))},
            "palette": style_settings.get("palette", ["#0072B2", "#D55E00", "#009E73"]),
        },
        "layout": layout,
        "panels": [panel],
        "delivery": {"chart_decision_hash": _hash_payload(decision), "materialized_as": [plot["type"] for plot in plots], "data_columns": mapping, "figure_contract_hash": _hash_payload(figure_contract) if figure_contract else None},
    }
    validate_payload(spec, "visualspec-v2.schema.json")
    report = {
        "schema": "scientificfigure.chart_decision_materialization.v1",
        "decision_hash": _hash_payload(decision),
        "recommended_type": recommended,
        "materialized_as": [plot["type"] for plot in plots],
        "data_columns": mapping,
        "derived_data": None if derived_path is None else derived_path.relative_to(root).as_posix(),
        "layout": layout,
        "panel_semantics": {panel_id: semantics} if semantics else {},
        "status": "pass",
    }
    return spec, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize ChartDecision into a validated VisualSpec without silent chart fallback.")
    parser.add_argument("--decision", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--x", required=True)
    parser.add_argument("--y", required=True)
    parser.add_argument("--style-profile", type=Path)
    parser.add_argument("--intent", type=Path)
    parser.add_argument("--figure-contract", type=Path)
    args = parser.parse_args()
    try:
        spec, report = materialize_chart_decision(load_json(args.decision), data_path=args.data, output_dir=args.output_dir, x=args.x, y=args.y, style_profile=load_json(args.style_profile) if args.style_profile else None, figure_intent=load_json(args.intent) if args.intent else None, figure_contract=load_json(args.figure_contract) if args.figure_contract else None)
        write_json(args.output_dir / "generated_visualspec.json", spec)
        write_json(args.output_dir / "chart_decision_materialization.json", report)
    except Exception as exc:
        parser.exit(2, f"chart_decision_to_visualspec: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
