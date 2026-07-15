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


def recommend_chart(
    profile: dict[str, Any],
    intent: dict[str, Any],
    *,
    x: str | None = None,
    y: str | None = None,
    group: list[str] | None = None,
    requested_type: str | None = None,
    journal_profile: str | None = None,
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

    if task in {"trend_comparison", "temporal_change"}:
        if x_info and x_info.get("inferred_type") in {"continuous", "datetime", "ordinal"}:
            recommended = "line_with_error_band" if y_info and y_info.get("outlier_count_iqr", 0) >= 0 else "line_or_scatter"
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

    if recommended in {"line_with_error_band", "line_with_errorbar", "errorbar"} and not intent.get("uncertainty_semantics"):
        warnings.append({"code": "error_semantics_required", "severity": "warning", "message": "误差带/误差棒必须标明 SD、SEM、95% CI 或其他定义。"})
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
    args = parser.parse_args()
    try:
        payload = recommend_chart(load_json(args.profile), load_json(args.intent), x=args.x, y=args.y, group=args.group, requested_type=args.requested_type, journal_profile=args.journal_profile)
        write_json(args.output, payload)
    except Exception as exc:
        parser.exit(2, f"recommend_scientific_chart: {exc}\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
