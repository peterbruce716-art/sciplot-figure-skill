from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from score_iteration import score_images


def _path(value: Any, root: Path, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty path string")
    path = Path(value)
    return path if path.is_absolute() else root / path


def _threshold_failure(score: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if thresholds.get("require_canvas_match", True) and not score["canvas_size_match"]:
        failures.append("canvas size differs from source")
    checks = (
        ("max_mae_0_1", "mae_0_1", "max"),
        ("max_rmse_0_1", "rmse_0_1", "max"),
        ("min_ssim_score", "ssim_score", "min"),
        ("min_edge_score", "edge_score", "min"),
        ("min_layout_score", "layout_score", "min"),
        ("min_color_score", "color_score", "min"),
    )
    for threshold_name, metric_name, direction in checks:
        if threshold_name not in thresholds:
            continue
        limit = float(thresholds[threshold_name])
        value = float(score[metric_name])
        failed = value > limit if direction == "max" else value < limit
        if failed:
            operator = ">" if direction == "max" else "<"
            failures.append(f"{metric_name}={value:.8f} {operator} {limit:.8f}")
    if "max_registration_shift_px" in thresholds:
        limit = float(thresholds["max_registration_shift_px"])
        shift = score.get("registration_shift")
        if not isinstance(shift, dict):
            failures.append("registration shift is unavailable")
        else:
            dx = abs(float(shift.get("dx_px", 0.0)))
            dy = abs(float(shift.get("dy_px", 0.0)))
            if max(dx, dy) > limit:
                failures.append(f"registration shift max({dx:.3f}, {dy:.3f}) > {limit:.3f} px")
    return failures


def score_batch(manifest_path: Path, out_dir: Path, *, project_root: Path | None = None) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema") != "scientificfigure.visual_batch.v1":
        raise ValueError("batch manifest schema must be scientificfigure.visual_batch.v1")
    records = manifest.get("figures")
    if not isinstance(records, list) or not records:
        raise ValueError("batch manifest figures must be a non-empty list")
    root = manifest_path.parent
    resolved_project_root = project_root.resolve() if project_root else None
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    batch_failures: list[str] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"figures[{index}] must be an object")
        figure_id = str(record.get("id", "")).strip()
        if not figure_id:
            raise ValueError(f"figures[{index}].id must be non-empty")
        if figure_id in seen:
            raise ValueError(f"duplicate figure id: {figure_id}")
        seen.add(figure_id)
        source = _path(record.get("source"), root, f"figures[{index}].source")
        actual = _path(record.get("actual"), root, f"figures[{index}].actual")
        missing = [str(path) for path in (source, actual) if not path.is_file()]
        if missing:
            failures = [f"missing file: {path}" for path in missing]
            results.append({"id": figure_id, "status": "failed", "failures": failures})
            batch_failures.extend(f"{figure_id}: {item}" for item in failures)
            continue
        comparison_dir = out_dir / figure_id
        score = score_images(source, actual, comparison_dir=comparison_dir, project_root=resolved_project_root)
        thresholds = record.get("thresholds") if isinstance(record.get("thresholds"), dict) else {}
        failures = _threshold_failure(score, thresholds)
        score_path = out_dir / f"{figure_id}.score.json"
        score_path.write_text(json.dumps(score, indent=2) + "\n", encoding="utf-8")
        results.append(
            {
                "id": figure_id,
                "status": "pass" if not failures else "failed",
                "failures": failures,
                "thresholds": thresholds,
                "score_report": score_path.relative_to(out_dir).as_posix(),
                "metrics": {key: score[key] for key in ("mae_0_1", "rmse_0_1", "ssim_score", "edge_score", "layout_score", "color_score")},
            }
        )
        batch_failures.extend(f"{figure_id}: {item}" for item in failures)
    return {
        "schema": "scientificfigure.visual_batch_report.v1",
        "status": "pass" if not batch_failures and len(results) == len(records) else "failed",
        "expected_figure_count": len(records),
        "evaluated_figure_count": len(results),
        "failures": batch_failures,
        "figures": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed visual QA for a declared figure batch.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    try:
        report = score_batch(args.manifest, args.out_dir, project_root=args.project_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"schema": "scientificfigure.visual_batch_report.v1", "status": "failed", "failures": [str(exc)], "figures": []}
    payload = json.dumps(report, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
