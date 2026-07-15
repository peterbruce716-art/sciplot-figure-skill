from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from advisor_common import load_json, write_json
from font_resolver import resolve_fonts
from prepare_ai_visual_review import prepare_review
from profile_scientific_data import profile_dataframe, read_table
from recommend_scientific_chart import recommend_chart
from resolve_style_profile import resolve_style
from evaluate_scientific_plot_policy import evaluate_policies


def _intent(path: Path | None) -> dict[str, Any]:
    if path:
        return load_json(path)
    return {
        "schema": "scientificfigure.figure_intent.v1", "schema_version": "1.0",
        "claim": "Describe the dominant relationship in the supplied data",
        "task_type": "trend_comparison", "primary_message": "Expose the data pattern without hiding observations",
        "audience": "scientific_readers", "priority_variables": [], "uncertainty_semantics": None,
    }


def _build_visualspec(data: Path, output: Path, *, x: str, y: str) -> Path:
    data_ref = data.relative_to(output).as_posix()
    spec = {
        "schema": "scientificfigure.visualspec.v2",
        "figure": {"size_mm": [85, 60], "dpi": 300, "crop_mode": "fixed_canvas"},
        "panels": [{"id": "A", "bbox_normalized": [0.15, 0.16, 0.78, 0.75], "source_strategy": "raw_data", "representation": "semantic_vector", "axes": {"x": {"label": x}, "y": {"label": y}}, "plots": [{"type": "line", "data": {"source": data_ref, "mapping": {"x": x, "y": y}}, "style": {"color": "#0072B2"}}], "annotations": []}],
    }
    path = output / "visualspec.json"
    write_json(path, spec)
    return path


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, Path] = {}
    if not args.disable_advisor:
        frame = read_table(args.data, sheet=args.sheet)
        profile = profile_dataframe(frame, source_path=args.data, sheet=args.sheet, groups=args.group, x=args.x, y=args.y)
        artifacts["data_profile"] = output / "advisor" / "data_profile.json"
        write_json(artifacts["data_profile"], profile)
        intent = _intent(args.intent)
        artifacts["figure_intent"] = output / "advisor" / "figure_intent.json"
        write_json(artifacts["figure_intent"], intent)
        decision = recommend_chart(profile, intent, x=args.x, y=args.y, group=args.group, requested_type=args.requested_type, journal_profile=args.style)
        artifacts["chart_decision"] = output / "advisor" / "chart_decision.json"
        write_json(artifacts["chart_decision"], decision)
        context = {"sample": {"min_group_n": min((int(item.get("sample_count", 0)) for item in profile.get("group_statistics", [])), default=0)}, "chart": {"type": decision["recommended_type"], "has_uncertainty": bool(intent.get("uncertainty_semantics")), "raw_points_visible": "raw_points" in decision.get("required_visual_elements", [])}, "intent": intent, "data": {"category_count": max((int(item.get("unique_count", 0)) for item in profile.get("columns", [])), default=0), "x_numeric": bool(args.x and next((item.get("inferred_type") == "continuous" for item in profile.get("columns", []) if item.get("name") == args.x), False)), "x_treated_as_category": decision["recommended_type"] in {"grouped_bar", "bar"}}, "caption": {"sample_size_declared": False}, "layout": {"panel_count": 1, "panel_labels_present": True}, "style": {"colormap": None}}
        policy = load_json(args.policy)
        policy_report = evaluate_policies(context, policy, disabled=set(args.disable_policy))
        artifacts["policy_report"] = output / "advisor" / "policy_report.json"
        write_json(artifacts["policy_report"], policy_report)
    else:
        profile = None
        intent = _intent(args.intent)

    if args.style:
        style = resolve_style(args.style, override=load_json(args.style_override) if args.style_override else None)
        artifacts["style_profile"] = output / "style" / "resolved_style_profile.json"
        write_json(artifacts["style_profile"], style)
        font = resolve_fonts(latin=style["settings"].get("latin_font"), cjk=style["settings"].get("cjk_font"), serif_for_zh=bool(style["settings"].get("serif_for_zh")))
    else:
        font = resolve_fonts(latin=args.latin_font, cjk=args.cjk_font)
    artifacts["font_resolution"] = output / "style" / "font_resolution.json"
    write_json(artifacts["font_resolution"], font)

    spec_path = args.spec
    if args.generate_visualspec:
        if not args.x or not args.y:
            raise ValueError("--generate-visualspec requires --x and --y")
        # Keep the generated spec self-contained so run_reproduction can preflight and copy it.
        local_data = output / "input" / args.data.name
        local_data.parent.mkdir(parents=True, exist_ok=True)
        if local_data.resolve() != args.data.resolve():
            shutil.copyfile(args.data, local_data)
        spec_path = _build_visualspec(local_data, output, x=args.x, y=args.y)
    if args.run_ai_review and args.image:
        review = prepare_review(args.image, visualspec=spec_path, font=artifacts["font_resolution"])
        artifacts["ai_review"] = output / "qa" / "ai_visual_review.json"
        write_json(artifacts["ai_review"], review)

    if args.dry_run:
        return {"status": "dry_run", "artifacts": {key: str(value.relative_to(output)).replace("\\", "/") for key, value in artifacts.items()}, "spec": str(spec_path) if spec_path else None}

    if args.create_bundle or args.run_qa:
        if not spec_path:
            raise ValueError("--run-qa/--create-bundle requires --spec or --generate-visualspec")
        command = [sys.executable, str(Path(__file__).resolve().parent / "run_reproduction.py"), "--spec", str(spec_path), "--out-dir", str(output / "bundle")]
        if args.image:
            command.extend(["--source", str(args.image)])
        for key, flag in [("data_profile", "--data-profile"), ("figure_intent", "--figure-intent"), ("chart_decision", "--chart-decision"), ("policy_report", "--policy-report"), ("style_profile", "--style-profile"), ("font_resolution", "--font-resolution"), ("ai_review", "--ai-review")]:
            if key in artifacts:
                command.extend([flag, str(artifacts[key])])
        if args.strict:
            command.append("--require-strict")
        completed = subprocess.run(command, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"run_reproduction failed with exit code {completed.returncode}")
    return {"status": "completed", "artifacts": {key: str(value.relative_to(output)).replace("\\", "/") for key, value in artifacts.items()}, "spec": str(spec_path) if spec_path else None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Advisor-first scientific figure pipeline with optional deterministic SciPlot bundle QA.")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--intent", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--sheet")
    parser.add_argument("--x")
    parser.add_argument("--y")
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--requested-type")
    parser.add_argument("--style")
    parser.add_argument("--style-override", type=Path)
    parser.add_argument("--latin-font")
    parser.add_argument("--cjk-font")
    parser.add_argument("--policy", type=Path, default=Path(__file__).resolve().parents[1] / "policies" / "scientific-plot-policy-v1.json")
    parser.add_argument("--disable-policy", action="append", default=[])
    parser.add_argument("--disable-advisor", action="store_true")
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--generate-visualspec", action="store_true")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--run-ai-review", action="store_true")
    parser.add_argument("--run-qa", action="store_true")
    parser.add_argument("--create-bundle", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = run_pipeline(args)
    except Exception as exc:
        parser.exit(2, f"scientific_figure_pipeline: {exc}\n")
    write_json(args.output_dir / "pipeline_report.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
