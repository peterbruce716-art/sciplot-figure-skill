"""Run five privacy-safe synthetic figures through the real SciPlot CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_cases(*, polished: bool = False) -> dict[str, dict[str, Any]]:
    horizontal = np.linspace(0, 4, 41)
    response = 1 + 2 * (1 - np.exp(-horizontal))
    grid = np.linspace(-2, 2, 25)
    mesh_x, mesh_y = np.meshgrid(grid, grid)
    definitions = {
        "01_line": ([
            {"type": "line", "label": "Condition A", "data": {"x": horizontal.tolist(), "y": response.tolist()}, "style": {"color": "#0072B2", "line_width_pt": 1.6}},
            {"type": "line", "label": "Condition B", "data": {"x": horizontal.tolist(), "y": (response * 0.75).tolist()}, "style": {"color": "#D55E00", "line_style": "dashed", "line_width_pt": 1.6}},
        ], [0, 4], [0, 3.5], "Time (a.u.)", "Response (a.u.)"),
        "02_scatter": ([
            {"type": "scatter", "label": "Synthetic points", "data": {"x": horizontal[::2].tolist(), "y": (response[::2] + 0.12 * np.sin(horizontal[::2] * 8)).tolist()}, "style": {"color": "#009E73", "marker_size_pt2": 22, "alpha": 0.85}},
        ], [-0.2, 4.2], [0, 3.5], "Input (a.u.)", "Response (a.u.)"),
        "03_uncertainty": ([
            {"type": "fill_between", "data": {"x": horizontal.tolist(), "y1": (response - 0.2).tolist(), "y2": (response + 0.2).tolist()}, "style": {"color": "#0072B2", "alpha": 0.18}},
            {"type": "errorbar", "label": "Synthetic mean +/- SD", "data": {"x": horizontal[::5].tolist(), "y": response[::5].tolist(), "yerr": [0.2] * 9, "uncertainty": {"source": "explicit", "semantics": "standard deviation"}}, "style": {"color": "#0072B2", "marker": "o", "capsize": 3}},
        ], [-0.2, 4.2], [0, 3.7], "Time (a.u.)", "Response (a.u.)"),
        "04_grouped_bar": ([
            {"type": "grouped_bar", "data": {"x": [0, 1, 2, 3], "groups": [{"label": "Condition A", "y": [1.2, 2.1, 2.6, 3.0], "color": "#0072B2"}, {"label": "Condition B", "y": [1.0, 1.7, 2.2, 2.5], "color": "#E69F00"}]}, "style": {"bar_width": 0.32}},
        ], [-0.6, 3.6], [0, 3.8], "Group index", "Response (a.u.)"),
        "05_contour": ([
            {"type": "contour", "colorbar": True, "data": {"x": grid.tolist(), "y": grid.tolist(), "z": np.exp(-(mesh_x ** 2 + mesh_y ** 2)).tolist()}, "style": {"levels": 10, "cmap": "viridis"}},
        ], [-2, 2], [-2, 2], "Position X (a.u.)", "Position Y (a.u.)"),
    }
    cases = {}
    for index, (name, definition) in enumerate(definitions.items()):
        plots, x_limits, y_limits, x_label, y_label = definition
        cases[name] = {
            "schema": "scientificfigure.visualspec.v2",
            "figure": {"size_mm": [120, 85], "dpi": 220, "crop_mode": "fixed_canvas", "background": "white"},
            "theme": {"font": {"family_candidates": ["DejaVu Sans"], "size_pt": 9}},
            "panels": [{
                "id": "A", "bbox_normalized": [0.16, 0.19, 0.78, 0.72],
                "source_strategy": "raw_data", "representation": "semantic_vector",
                "axes": {"x": {"limits": x_limits, "label": x_label}, "y": {"limits": y_limits, "label": y_label}},
                "plots": plots, "legend": {"visible": name != "05_contour", "loc": "lower right", "font_size_pt": 8},
                "annotations": [{"type": "text", "coordinate_space": "axes_fraction", "coordinates": [0.025, 0.97], "text": f"({chr(97 + index)})", "style": {"ha": "left", "va": "top", "font_size_pt": 11}}],
            }],
        }
    if polished:
        bar_panel = cases["04_grouped_bar"]["panels"][0]
        bar_panel["legend"].update({"loc": "upper left", "bbox_to_anchor": [0.07, 0.98]})
        bar_panel["axes"]["x"]["ticks"] = [0, 1, 2, 3]
        cases["05_contour"]["panels"][0]["annotations"][0]["style"]["color"] = "white"
    return cases


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}


def project_evidence(project: Path, profile: str) -> tuple[dict[str, Path], dict[str, Any]]:
    if profile == "audit":
        manifest = load_json(project / "reproduction_manifest.json")
        semantic = load_json(project / "qa" / "semantic_audit.json")
        vector = load_json(project / "qa" / "vector_validation.json")
        status = "pass" if manifest.get("overall_status") == "pass" else "fail"
        directory, stem = "outputs", "render"
    else:
        report = load_json(project / "qa" / "report.json")
        semantic = report.get("semantic_audit", {})
        vector = report.get("vector_validation", {})
        status = report.get("status", "fail")
        directory, stem = "output", "figure"
    paths = {extension: project / directory / f"{stem}.{extension}" for extension in ("png", "svg", "pdf")}
    return paths, {"status": status, "semantic_status": semantic.get("overall"), "vector_status": vector.get("status")}


def case_passes(returncode: int, result: dict[str, Any], evidence: dict[str, Any], outputs: dict[str, Any], validated: bool) -> bool:
    return (
        returncode == 0
        and result.get("status") in {"ok", "pass"}
        and all(evidence.get(key) == "pass" for key in ("status", "semantic_status", "vector_status"))
        and set(outputs) == {"png", "svg", "pdf"}
        and validated
    )


def run_benchmark(root: Path, profile: str, compare: Path | None = None, *, polished: bool = False) -> dict[str, Any]:
    root = root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("Benchmark output must be new or empty; existing evidence is never overwritten")
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    thumbnails = []
    environment = dict(os.environ, MPLBACKEND="Agg", PYTHONIOENCODING="utf-8")
    for name, spec in build_cases(polished=polished).items():
        spec_path = root / "inputs" / f"{name}.json"
        write_json(spec_path, spec)
        project = root / name
        command = [sys.executable, str(ROOT / "scripts" / "sciplot.py"), "run", "--spec", str(spec_path), "--profile", profile, "--outputs", "png,svg,pdf", "--out-dir", str(project), "--json"]
        started = time.perf_counter()
        try:
            completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=environment, timeout=360)
            stdout, stderr, returncode = completed.stdout, completed.stderr, completed.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, returncode = str(exc.stdout or ""), str(exc.stderr or ""), -1
        elapsed = time.perf_counter() - started
        logs = root / "logs"
        logs.mkdir(exist_ok=True)
        (logs / f"{name}.stdout.txt").write_text(stdout, encoding="utf-8")
        (logs / f"{name}.stderr.txt").write_text(stderr, encoding="utf-8")
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            result = {"status": "fail", "reason": "CLI did not emit valid JSON"}
        paths, evidence = project_evidence(project, profile)
        outputs = {}
        for extension, artifact in paths.items():
            if artifact.is_file():
                outputs[extension] = {"path": artifact.relative_to(root).as_posix(), "bytes": artifact.stat().st_size, "sha256": sha256(artifact)}
        validation_command = [sys.executable, str(ROOT / "scripts" / "sciplot.py"), "validate", "--project", str(project), "--profile", profile, "--json"]
        validation_started = time.perf_counter()
        try:
            validation = subprocess.run(validation_command, capture_output=True, text=True, encoding="utf-8", env=environment, timeout=180)
            (logs / f"{name}.validation.stdout.txt").write_text(validation.stdout, encoding="utf-8")
            (logs / f"{name}.validation.stderr.txt").write_text(validation.stderr, encoding="utf-8")
            validation_result = json.loads(validation.stdout)
            validated = validation.returncode == 0 and validation_result.get("status") in {"pass", "ok"}
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            validation_result = {"status": "fail", "error": str(exc)}
            validated = False
        validation_elapsed = time.perf_counter() - validation_started
        passed = case_passes(returncode, result, evidence, outputs, validated)
        row = {"name": name, "status": "pass" if passed else "fail", "returncode": returncode, "duration_seconds": round(elapsed, 3), "validation_seconds": round(validation_elapsed, 3), "validation_command": validation_command, "validation": validation_result, "command": command, "input_sha256": sha256(spec_path), "result": result, "qa_status": evidence["status"], "semantic_status": evidence["semantic_status"], "vector_status": evidence["vector_status"], "outputs": outputs}
        if "png" in outputs:
            image_path = root / outputs["png"]["path"]
            with Image.open(image_path) as image:
                row["canvas_px"] = list(image.size)
                thumbnail = image.convert("RGB")
                thumbnail.thumbnail((520, 370))
                thumbnails.append((name, thumbnail))
            if compare:
                previous = load_json(compare / "benchmark.json")
                prior = next((entry for entry in previous.get("figures", []) if entry["name"] == name), {})
                prior_image = prior.get("outputs", {}).get("png", {})
                prior_spec = load_json(compare / "inputs" / f"{name}.json")
                row["comparison"] = {"input_identical": prior.get("input_sha256") == row["input_sha256"], "plot_data_identical": [panel.get("plots") for panel in prior_spec.get("panels", [])] == [panel.get("plots") for panel in spec["panels"]], "png_identical": prior_image.get("sha256") == outputs["png"]["sha256"]}
        rows.append(row)
        print(f"{name}: {row['status']} ({elapsed:.2f}s)", file=sys.stderr, flush=True)
    sheet = Image.new("RGB", (1040, 1200), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (name, thumbnail) in enumerate(thumbnails):
        left, top = (index % 2) * 520, (index // 2) * 400
        draw.text((left + 12, top + 6), name, fill="black")
        sheet.paste(thumbnail, (left, top + 25))
    sheet.save(root / "contact_sheet.png")
    report = {"schema": "sciplot.five-figure-benchmark.v1", "profile": profile, "presentation": "reviewed" if polished else "baseline", "status": "pass" if all(row["status"] == "pass" for row in rows) else "fail", "passed": sum(row["status"] == "pass" for row in rows), "total": len(rows), "duration_seconds": round(sum(row["duration_seconds"] for row in rows), 3), "validation_seconds": round(sum(row["validation_seconds"] for row in rows), 3), "skill_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(), "skill_root": str(ROOT), "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__}, "limitations": ["Deterministic synthetic engineering fixtures, not experimental measurements or paper reproduction.", "PNG identity measures repeatability, not similarity to an independent published reference.", "Standard runs do not prove portable audit bundles; select audit and independently verify bundles for that claim."], "figures": rows}
    write_json(root / "benchmark.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=("standard", "audit"), default="standard")
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--polished", action="store_true", help="Improve bar legend placement and contour label contrast without changing any plot data.")
    args = parser.parse_args()
    report = run_benchmark(args.out_dir, args.profile, args.compare, polished=args.polished)
    print(json.dumps({key: value for key, value in report.items() if key != "figures"}, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
