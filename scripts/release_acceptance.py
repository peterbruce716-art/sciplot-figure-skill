from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fixed_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["MPLBACKEND"] = "Agg"
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "1"
    return env


def run_step(name: str, cmd: list[str], *, timeout: int = 180) -> dict[str, Any]:
    completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout, env=fixed_env())
    return {
        "name": name,
        "status": "pass" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release acceptance for sciplot-figure-skill.")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    version_path = ROOT / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else "2.5.1"
    checks: dict[str, str] = {}
    details: dict[str, Any] = {}

    with tempfile.TemporaryDirectory(prefix="sfr-release-") as tmp:
        workspace = Path(tmp)
        zip_path = workspace / "sciplot-figure-skill.zip"
        baseline = workspace / "baseline"
        bundle = workspace / "bundle"
        spec = ROOT / "examples" / "line_plot" / "visualspec_v2.json"

        steps = [
            ("root_package", [sys.executable, str(SCRIPTS / "validate_skill_package.py"), "--root", str(ROOT)]),
            ("version_consistency", [sys.executable, str(SCRIPTS / "check_version_consistency.py"), "--root", str(ROOT), "--expected", version]),
            ("execution_profiles", [sys.executable, "-m", "unittest", "discover", "-s", str(SCRIPTS / "tests"), "-p", "test_execution_profiles.py"]),
            ("unified_cli", [sys.executable, "-m", "unittest", "discover", "-s", str(SCRIPTS / "tests"), "-p", "test_sciplot_cli.py"]),
            ("data_swap_hardening", [sys.executable, "-m", "unittest", "discover", "-s", str(SCRIPTS / "tests"), "-p", "test_data_swap_template.py"]),
            ("build_zip", [sys.executable, str(SCRIPTS / "build_skill_package.py"), "--root", str(ROOT), "--out", str(zip_path)]),
            ("zip_package", [sys.executable, str(SCRIPTS / "validate_skill_package.py"), "--root", str(ROOT), "--zip", str(zip_path)]),
            ("render_baseline", [sys.executable, str(SCRIPTS / "render_matplotlib.py"), "--spec", str(spec), "--out-dir", str(baseline)]),
            ("run_reproduction", [sys.executable, str(SCRIPTS / "run_reproduction.py"), "--spec", str(spec), "--source", str(baseline / "render.png"), "--out-dir", str(bundle), "--require-strict"]),
            ("bundle_verify", [sys.executable, str(bundle / "verify.py")]),
            ("portability", [sys.executable, str(SCRIPTS / "validate_portability.py"), "--root", str(bundle)]),
        ]
        for name, cmd in steps:
            result = run_step(name, cmd, timeout=240)
            details[name] = result
            checks[name] = result["status"]
            if result["status"] != "pass":
                break

        manifest_path = bundle / "reproduction_manifest.json"
        if manifest_path.exists():
            manifest = load_json(manifest_path)
            checks["official_example"] = str(manifest.get("status"))
        else:
            checks["official_example"] = "missing_manifest"

    status = "pass" if all(value in {"pass", "semantic_strict_pass"} for value in checks.values()) and checks.get("official_example") == "semantic_strict_pass" else "failed"
    report = {
        "schema": "scientificfigure.release_acceptance.v1",
        "version": version,
        "status": status,
        "checks": checks,
        "details": details,
    }
    output = args.json_out or ROOT / "release_acceptance.json"
    write_json(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
