from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from visualspec import FINAL_STATUSES, manifest_overall_status, portable_path, status_to_qa_result, write_json


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def portable_or_none(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return portable_path(path, root)
    except ValueError:
        return None


def make_score_portable(score: dict[str, Any], root: Path) -> dict[str, Any]:
    result = dict(score)
    for key in ("source", "actual"):
        if result.get(key):
            result[key] = portable_path(Path(str(result[key])), root)
    outputs = result.get("comparison_outputs")
    if isinstance(outputs, dict):
        result["comparison_outputs"] = {
            name: portable_path(Path(str(value)), root) if value else value
            for name, value in outputs.items()
        }
    return result


def semantic_visual_strict_score_ok(score: dict[str, Any]) -> bool:
    if score.get("canvas_size_match") is False:
        return False
    if float(score.get("score_0_1", 1.0)) > 0.08:
        return False
    bbox_error = score.get("content_bbox_error")
    if bbox_error is not None and float(bbox_error) > 0.03:
        return False
    return True


def _status_from_score(score: dict[str, Any], *, profile: str, source_strategy: str) -> str:
    if profile == "trace" or source_strategy == "pixel_trace":
        return "visual_trace_pass" if score.get("exact_pixel_match") is True else "not_strict"
    if (score.get("source_content_bbox") is None) != (score.get("actual_content_bbox") is None):
        return "not_strict"
    if semantic_visual_strict_score_ok(score):
        return "semantic_strict_pass"
    if float(score.get("score_0_1", 1.0)) <= 0.30:
        return "semantic_near_pass"
    return "not_strict"


def classify_source_free_status(
    *,
    source_strategy: str,
    representation: str,
    semantic_audit: dict[str, Any] | None,
    vector_validation: dict[str, Any] | None,
) -> str:
    """Classify a raw-data render when no reference image is available.

    This is intentionally distinct from semantic_strict_pass: semantic and vector
    checks can validate the generated artifact, but they cannot establish visual
    fidelity to an external reference that was never supplied.
    """
    if source_strategy != "raw_data":
        return "render_only"
    if semantic_audit is None or vector_validation is None:
        return "render_only"
    semantic_ok = semantic_audit.get("overall") == "pass"
    vector_required = representation == "semantic_vector"
    vector_ok = (not vector_required) or vector_validation.get("status") == "pass"
    return "semantic_validated_pass" if semantic_ok and vector_ok else "not_strict"


def _load_optional_json(path: Path | None) -> dict[str, Any] | None:
    return load_json(path) if path and path.exists() else None


def _load_panel_scores(panel_score_dir: Path | None) -> dict[str, dict[str, Any]]:
    if panel_score_dir is None or not panel_score_dir.exists():
        return {}
    return {
        item.stem: load_json(item)
        for item in panel_score_dir.glob("*.json")
        if item.is_file()
    }


def classify_status(
    score: dict[str, Any],
    *,
    profile: str,
    source_strategy: str,
    representation: str,
    semantic_audit: dict[str, Any] | None = None,
    vector_validation: dict[str, Any] | None = None,
    panel_scores: dict[str, dict[str, Any]] | None = None,
    required_panel_ids: set[str] | None = None,
) -> str:
    visual_status = _status_from_score(score, profile=profile, source_strategy=source_strategy)
    if profile == "trace" or source_strategy == "pixel_trace":
        return visual_status
    if visual_status == "not_strict":
        return "not_strict"
    semantic_ok = semantic_audit is not None and semantic_audit.get("overall") == "pass"
    if semantic_audit is not None and not semantic_ok:
        return "not_strict"
    vector_required = representation == "semantic_vector"
    vector_ok = (not vector_required) or (vector_validation is not None and vector_validation.get("status") == "pass")
    panel_scores = panel_scores or {}
    required_panel_ids = required_panel_ids or set(panel_scores)
    panels_ok = set(panel_scores) >= required_panel_ids
    for panel_id in required_panel_ids:
        panel_score = panel_scores.get(panel_id)
        if panel_score is None:
            panels_ok = False
            continue
        panel_status = _status_from_score(panel_score, profile=profile, source_strategy=source_strategy)
        if panel_status != "semantic_strict_pass":
            panels_ok = False
    if required_panel_ids and not panels_ok:
        return "not_strict"
    if visual_status == "semantic_strict_pass" and semantic_ok and vector_ok and panels_ok:
        return "semantic_strict_pass"
    if float(score.get("score_0_1", 1.0)) <= 0.30:
        return "semantic_near_pass"
    return "not_strict"


def finalize_manifest(
    manifest_path: Path,
    *,
    score_path: Path | None,
    script_path: Path | None,
    source_path: Path | None,
    output_path: Path,
    qa_profile: str = "semantic",
    project_root: Path | None = None,
    spec_path: Path | None = None,
    runner_path: Path | None = None,
    semantic_audit_path: Path | None = None,
    vector_validation_path: Path | None = None,
    panel_score_dir: Path | None = None,
    checksums_path: Path | None = None,
) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    raw_score = load_json(score_path) if score_path else None
    project_root = (project_root or manifest_path.parent).resolve()
    score = make_score_portable(raw_score, project_root) if raw_score else None
    semantic_audit = _load_optional_json(semantic_audit_path)
    vector_validation = _load_optional_json(vector_validation_path)
    panel_scores = _load_panel_scores(panel_score_dir)
    manifest["project_root"] = "."
    if spec_path:
        manifest["spec_path"] = portable_path(spec_path, project_root)
    elif manifest.get("spec_path"):
        manifest["spec_path"] = portable_path(Path(str(manifest["spec_path"])), project_root)
    if manifest.get("output_dir"):
        manifest["output_dir"] = portable_path(Path(str(manifest["output_dir"])), project_root)
    if manifest.get("semantics"):
        manifest["semantics"] = portable_path(Path(str(manifest["semantics"])), project_root)
    root_exports = manifest.get("exports")
    if isinstance(root_exports, dict):
        for key, value in list(root_exports.items()):
            if value:
                root_exports[key] = portable_path(Path(str(value)), project_root)
    runner_ref = portable_or_none(runner_path, project_root)
    if runner_ref:
        manifest["runner"] = runner_ref
    else:
        manifest.pop("runner", None)
    figures = manifest.setdefault("figures", {})
    per_figure_scripts = manifest.setdefault("per_figure_scripts", {})

    final_statuses: list[str] = []
    for fig_id, figure in figures.items():
        if not isinstance(figure, dict):
            continue
        if source_path:
            figure["source"] = portable_path(source_path, project_root)
        if script_path:
            figure["script"] = portable_path(script_path, project_root)
            per_figure_scripts[fig_id] = portable_path(script_path, project_root)
        if spec_path:
            figure["spec"] = portable_path(spec_path, project_root)
        if runner_ref:
            figure["runner"] = runner_ref
        else:
            figure.pop("runner", None)
        exports = figure.get("exports")
        if isinstance(exports, dict):
            for key, value in list(exports.items()):
                if value:
                    exports[key] = portable_path(Path(str(value)), project_root)
        figure.setdefault("source_strategy", manifest.get("source_strategy", "raw_data"))
        figure.setdefault("representation", manifest.get("representation", "semantic_vector"))
        figure.setdefault("qa", {})
        figure["qa"]["profile"] = qa_profile
        if score:
            figure["score"] = score
            if semantic_audit:
                score["scientific_fidelity"] = semantic_audit.get("scientific_fidelity", semantic_audit.get("checks", {}))
            figure["qa"]["score"] = score
            figure["qa"]["score_report"] = portable_path(score_path, project_root)
            figure["qa"]["execution_status"] = "completed"
            figure_status = classify_status(
                score,
                profile=qa_profile,
                source_strategy=str(figure.get("source_strategy", "raw_data")),
                representation=str(figure.get("representation", manifest.get("representation", "semantic_vector"))),
                semantic_audit=semantic_audit,
                vector_validation=vector_validation,
                panel_scores=panel_scores,
                required_panel_ids=set((figure.get("panels") or {}).keys()) if isinstance(figure.get("panels"), dict) else set(),
            )
            figure["qa"]["result"] = status_to_qa_result(figure_status)
        else:
            figure_status = classify_source_free_status(
                source_strategy=str(figure.get("source_strategy", "raw_data")),
                representation=str(figure.get("representation", manifest.get("representation", "semantic_vector"))),
                semantic_audit=semantic_audit,
                vector_validation=vector_validation,
            )
            if figure_status == "semantic_validated_pass":
                figure["qa"]["execution_status"] = "completed"
                figure["qa"]["result"] = status_to_qa_result(figure_status)
                figure["qa"]["validation_basis"] = "semantic_and_vector_without_reference_image"
            elif figure_status == "not_strict":
                figure["qa"]["execution_status"] = "failed"
                figure["qa"]["result"] = "not_strict"
            else:
                figure["qa"]["execution_status"] = "not_run"
                figure["qa"]["result"] = "not_applicable"
        panels = figure.get("panels")
        if isinstance(panels, dict):
            for panel_id, panel in panels.items():
                if not isinstance(panel, dict):
                    continue
                panel.setdefault("qa", {})
                if panel_id in panel_scores:
                    panel_score = make_score_portable(panel_scores[panel_id], project_root)
                    panel["qa"]["execution_status"] = "completed"
                    panel["qa"]["score_report"] = portable_path(panel_score_dir / f"{panel_id}.json", project_root) if panel_score_dir else None
                    panel_status = _status_from_score(panel_score, profile=qa_profile, source_strategy=str(figure.get("source_strategy", "raw_data")))
                    panel["qa"]["result"] = status_to_qa_result(panel_status)
                    panel["qa"]["score"] = panel_score
                else:
                    panel["qa"].setdefault("execution_status", "not_run")
                    panel["qa"].setdefault("result", "not_applicable")
        figure["status"] = figure_status
        final_statuses.append(figure_status)

    if script_path:
        manifest["source_code_status"] = "pass"
    elif manifest.get("source_code_status") != "failed":
        manifest["source_code_status"] = "incomplete"

    if score:
        manifest["visual_qa_status"] = "pass"
        manifest["qa_status"] = "completed"
        manifest["qa_execution_status"] = "completed"
    elif final_statuses and all(status == "semantic_validated_pass" for status in final_statuses):
        manifest["visual_qa_status"] = "not_applicable"
        manifest["qa_status"] = "completed"
        manifest["qa_execution_status"] = "completed"
    elif any(status == "not_strict" for status in final_statuses):
        manifest["visual_qa_status"] = "not_applicable"
        manifest["qa_status"] = "failed"
        manifest["qa_execution_status"] = "failed"
    else:
        manifest["visual_qa_status"] = "not_run"
        manifest["qa_status"] = "not_run"
        manifest["qa_execution_status"] = "not_run"

    if semantic_audit:
        manifest["semantic_audit"] = semantic_audit
        manifest["semantic_reconstruction_status"] = "pass" if semantic_audit.get("overall") == "pass" else "failed"
    if vector_validation:
        manifest["vector_validation"] = vector_validation
        manifest["vector_validation_status"] = "pass" if vector_validation.get("status") == "pass" else "failed"
    if checksums_path:
        manifest["checksums"] = portable_path(checksums_path, project_root)

    if final_statuses:
        if any(status == "not_strict" for status in final_statuses):
            manifest["status"] = "not_strict"
        elif any(status == "render_only" for status in final_statuses):
            manifest["status"] = "render_only"
        elif all(status == "visual_trace_pass" for status in final_statuses):
            manifest["status"] = "visual_trace_pass"
        elif all(status == "semantic_strict_pass" for status in final_statuses):
            manifest["status"] = "semantic_strict_pass"
        elif all(status == "semantic_validated_pass" for status in final_statuses):
            manifest["status"] = "semantic_validated_pass"
        else:
            manifest["status"] = "semantic_near_pass"
    else:
        manifest["status"] = "failed"

    if manifest["status"] not in FINAL_STATUSES:
        manifest["status"] = "failed"
    manifest["run_status"] = "completed" if manifest["status"] != "failed" else "failed"
    manifest["quality_status"] = status_to_qa_result(manifest["status"]) if manifest["status"] != "render_only" else "render_only"
    manifest["overall_status"] = manifest_overall_status(manifest)
    write_json(output_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize a scientific figure reproduction manifest with score and script evidence.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--score", type=Path)
    parser.add_argument("--script", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--qa-profile", choices=["semantic", "visual", "trace"], default="semantic")
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--runner", type=Path)
    parser.add_argument("--semantic-audit", type=Path)
    parser.add_argument("--vector-validation", type=Path)
    parser.add_argument("--panel-score-dir", type=Path)
    parser.add_argument("--checksums", type=Path)
    args = parser.parse_args()
    result = finalize_manifest(
        args.manifest,
        score_path=args.score,
        script_path=args.script,
        source_path=args.source,
        output_path=args.out,
        qa_profile=args.qa_profile,
        project_root=args.project_root,
        spec_path=args.spec,
        runner_path=args.runner,
        semantic_audit_path=args.semantic_audit,
        vector_validation_path=args.vector_validation,
        panel_score_dir=args.panel_score_dir,
        checksums_path=args.checksums,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"semantic_strict_pass", "semantic_validated_pass", "semantic_near_pass", "visual_trace_pass"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
