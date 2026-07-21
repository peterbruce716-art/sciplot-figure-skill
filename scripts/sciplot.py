"""Unified profile-aware entry point for SciPlot figure workflows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from PIL import Image

from audit_semantics import audit_mapping_validity, audit_semantics
from check_boxed_text_safety import analyze_boxed_text
from check_canvas_safety import analyze_canvas
from check_plot_geometry_safety import analyze_plot_geometry
from check_vector_output import check_pdf, check_svg, check_vector_outputs
from data_resolver import load_data_source
from execution_planner import ExecutionRequest, PlannerError, build_execution_plan
from output_policy import OutputSelection, resolve_outputs
from render_visualspec_matplotlib import render_file
from visualspec import load_json, validate_visualspec


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
CLAIMS = ("preview", "manuscript", "reusable", "archival", "release")


class WorkflowError(RuntimeError):
    def __init__(self, failure_type: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.failure_type = failure_type
        self.details = details


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _ensure_project_root(project: Path) -> Path:
    project = project.resolve()
    if project.exists() and project.is_file():
        raise WorkflowError("invalid_output_directory", "--out-dir points to a file", path=str(project))
    if project.exists() and any(project.iterdir()) and not (project / "execution_plan.json").is_file():
        raise WorkflowError(
            "unsafe_nonempty_output_directory",
            "Refusing to write into a non-empty directory that is not an existing SciPlot project",
            path=str(project),
        )
    project.mkdir(parents=True, exist_ok=True)
    return project


def _safe_copy(source: Path, destination: Path, project: Path) -> Path:
    source = source.resolve()
    destination = destination.resolve()
    try:
        destination.relative_to(project.resolve())
    except ValueError as exc:
        raise WorkflowError("output_path_escape", "Output path escapes the project root", path=str(destination)) from exc
    if source == destination:
        raise WorkflowError("input_output_collision", "An output path would overwrite an input", path=str(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


def _numeric_columns(table: Any) -> list[str]:
    if not isinstance(table, dict):
        return []
    result: list[str] = []
    for name, values in table.items():
        if isinstance(values, list) and values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            result.append(str(name))
    return result


def _build_visualspec(input_path: Path, copied_ref: str, *, x: str | None, y: str | None, yerr: str | None, plot_type: str | None) -> dict[str, Any]:
    table = load_data_source(input_path)
    numeric = _numeric_columns(table)
    x_name = x or (numeric[0] if numeric else None)
    y_name = y or (numeric[1] if len(numeric) > 1 else None)
    if not x_name or not y_name:
        raise WorkflowError("mapping_inference_failed", "Input needs at least two numeric columns or explicit --x/--y mappings")
    if not isinstance(table, dict) or x_name not in table or y_name not in table:
        raise WorkflowError("mapping_column_missing", "Mapped x/y column is missing", x=x_name, y=y_name)
    if x_name == y_name:
        raise WorkflowError("mapping_columns_overlap", "x and y must use different columns", column=x_name)
    if yerr:
        if yerr not in table:
            raise WorkflowError("mapping_column_missing", "Mapped yerr column is missing", yerr=yerr)
        if yerr == y_name:
            raise WorkflowError("uncertainty_same_as_measurement", "yerr must not use the y column", column=yerr)
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) < 0 for value in table[yerr]):
            raise WorkflowError("uncertainty_values_invalid", "yerr must contain finite non-negative numeric values", column=yerr)
    chosen_type = plot_type or ("errorbar" if yerr else "line")
    if chosen_type not in {"line", "scatter", "errorbar"}:
        raise WorkflowError("unsupported_inferred_plot", "Raw-input inference supports line, scatter, or errorbar", plot_type=chosen_type)
    if chosen_type == "errorbar" and not yerr:
        raise WorkflowError("missing_uncertainty_mapping", "errorbar requires --yerr")
    input_hash = sha256_file(input_path)
    mapping = {"x": x_name, "y": y_name}
    if yerr:
        mapping["yerr"] = yerr
    data: dict[str, Any] = {"source": copied_ref, "mapping": mapping}
    if yerr:
        data["uncertainty"] = {"semantics": "user_declared", "evidence_source": "explicit_cli_mapping", "column": yerr}
    return {
        "schema": "scientificfigure.visualspec.v2",
        "figure": {"id": "figure", "size_mm": [90, 60], "dpi": 200, "crop_mode": "fixed_canvas", "background": "white"},
        "theme": {"font": {"family_candidates": ["Liberation Sans", "DejaVu Sans"], "size_pt": 8}},
        "panels": [
            {
                "id": "figure",
                "bbox_normalized": [0.16, 0.18, 0.78, 0.74],
                "source_strategy": "raw_data",
                "representation": "semantic_vector",
                "axes": {"x": {"label": x_name}, "y": {"label": y_name}},
                "plots": [{"type": chosen_type, "data": data, "style": {"color": "#176B87", "line_width_pt": 1.2}}],
                "annotations": [],
            }
        ],
        "delivery": {
            "materialized_as": [chosen_type],
            "data_columns": mapping,
            "data_sha256": input_hash,
            "source_hashes": {copied_ref: input_hash},
            "mapping_validity": {"status": "pass", "source": "explicit_or_deterministic_cli_mapping"},
        },
    }


def _copy_spec_sources(spec: dict[str, Any], spec_path: Path, project: Path) -> tuple[dict[str, Any], dict[str, str]]:
    base = spec_path.resolve().parent
    hashes: dict[str, str] = {}
    used: set[str] = set()
    for panel in spec.get("panels", []):
        for plot in panel.get("plots", []):
            data = plot.get("data") or {}
            source_value = data.get("source") if isinstance(data, dict) else None
            if not source_value:
                continue
            source = Path(str(source_value))
            source = source if source.is_absolute() else base / source
            if not source.is_file():
                raise WorkflowError("missing_input", "VisualSpec data source does not exist", path=str(source))
            name = source.name
            if name in used:
                name = f"{source.stem}_{hashlib.sha1(str(source.resolve()).encode()).hexdigest()[:8]}{source.suffix}"
            used.add(name)
            copied = _safe_copy(source, project / "input" / name, project)
            ref = relative(copied, project)
            data["source"] = ref
            hashes[ref] = sha256_file(copied)
    delivery = spec.setdefault("delivery", {})
    if hashes:
        delivery["source_hashes"] = hashes
        if len(hashes) == 1:
            delivery["data_sha256"] = next(iter(hashes.values()))
        delivery.setdefault("mapping_validity", {"status": "pass", "source": "existing_visualspec_mapping"})
    return spec, hashes


def _prepare_visualspec(args: argparse.Namespace, project: Path) -> tuple[Path, dict[str, str]]:
    if bool(args.input) == bool(args.spec):
        raise WorkflowError("input_selection_error", "Provide exactly one of --input or --spec")
    if args.input:
        source = args.input.resolve()
        if not source.is_file():
            raise WorkflowError("missing_input", "Input data file does not exist", path=str(source))
        copied = _safe_copy(source, project / "input" / source.name, project)
        ref = relative(copied, project)
        spec = _build_visualspec(copied, ref, x=args.x, y=args.y, yerr=args.yerr, plot_type=args.plot_type)
        hashes = {ref: sha256_file(copied)}
    else:
        source_spec = args.spec.resolve()
        if not source_spec.is_file():
            raise WorkflowError("missing_spec", "VisualSpec file does not exist", path=str(source_spec))
        spec = load_json(source_spec)
        spec, hashes = _copy_spec_sources(spec, source_spec, project)
    errors = validate_visualspec(spec)
    if errors:
        raise WorkflowError("invalid_visualspec", "VisualSpec validation failed", errors=errors)
    spec_path = project / "visualspec.json"
    write_json(spec_path, spec)
    hashes.setdefault("visualspec.json", sha256_file(spec_path))
    return spec_path, hashes


def _plot_kinds(spec: dict[str, Any]) -> set[str]:
    return {str(plot.get("type")) for panel in spec.get("panels", []) for plot in panel.get("plots", []) if plot.get("type")}


def _has_boxed_text(spec: dict[str, Any]) -> bool:
    policy = spec.get("qa_policy") or {}
    value = policy.get("boxed_text_safety") if isinstance(policy, dict) else None
    return isinstance(value, dict) and value.get("enabled") is True


def _declared_safety_report(
    spec: dict[str, Any],
    policy_name: str,
    image_path: Path,
    analyzer: Any,
    project: Path,
) -> dict[str, Any]:
    qa_policy = spec.get("qa_policy") or {}
    policy = qa_policy.get(policy_name) if isinstance(qa_policy, dict) else None
    if not isinstance(policy, dict) or policy.get("enabled") is not True:
        return {"status": "not_applicable", "reason": f"{policy_name} is not enabled in qa_policy"}
    regions = policy.get("regions")
    if not isinstance(regions, list) or not regions:
        return {"status": "failed", "reason": f"{policy_name} requires a non-empty regions array"}
    return analyzer(image_path, regions, project_root=project)


def _source_has_boxed_text(spec_path: Path | None) -> bool:
    if spec_path is None or not spec_path.is_file():
        return False
    try:
        return _has_boxed_text(load_json(spec_path))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _write_rerun_script(project: Path, selection: OutputSelection, *, write_support_files: bool) -> Path:
    script_path = project / "src" / "render.py"
    runner = SCRIPT_DIR / "render_visualspec_matplotlib.py"
    text = f'''from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND = [
    sys.executable,
    {str(runner)!r},
    "--spec", str(ROOT / "visualspec.json"),
    "--out-dir", str(ROOT / "output"),
    "--formats", {','.join(selection.formats)!r},
    "--basename", "figure",
    *([] if {write_support_files!r} else ["--no-support-files"]),
]

if __name__ == "__main__":
    raise SystemExit(subprocess.call(COMMAND))
'''
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(text, encoding="utf-8")
    return script_path


def _parse_outputs(project: Path, formats: tuple[str, ...]) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    for fmt in formats:
        path = project / "output" / f"figure.{fmt}"
        if not path.is_file() or path.stat().st_size == 0:
            reports[fmt] = {"status": "failed", "reason": "missing_or_empty"}
            continue
        try:
            if fmt == "png":
                with Image.open(path) as image:
                    image.verify()
            elif fmt == "svg":
                ET.parse(path)
            elif fmt == "pdf":
                report = check_pdf(path, representation="semantic_raster", project_root=project)
                if report["status"] != "pass":
                    reports[fmt] = report
                    continue
            reports[fmt] = {"status": "pass", "path": relative(path, project), "sha256": sha256_file(path)}
        except Exception as exc:
            reports[fmt] = {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}
    return reports


def _vector_report(project: Path, formats: tuple[str, ...], representation: str) -> dict[str, Any]:
    svg = project / "output" / "figure.svg"
    pdf = project / "output" / "figure.pdf"
    if "svg" in formats and "pdf" in formats:
        return check_vector_outputs(svg, pdf, representation=representation, project_root=project)
    if "svg" in formats:
        report = check_svg(svg, representation=representation, project_root=project)
        return {"schema": "scientificfigure.vector_validation.v1", "status": report["status"], "representation": representation, "svg": report, "pdf": None}
    if "pdf" in formats:
        report = check_pdf(pdf, representation=representation, project_root=project)
        return {"schema": "scientificfigure.vector_validation.v1", "status": report["status"], "representation": representation, "svg": None, "pdf": report}
    return {"schema": "scientificfigure.vector_validation.v1", "status": "not_applicable", "reason": "no vector output requested"}


def _representation(spec: dict[str, Any]) -> str:
    values = {str(panel.get("representation", "semantic_vector")) for panel in spec.get("panels", [])}
    return values.pop() if len(values) == 1 else "mixed"


def _project_checksums(project: Path, paths: list[Path]) -> dict[str, str]:
    return {relative(path, project): sha256_file(path) for path in paths if path.is_file()}


def _validate_project_manifest(project: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    references = [manifest.get("visualspec"), manifest.get("render_script"), manifest.get("qa_report"), *(manifest.get("outputs") or {}).values()]
    for value in references:
        if not isinstance(value, str) or not value:
            failures.append({"code": "missing_reference", "path": str(value)})
            continue
        candidate = (project / value).resolve()
        if not candidate.is_relative_to(project.resolve()):
            failures.append({"code": "path_escape", "path": value})
        elif not candidate.is_file():
            failures.append({"code": "missing_file", "path": value})
    for value, expected in (manifest.get("checksums") or {}).items():
        candidate = (project / value).resolve()
        if not candidate.is_relative_to(project.resolve()) or not candidate.is_file():
            failures.append({"code": "checksum_path_invalid", "path": str(value)})
        elif sha256_file(candidate) != expected:
            failures.append({"code": "checksum_mismatch", "path": str(value)})
    return {"status": "pass" if not failures else "failed", "failures": failures}


def _canvas_config(spec: dict[str, Any]) -> tuple[int, str, int, tuple[str, ...]]:
    policy = spec.get("qa_policy") or {}
    canvas = policy.get("canvas_safety") if isinstance(policy, dict) else None
    canvas = canvas if isinstance(canvas, dict) else {}
    enabled = canvas.get("enabled", True) is not False
    edges = canvas.get("required_edges") if isinstance(canvas.get("required_edges"), list) else ("top", "right", "bottom", "left")
    figure = spec.get("figure") or {}
    return (
        max(1, int(canvas.get("margin_px", 1))),
        str(canvas.get("background", figure.get("background", "#ffffff"))),
        int(canvas.get("tolerance", 10)),
        tuple(str(edge) for edge in edges) if enabled else (),
    )


def _canvas_report(spec: dict[str, Any], image: Path, project: Path) -> dict[str, Any]:
    margin, background, tolerance, edges = _canvas_config(spec)
    return analyze_canvas(image, margin_px=margin, background=background, tolerance=tolerance, required_edges=edges, project_root=project)


def _run_lightweight(args: argparse.Namespace, plan: Any, project: Path, started: float) -> dict[str, Any]:
    spec_path, input_hashes = _prepare_visualspec(args, project)
    spec = load_json(spec_path)
    selection = resolve_outputs(
        args.outputs,
        profile=plan.selected_profile,
        plot_kinds=_plot_kinds(spec),
        preview_only=(args.claim == "preview"),
    )
    if "png" not in selection.formats:
        raise WorkflowError("png_required", "quick and standard profiles require PNG for canvas safety")
    write_support_files = plan.selected_profile != "quick"
    render_script = _write_rerun_script(project, selection, write_support_files=write_support_files)
    output_dir = project / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    for fmt in ("png", "svg", "pdf"):
        stale = output_dir / f"figure.{fmt}"
        if fmt not in selection.formats and stale.is_file():
            stale.unlink()
    render_manifest = render_file(
        spec_path,
        output_dir,
        script_path=render_script,
        output_formats=selection.formats,
        basename="figure",
        write_support_files=write_support_files,
    )
    parseability = _parse_outputs(project, selection.formats)
    mapping = audit_mapping_validity(spec, spec_path=spec_path)
    canvas = _canvas_report(spec, output_dir / "figure.png", project)
    semantic: dict[str, Any] = {"status": "not_run", "overall": "not_run"}
    vector: dict[str, Any] = {"status": "not_run"}
    geometry: dict[str, Any] = {"status": "not_run"}
    boxed_text: dict[str, Any] = {"status": "not_run"}
    if plan.selected_profile == "standard":
        semantic = audit_semantics(spec_path, output_dir / "render_semantics.json", project_root=project)
        vector = _vector_report(project, selection.formats, _representation(spec))
        geometry = _declared_safety_report(spec, "plot_geometry_safety", output_dir / "figure.png", analyze_plot_geometry, project)
        boxed_text = _declared_safety_report(spec, "boxed_text_safety", output_dir / "figure.png", analyze_boxed_text, project)
    parse_ok = all(item.get("status") == "pass" for item in parseability.values())
    required_ok = render_manifest.get("render_status") == "pass" and parse_ok and mapping["status"] == "pass" and canvas["status"] == "pass"
    if plan.selected_profile == "standard":
        required_ok = (
            required_ok
            and semantic["overall"] == "pass"
            and vector["status"] in {"pass", "not_applicable"}
            and geometry["status"] in {"pass", "not_applicable"}
            and boxed_text["status"] in {"pass", "not_applicable"}
        )
    report_path = project / ("quick_report.json" if plan.selected_profile == "quick" else "qa" / Path("report.json"))
    outputs = {fmt: f"output/figure.{fmt}" for fmt in selection.formats}
    checksums = _project_checksums(project, [spec_path, render_script, *(project / path for path in outputs.values())]) if plan.selected_profile == "standard" else {}
    report: dict[str, Any] = {
        "schema": "sciplot.quick-report.v1" if plan.selected_profile == "quick" else "sciplot.qa-report.v1",
        "status": "pass" if required_ok else "failed",
        "selected_profile": plan.selected_profile,
        "enabled_gates": list(plan.enabled_gates),
        "input_hashes": input_hashes,
        "output_selection": selection.to_dict(),
        "parseability": parseability,
        "mapping_validation": mapping,
        "canvas_safety": canvas,
        "plot_geometry_safety": geometry,
        "boxed_text_safety": boxed_text,
        "semantic_audit": semantic,
        "vector_validation": vector,
    }
    if plan.selected_profile == "standard":
        report["checksums"] = checksums
        report["environment_summary"] = {"python": platform.python_version(), "implementation": platform.python_implementation(), "platform": platform.system()}
    write_json(report_path, report)
    manifest = {
        "schema": "sciplot.project-manifest.v1",
        "status": "ok" if required_ok else "failed",
        "profile": plan.selected_profile,
        "visualspec": "visualspec.json",
        "render_script": relative(render_script, project),
        "outputs": outputs,
        "qa_report": relative(report_path, project),
        "input_hashes": input_hashes,
        "data_swap_template": relative(args.template.resolve(), project) if args.template and args.template.resolve().is_relative_to(project) else None,
    }
    if plan.selected_profile == "standard":
        manifest["checksums"] = checksums
    write_json(project / "manifest.json", manifest)
    if plan.selected_profile == "standard":
        manifest_validation = _validate_project_manifest(project, manifest)
        required_ok = required_ok and manifest_validation["status"] == "pass"
        report["manifest_validation"] = manifest_validation
        report["status"] = "pass" if required_ok else "failed"
        manifest["status"] = "ok" if required_ok else "failed"
        write_json(report_path, report)
        write_json(project / "manifest.json", manifest)
    created_files = sum(1 for path in project.rglob("*") if path.is_file())
    result = {
        "schema": "sciplot.run-result.v1",
        "status": "ok" if required_ok else "failed",
        "selected_profile": plan.selected_profile,
        "project": str(project),
        "input_hash": next(iter(input_hashes.values()), None),
        "input_hashes": input_hashes,
        "outputs": outputs,
        "report": relative(report_path, project),
        "performance": {
            "subprocess_count": 0,
            "render_count": 1,
            "created_file_count": created_files,
            "enabled_gate_count": len(plan.enabled_gates),
            "duration_seconds": round(time.perf_counter() - started, 3),
        },
    }
    return result


def run_command(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    request = ExecutionRequest(
        profile=args.profile,
        claim=args.claim,
        has_input=bool(args.input),
        has_reference=bool(args.source),
        require_strict=args.require_strict,
        enable_data_swap=args.enable_data_swap,
        verify_data_driven=args.verify_data_driven,
        create_bundle=args.create_bundle,
        release_acceptance=args.claim == "release",
        has_boxed_text=_source_has_boxed_text(args.spec),
        preview_only=args.claim == "preview",
    )
    plan = build_execution_plan(request)
    print(f"SciPlot profile={plan.selected_profile}; gates={','.join(plan.enabled_gates)}", file=sys.stderr)
    if plan.require_data_swap and args.template is None:
        raise WorkflowError(
            "missing_data_swap_template",
            "Reusable/data-swap verification requires --template and isolated baseline/changed inputs",
        )
    if plan.require_data_swap and plan.selected_profile != "audit":
        raise WorkflowError(
            "data_swap_requires_audit",
            "Changed-input proof is an audit capability; use --profile audit or --profile auto",
        )
    if plan.selected_profile == "audit":
        with tempfile.TemporaryDirectory(prefix="sciplot-audit-") as staging_name:
            staging = Path(staging_name)
            _prepare_visualspec(args, staging)
            finalize_args = argparse.Namespace(
                project=staging,
                profile="audit",
                bundle=args.out_dir,
                source=args.source,
                claim=args.claim,
                require_strict=args.require_strict,
                enable_data_swap=args.enable_data_swap,
                verify_data_driven=args.verify_data_driven,
                template=args.template,
                figure=getattr(args, "figure", None),
                baseline_data=getattr(args, "baseline_data", None),
                changed_data=getattr(args, "changed_data", None),
                release_acceptance=args.claim == "release",
            )
            result = finalize_command(finalize_args)
            result["selected_profile"] = "audit"
            result["project"] = str(args.out_dir.resolve())
            result["execution_plan"] = "qa/execution_plan.json"
            return result
    project = _ensure_project_root(args.out_dir)
    write_json(project / "execution_plan.json", plan.to_dict())
    return _run_lightweight(args, plan, project, started)


def validate_command(args: argparse.Namespace) -> dict[str, Any]:
    project = args.project.resolve()
    if not project.is_dir():
        raise WorkflowError("missing_project", "Project directory does not exist", path=str(project))
    if args.profile == "audit":
        required = ("verify.py", "run_report.json", "reproduction_manifest.json", "bundle.lock.json")
        missing = [name for name in required if not (project / name).is_file()]
        if missing:
            raise WorkflowError(
                "invalid_audit_bundle",
                "Audit validation requires a completed portable bundle; use finalize first",
                missing=missing,
            )
        verify = _run_captured([sys.executable, str(project / "verify.py")], timeout=600)
        manifest = load_json(project / "reproduction_manifest.json")
        run_report = load_json(project / "run_report.json")
        if verify.returncode != 0:
            raise WorkflowError(
                "audit_bundle_verification_failed",
                "Portable audit bundle verification failed",
                stdout=verify.stdout[-4000:],
                stderr=verify.stderr[-4000:],
            )
        result = {
            "schema": "sciplot.validation-result.v1",
            "status": "pass",
            "profile": "audit",
            "project": str(project),
            "bundle_verification": {"status": "pass", "returncode": verify.returncode},
            "manifest_status": manifest.get("status"),
            "audit_report_status": run_report.get("status"),
        }
        return result
    spec_path = project / "visualspec.json"
    manifest_path = project / "manifest.json"
    if not spec_path.is_file() or not manifest_path.is_file():
        raise WorkflowError("invalid_project", "Project is missing visualspec.json or manifest.json")
    spec = load_json(spec_path)
    manifest = load_json(manifest_path)
    formats = tuple((manifest.get("outputs") or {}).keys())
    parseability = _parse_outputs(project, formats)
    mapping = audit_mapping_validity(spec, spec_path=spec_path)
    canvas = _canvas_report(spec, project / "output" / "figure.png", project)
    semantic = {"status": "not_run", "overall": "not_run"}
    vector = {"status": "not_run"}
    geometry = {"status": "not_run"}
    boxed_text = {"status": "not_run"}
    manifest_validation = {"status": "not_run", "failures": []}
    if args.profile == "standard":
        semantic = audit_semantics(spec_path, project / "output" / "render_semantics.json", project_root=project)
        vector = _vector_report(project, formats, _representation(spec))
        geometry = _declared_safety_report(spec, "plot_geometry_safety", project / "output" / "figure.png", analyze_plot_geometry, project)
        boxed_text = _declared_safety_report(spec, "boxed_text_safety", project / "output" / "figure.png", analyze_boxed_text, project)
        manifest_validation = _validate_project_manifest(project, manifest)
    ok = all(item.get("status") == "pass" for item in parseability.values()) and mapping["status"] == "pass" and canvas["status"] == "pass"
    if args.profile == "standard":
        ok = (
            ok
            and semantic["overall"] == "pass"
            and vector["status"] in {"pass", "not_applicable"}
            and geometry["status"] in {"pass", "not_applicable"}
            and boxed_text["status"] in {"pass", "not_applicable"}
            and manifest_validation["status"] == "pass"
        )
    result = {
        "schema": "sciplot.validation-result.v1",
        "status": "pass" if ok else "failed",
        "profile": args.profile,
        "project": str(project),
        "parseability": parseability,
        "mapping_validation": mapping,
        "canvas_safety": canvas,
        "plot_geometry_safety": geometry,
        "boxed_text_safety": boxed_text,
        "semantic_audit": semantic,
        "vector_validation": vector,
        "manifest_validation": manifest_validation,
    }
    write_json(project / "qa" / "validation_report.json", result)
    return result


def _subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["MPLBACKEND"] = "Agg"
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "1"
    return env


def _run_captured(command: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
        env=_subprocess_env(),
    )


def finalize_command(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    project = args.project.resolve()
    bundle = args.bundle.resolve()
    if not project.is_dir() or not (project / "visualspec.json").is_file():
        raise WorkflowError("invalid_project", "finalize requires a project with visualspec.json", path=str(project))
    if bundle == project or bundle.is_relative_to(project):
        raise WorkflowError("bundle_path_overlap", "Audit bundle must be outside the working project", path=str(bundle))
    if bundle.exists() and (bundle.is_file() or any(bundle.iterdir())):
        raise WorkflowError("unsafe_nonempty_bundle", "Audit bundle path must be new or empty", path=str(bundle))
    plan = build_execution_plan(
        ExecutionRequest(
            profile="audit",
            claim=args.claim,
            require_strict=args.require_strict,
            enable_data_swap=args.enable_data_swap,
            verify_data_driven=args.verify_data_driven,
            create_bundle=True,
            release_acceptance=args.release_acceptance,
        )
    )
    required_swap_values = (args.template, args.figure, args.baseline_data, args.changed_data)
    if plan.require_data_swap and not all(required_swap_values):
        raise WorkflowError(
            "missing_data_swap_evidence",
            "Audit reusable proof requires --template, --figure, --baseline-data, and --changed-data",
        )
    data_swap_proof: dict[str, Any] | None = None
    proof_path: Path | None = None
    release_report: dict[str, Any] | None = None
    release_path: Path | None = None
    plan_path = project / "qa" / "finalize_execution_plan.json"
    write_json(plan_path, plan.to_dict())
    subprocess_count = 0
    if plan.require_data_swap:
        proof_path = project / "qa" / "data_swap_change_proof.json"
        proof_command = [
            sys.executable,
            str(SCRIPT_DIR / "verify_data_swap_change.py"),
            "--root",
            str(args.template.resolve().parent),
            "--template",
            str(args.template.resolve()),
            "--figure",
            args.figure,
            "--baseline-data",
            str(args.baseline_data.resolve()),
            "--changed-data",
            str(args.changed_data.resolve()),
            "--baseline-out-dir",
            str(project / "qa" / "data_swap_baseline"),
            "--changed-out-dir",
            str(project / "qa" / "data_swap_changed"),
            "--json-out",
            str(proof_path),
        ]
        proof_run = _run_captured(proof_command)
        subprocess_count += 1
        if proof_run.returncode != 0 or not proof_path.is_file():
            raise WorkflowError("data_swap_proof_failed", "Changed-input proof failed", stdout=proof_run.stdout[-4000:], stderr=proof_run.stderr[-4000:])
        data_swap_proof = load_json(proof_path)

    if "release_acceptance" in plan.enabled_gates:
        release_path = project / "qa" / "release_acceptance.json"
        release_run = _run_captured([sys.executable, str(SCRIPT_DIR / "release_acceptance.py"), "--json-out", str(release_path)], timeout=1200)
        subprocess_count += 1
        if release_run.returncode != 0 or not release_path.is_file():
            raise WorkflowError("release_acceptance_failed", "Release acceptance failed", stdout=release_run.stdout[-4000:], stderr=release_run.stderr[-4000:])
        release_report = load_json(release_path)

    command = [
        sys.executable,
        str(SCRIPT_DIR / "run_reproduction.py"),
        "--spec",
        str(project / "visualspec.json"),
        "--out-dir",
        str(bundle),
    ]
    command.extend(["--execution-plan", str(plan_path)])
    if data_swap_proof is not None and proof_path is not None:
        command.extend(["--data-swap-template", str(args.template.resolve()), "--data-swap-proof", str(proof_path)])
    if release_report is not None and release_path is not None:
        command.extend(["--release-acceptance-report", str(release_path)])
    if args.source:
        if not args.source.is_file():
            raise WorkflowError("missing_reference", "Reference image does not exist", path=str(args.source))
        command.extend(["--source", str(args.source.resolve())])
    if args.require_strict:
        command.append("--require-strict")
    completed = _run_captured(command)
    subprocess_count += 1
    if completed.returncode != 0:
        report_path = bundle / "run_report.json"
        details = load_json(report_path) if report_path.is_file() else {"stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:]}
        raise WorkflowError("audit_bundle_failed", "Existing audit runner did not complete", audit_report=details)

    manifest = load_json(bundle / "reproduction_manifest.json")
    run_report = load_json(bundle / "run_report.json")
    return {
        "schema": "sciplot.finalize-result.v1",
        "status": "pass",
        "profile": "audit",
        "project": str(project),
        "bundle": str(bundle),
        "manifest_status": manifest.get("status"),
        "audit_report_status": run_report.get("status"),
        "data_swap_proof": data_swap_proof,
        "release_acceptance": release_report,
        "performance": {
            "subprocess_count": subprocess_count,
            "render_count": 1 + (2 if data_swap_proof else 0),
            "created_file_count": sum(1 for path in bundle.rglob("*") if path.is_file()),
            "enabled_gate_count": len(plan.enabled_gates),
            "duration_seconds": round(time.perf_counter() - started, 3),
        },
    }


def trace_pdf_command(args: argparse.Namespace) -> dict[str, Any]:
    pdf = args.pdf.resolve()
    out_dir = args.out_dir.resolve()
    if not pdf.is_file():
        raise WorkflowError("missing_pdf", "Source PDF does not exist", path=str(pdf))
    if args.clip_manifest is None or not args.clip_manifest.is_file():
        raise WorkflowError("missing_clip_manifest", "trace-pdf requires an existing --clip-manifest")
    if out_dir == pdf or out_dir.is_relative_to(pdf.parent) and out_dir.name == pdf.name:
        raise WorkflowError("input_output_collision", "Trace output cannot overwrite the source PDF")
    plan = build_execution_plan(ExecutionRequest(profile="auto", pdf_trace=True))
    command = [
        sys.executable,
        str(SCRIPT_DIR / "fresh_pdf_batch.py"),
        "--pdf",
        str(pdf),
        "--clip-manifest",
        str(args.clip_manifest.resolve()),
        "--out-dir",
        str(out_dir),
    ]
    completed = _run_captured(command, timeout=1200)
    if completed.returncode != 0:
        try:
            details = json.loads(completed.stdout)
        except json.JSONDecodeError:
            details = {"stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:]}
        raise WorkflowError("pdf_trace_failed", "Fresh PDF trace runner failed", trace_report=details)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise WorkflowError("invalid_child_json", "Fresh PDF trace runner did not emit one JSON document") from exc
    write_json(out_dir / "execution_plan.json", plan.to_dict())
    result["selected_profile"] = plan.selected_profile
    result["enabled_gates"] = list(plan.enabled_gates)
    return result


def _common_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Emit one machine-readable JSON document on stdout.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run profile-aware SciPlot figure workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Create a quick, standard, or planned audit project.")
    run_parser.add_argument("--profile", choices=("auto", "quick", "standard", "audit"), default="standard")
    run_parser.add_argument("--input", type=Path)
    run_parser.add_argument("--spec", type=Path)
    run_parser.add_argument("--source", type=Path, help="Optional reference image; used by audit finalization.")
    run_parser.add_argument("--out-dir", required=True, type=Path)
    run_parser.add_argument("--outputs", default="auto")
    run_parser.add_argument("--x")
    run_parser.add_argument("--y")
    run_parser.add_argument("--yerr")
    run_parser.add_argument("--plot-type", choices=("line", "scatter", "errorbar"))
    run_parser.add_argument("--claim", choices=CLAIMS)
    run_parser.add_argument("--enable-data-swap", action="store_true")
    run_parser.add_argument("--verify-data-driven", action="store_true")
    run_parser.add_argument("--require-strict", action="store_true")
    run_parser.add_argument("--create-bundle", action="store_true")
    run_parser.add_argument("--template", type=Path)
    run_parser.add_argument("--figure")
    run_parser.add_argument("--baseline-data", type=Path)
    run_parser.add_argument("--changed-data", type=Path)
    _common_json(run_parser)
    run_parser.set_defaults(handler=run_command)

    validate_parser = subparsers.add_parser("validate", help="Re-run the validation set for a project.")
    validate_parser.add_argument("--project", required=True, type=Path)
    validate_parser.add_argument("--profile", choices=("quick", "standard", "audit"), default="standard")
    _common_json(validate_parser)
    validate_parser.set_defaults(handler=validate_command)

    finalize_parser = subparsers.add_parser("finalize", help="Upgrade a working project to a strict audit bundle.")
    finalize_parser.add_argument("--project", required=True, type=Path)
    finalize_parser.add_argument("--profile", choices=("audit",), default="audit")
    finalize_parser.add_argument("--bundle", required=True, type=Path)
    finalize_parser.add_argument("--source", type=Path)
    finalize_parser.add_argument("--claim", choices=CLAIMS)
    finalize_parser.add_argument("--require-strict", action="store_true")
    finalize_parser.add_argument("--enable-data-swap", action="store_true")
    finalize_parser.add_argument("--verify-data-driven", action="store_true")
    finalize_parser.add_argument("--template", type=Path)
    finalize_parser.add_argument("--figure")
    finalize_parser.add_argument("--baseline-data", type=Path)
    finalize_parser.add_argument("--changed-data", type=Path)
    finalize_parser.add_argument("--release-acceptance", action="store_true")
    _common_json(finalize_parser)
    finalize_parser.set_defaults(handler=finalize_command)

    trace_parser = subparsers.add_parser("trace-pdf", help="Delegate a fresh source-bound PDF trace batch.")
    trace_parser.add_argument("--pdf", required=True, type=Path)
    trace_parser.add_argument("--clip-manifest", type=Path)
    trace_parser.add_argument("--out-dir", required=True, type=Path)
    _common_json(trace_parser)
    trace_parser.set_defaults(handler=trace_pdf_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.handler(args)
        returncode = 0 if result.get("status") in {"ok", "pass"} else 2
    except WorkflowError as exc:
        result = {"schema": "sciplot.error.v1", "status": "failed", "failure_type": exc.failure_type, "message": str(exc), **exc.details}
        returncode = 2
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError, PlannerError) as exc:
        result = {"schema": "sciplot.error.v1", "status": "failed", "failure_type": type(exc).__name__, "message": str(exc)}
        returncode = 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
