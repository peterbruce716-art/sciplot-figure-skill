from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from advisor_common import load_json, validate_payload, write_json


def _column(profile: dict[str, Any], name: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    return next((item for item in profile.get("columns", []) if item.get("name") == name), None)


def _uncertainty_evidence(profile: dict[str, Any], column: str) -> dict[str, Any]:
    evidence = next((item for item in profile.get("uncertainty_evidence", []) if item.get("column") == column), None)
    if evidence is None:
        record = _column(profile, column) or {}
        evidence = record.get("uncertainty_evidence")
    return dict(evidence or {})


def recommend_chart(
    profile: dict[str, Any],
    intent: dict[str, Any],
    *,
    x: str | None = None,
    y: str | None = None,
    group: list[str] | None = None,
    requested_type: str | None = None,
    journal_profile: str | None = None,
    figure_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    group = group or []
    task = str(intent.get("task_type", "trend_comparison"))
    x_info = _column(profile, x)
    y_info = _column(profile, y)
    group_count = len(profile.get("group_statistics", []))
    min_n = min((int(item.get("sample_count", 0)) for item in profile.get("group_statistics", [])), default=None)
    warnings: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    reasons: list[str] = []
    required: list[str] = []
    uncertainty_source: str | None = None
    uncertainty_evidence: dict[str, Any] | None = None
    data_columns: dict[str, Any] = {"x": x, "y": y, "group": group}
    requires_user_confirmation = False
    contract_summary: dict[str, Any] | None = None
    contract_preferred: str | None = None
    if figure_contract:
        panels = list(figure_contract.get("panel_plan") or [])
        first_panel = panels[0] if panels else {}
        contract_preferred = first_panel.get("preferred_representation")
        contract_summary = {
            "schema": figure_contract.get("schema"),
            "scientific_question": figure_contract.get("scientific_question"),
            "core_claim": figure_contract.get("core_claim"),
            "archetype": figure_contract.get("archetype"),
            "hero_panel_id": figure_contract.get("hero_panel_id"),
            "panel_count": len(panels),
            "evidence_ids": [item.get("id") for item in figure_contract.get("evidence_chain", [])],
        }

    if task in {"trend_comparison", "temporal_change"}:
        if x_info and x_info.get("inferred_type") in {"continuous", "datetime", "ordinal"}:
            repeated = profile.get("repeated_x") or {}
            has_repeats = bool(repeated.get("has_repeated_observations"))
            uncertainty_columns = sorted(
                list(profile.get("uncertainty_columns") or []),
                key=lambda column: 0 if _uncertainty_evidence(profile, column).get("source") == "explicit" else 1,
            )
            if uncertainty_columns:
                candidate = uncertainty_columns[0]
                candidate_evidence = _uncertainty_evidence(profile, candidate)
                validation = candidate_evidence.get("value_validation") or {}
                if validation.get("status") == "failed":
                    first = (validation.get("errors") or [{"code": "uncertainty_invalid"}])[0]
                    raise ValueError(f"{first.get('code', 'uncertainty_invalid')}: uncertainty column '{candidate}' failed value validation")
                declared_semantics = intent.get("uncertainty_semantics") or candidate_evidence.get("semantics")
                candidate_evidence.update({"column": candidate, "semantics": declared_semantics})
                if candidate_evidence.get("source") == "explicit" or intent.get("uncertainty_semantics"):
                    recommended = "line_with_error_bars"
                    uncertainty_source = candidate
                    uncertainty_evidence = candidate_evidence
                    data_columns["error"] = candidate
                    required.extend(["uncertainty_definition", "sample_count"])
                else:
                    recommended = "line_with_markers"
                    requires_user_confirmation = True
                    warnings.append({"code": "uncertainty_confirmation_required", "severity": "warning", "message": f"Column '{candidate}' is only a name-inferred uncertainty candidate; confirm its scientific definition before drawing error bars."})
            elif has_repeats and intent.get("uncertainty_semantics"):
                recommended = "line_with_error_band"
                uncertainty_source = "repeated_observations"
                uncertainty_evidence = {"column": None, "source": "metadata", "match_type": "repeated_observations", "matched_token": None, "confidence": 1.0, "semantics": intent.get("uncertainty_semantics")}
                required.extend(["uncertainty_definition", "sample_count"])
            elif x_info.get("inferred_type") == "ordinal":
                recommended = "line_with_markers"
            else:
                recommended = "line_with_markers" if y else "scatter"
            if intent.get("uncertainty_semantics") and not uncertainty_columns and not has_repeats:
                warnings.append({"code": "uncertainty_values_missing", "severity": "warning", "message": "Uncertainty semantics were declared, but no repeated observations or independent uncertainty column supplies values."})
            reasons.append("横轴具有连续、时间或有序物理意义，趋势图保留了顺序信息")
            required.extend(["axis_units", "sample_count"])
        else:
            recommended = "dot_plot_or_grouped_bar"
            reasons.append("横轴不是明确连续变量，使用点图或分组比较更不容易暗示连续变化")
    elif task == "group_comparison":
        recommended = "box_with_raw_points" if min_n is not None and min_n < 10 else "box_or_violin_with_raw_points"
        reasons.append("论证目标是组间比较，原始点能显示样本量和组内分布")
        required.extend(["raw_points_or_sample_count", "uncertainty_definition"])
    elif task == "distribution_comparison":
        recommended = "box_violin_or_ecdf"
        reasons.append("目标是分布而不是单一中心值，箱线图、小提琴图或 ECDF 更合适")
        required.extend(["sample_count", "distribution_definition"])
    elif task == "correlation":
        recommended = "scatter_with_model_fit"
        reasons.append("相关性应保留每个观测点，并明确拟合模型而不是只画汇总值")
        required.extend(["raw_points", "fit_model_definition", "units"])
    elif task == "model_vs_experiment":
        recommended = "observed_vs_predicted_or_line_overlay"
        reasons.append("实验与模型需要共享坐标系并用冗余线型区分数据来源")
        required.extend(["source_encoding", "units", "fit_or_error_definition"])
    elif task == "uncertainty_visualization":
        recommended = "line_with_error_band_or_errorbar"
        reasons.append("不确定性是主信息，必须把误差语义写入图注和机器可读配置")
        required.extend(["uncertainty_definition", "sample_count"])
    elif task == "composition":
        recommended = "sorted_horizontal_bar_or_treemap"
        reasons.append("类别数量和可比较性优先于饼图的角度编码")
        required.extend(["denominator", "category_order"])
    elif task == "multi_panel_summary":
        recommended = "small_multiples"
        reasons.append("多论点应拆成尺度和语义一致的小面板，而不是挤在一张坐标轴")
        required.extend(["panel_claims", "shared_units"])
    else:
        recommended = "semantic_vector_reconstruction"
        reasons.append("图像重建优先保留可编辑语义对象，并将视觉追踪与科学数据恢复区分")

    if contract_preferred:
        representation_map = {
            "line_with_uncertainty": "line_with_error_band",
            "line_with_error_bars": "line_with_error_bars",
            "scatter_regression": "scatter",
            "grouped_bar": "grouped_bar",
            "heatmap": "heatmap",
            "pca": "scatter",
            "box_violin": "box_with_raw_points",
            "chart_from_data_profile": recommended,
        }
        mapped = representation_map.get(str(contract_preferred), recommended)
        if contract_preferred == "line_with_uncertainty" and recommended == "line_with_error_bars":
            mapped = recommended
        if mapped != recommended:
            reasons.insert(0, f"FigureContract preferred_representation={contract_preferred} adjusted the chart recommendation to {mapped}")
            recommended = mapped
        required.extend(["figure_contract", "evidence_trace", "panel_role"])

    if group_count > 12:
        warnings.append({"code": "too_many_groups", "severity": "warning", "message": "组或系列超过 12 个，建议使用 small multiples 或分层筛选。"})
    if min_n is not None and min_n < 10:
        warnings.append({"code": "small_sample", "severity": "warning", "message": "至少一个组样本量小于 10，不建议只画均值柱。"})
    if intent.get("uncertainty_semantics") is None and task in {"uncertainty_visualization", "group_comparison", "trend_comparison"}:
        warnings.append({"code": "uncertainty_undefined", "severity": "warning", "message": "误差或分布语义尚未声明，不能默认 SD、SEM 或置信区间。"})
    if requested_type:
        if requested_type in {"pie", "pie_chart", "3d", "3d_bar", "dual_y", "dual_axis", "rainbow", "jet"}:
            warnings.append({"code": "requested_type_risky", "severity": "warning", "message": f"用户指定的图型 '{requested_type}' 存在可比性、色觉或误导风险；已保留为请求但给出替代建议。"})
            rejected.append({"type": requested_type, "reason": "经验规则显示该图型可能降低可比性或掩盖分布；如必须使用，应显式记录限制。"})
        else:
            recommended = requested_type
            reasons.insert(0, "用户明确指定图型，以下建议优先保留该约束并附带风险提示")

    if recommended in {"line_with_error_band", "line_with_error_bars", "line_with_errorbar", "errorbar"} and not intent.get("uncertainty_semantics"):
        if not (uncertainty_evidence and uncertainty_evidence.get("semantics")):
            warnings.append({"code": "error_semantics_required", "severity": "warning", "message": "误差带/误差棒必须标明 SD、SEM、95% CI 或其他定义。"})
    if recommended in {"line_with_error_band", "line_with_error_bars", "line_with_errorbar", "errorbar"} and uncertainty_evidence is None:
        warnings.append({"code": "uncertainty_values_missing", "severity": "warning", "message": "The requested uncertainty chart has no traceable uncertainty values; using a marker line instead."})
        recommended = "line_with_markers"
        uncertainty_source = None
        data_columns.pop("error", None)
    if x_info and x_info.get("inferred_type") == "categorical" and task in {"trend_comparison", "temporal_change"}:
        warnings.append({"code": "categorical_x_trend", "severity": "warning", "message": "分类横轴不应被折线连接来暗示连续趋势。"})

    alternatives = [item for item in [
        "line_with_errorbar", "scatter_with_model_fit", "small_multiples", "box_with_raw_points", "stripplot", "ecdf"
    ] if item != recommended][:3]
    payload = {
        "schema": "scientificfigure.chart_decision.v1",
        "schema_version": "1.0",
        "recommended_type": recommended,
        "alternatives": alternatives,
        "rejected_types": rejected,
        "reasoning_summary": reasons,
        "required_visual_elements": sorted(set(required)),
        "warnings": warnings,
        "user_requested_type": requested_type,
        "journal_profile": journal_profile,
        "uncertainty_source": uncertainty_source,
        "uncertainty_evidence": uncertainty_evidence,
        "data_source": profile.get("source"),
        "data_columns": data_columns,
        "requires_user_confirmation": requires_user_confirmation,
        "figure_contract": contract_summary,
        "layout": {"archetype": figure_contract.get("archetype"), "hero_panel_id": figure_contract.get("hero_panel_id")} if figure_contract else None,
        "statistics_report_required": True,
    }
    validate_payload(payload, "chart-decision-v1.schema.json")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Recommend a scientific chart from a data profile and figure intent.")
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--intent", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--x")
    parser.add_argument("--y")
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--requested-type")
    parser.add_argument("--journal-profile")
    parser.add_argument("--figure-contract", type=Path)
    args = parser.parse_args()
    try:
        payload = recommend_chart(load_json(args.profile), load_json(args.intent), x=args.x, y=args.y, group=args.group, requested_type=args.requested_type, journal_profile=args.journal_profile, figure_contract=load_json(args.figure_contract) if args.figure_contract else None)
        write_json(args.output, payload)
    except Exception as exc:
        parser.exit(2, f"recommend_scientific_chart: {exc}\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
