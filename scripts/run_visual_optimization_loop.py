from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from portable_paths import portable_command, portable_path


def run(cmd: list[str], *, project_root: Path, timeout: int = 120) -> dict[str, object]:
    try:
        completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
        return {
            "command": portable_command(cmd, project_root),
            "returncode": completed.returncode,
            "status": "ok" if completed.returncode == 0 else "failed",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": portable_command(cmd, project_root),
            "returncode": None,
            "status": "failed",
            "failure_type": "timeout",
            "timeout_seconds": timeout,
        }


def step_failed(record: dict[str, object]) -> bool:
    for key in ["accepted_render", "accepted_score", "patch", "apply_patch", "candidate_render", "candidate_score"]:
        value = record.get(key)
        if isinstance(value, dict) and value.get("status") == "failed":
            return True
    return "error" in record


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded v6 visual render/score/patch loop.")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--source", type=Path, help="Optional source image for scoring.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--max-iterations", type=int, default=1)
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    args.out_dir.mkdir(parents=True, exist_ok=True)
    accepted = args.out_dir / "accepted.visualspec.json"
    shutil.copyfile(args.spec, accepted)
    iterations: list[dict[str, object]] = []
    best_score: float | None = None
    no_improvement_count = 0
    fatal_failure = False
    for i in range(1, max(1, args.max_iterations) + 1):
        iter_dir = args.out_dir / f"iter_{i:02d}"
        iter_dir.mkdir(parents=True, exist_ok=True)
        accepted_before = iter_dir / "accepted_before.json"
        shutil.copyfile(accepted, accepted_before)
        accepted_render_dir = iter_dir / "accepted_render"
        render = run([sys.executable, str(script_dir / "render_visualspec_matplotlib.py"), "--spec", str(accepted), "--out-dir", str(accepted_render_dir)], project_root=args.out_dir)
        record: dict[str, object] = {"iteration": i, "accepted_before": portable_path(accepted_before, args.out_dir), "accepted_render": render}
        if render["status"] == "failed":
            record["decision"] = {"status": "stopped", "reason": "accepted_render_failed"}
            fatal_failure = True
            iterations.append(record)
            break
        if args.source and (accepted_render_dir / "render.png").exists():
            score_json = iter_dir / "accepted_score.json"
            score = run([sys.executable, str(script_dir / "score_iteration.py"), "--source", str(args.source), "--actual", str(accepted_render_dir / "render.png"), "--json-out", str(score_json), "--project-root", str(args.out_dir)], project_root=args.out_dir)
            record["accepted_score"] = score
            if score["status"] == "failed":
                record["decision"] = {"status": "stopped", "reason": "accepted_score_failed"}
                fatal_failure = True
                iterations.append(record)
                break
            try:
                payload = json.loads(score_json.read_text(encoding="utf-8"))
                current = float(payload.get("score_0_1", payload["mae_0_1"]))
                record["accepted_score_0_1"] = current
                if current == 0:
                    record["decision"] = {"status": "kept_accepted", "reason": "score_is_zero"}
                    iterations.append(record)
                    break
                if best_score is None or current < best_score:
                    best_score = current
                patch_json = iter_dir / "proposed_patch.json"
                patch = run([sys.executable, str(script_dir / "estimate_visual_patch.py"), "--spec", str(accepted), "--score", str(score_json), "--out", str(patch_json)], project_root=args.out_dir)
                record["patch"] = patch
                if patch["status"] == "failed":
                    record["decision"] = {"status": "stopped", "reason": "patch_generation_failed"}
                    fatal_failure = True
                    iterations.append(record)
                    break
                patch_payload = json.loads(patch_json.read_text(encoding="utf-8")) if patch_json.exists() else {}
                if patch_payload.get("status") != "proposed":
                    record["decision"] = {"status": "kept_accepted", "reason": "no_candidate_patch"}
                    iterations.append(record)
                    break
                else:
                    candidate = iter_dir / "candidate.json"
                    patch_report = iter_dir / "patch_report.json"
                    apply_patch = run([sys.executable, str(script_dir / "apply_visual_patch.py"), "--spec", str(accepted), "--patch", str(patch_json), "--out", str(candidate), "--report", str(patch_report)], project_root=args.out_dir)
                    record["apply_patch"] = apply_patch
                    if apply_patch["status"] == "failed":
                        record["decision"] = {"status": "stopped", "reason": "patch_application_failed"}
                        fatal_failure = True
                        iterations.append(record)
                        break
                    candidate_render_dir = iter_dir / "candidate_render"
                    candidate_render = run([sys.executable, str(script_dir / "render_visualspec_matplotlib.py"), "--spec", str(candidate), "--out-dir", str(candidate_render_dir)], project_root=args.out_dir)
                    record["candidate_render"] = candidate_render
                    if candidate_render["status"] == "failed":
                        record["decision"] = {"status": "stopped", "reason": "candidate_render_failed"}
                        fatal_failure = True
                        iterations.append(record)
                        break
                    candidate_score_json = iter_dir / "candidate_score.json"
                    candidate_score = run([sys.executable, str(script_dir / "score_iteration.py"), "--source", str(args.source), "--actual", str(candidate_render_dir / "render.png"), "--json-out", str(candidate_score_json), "--project-root", str(args.out_dir)], project_root=args.out_dir)
                    record["candidate_score"] = candidate_score
                    if candidate_score["status"] == "failed":
                        record["decision"] = {"status": "stopped", "reason": "candidate_score_failed"}
                        fatal_failure = True
                        iterations.append(record)
                        break
                    candidate_payload = json.loads(candidate_score_json.read_text(encoding="utf-8"))
                    candidate_value = float(candidate_payload.get("score_0_1", candidate_payload["mae_0_1"]))
                    record["candidate_score_0_1"] = candidate_value
                    if candidate_value < current:
                        shutil.copyfile(candidate, accepted)
                        best_score = candidate_value
                        no_improvement_count = 0
                        record["decision"] = {"status": "accepted_candidate", "reason": "score_improved"}
                    else:
                        no_improvement_count += 1
                        record["decision"] = {"status": "rolled_back_candidate", "reason": "score_not_improved"}
                        if candidate_value > current or no_improvement_count >= 2:
                            iterations.append(record)
                            break
            except Exception as exc:
                record["decision"] = {"status": "stopped", "reason": "score_or_patch_parse_failed"}
                record["error"] = str(exc)
                fatal_failure = True
        else:
            record["decision"] = {"status": "kept_accepted", "reason": "render_only"}
        iterations.append(record)
    manifest = {
        "schema": "scientificfigure.visual_optimization_loop.v2",
        "status": "failed" if fatal_failure or any(step_failed(item) for item in iterations) else "ok",
        "iterations": iterations,
        "best_score": best_score,
    }
    (args.out_dir / "visual_loop_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
