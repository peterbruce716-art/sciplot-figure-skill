"""Measure old audit and profile-aware line-plot workflows on one local fixture."""

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

from execution_profiles import get_profile


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SPEC = ROOT / "examples" / "line_plot" / "visualspec_v2.json"


def count_command_steps(value: Any) -> int:
    if isinstance(value, dict):
        own = 1 if isinstance(value.get("command"), (list, dict)) else 0
        return own + sum(count_command_steps(item) for item in value.values())
    if isinstance(value, list):
        return sum(count_command_steps(item) for item in value)
    return 0


def count_render_steps(value: Any) -> int:
    if isinstance(value, dict):
        command = value.get("command")
        if isinstance(command, dict):
            script = str(command.get("script") or "")
        elif isinstance(command, list):
            script = str(command[1]) if len(command) > 1 else ""
        else:
            script = ""
        name = Path(script).name.lower()
        own = 1 if name == "render.py" or name.startswith("render_") else 0
        return own + sum(count_render_steps(item) for item in value.values())
    if isinstance(value, list):
        return sum(count_render_steps(item) for item in value)
    return 0


def reduction_percent(baseline: int, current: int) -> float | None:
    if baseline == 0:
        return None
    return round((baseline - current) / baseline * 100, 1)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["MPLBACKEND"] = "Agg"
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "1"
    return env


def _run(command: list[str]) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, env=_env(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=1200)
    elapsed = round(time.perf_counter() - started, 3)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr[-4000:]}")
    try:
        return json.loads(completed.stdout), elapsed
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"command did not emit JSON: {' '.join(command)}\n{completed.stdout[-4000:]}") from exc


def _file_count(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file())


def _profile_case(profile: str, root: Path) -> dict[str, Any]:
    output = root / profile
    result, elapsed = _run([sys.executable, str(SCRIPTS / "sciplot.py"), "run", "--spec", str(SPEC), "--profile", profile, "--out-dir", str(output), "--json"])
    performance = result.get("performance", {})
    plan_path = output / "execution_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else {}
    audit_report_path = output / "run_report.json"
    audit_report = json.loads(audit_report_path.read_text(encoding="utf-8-sig")) if audit_report_path.is_file() else {}
    recorded_subprocesses = count_command_steps(audit_report) if audit_report else performance.get("subprocess_count", 0)
    recorded_renders = count_render_steps(audit_report) if audit_report else performance.get("render_count", 1)
    return {
        "status": result.get("status"),
        "subprocess_count": recorded_subprocesses,
        "render_count": recorded_renders,
        "created_file_count": _file_count(output),
        "enabled_gate_count": performance.get("enabled_gate_count", len(plan.get("enabled_gates", []))),
        "duration_seconds": elapsed,
    }


def build_benchmark() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sciplot-benchmark-") as temp:
        workspace = Path(temp)
        legacy_dir = workspace / "legacy"
        legacy, legacy_elapsed = _run([sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(SPEC), "--out-dir", str(legacy_dir)])
        legacy_report = json.loads((legacy_dir / "run_report.json").read_text(encoding="utf-8-sig"))
        baseline = {
            "workflow": "v2.9.3 run_reproduction",
            "status": legacy.get("status"),
            "subprocess_count": count_command_steps(legacy_report),
            "render_count": count_render_steps(legacy_report),
            "created_file_count": _file_count(legacy_dir),
            "enabled_gate_count": len(get_profile("audit").required_gates),
            "duration_seconds": legacy_elapsed,
        }
        profiles = {profile: _profile_case(profile, workspace) for profile in ("quick", "standard", "audit")}
    return {
        "schema": "sciplot.workflow-profile-benchmark.v1",
        "fixture": str(SPEC.relative_to(ROOT)).replace("\\", "/"),
        "baseline": baseline,
        "profiles": profiles,
        "reductions_vs_baseline": {
            profile: {
                "subprocess_percent": reduction_percent(baseline["subprocess_count"], data["subprocess_count"]),
                "render_percent": reduction_percent(baseline["render_count"], data["render_count"]),
                "file_percent": reduction_percent(baseline["created_file_count"], data["created_file_count"]),
                "gate_percent": reduction_percent(baseline["enabled_gate_count"], data["enabled_gate_count"]),
            }
            for profile, data in profiles.items()
        },
        "reductions_quick_vs_standard": {
            "file_percent": reduction_percent(profiles["standard"]["created_file_count"], profiles["quick"]["created_file_count"]),
            "gate_percent": reduction_percent(profiles["standard"]["enabled_gate_count"], profiles["quick"]["enabled_gate_count"]),
        },
        "limitations": [
            "Legacy command counts are derived from its recorded nested command steps; profile subprocess counts are internal child-process counts.",
            "The old full workflow is classified with the same audit gate taxonomy used by the new planner; subprocess steps remain a separate measured metric.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark SciPlot workflow profiles.")
    parser.add_argument("--json-out", type=Path, default=ROOT / "outputs" / "workflow_profile_benchmark.json")
    args = parser.parse_args()
    report = build_benchmark()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
