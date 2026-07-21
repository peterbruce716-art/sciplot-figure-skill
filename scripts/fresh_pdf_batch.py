from __future__ import annotations

"""Fresh, source-bound PDF trace batch for a declared figure set."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pdf_vector_trace import trace_pdf_clip
from score_batch import score_batch


# Backward-compatible injection point for callers that import the module.
# Installed skills must not ship paper-specific figure declarations.
FIGURE_CLIPS: dict[str, dict[str, Any]] = {}
FORBIDDEN_PATH_TOKENS = (
    "validated_reuse",
    "validated_crop_reextract",
    "old_data",
    "five_figure_fresh_20260719",
    "five_figure_redo_20260719",
)

PER_FIGURE_SCRIPT_TEMPLATE = '''from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


TRACE_SCRIPT = Path({trace_script!r})
SOURCE_PDF = Path({source_pdf!r})
SOURCE_SHA256 = {source_sha256!r}
PAGE = {page}
CLIP_PDF_POINTS = {clip!r}
DPI = {dpi}
FIGURE_ID = {figure_id!r}
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reruns" / ("fig" + FIGURE_ID)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not SOURCE_PDF.is_file():
        raise FileNotFoundError(f"source PDF not found: {{SOURCE_PDF}}")
    actual_sha256 = _sha256(SOURCE_PDF)
    if actual_sha256 != SOURCE_SHA256:
        raise RuntimeError(
            "source PDF SHA-256 mismatch; refusing to consume a different or stale input"
        )
    sys.path.insert(0, str(TRACE_SCRIPT.parent))
    from pdf_vector_trace import trace_pdf_clip

    manifest = trace_pdf_clip(
        SOURCE_PDF,
        PAGE,
        tuple(float(value) for value in CLIP_PDF_POINTS),
        OUT_DIR,
        "fig" + FIGURE_ID,
        dpi=DPI,
    )
    manifest.update(
        {{
            "figure_id": FIGURE_ID,
            "source_pdf_sha256": actual_sha256,
            "historical_data_consumed": False,
            "per_figure_script": str(Path(__file__).relative_to(ROOT).as_posix()),
        }}
    )
    manifest_path = OUT_DIR / ("fig" + FIGURE_ID + "_per_figure_trace_manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "visual_trace_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
'''


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_anchored_figure_caption(text: str, figure_id: str) -> bool:
    """Match a figure caption, not an in-text reference to that figure."""

    escaped = re.escape(str(figure_id))
    return re.match(rf"^\s*Fig(?:ure)?\.?\s*{escaped}\s*\.", text, re.IGNORECASE) is not None


def select_anchored_caption_block(blocks: list[Any], figure_id: str) -> Any | None:
    """Return the first block whose text starts with the requested caption."""

    for block in blocks:
        if isinstance(block, dict):
            text = block.get("text", "")
        elif isinstance(block, (list, tuple)) and len(block) >= 5:
            text = block[4]
        else:
            continue
        if isinstance(text, str) and is_anchored_figure_caption(" ".join(text.split()), figure_id):
            return block
    return None


def _normalize_figure_clips(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("E127_FIGURE_CLIPS_REQUIRED: declare at least one figure clip")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_id, record in raw.items():
        figure_id = str(raw_id).strip()
        if not figure_id or not isinstance(record, dict):
            raise ValueError("E128_INVALID_FIGURE_CLIP: figure id and object record are required")
        try:
            page = int(record["page"])
            clip = [float(value) for value in record["clip_pdf_points"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"E128_INVALID_FIGURE_CLIP: {figure_id}") from exc
        if page < 1 or len(clip) != 4 or not (0 <= clip[0] < clip[2] and 0 <= clip[1] < clip[3]):
            raise ValueError(f"E128_INVALID_FIGURE_CLIP: {figure_id}")
        normalized[figure_id] = {"page": page, "clip_pdf_points": clip}
    return normalized


def load_clip_manifest(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != "scientificfigure.pdf-clip-manifest.v1":
        raise ValueError("E129_INVALID_CLIP_MANIFEST: schema scientificfigure.pdf-clip-manifest.v1 required")
    return _normalize_figure_clips(payload.get("figures"))


def parse_figure_clip(value: str) -> tuple[str, dict[str, Any]]:
    try:
        figure_id, page_text, clip_text = value.split(":", 2)
        record = {
            "page": int(page_text),
            "clip_pdf_points": [float(part.strip()) for part in clip_text.split(",")],
        }
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("figure clip must be ID:PAGE:X0,Y0,X1,Y1") from exc
    normalized = _normalize_figure_clips({figure_id: record})
    return figure_id, normalized[figure_id]


def _ensure_fresh_output(out_dir: Path) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError("E126_FRESH_OUTPUT_NOT_EMPTY: output directory must be new or empty")
    out_dir.mkdir(parents=True, exist_ok=True)


def _validate_pdf_clips(pdf: Path, figure_clips: dict[str, dict[str, Any]]) -> None:
    """Fail closed when declared page/clip geometry cannot exist in the source PDF."""

    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("E130_PDF_VALIDATION_UNAVAILABLE: PyMuPDF is required to validate PDF clips") from exc
    document = fitz.open(pdf)
    try:
        for figure_id, config in figure_clips.items():
            page_number = int(config["page"])
            if page_number < 1 or page_number > document.page_count:
                raise ValueError(
                    f"E130_PAGE_OUT_OF_RANGE: figure {figure_id} declares page {page_number}, "
                    f"but the PDF has {document.page_count} pages"
                )
            page = document[page_number - 1]
            x0, y0, x1, y1 = (float(value) for value in config["clip_pdf_points"])
            width, height = float(page.rect.width), float(page.rect.height)
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
                raise ValueError(
                    f"E131_CLIP_OUT_OF_PAGE: figure {figure_id} clip "
                    f"[{x0}, {y0}, {x1}, {y1}] exceeds page {page_number} bounds [0, 0, {width}, {height}]"
                )
    finally:
        document.close()


def _write_per_figure_script(
    out_dir: Path,
    figure_id: str,
    config: dict[str, Any],
    *,
    source_pdf: Path,
    source_sha256: str,
    dpi: int,
) -> Path:
    script_path = out_dir / "scripts" / f"fig{figure_id}_trace.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        PER_FIGURE_SCRIPT_TEMPLATE.format(
            trace_script=str((SCRIPT_DIR / "pdf_vector_trace.py").resolve()),
            source_pdf=str(source_pdf),
            source_sha256=source_sha256,
            page=int(config["page"]),
            clip=tuple(float(value) for value in config["clip_pdf_points"]),
            dpi=dpi,
            figure_id=figure_id,
        ),
        encoding="utf-8",
        newline="\n",
    )
    return script_path


def _write_trace_rerun_manifest(
    out_dir: Path,
    *,
    pdf: Path,
    pdf_hash: str,
    figures: list[str],
    results: dict[str, dict[str, Any]],
    per_figure_scripts: dict[str, str],
    figure_clips: dict[str, dict[str, Any]],
    dpi: int,
) -> Path:
    """Write a portable rerun contract for pixel-trace batches.

    A PDF trace is intentionally not advertised as a data-swap template: it
    remains bound to the source PDF and its clip geometry.  This contract
    captures the immutable source identity and the exact per-figure entry
    points needed to reproduce the trace without consuming historical output.
    """
    payload = {
        "schema": "sciplot.pdf_trace_rerun.v1",
        "input_mode": "fresh_pdf",
        "historical_data_consumed": False,
        "source_strategy": "pixel_trace",
        "representation": "pixel_primitives",
        "source_pdf": {"name": pdf.name, "sha256": pdf_hash},
        "dpi": dpi,
        "figures": {
            figure_id: {
                "page_number": int(figure_clips[figure_id]["page"]),
                "clip_pdf_points": list(figure_clips[figure_id]["clip_pdf_points"]),
                "per_figure_script": per_figure_scripts[figure_id],
                "outputs": results[figure_id]["outputs"],
                "visual_qa": results[figure_id]["outputs"]["visual_qa"],
                "geometry_audit": results[figure_id]["outputs"]["geometry_audit"],
                "status": results[figure_id]["status"],
            }
            for figure_id in figures
        },
    }
    path = out_dir / "trace_rerun_manifest.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def run_batch(
    pdf: Path,
    out_dir: Path,
    *,
    figures: list[str],
    dpi: int,
    figure_clips: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pdf = pdf.resolve()
    out_dir = out_dir.resolve()
    declared_clips = _normalize_figure_clips(figure_clips if figure_clips is not None else FIGURE_CLIPS)
    if not pdf.is_file():
        raise FileNotFoundError(f"source PDF not found: {pdf}")
    serialized_paths = f"{pdf} {out_dir}".lower()
    rejected = [token for token in FORBIDDEN_PATH_TOKENS if token in serialized_paths]
    if rejected:
        raise ValueError(f"E124_HISTORICAL_PATH_REJECTED: {', '.join(rejected)}")
    unknown = [figure_id for figure_id in figures if figure_id not in declared_clips]
    if unknown:
        raise ValueError(f"unknown figure ids: {', '.join(unknown)}")
    if len(set(figures)) != len(figures):
        raise ValueError("duplicate figure ids are not allowed")
    _ensure_fresh_output(out_dir)
    _validate_pdf_clips(pdf, declared_clips)

    pdf_hash = sha256(pdf)
    results: dict[str, dict[str, Any]] = {}
    per_figure_scripts: dict[str, str] = {}
    for figure_id in figures:
        config = declared_clips[figure_id]
        figure_dir = out_dir / f"fig{figure_id}"
        result = trace_pdf_clip(
            pdf,
            int(config["page"]),
            tuple(float(value) for value in config["clip_pdf_points"]),
            figure_dir,
            f"fig{figure_id}",
            dpi=dpi,
        )
        result["figure_id"] = figure_id
        result["source_pdf_sha256"] = pdf_hash
        result["fresh_extraction"] = True
        result["historical_data_consumed"] = False
        script_path = _write_per_figure_script(
            out_dir,
            figure_id,
            config,
            source_pdf=pdf,
            source_sha256=pdf_hash,
            dpi=dpi,
        )
        per_figure_scripts[figure_id] = script_path.relative_to(out_dir).as_posix()
        result["per_figure_script"] = per_figure_scripts[figure_id]
        result["outputs"] = {key: f"fig{figure_id}/{value}" for key, value in result["outputs"].items()}
        results[figure_id] = result

    visual_manifest = {
        "schema": "scientificfigure.visual_batch.v1",
        "figures": [
            {
                "id": f"fig{figure_id}",
                "source": f"fig{figure_id}/fig{figure_id}_reference.png",
                "actual": f"fig{figure_id}/fig{figure_id}.png",
                "thresholds": {"require_canvas_match": True, "max_mae_0_1": 0.08},
            }
            for figure_id in figures
        ],
    }
    visual_manifest_path = out_dir / "visual_batch_manifest.json"
    visual_manifest_path.write_text(json.dumps(visual_manifest, indent=2) + "\n", encoding="utf-8")
    visual_report = score_batch(visual_manifest_path, out_dir / "qa", project_root=out_dir)
    visual_report_path = out_dir / "qa" / "visual_batch_report.json"
    visual_report_path.write_text(json.dumps(visual_report, indent=2) + "\n", encoding="utf-8")
    rerun_manifest_path = _write_trace_rerun_manifest(
        out_dir,
        pdf=pdf,
        pdf_hash=pdf_hash,
        figures=figures,
        results=results,
        per_figure_scripts=per_figure_scripts,
        figure_clips=declared_clips,
        dpi=dpi,
    )

    manifest = {
        "schema": "sciplot.fresh_pdf_batch.v1",
        "status": "pass" if all(item["status"] == "visual_trace_pass" for item in results.values()) and visual_report["status"] == "pass" else "failed",
        "fresh_extraction": True,
        "historical_data_consumed": False,
        "source_strategy": "pixel_trace",
        "representation": "pixel_primitives",
        "source_pdf": {"name": pdf.name, "sha256": pdf_hash},
        "figures": results,
        "figure_order": figures,
        "per_figure_scripts": per_figure_scripts,
        "dpi": dpi,
        "visual_batch_qa": "qa/visual_batch_report.json",
        "trace_rerun_manifest": rerun_manifest_path.name,
        "forbidden_path_tokens": list(FORBIDDEN_PATH_TOKENS),
    }
    (out_dir / "fresh_pdf_batch_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    policy = {
        "schema": "sciplot.fresh_pdf_source_policy.v1",
        "data_policy": "fresh_pdf_trace",
        "historical_data_allowed": False,
        "historical_data_consumed": False,
        "fresh_extraction": True,
        "source_pdf_sha256": pdf_hash,
        "figures": figures,
        "forbidden_path_tokens": list(FORBIDDEN_PATH_TOKENS),
    }
    (out_dir / "source_policy.json").write_text(
        json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproduce manifest-declared paper figures from a fresh PDF source.")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--clip-manifest", type=Path)
    parser.add_argument("--figure-clip", action="append", type=parse_figure_clip)
    parser.add_argument("--figure", dest="figures", action="append")
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()
    try:
        declared: dict[str, dict[str, Any]] = {}
        if args.clip_manifest:
            declared.update(load_clip_manifest(args.clip_manifest))
        for figure_id, record in args.figure_clip or []:
            if figure_id in declared:
                raise ValueError(f"duplicate figure id: {figure_id}")
            declared[figure_id] = record
        declared = _normalize_figure_clips(declared)
        figures = args.figures or list(declared)
        manifest = run_batch(
            args.pdf,
            args.out_dir,
            figures=figures,
            dpi=args.dpi,
            figure_clips=declared,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"schema": "sciplot.fresh_pdf_batch.v1", "status": "failed", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
