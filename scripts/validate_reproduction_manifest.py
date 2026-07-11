from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from visualspec import _json_schema_errors, schema_path


def resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def figure_value(figure: dict[str, Any], key: str) -> Any:
    if key in {"png", "svg", "pdf"}:
        exports = figure.get("exports")
        if isinstance(exports, dict) and key in exports:
            return exports[key]
    if key == "script" and figure.get("script"):
        return figure.get("script")
    return figure.get(key)


def figure_score(figure: dict[str, Any]) -> dict[str, Any] | None:
    score = figure.get("score")
    if isinstance(score, dict):
        return score
    qa = figure.get("qa")
    if isinstance(qa, dict) and isinstance(qa.get("score"), dict):
        return qa["score"]
    return None


def qa_profile(manifest: dict[str, Any], figure: dict[str, Any]) -> str:
    qa = figure.get("qa")
    if isinstance(qa, dict) and qa.get("profile"):
        return str(qa["profile"])
    if figure.get("qa_profile"):
        return str(figure["qa_profile"])
    return str(manifest.get("qa_profile", "semantic"))


def source_strategy(manifest: dict[str, Any], figure: dict[str, Any]) -> str:
    return str(figure.get("source_strategy", manifest.get("source_strategy", figure.get("reconstruction_mode", ""))))


def semantic_strict_score_ok(score: dict[str, Any]) -> bool:
    if score.get("canvas_size_match") is False:
        return False
    if float(score.get("score_0_1", 1.0)) > 0.08:
        return False
    bbox_error = score.get("content_bbox_error")
    if bbox_error is not None and float(bbox_error) > 0.03:
        return False
    return True


def semantic_audit_ok(manifest: dict[str, Any]) -> bool:
    audit = manifest.get("semantic_audit")
    return isinstance(audit, dict) and audit.get("overall") == "pass"


def vector_validation_ok(manifest: dict[str, Any], figure: dict[str, Any]) -> bool:
    representation = str(figure.get("representation", manifest.get("representation", "semantic_vector")))
    if representation != "semantic_vector":
        return True
    validation = manifest.get("vector_validation")
    return isinstance(validation, dict) and validation.get("status") == "pass"


def source_free_validation_ok(manifest: dict[str, Any], figure: dict[str, Any]) -> bool:
    return (
        not figure.get("source")
        and source_strategy(manifest, figure) == "raw_data"
        and figure.get("status") == "semantic_validated_pass"
        and semantic_audit_ok(manifest)
        and vector_validation_ok(manifest, figure)
    )




def validate_manifest(manifest_path: Path, *, root: Path | None = None, require_strict: bool = False) -> dict[str, Any]:
    root = (root or manifest_path.parent).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[dict[str, str]] = [
        {"code": "schema_error", "message": error}
        for error in _json_schema_errors(manifest, schema_path("manifest-v2.schema.json"))
    ]
    figures = manifest.get("figures")
    scripts = manifest.get("per_figure_scripts")
    schema = manifest.get("schema")

    if not isinstance(figures, dict) or not figures:
        failures.append({"code": "missing_figures", "message": "manifest must contain a non-empty figures object"})
        figures = {}
    if not isinstance(scripts, dict):
        scripts = {}
    if not scripts and not all(isinstance(item, dict) and item.get("script") for item in figures.values()):
        failures.append({"code": "missing_per_figure_scripts", "message": "manifest must contain per_figure_scripts or per-figure script fields"})

    for fig_id, figure in figures.items():
        if fig_id not in scripts and not figure_value(figure, "script"):
            failures.append({"code": "missing_figure_script", "figure": fig_id, "message": "figure has no per_figure_scripts entry"})
        else:
            script_value = scripts.get(fig_id) if fig_id in scripts else figure_value(figure, "script")
            script_path = resolve_path(root, str(script_value))
            if script_path is None or not script_path.exists():
                failures.append({"code": "figure_script_not_found", "figure": fig_id, "path": str(script_value)})

        if not isinstance(figure, dict):
            failures.append({"code": "invalid_figure_record", "figure": fig_id})
            continue

        source_value = figure.get("source")
        source_path = resolve_path(root, str(source_value or ""))
        if source_value and (source_path is None or not source_path.exists()):
            failures.append({"code": "source_not_found", "figure": fig_id, "path": str(source_value)})

        for key in ["png", "svg", "pdf"]:
            output_path = resolve_path(root, str(figure_value(figure, key) or ""))
            if output_path is None or not output_path.exists():
                failures.append({"code": "output_not_found", "figure": fig_id, "output": key, "path": str(figure_value(figure, key))})

        score = figure_score(figure)
        source_free_validated = source_free_validation_ok(manifest, figure)
        if not isinstance(score, dict) and not source_free_validated:
            failures.append({"code": "missing_score", "figure": fig_id})
            continue
        qa = figure.get("qa")
        if isinstance(qa, dict):
            if qa.get("execution_status") not in {"completed", "not_run", "failed"}:
                failures.append({"code": "invalid_qa_execution_status", "figure": fig_id})
            if qa.get("result") not in {"strict_pass", "validated_pass", "near_pass", "not_strict", "not_applicable"}:
                failures.append({"code": "invalid_qa_result", "figure": fig_id})
            if figure.get("status") == "semantic_strict_pass" and qa.get("result") != "strict_pass":
                failures.append({"code": "strict_figure_has_non_strict_qa", "figure": fig_id})
            if figure.get("status") == "semantic_validated_pass" and qa.get("result") != "validated_pass":
                failures.append({"code": "validated_figure_has_wrong_qa", "figure": fig_id})

        strategy = source_strategy(manifest, figure)
        profile = qa_profile(manifest, figure)
        if strategy == "pixel_trace" and figure.get("semantic_reconstruction_status") == "pass":
            failures.append({"code": "pixel_trace_claims_semantic_pass", "figure": fig_id})

        if require_strict:
            old_visual_strict = "visual_" + "strict_" + "pass"
            if strategy == "pixel_trace" and manifest.get("status") in {old_visual_strict, "semantic_strict_pass"}:
                failures.append({"code": "pixel_trace_cannot_claim_semantic_strict", "figure": fig_id})
            is_trace = profile == "trace" or strategy == "pixel_trace"
            if not isinstance(score, dict):
                failures.append({"code": "strict_requires_reference_score", "figure": fig_id})
            elif is_trace:
                if score.get("exact_pixel_match") is not True:
                    failures.append({"code": "not_exact_pixel_match", "figure": fig_id})
                if float(score.get("mae_0_1", 1.0)) != 0.0:
                    failures.append({"code": "nonzero_mae", "figure": fig_id, "value": str(score.get("mae_0_1"))})
                if float(score.get("rmse_0_1", 1.0)) != 0.0:
                    failures.append({"code": "nonzero_rmse", "figure": fig_id, "value": str(score.get("rmse_0_1"))})
            elif not semantic_strict_score_ok(score):
                failures.append({"code": "semantic_strict_score_threshold_failed", "figure": fig_id, "score": str(score.get("score_0_1"))})
            if not is_trace:
                if not semantic_audit_ok(manifest):
                    failures.append({"code": "semantic_audit_not_passed", "figure": fig_id})
                if not vector_validation_ok(manifest, figure):
                    failures.append({"code": "vector_validation_not_passed", "figure": fig_id})
                panels = figure.get("panels")
                if isinstance(panels, dict):
                    for panel_id, panel in panels.items():
                        panel_qa = panel.get("qa") if isinstance(panel, dict) else None
                        if not isinstance(panel_qa, dict) or panel_qa.get("execution_status") != "completed":
                            failures.append({"code": "panel_qa_not_completed", "figure": fig_id, "panel": panel_id})
                        elif panel_qa.get("result") != "strict_pass":
                            failures.append({"code": "panel_qa_not_strict", "figure": fig_id, "panel": panel_id, "result": str(panel_qa.get("result"))})
                else:
                    failures.append({"code": "missing_panel_records", "figure": fig_id})

    if require_strict:
        allowed_strict = {"semantic_strict_pass", "visual_trace_pass"}
        if manifest.get("status") not in allowed_strict:
            failures.append({"code": "manifest_not_strict_pass", "status": str(manifest.get("status")), "allowed": ",".join(sorted(allowed_strict))})
    if schema == "scientificfigure.manifest.v2" and manifest.get("overall_status") in {"strict_pass", "near_pass", "pass"} and manifest.get("qa_execution_status") != "completed":
        failures.append({"code": "false_visual_pass", "message": "manifest quality status requires completed QA execution"})

    return {
        "schema": "scientificfigure.reproduction_manifest_validation.v1",
        "manifest": str(manifest_path),
        "root": str(root),
        "require_strict": require_strict,
        "status": "ok" if not failures else "failed",
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate scientific figure reproduction manifests.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--root", type=Path, help="Project root for relative paths.")
    parser.add_argument("--require-strict", action="store_true", help="Require exact pixel match and zero MAE/RMSE.")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = validate_manifest(args.manifest, root=args.root, require_strict=args.require_strict)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
