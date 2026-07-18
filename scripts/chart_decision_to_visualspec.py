from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd

from advisor_common import load_json, validate_payload, write_json
from advisor_common import sha256_file
from resolve_panel_layout import panel_semantics, resolve_layout
from uncertainty_semantics import UncertaintySemanticError, validate_uncertainty_values


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
    decision_columns = decision.get("data_columns") or {}
    for axis, supplied in (("x", x), ("y", y)):
        declared = decision_columns.get(axis)
        if declared is not None and declared != supplied:
            raise UncertaintySemanticError("source_mapping_mismatch", f"ChartDecision {axis} mapping differs from the materializer argument", declared=declared, supplied=supplied)
    if decision.get("requires_user_confirmation") is True and recommended in {"line_with_error_bars", "line_with_error_band"}:
        raise UncertaintySemanticError("uncertainty_confirmation_required", "ChartDecision requires user confirmation before materialization")
    data_sha256 = sha256_file(source)
    declared_sha256 = (decision.get("data_source") or {}).get("sha256")
    if declared_sha256 and declared_sha256 != data_sha256:
        raise UncertaintySemanticError("data_source_mismatch", "ChartDecision data source hash differs from the materialized data", declared=declared_sha256, actual=data_sha256)
    root = output_dir.resolve()
    derived_path: Path | None = None
    plot_style = _style(style_profile)
    plots: list[dict[str, Any]] = []
    mapping: dict[str, Any] = {"x": x, "y": y}
    source_ref = _source_ref(source, root)
    source_hashes: dict[str, str] = {source_ref: data_sha256}
    contract_panels = list((figure_contract or {}).get("panel_plan") or [])
    panel_id = str(contract_panels[0].get("panel_id")) if contract_panels and contract_panels[0].get("panel_id") else "A"
    layout = resolve_layout(figure_contract, panel_ids=[panel_id])
    semantics = panel_semantics(figure_contract).get(panel_id, {})
    mapping_validity: dict[str, Any] = {
        "status": "pass",
        "measurement_column": y,
        "uncertainty_column": None,
        "checks": {"measurement_mapping": "pass", "uncertainty_not_requested": "pass"},
    }

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
        if decision.get("uncertainty_source") != error_column:
            raise UncertaintySemanticError("uncertainty_source_mismatch", "ChartDecision error mapping and uncertainty source do not agree")
        frame = pd.read_csv(source)
        missing = [name for name in (x, y, error_column) if name not in frame.columns]
        if missing:
            raise UncertaintySemanticError("uncertainty_column_missing", f"mapped data columns are missing: {', '.join(missing)}")
        evidence = decision.get("uncertainty_evidence")
        if isinstance(evidence, dict) and evidence.get("column") not in {None, error_column}:
            raise UncertaintySemanticError("uncertainty_source_mismatch", "uncertainty evidence names a different source column")
        mapping_validity = validate_uncertainty_values(
            frame[y].tolist(),
            frame[error_column].tolist(),
            measurement_column=y,
            uncertainty_column=error_column,
            evidence=evidence,
            override=decision.get("uncertainty_override"),
        )
        plots.append({"type": "errorbar", "data": {"source": source_ref, "mapping": {"x": x, "y": y, "yerr": error_column}, "uncertainty": evidence, "uncertainty_override": decision.get("uncertainty_override")}, "style": _typed_style(plot_style, "errorbar")})
        mapping["yerr"] = error_column
    elif recommended == "line_with_error_band":
        evidence = decision.get("uncertainty_evidence")
        if not isinstance(evidence, dict) or not evidence.get("semantics"):
            raise UncertaintySemanticError("uncertainty_definition_unknown", "error bands require traceable uncertainty semantics")
        frame = pd.read_csv(source)
        if x not in frame or y not in frame:
            raise ValueError(f"data columns not found: {x}, {y}")
        lower = decision.get("data_columns", {}).get("lower")
        upper = decision.get("data_columns", {}).get("upper")
        semantics_name = str(evidence.get("semantics", "")).strip().lower().replace("_", " ")
        if lower and upper and lower in frame and upper in frame:
            derived = frame[[x, y, lower, upper]].copy()
            lower_values = pd.to_numeric(derived[lower], errors="coerce")
            upper_values = pd.to_numeric(derived[upper], errors="coerce")
            if lower_values.isna().any() or upper_values.isna().any() or (lower_values > upper_values).any():
                raise UncertaintySemanticError("uncertainty_band_invalid_bounds", "error-band bounds must be finite numeric values with lower <= upper")
            mapping.update({"lower": lower, "upper": upper})
        else:
            if semantics_name not in {"standard deviation", "standard error"}:
                raise UncertaintySemanticError("uncertainty_band_requires_declared_bounds", "automatic error bands support standard deviation or standard error; provide lower and upper columns for other definitions")
            grouped = frame.groupby([x], sort=True, dropna=False)[y]
            derived = grouped.agg(["mean", "std", "count"]).reset_index().rename(columns={"mean": y})
            derived["std"] = pd.to_numeric(derived["std"], errors="coerce").fillna(0.0)
            if semantics_name == "standard error":
                derived["std"] = derived["std"] / derived["count"].clip(lower=1).pow(0.5)
            derived["lower"] = derived[y] - derived["std"]
            derived["upper"] = derived[y] + derived["std"]
            mapping.update({"lower": "lower", "upper": "upper", "uncertainty": "std"})
        derived_path = output_dir / "derived" / f"{source.stem}_error_band.csv"
        derived_path.parent.mkdir(parents=True, exist_ok=True)
        derived.to_csv(derived_path, index=False)
        derived_ref = _source_ref(derived_path, root)
        source_hashes[derived_ref] = sha256_file(derived_path)
        plots.extend([
            {"type": "fill_between", "data": {"source": derived_ref, "mapping": {"x": x, "y1": mapping["lower"], "y2": mapping["upper"]}, "uncertainty": evidence}, "style": {"color": plot_style["color"], "alpha": 0.18}},
            {"type": "line", "data": {"source": derived_ref, "mapping": {"x": x, "y": y}}, "style": _typed_style(plot_style, "line")},
        ])
        mapping_validity = {
            "status": "pass",
            "measurement_column": y,
            "uncertainty_column": decision.get("uncertainty_source"),
            "checks": {"measurement_mapping": "pass", "definition_known": "pass", "traceable_source": "pass"},
            "evidence": evidence,
        }
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
        "delivery": {"chart_decision_hash": _hash_payload(decision), "materialized_as": [plot["type"] for plot in plots], "data_columns": mapping, "data_sha256": data_sha256, "source_hashes": source_hashes, "mapping_validity": mapping_validity, "figure_contract_hash": _hash_payload(figure_contract) if figure_contract else None},
    }
    validate_payload(spec, "visualspec-v2.schema.json")
    report = {
        "schema": "scientificfigure.chart_decision_materialization.v1",
        "decision_hash": _hash_payload(decision),
        "recommended_type": recommended,
        "materialized_as": [plot["type"] for plot in plots],
        "data_columns": mapping,
        "data_sha256": data_sha256,
        "source_hashes": source_hashes,
        "mapping_validity": mapping_validity,
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
