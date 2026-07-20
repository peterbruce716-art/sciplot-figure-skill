from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image

from bundle_lock import fixed_environment, verify_bundle_lock, write_run_attestation
from environment_policy import verify_environment_policy
from portable_paths import portable_command, portable_json, portable_path
from visualspec import manifest_overall_status, status_to_qa_result


DEFAULT_TIMEOUTS = {
    "validate_visualspec": 30,
    "render": 120,
    "score": 60,
    "semantic_audit": 30,
    "vector_validation": 30,
    "canvas_safety": 30,
    "boxed_text_safety": 30,
    "plot_geometry_safety": 30,
    "finalize_manifest": 30,
    "checksums": 30,
    "validate_manifest": 30,
}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sanitize_delivery_json(root: Path) -> None:
    for path in sorted(root.rglob("*.json")):
        try:
            relative = path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if relative.parts and relative.parts[0] in {"logs", "scratch"}:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        sanitized = portable_json(payload, root)
        if sanitized != payload:
            write_json(path, sanitized)


def rel(path: Path, root: Path) -> str:
    return portable_path(path, root) or path.name


def run(cmd: list[str], *, log_path: Path, timeout: int, bundle_root: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    start = time.perf_counter()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout, env=env)
        status = "ok" if completed.returncode == 0 else "failed"
        log_path.write_text(
            "COMMAND\n" + json.dumps(cmd, ensure_ascii=False) + "\n\nSTDOUT\n" + completed.stdout + "\n\nSTDERR\n" + completed.stderr,
            encoding="utf-8",
        )
        return {"command": portable_command(cmd, bundle_root), "returncode": completed.returncode, "status": status, "duration_seconds": round(time.perf_counter() - start, 3), "log": portable_path(log_path, bundle_root)}
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        log_path.write_text(
            "COMMAND\n" + json.dumps(cmd, ensure_ascii=False) + f"\n\nTIMEOUT after {timeout}s\n\nSTDOUT\n{stdout}\n\nSTDERR\n{stderr}",
            encoding="utf-8",
        )
        return {"command": portable_command(cmd, bundle_root), "returncode": None, "status": "failed", "failure_type": "timeout", "timeout_seconds": timeout, "duration_seconds": round(time.perf_counter() - start, 3), "log": portable_path(log_path, bundle_root)}


def panel_crop_box(bbox: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    left = int(float(bbox[0]) * width)
    bottom = int(float(bbox[1]) * height)
    box_width = int(float(bbox[2]) * width)
    box_height = int(float(bbox[3]) * height)
    top = max(0, height - bottom - box_height)
    right = max(left + 1, min(width, left + box_width))
    lower = max(top + 1, min(height, top + box_height))
    return (max(0, left), top, right, lower)


def crop_panel_images(source: Path, actual: Path, spec_path: Path, qa_dir: Path) -> list[dict[str, Path]]:
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    src = Image.open(source).convert("RGB")
    act = Image.open(actual).convert("RGB")
    crops: list[dict[str, Path]] = []
    crop_dir = qa_dir / "panel_crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    for panel in spec.get("panels", []):
        panel_id = str(panel.get("id", "panel"))
        bbox = panel.get("bbox_normalized")
        if not (isinstance(bbox, list) and len(bbox) == 4):
            continue
        source_crop_path = crop_dir / f"{panel_id}_source.png"
        actual_crop_path = crop_dir / f"{panel_id}_render.png"
        src.crop(panel_crop_box(bbox, src.width, src.height)).save(source_crop_path)
        act.crop(panel_crop_box(bbox, act.width, act.height)).save(actual_crop_path)
        crops.append({"id": panel_id, "source": source_crop_path, "actual": actual_crop_path})
    return crops


def bundled_source_path(bundle_root: Path) -> Path | None:
    pointer = bundle_root / "source_pointer.json"
    if not pointer.exists():
        return None
    data = json.loads(pointer.read_text(encoding="utf-8-sig"))
    value = data.get("source")
    return bundle_root / value if value else None


def command_renderer_config(bundle_root: Path) -> dict[str, Any] | None:
    path = bundle_root / "renderer_config.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) and payload.get("type") == "command" else None


def canvas_safety_config(spec_path: Path) -> dict[str, Any] | None:
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    policy = spec.get("qa_policy", {})
    config = policy.get("canvas_safety") if isinstance(policy, dict) else None
    if not isinstance(config, dict) or not config.get("enabled", False):
        return None
    return config


def boxed_text_safety_config(spec_path: Path) -> dict[str, Any] | None:
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    policy = spec.get("qa_policy", {})
    config = policy.get("boxed_text_safety") if isinstance(policy, dict) else None
    if not isinstance(config, dict) or not config.get("enabled", False):
        return None
    return config


def plot_geometry_safety_config(spec_path: Path) -> dict[str, Any] | None:
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    policy = spec.get("qa_policy", {})
    config = policy.get("plot_geometry_safety") if isinstance(policy, dict) else None
    if not isinstance(config, dict) or not config.get("enabled", False):
        return None
    return config


def cap_command_renderer_manifest(manifest_path: Path) -> None:
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    changed = False
    figures = manifest.get("figures")
    if isinstance(figures, dict):
        for figure in figures.values():
            if not isinstance(figure, dict):
                continue
            if figure.get("status") == "semantic_strict_pass":
                figure["status"] = "semantic_near_pass"
                changed = True
            qa = figure.get("qa")
            if isinstance(qa, dict) and qa.get("result") == "strict_pass":
                qa["result"] = status_to_qa_result("semantic_near_pass")
                qa["semantic_attestation_limit"] = "custom_command_renderer_max_semantic_near_pass"
                changed = True
    if manifest.get("status") == "semantic_strict_pass":
        manifest["status"] = "semantic_near_pass"
        changed = True
    if changed:
        manifest["quality_status"] = status_to_qa_result(str(manifest.get("status")))
        manifest["overall_status"] = manifest_overall_status(manifest)
        notes = manifest.setdefault("notes", [])
        if isinstance(notes, list):
            notes.append("custom_command_renderer_max_semantic_near_pass")
        write_json(manifest_path, manifest)


def bundle_reproduce(bundle_root: Path, *, require_strict: bool = False, qa_profile: str = "semantic") -> int:
    bundle_root = bundle_root.resolve()
    script_dir = Path(__file__).resolve().parent
    logs_dir = bundle_root / "logs"
    outputs_dir = bundle_root / "outputs"
    qa_dir = bundle_root / "qa"
    mplconfig = Path(tempfile.mkdtemp(prefix="sfr-mplconfig-"))
    env = fixed_environment(os.environ, mplconfig=mplconfig)

    report: dict[str, Any] = {"schema": "scientificfigure.reproduction_run.v2", "status": "failed", "project_root": ".", "steps": {}}
    work_spec = bundle_root / "visualspec.json"
    bundled_source = bundled_source_path(bundle_root)

    steps = report["steps"]
    lock = verify_bundle_lock(bundle_root, bundle_root / "bundle.lock.json")
    steps["bundle_lock_preflight"] = lock
    if lock["status"] != "pass":
        report["stage"] = "bundle_lock_preflight"
        report["failure_type"] = "immutable_bundle_modified"
        write_json(bundle_root / "run_report.json", report)
        write_run_attestation(bundle_root, status="failed", steps=steps)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    environment_policy = verify_environment_policy(bundle_root / "environment" / "environment_policy.json")
    steps["environment_policy"] = environment_policy
    if environment_policy["status"] != "pass":
        report["stage"] = "environment_policy"
        report["failure_type"] = "environment_mismatch"
        write_json(bundle_root / "run_report.json", report)
        write_run_attestation(bundle_root, status="failed", steps=steps)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    validate = run([sys.executable, str(script_dir / "validate_visualspec.py"), "--path", str(work_spec), "--json-out", str(bundle_root / "visualspec_validation.json"), "--project-root", str(bundle_root)], log_path=logs_dir / "validate_visualspec.log", timeout=DEFAULT_TIMEOUTS["validate_visualspec"], bundle_root=bundle_root, env=env)
    steps["validate_visualspec"] = validate
    if validate["status"] == "failed":
        write_json(bundle_root / "run_report.json", report)
        write_run_attestation(bundle_root, status="failed", steps=steps)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    render = run([sys.executable, str(bundle_root / "render.py")], log_path=logs_dir / "render.log", timeout=DEFAULT_TIMEOUTS["render"], bundle_root=bundle_root, env=env)
    steps["render"] = render
    if render["status"] == "failed":
        write_json(bundle_root / "run_report.json", report)
        write_run_attestation(bundle_root, status="failed", steps=steps)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    canvas_safety_json = qa_dir / "canvas_safety.json"
    canvas_config = canvas_safety_config(work_spec)
    if canvas_config:
        required_edges = canvas_config.get("required_edges", ["top", "right", "bottom", "left"])
        if not isinstance(required_edges, list):
            required_edges = ["top", "right", "bottom", "left"]
        canvas_safety_cmd = [
            sys.executable,
            str(script_dir / "check_canvas_safety.py"),
            "--image",
            str(outputs_dir / "render.png"),
            "--margin-px",
            str(int(canvas_config.get("margin_px", 5))),
            "--background",
            str(canvas_config.get("background", "#ffffff")),
            "--tolerance",
            str(int(canvas_config.get("tolerance", 10))),
            "--require-edges",
            ",".join(str(edge) for edge in required_edges),
            "--json-out",
            str(canvas_safety_json),
            "--project-root",
            str(bundle_root),
        ]
        canvas_safety = run(
            canvas_safety_cmd,
            log_path=logs_dir / "canvas_safety.log",
            timeout=DEFAULT_TIMEOUTS["canvas_safety"],
            bundle_root=bundle_root,
            env=env,
        )
        steps["canvas_safety"] = canvas_safety
        if canvas_safety["status"] == "failed":
            report["stage"] = "canvas_safety"
            report["failure_type"] = "required_canvas_margin_not_clear"
            write_json(bundle_root / "run_report.json", report)
            write_run_attestation(bundle_root, status="failed", steps=steps)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2
    else:
        steps["canvas_safety"] = {"status": "skipped", "reason": "qa_policy.canvas_safety not enabled"}

    plot_geometry_safety_json = qa_dir / "plot_geometry_safety.json"
    plot_geometry_config = plot_geometry_safety_config(work_spec)
    if plot_geometry_config:
        plot_geometry_safety = run(
            [
                sys.executable,
                str(script_dir / "check_plot_geometry_safety.py"),
                "--image",
                str(outputs_dir / "render.png"),
                "--spec",
                str(work_spec),
                "--json-out",
                str(plot_geometry_safety_json),
                "--project-root",
                str(bundle_root),
            ],
            log_path=logs_dir / "plot_geometry_safety.log",
            timeout=DEFAULT_TIMEOUTS["plot_geometry_safety"],
            bundle_root=bundle_root,
            env=env,
        )
        steps["plot_geometry_safety"] = plot_geometry_safety
        if plot_geometry_safety["status"] == "failed":
            report["stage"] = "plot_geometry_safety"
            report["failure_type"] = "plot_region_bbox_mismatch"
            write_json(bundle_root / "run_report.json", report)
            write_run_attestation(bundle_root, status="failed", steps=steps)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2
    else:
        steps["plot_geometry_safety"] = {"status": "skipped", "reason": "qa_policy.plot_geometry_safety not enabled"}

    boxed_text_safety_json = qa_dir / "boxed_text_safety.json"
    boxed_text_config = boxed_text_safety_config(work_spec)
    if boxed_text_config:
        boxed_text_safety = run(
            [
                sys.executable,
                str(script_dir / "check_boxed_text_safety.py"),
                "--image",
                str(outputs_dir / "render.png"),
                "--spec",
                str(work_spec),
                "--json-out",
                str(boxed_text_safety_json),
                "--project-root",
                str(bundle_root),
            ],
            log_path=logs_dir / "boxed_text_safety.log",
            timeout=DEFAULT_TIMEOUTS["boxed_text_safety"],
            bundle_root=bundle_root,
            env=env,
        )
        steps["boxed_text_safety"] = boxed_text_safety
        if boxed_text_safety["status"] == "failed":
            report["stage"] = "boxed_text_safety"
            report["failure_type"] = "boxed_text_ink_or_padding_failed"
            write_json(bundle_root / "run_report.json", report)
            write_run_attestation(bundle_root, status="failed", steps=steps)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2
    else:
        steps["boxed_text_safety"] = {"status": "skipped", "reason": "qa_policy.boxed_text_safety not enabled"}

    score_json = bundle_root / "visual_score.json"
    comparison_dir = bundle_root / "comparison"
    if bundled_source:
        score = run([sys.executable, str(script_dir / "score_visual.py"), "--source", str(bundled_source), "--actual", str(outputs_dir / "render.png"), "--json-out", str(score_json), "--comparison-dir", str(comparison_dir), "--spec", str(work_spec), "--project-root", str(bundle_root)], log_path=logs_dir / "score.log", timeout=DEFAULT_TIMEOUTS["score"], bundle_root=bundle_root, env=env)
        steps["score"] = score
        if score["status"] == "failed":
            write_json(bundle_root / "run_report.json", report)
            write_run_attestation(bundle_root, status="failed", steps=steps)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2
    else:
        steps["score"] = {"status": "skipped", "reason": "source image not provided"}

    panel_score_dir = qa_dir / "panels"
    if bundled_source:
        panel_score_dir.mkdir(parents=True, exist_ok=True)
        for crop in crop_panel_images(bundled_source, outputs_dir / "render.png", work_spec, qa_dir):
            panel_score = run([sys.executable, str(script_dir / "score_visual.py"), "--source", str(crop["source"]), "--actual", str(crop["actual"]), "--json-out", str(panel_score_dir / f"{crop['id']}.json"), "--project-root", str(bundle_root)], log_path=logs_dir / f"score_panel_{crop['id']}.log", timeout=DEFAULT_TIMEOUTS["score"], bundle_root=bundle_root, env=env)
            steps[f"score_panel_{crop['id']}"] = panel_score
            if panel_score["status"] == "failed":
                report["stage"] = f"score_panel_{crop['id']}"
                report["failure_type"] = "panel_score_failed"
                write_json(bundle_root / "run_report.json", report)
                write_run_attestation(bundle_root, status="failed", steps=steps)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 2

    semantic_audit_json = qa_dir / "semantic_audit.json"
    semantic_audit = run([sys.executable, str(script_dir / "audit_semantics.py"), "--spec", str(work_spec), "--semantics", str(outputs_dir / "render_semantics.json"), "--json-out", str(semantic_audit_json), "--project-root", str(bundle_root)], log_path=logs_dir / "semantic_audit.log", timeout=DEFAULT_TIMEOUTS["semantic_audit"], bundle_root=bundle_root, env=env)
    steps["semantic_audit"] = semantic_audit

    representation = "semantic_vector"
    try:
        spec = json.loads(work_spec.read_text(encoding="utf-8-sig"))
        representations = {panel.get("representation", "semantic_vector") for panel in spec.get("panels", [])}
        representation = representations.pop() if len(representations) == 1 else "mixed"
    except Exception:
        representation = "semantic_vector"
    vector_validation_json = qa_dir / "vector_validation.json"
    vector_validation = run([sys.executable, str(script_dir / "check_vector_output.py"), "--svg", str(outputs_dir / "render.svg"), "--pdf", str(outputs_dir / "render.pdf"), "--representation", representation, "--json-out", str(vector_validation_json), "--project-root", str(bundle_root)], log_path=logs_dir / "vector_validation.log", timeout=DEFAULT_TIMEOUTS["vector_validation"], bundle_root=bundle_root, env=env)
    steps["vector_validation"] = vector_validation

    final_manifest = bundle_root / "reproduction_manifest.json"
    checksums = bundle_root / "checksums.json"
    finalize_cmd = [
        sys.executable,
        str(script_dir / "finalize_manifest.py"),
        "--manifest",
        str(outputs_dir / "render_manifest.json"),
        "--script",
        str(bundle_root / "render.py"),
        "--spec",
        str(work_spec),
        "--runner",
        str(bundle_root / "reproduce.py"),
        "--project-root",
        str(bundle_root),
        "--out",
        str(final_manifest),
        "--qa-profile",
        qa_profile,
        "--semantic-audit",
        str(semantic_audit_json),
        "--vector-validation",
        str(vector_validation_json),
        "--panel-score-dir",
        str(panel_score_dir),
        "--checksums",
        str(checksums),
    ]
    if bundled_source:
        finalize_cmd.extend(["--source", str(bundled_source), "--score", str(score_json)])
    if canvas_config:
        finalize_cmd.extend(["--canvas-safety", str(canvas_safety_json)])
    if plot_geometry_config:
        finalize_cmd.extend(["--plot-geometry-safety", str(plot_geometry_safety_json)])
    if boxed_text_config:
        finalize_cmd.extend(["--boxed-text-safety", str(boxed_text_safety_json)])
    finalize = run(finalize_cmd, log_path=logs_dir / "finalize_manifest.log", timeout=DEFAULT_TIMEOUTS["finalize_manifest"], bundle_root=bundle_root, env=env)
    steps["finalize_manifest"] = finalize
    if command_renderer_config(bundle_root):
        cap_command_renderer_manifest(final_manifest)

    write_run_attestation(bundle_root, status="attested_before_checksums", steps=steps)
    sanitize_delivery_json(bundle_root)
    portability = run([sys.executable, str(script_dir / "validate_portability.py"), "--root", str(bundle_root), "--json-out", str(qa_dir / "portability_validation.json")], log_path=logs_dir / "validate_portability.log", timeout=DEFAULT_TIMEOUTS["validate_manifest"], bundle_root=bundle_root, env=env)
    steps["validate_portability"] = portability
    checksum_write = run([sys.executable, str(script_dir / "verify_checksums.py"), "--root", str(bundle_root), "--checksums", str(checksums), "--write"], log_path=logs_dir / "write_checksums.log", timeout=DEFAULT_TIMEOUTS["checksums"], bundle_root=bundle_root, env=env)
    steps["write_checksums"] = checksum_write
    checksum_verify = run([sys.executable, str(script_dir / "verify_checksums.py"), "--root", str(bundle_root), "--checksums", str(checksums), "--json-out", str(qa_dir / "checksum_verification.json")], log_path=logs_dir / "verify_checksums.log", timeout=DEFAULT_TIMEOUTS["checksums"], bundle_root=bundle_root, env=env)
    steps["verify_checksums"] = checksum_verify

    validation_cmd = [sys.executable, str(script_dir / "validate_manifest.py"), "--manifest", str(final_manifest), "--root", str(bundle_root)]
    if require_strict:
        validation_cmd.append("--require-strict")
    manifest_validation = run(validation_cmd, log_path=logs_dir / "validate_manifest.log", timeout=DEFAULT_TIMEOUTS["validate_manifest"], bundle_root=bundle_root, env=env)
    steps["validate_manifest"] = manifest_validation

    report["manifest"] = rel(final_manifest, bundle_root)
    required_steps = [finalize, checksum_write, checksum_verify, manifest_validation, portability]
    report["status"] = "ok" if all(step["status"] == "ok" for step in required_steps) else "incomplete"
    write_json(bundle_root / "run_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a prepared SciPlot figure bundle to completion.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--require-strict", action="store_true")
    parser.add_argument("--qa-profile", choices=["semantic", "visual", "trace"], default="semantic")
    args = parser.parse_args()
    return bundle_reproduce(args.bundle_root, require_strict=args.require_strict, qa_profile=args.qa_profile)


if __name__ == "__main__":
    raise SystemExit(main())
