from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image

from advisor_common import load_json, sha256_file, validate_payload, write_json


REVIEW_SCOPE = [
    "scientific_question_clarity", "claim_evidence_alignment", "panel_role_clarity",
    "statistical_transparency", "negative_result_honesty", "visual_hierarchy",
    "legend_annotation_clarity", "journal_width_readability",
    "legend_overlap", "annotation_overlap", "panel_label_alignment",
    "color_discriminability", "panel_consistency", "title_redundancy", "crowding",
    "information_density", "visual_balance",
]


def _gate(*reports: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    evidence: dict[str, Any] = {}
    status = "pass"
    for report in reports:
        if not report:
            continue
        name = str(report.get("schema", "report")).split(".")[-1]
        evidence[name] = {key: report[key] for key in ["status", "overall", "result"] if key in report}
        if report.get("status") in {"failed", "fail", "not_strict"} or report.get("overall") in {"failed", "fail"}:
            status = "failed"
        elif status == "pass" and report.get("status") in {"warning", "pass_with_warnings", "near_pass"}:
            status = "warning"
    return status, evidence


def prepare_review(
    image: Path,
    *,
    visualspec: Path | None = None,
    deterministic: Path | None = None,
    semantic: Path | None = None,
    font: Path | None = None,
) -> dict[str, Any]:
    with Image.open(image) as preview:
        width, height = preview.size
    reports = [load_json(path) for path in [deterministic, semantic, font] if path and path.exists()]
    gate, evidence = _gate(*reports)
    payload = {
        "schema": "scientificfigure.ai_visual_review.v1",
        "schema_version": "1.0",
        "status": "pending_advisory",
        "image": {"path": image.name, "sha256": sha256_file(image), "width_px": int(width), "height_px": int(height)},
        "visualspec": visualspec.name if visualspec else None,
        "evidence": evidence,
        "deterministic_gate": gate,
        "review_scope": REVIEW_SCOPE,
        "issues": [],
        "overall_readability": "pending",
        "requires_deterministic_rerun": False,
        "constraints": [
            "This is an advisory input/output contract; it does not modify the image.",
            "Deterministic, semantic, vector, font, and policy QA remain the primary gates.",
            "Any accepted suggestion requires a full deterministic rerun.",
        ],
    }
    validate_payload(payload, "ai-visual-review-v1.schema.json")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an offline, structured visual-review request; no model or network call is made.")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--visualspec", type=Path)
    parser.add_argument("--deterministic-report", type=Path)
    parser.add_argument("--semantic-report", type=Path)
    parser.add_argument("--font-report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = prepare_review(args.image, visualspec=args.visualspec, deterministic=args.deterministic_report, semantic=args.semantic_report, font=args.font_report)
        write_json(args.output, payload)
    except Exception as exc:
        parser.exit(2, f"prepare_ai_visual_review: {exc}\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
