from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import locale
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image

from bundle_lock import fixed_environment, write_bundle_lock
from environment_policy import REQUIRED_PACKAGES, write_environment_policy
from portable_paths import portable_command, portable_path


DEFAULT_TIMEOUTS = {
    "validate_visualspec": 30,
    "render": 120,
    "score": 60,
    "semantic_audit": 30,
    "vector_validation": 30,
    "finalize_manifest": 30,
    "validate_manifest": 30,
}

RUNTIME_FILES = [
    "capability_model.py",
    "capabilities.py",
    "data_resolver.py",
    "visualspec.py",
    "render_visualspec_matplotlib.py",
    "audit_semantics.py",
    "score_iteration.py",
    "score_visual.py",
    "validate_visualspec.py",
    "check_vector_output.py",
    "check_canvas_safety.py",
    "check_boxed_text_safety.py",
    "check_plot_geometry_safety.py",
    "finalize_manifest.py",
    "validate_manifest.py",
    "validate_reproduction_manifest.py",
    "check_environment.py",
    "environment_policy.py",
    "verify_checksums.py",
    "bundle_lock.py",
    "bundle_reproduce.py",
    "portable_paths.py",
    "validate_portability.py",
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def run(cmd: list[str], *, log_path: Path, timeout: int, bundle_root: Path) -> dict[str, object]:
    start = time.perf_counter()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mplconfig = Path(tempfile.mkdtemp(prefix="sfr-mplconfig-"))
        env = fixed_environment(os.environ, mplconfig=mplconfig)
        completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout, env=env)
        duration = time.perf_counter() - start
        log_path.write_text(
            "COMMAND\n" + json.dumps(cmd, ensure_ascii=False) + "\n\nSTDOUT\n" + completed.stdout + "\n\nSTDERR\n" + completed.stderr,
            encoding="utf-8",
        )
        return {
            "command": portable_command(cmd, bundle_root),
            "returncode": completed.returncode,
            "status": "ok" if completed.returncode == 0 else "failed",
            "duration_seconds": round(duration, 3),
            "log": portable_path(log_path, bundle_root),
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - start
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        log_path.write_text(
            "COMMAND\n" + json.dumps(cmd, ensure_ascii=False) + f"\n\nTIMEOUT after {timeout}s\n\nSTDOUT\n{stdout}\n\nSTDERR\n{stderr}",
            encoding="utf-8",
        )
        return {
            "command": portable_command(cmd, bundle_root),
            "returncode": None,
            "status": "failed",
            "failure_type": "timeout",
            "timeout_seconds": timeout,
            "duration_seconds": round(duration, 3),
            "log": portable_path(log_path, bundle_root),
        }


def _copy_input(src: Path, inputs_dir: Path, used: dict[str, Path]) -> str:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    candidate = inputs_dir / src.name
    if candidate.name in used and used[candidate.name].resolve() != src.resolve():
        candidate = inputs_dir / f"{src.stem}_{hashlib.sha1(str(src.resolve()).encode('utf-8')).hexdigest()[:8]}{src.suffix}"
    used[candidate.name] = src
    if src.resolve() != candidate.resolve():
        shutil.copyfile(src, candidate)
    return f"inputs/{candidate.name}"


def _resolve_source(value: str, base_dir: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def preflight_inputs(spec_path: Path, *, source: Path | None = None, report_root: Path | None = None) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    base_dir = spec_path.resolve().parent
    checks: list[dict[str, str]] = []
    if source is not None:
        checks.append({"path": str(source), "spec_location": "--source"})
    for panel_index, panel in enumerate(spec.get("panels", [])):
        if panel.get("source_crop"):
            checks.append({"path": str(_resolve_source(str(panel["source_crop"]), base_dir)), "spec_location": f"panels[{panel_index}].source_crop"})
        for plot_index, plot in enumerate(panel.get("plots", [])):
            data = plot.get("data")
            if isinstance(data, dict) and data.get("source"):
                checks.append({"path": str(_resolve_source(str(data["source"]), base_dir)), "spec_location": f"panels[{panel_index}].plots[{plot_index}].data.source"})
    for item in checks:
        if not Path(item["path"]).exists():
            if report_root is not None:
                item["path"] = portable_path(item["path"], report_root) or Path(item["path"]).name
            return {"status": "failed", "stage": "input_preflight", "failure_type": "missing_external_data", **item}
    if report_root is not None:
        checks = [{**item, "path": portable_path(item["path"], report_root) or Path(item["path"]).name} for item in checks]
    return {"status": "ok", "stage": "input_preflight", "checked": checks}


def prepare_visualspec_bundle(spec_path: Path, out_dir: Path, *, source: Path | None = None) -> dict[str, Any]:
    inputs_dir = out_dir / "inputs"
    used: dict[str, Path] = {}
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    base_dir = spec_path.resolve().parent
    source_copy = None
    if source:
        source_copy = _copy_input(source.resolve(), inputs_dir, used)
    for panel in spec.get("panels", []):
        if panel.get("source_crop"):
            panel_source = _resolve_source(str(panel["source_crop"]), base_dir)
            panel["source_crop"] = _copy_input(panel_source.resolve(), inputs_dir, used)
        for plot in panel.get("plots", []):
            data = plot.get("data")
            if isinstance(data, dict) and data.get("source"):
                data_source = _resolve_source(str(data["source"]), base_dir)
                data["source"] = _copy_input(data_source.resolve(), inputs_dir, used)
    work_spec = out_dir / "visualspec.json"
    write_json(work_spec, spec)
    return {"spec": work_spec, "source": out_dir / source_copy if source_copy else None}


def write_environment_files(out_dir: Path) -> None:
    env_dir = out_dir / "environment"
    env_dir.mkdir(parents=True, exist_ok=True)
    requirements = REQUIRED_PACKAGES
    (env_dir / "requirements.txt").write_text("\n".join(requirements) + "\n", encoding="utf-8")
    lock_lines: list[str] = []
    for package in requirements:
        try:
            lock_lines.append(f"{package}=={importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            lock_lines.append(f"{package}  # not installed")
    (env_dir / "requirements-lock.txt").write_text("\n".join(lock_lines) + "\n", encoding="utf-8")
    payload = {
        "schema": "scientificfigure.bundle_environment.v1",
        "python": sys.version,
        "python_implementation": platform.python_implementation().lower(),
        "python_version": platform.python_version(),
        "executable_role": "python",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "locale": locale.getlocale(),
        "timezone": time.tzname,
        "backend": "matplotlib_agg",
    }
    write_json(env_dir / "environment.json", payload)
    try:
        from matplotlib import font_manager, ft2font

        preferred = {"DejaVu Sans", "STIXGeneral", "Arial", "Liberation Sans"}
        font_records = []
        seen: set[tuple[str, str, str, str]] = set()
        for font in font_manager.fontManager.ttflist:
            if font.name not in preferred:
                continue
            path = Path(font.fname)
            key = (font.name, font.style, str(font.weight), path.name)
            if key in seen:
                continue
            seen.add(key)
            record = {
                "family": font.name,
                "style": font.style,
                "weight": str(font.weight),
                "filename": path.name,
            }
            if path.exists():
                record["sha256"] = sha256_file(path)
            font_records.append(record)
        fonts_payload = {
            "schema": "scientificfigure.fonts.v3",
            "freetype": getattr(ft2font, "__freetype_version__", None),
            "resolved_fonts": sorted(font_records, key=lambda item: (item["family"], item["filename"])),
        }
    except Exception:
        fonts_payload = {"schema": "scientificfigure.fonts.v3", "freetype": None, "resolved_fonts": []}
    write_json(env_dir / "fonts.json", fonts_payload)
    write_environment_policy(env_dir / "environment_policy.json", mode="exact")


COMPANION_SPECS = {
    "data_profile": ("advisor", "data_profile.json", "data-profile-v1.schema.json"),
    "figure_intent": ("advisor", "figure_intent.json", "figure-intent-v1.schema.json"),
    "chart_decision": ("advisor", "chart_decision.json", "chart-decision-v1.schema.json"),
    "policy_report": ("advisor", "policy_report.json", None),
    "style_profile": ("style", "resolved_style_profile.json", "style-profile-v1.schema.json"),
    "font_resolution": ("style", "font_resolution.json", "font-resolution-v1.schema.json"),
    "ai_review": ("qa", "ai_visual_review.json", "ai-visual-review-v1.schema.json"),
}


def prepare_companion_artifacts(project_root: Path, values: dict[str, Path | None]) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for key, (directory, filename, schema_name) in COMPANION_SPECS.items():
        source = values.get(key)
        if source is None:
            continue
        source = source.resolve()
        if not source.exists():
            raise FileNotFoundError(f"companion artifact does not exist: {source}")
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError(f"companion artifact must be a JSON object: {source}")
        if schema_name:
            try:
                import jsonschema
                schema_path = Path(__file__).resolve().parents[1] / "schemas" / schema_name
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                failures = sorted(jsonschema.Draft202012Validator(schema).iter_errors(payload), key=lambda item: list(item.absolute_path))
                if failures:
                    raise ValueError(f"invalid {key}: {failures[0].message}")
            except ImportError as exc:
                raise RuntimeError("jsonschema is required for companion artifact validation") from exc
        destination = project_root / directory / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != destination.resolve():
            shutil.copyfile(source, destination)
        artifacts[key] = {"path": rel(destination, project_root), "sha256": sha256_file(destination), "schema": str(payload.get("schema", schema_name or "unknown"))}
    if artifacts:
        write_json(project_root / "companion_artifacts.json", {"schema": "scientificfigure.companion_artifacts.v1", "artifacts": artifacts})
    return artifacts


def prepare_runtime(script_dir: Path, out_dir: Path, *, custom_renderer: Path | None = None) -> dict[str, Any]:
    package_dir = out_dir / "runtime" / "scientific_figure_reproduction"
    package_dir.mkdir(parents=True, exist_ok=True)
    for filename in RUNTIME_FILES:
        shutil.copyfile(script_dir / filename, package_dir / filename)
    schema_dir = out_dir / "runtime" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    source_schema_dir = script_dir.parent / "schemas"
    for schema_path in source_schema_dir.glob("*.json"):
        shutil.copyfile(schema_path, schema_dir / schema_path.name)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "render.py").write_text(
        """from __future__ import annotations

from pathlib import Path
from typing import Any

from .render_visualspec_matplotlib import render_file as _render_file


def render_file(spec_path: Path | str, output_dir: Path | str, script_path: Path | str | None = None) -> dict[str, Any]:
    return _render_file(spec_path, output_dir, script_path=script_path)
""",
        encoding="utf-8",
    )
    if custom_renderer:
        custom_target = out_dir / "runtime" / "custom_renderer.py"
        shutil.copyfile(custom_renderer, custom_target)
        return {
            "type": "command",
            "command": [
                "{python}",
                "{here}/runtime/custom_renderer.py",
                "--spec",
                "{spec}",
                "--out-dir",
                "{out_dir}",
                "--script",
                "{script}",
            ],
        }
    return {"type": "builtin", "name": "matplotlib_visualspec"}


def create_entrypoint(path: Path, *, renderer_config: dict[str, Any]) -> None:
    write_json(path.parent / "renderer_config.json", renderer_config)
    text = '''from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUTPUTS = HERE / "outputs"


def _render_builtin() -> int:
    sys.path.insert(0, str(HERE / "runtime"))
    from scientific_figure_reproduction.render import render_file

    render_file(HERE / "visualspec.json", OUTPUTS, script_path=Path(__file__).resolve())
    return 0


def _render_command(config: dict[str, object]) -> int:
    replacements = {
        "{python}": sys.executable,
        "{here}": str(HERE),
        "{spec}": str(HERE / "visualspec.json"),
        "{out_dir}": str(OUTPUTS),
        "{script}": str(Path(__file__).resolve()),
    }
    command = []
    for item in config["command"]:
        text = str(item)
        for old, new in replacements.items():
            text = text.replace(old, new)
        command.append(text)
    return subprocess.call(command)


def main() -> int:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    config = json.loads((HERE / "renderer_config.json").read_text(encoding="utf-8"))
    if config.get("type") == "builtin":
        return _render_builtin()
    if config.get("type") == "command":
        return _render_command(config)
    raise SystemExit(f"unsupported renderer config: {config}")


if __name__ == "__main__":
    raise SystemExit(main())
'''
    path.write_text(text, encoding="utf-8")


def create_bundle_entrypoints(root: Path, *, renderer_config: dict[str, Any], require_strict: bool, qa_profile: str) -> None:
    create_entrypoint(root / "render.py", renderer_config=renderer_config)
    strict_flag = ", \"--require-strict\"" if require_strict else ""
    (root / "reproduce.py").write_text(
        f'''from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

if __name__ == "__main__":
    raise SystemExit(subprocess.call([
        sys.executable,
        str(HERE / "runtime" / "scientific_figure_reproduction" / "bundle_reproduce.py"),
        "--bundle-root",
        str(HERE),
        "--qa-profile",
        "{qa_profile}"{strict_flag},
    ]))
''',
        encoding="utf-8",
    )
    (root / "verify.py").write_text(
        '''from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE / "runtime" / "scientific_figure_reproduction"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

def main() -> int:
    lock = subprocess.call([sys.executable, str(RUNTIME / "bundle_lock.py"), "--root", str(HERE), "--lock", str(HERE / "bundle.lock.json")])
    environment = subprocess.call([sys.executable, str(RUNTIME / "environment_policy.py"), "--policy", str(HERE / "environment" / "environment_policy.json")])
    checksum = subprocess.call([sys.executable, str(RUNTIME / "verify_checksums.py"), "--root", str(HERE), "--checksums", str(HERE / "checksums.json")])
    manifest = subprocess.call([sys.executable, str(RUNTIME / "validate_manifest.py"), "--manifest", str(HERE / "reproduction_manifest.json"), "--root", str(HERE)])
    portability = subprocess.call([sys.executable, str(RUNTIME / "validate_portability.py"), "--root", str(HERE)])
    return 0 if lock == 0 and environment == 0 and checksum == 0 and manifest == 0 and portability == 0 else 2

if __name__ == "__main__":
    raise SystemExit(main())
''',
        encoding="utf-8",
    )


def _panel_crop_box(bbox: list[float], width: int, height: int) -> tuple[int, int, int, int]:
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
        src_crop = src.crop(_panel_crop_box(bbox, src.width, src.height))
        act_crop = act.crop(_panel_crop_box(bbox, act.width, act.height))
        source_crop_path = crop_dir / f"{panel_id}_source.png"
        actual_crop_path = crop_dir / f"{panel_id}_render.png"
        src_crop.save(source_crop_path)
        act_crop.save(actual_crop_path)
        crops.append({"id": panel_id, "source": source_crop_path, "actual": actual_crop_path})
    return crops


def write_checksums(root: Path) -> Path:
    tracked: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "checksums.json":
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        tracked[rel(path, root)] = sha256_file(path)
    output = root / "checksums.json"
    write_json(output, {"schema": "scientificfigure.checksums.v1", "files": tracked})
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the scientific figure reproduction closure: bundle, validate, render, score, audit, finalize, validate manifest.")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--source", type=Path, help="Source image for visual QA.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--script", type=Path, help="Renderer command that accepts --spec/--out-dir/--script. It is copied into the bundle.")
    parser.add_argument("--qa-profile", choices=["semantic", "visual", "trace"], default="semantic")
    parser.add_argument("--require-strict", action="store_true")
    parser.add_argument("--data-profile", type=Path)
    parser.add_argument("--figure-intent", type=Path)
    parser.add_argument("--chart-decision", type=Path)
    parser.add_argument("--policy-report", type=Path)
    parser.add_argument("--style-profile", type=Path)
    parser.add_argument("--font-resolution", type=Path)
    parser.add_argument("--ai-review", type=Path)
    parser.add_argument("--project-root", type=Path, help="Deprecated in v2.2; out-dir is the portable project root.")
    args = parser.parse_args()
    if args.require_strict and args.source is None:
        parser.error("--require-strict requires --source because strict visual fidelity needs a reference image")

    script_dir = Path(__file__).resolve().parent
    project_root = args.out_dir.resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    logs_dir = project_root / "logs"

    report: dict[str, object] = {
        "schema": "scientificfigure.reproduction_run.v2",
        "status": "failed",
        "project_root": ".",
        "steps": {},
    }

    preflight = preflight_inputs(args.spec, source=args.source, report_root=project_root)
    report["steps"]["input_preflight"] = preflight
    if preflight["status"] == "failed":
        report.update({key: preflight[key] for key in ("stage", "failure_type", "path", "spec_location") if key in preflight})
        write_json(project_root / "run_report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    bundle = prepare_visualspec_bundle(args.spec, project_root, source=args.source)
    bundled_source = bundle["source"]
    write_json(project_root / "source_pointer.json", {"source": rel(bundled_source, project_root) if bundled_source else None})
    companion = prepare_companion_artifacts(project_root, {
        "data_profile": args.data_profile,
        "figure_intent": args.figure_intent,
        "chart_decision": args.chart_decision,
        "policy_report": args.policy_report,
        "style_profile": args.style_profile,
        "font_resolution": args.font_resolution,
        "ai_review": args.ai_review,
    })
    report["companion_artifacts"] = companion
    write_environment_files(project_root)
    renderer_config = prepare_runtime(script_dir, project_root, custom_renderer=args.script)
    create_bundle_entrypoints(project_root, renderer_config=renderer_config, require_strict=args.require_strict, qa_profile=args.qa_profile)
    write_bundle_lock(project_root, project_root / "bundle.lock.json")

    reproduce = run([sys.executable, str(project_root / "reproduce.py")], log_path=logs_dir / "reproduce.log", timeout=DEFAULT_TIMEOUTS["render"] + DEFAULT_TIMEOUTS["score"] + DEFAULT_TIMEOUTS["semantic_audit"] + DEFAULT_TIMEOUTS["vector_validation"] + DEFAULT_TIMEOUTS["finalize_manifest"], bundle_root=project_root)
    if reproduce["status"] == "failed":
        bundle_report = project_root / "run_report.json"
        if bundle_report.exists():
            print(bundle_report.read_text(encoding="utf-8"))
        else:
            report["steps"]["reproduce"] = reproduce
            write_json(bundle_report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    final_report = json.loads((project_root / "run_report.json").read_text(encoding="utf-8-sig"))
    final_report.setdefault("steps", {})["input_preflight"] = preflight
    final_report["steps"]["outer_reproduce"] = reproduce
    write_json(project_root / "run_report.json", final_report)
    print(json.dumps(final_report, ensure_ascii=False, indent=2))
    return 0 if final_report.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
