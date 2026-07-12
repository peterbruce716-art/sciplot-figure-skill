from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from shared_geometry import SharedPathGeometry


def _svg_path_audit(svg_text: str) -> dict[str, Any]:
    root = ET.fromstring(svg_text)
    sources: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    empty_path_count = 0
    for index, element in enumerate(root.iter()):
        if element.tag.rsplit("}", 1)[-1] != "path":
            continue
        path_data = element.attrib.get("d", "").strip()
        if not path_data:
            empty_path_count += 1
            continue
        source_id = f"svg-path-{index}"
        source_hash = "sha256:" + hashlib.sha256(path_data.encode("utf-8")).hexdigest()
        style = element.attrib.get("style", "")
        roles = []
        if element.attrib.get("fill", "") not in {"", "none"} or "fill:" in style and "fill:none" not in style:
            roles.append("fill")
        if element.attrib.get("stroke", "") not in {"", "none"} or "stroke:" in style and "stroke:none" not in style:
            roles.append("boundary")
        sources[source_id] = {
            "source_hash": source_hash,
            "roles": roles or ["path"],
            "artist_count": 1,
        }
    if not sources:
        failures.append("no SVG paths were found")
    return {
        "schema": "sciplot.shared_geometry.audit.v1",
        "status": "pass" if not failures else "failed",
        "geometry_mode": "native_svg_paths",
        "artist_count": len(sources),
        "source_count": len(sources),
        "ignored_empty_path_count": empty_path_count,
        "sources": sources,
        "failures": failures,
    }


def _native_source_audit(page: Any, document: Any, clip: Any) -> dict[str, Any]:
    visible_images = []
    for image in page.get_image_info(xrefs=True):
        bbox = _fitz().Rect(image["bbox"])
        if bbox.intersects(clip):
            visible_images.append(image)
    if visible_images:
        sources = {}
        for index, image in enumerate(visible_images):
            xref = int(image.get("xref") or 0)
            image_bytes = document.extract_image(xref)["image"] if xref else bytes(image.get("digest") or b"")
            source_id = f"pdf-image-xref-{xref or index}"
            sources[source_id] = {
                "source_hash": "sha256:" + hashlib.sha256(image_bytes).hexdigest(),
                "roles": ["whole_figure_source"],
                "artist_count": 1,
                "bbox_pdf_points": list(image["bbox"]),
            }
        return {
            "schema": "sciplot.shared_geometry.audit.v1",
            "status": "pass",
            "geometry_mode": "native_raster_image",
            "artist_count": len(sources),
            "source_count": len(sources),
            "sources": sources,
            "failures": [],
        }

    sources = {}
    failures = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None or not rect.intersects(clip):
            continue
        try:
            sequence = int(drawing.get("seqno", len(sources)))
            geometry = _path_geometry(
                f"pdf-page-{page.number + 1}-seq-{sequence}",
                drawing.get("items") or [],
                bool(drawing.get("closePath")),
            )
        except ValueError as exc:
            failures.append(str(exc))
            continue
        sources[geometry.source_id] = {
            "source_hash": geometry.source_hash,
            "roles": ["fill_and_or_boundary"],
            "artist_count": 1,
        }
    if not sources:
        failures.append("no target-region vector paths or raster images were found")
    return {
        "schema": "sciplot.shared_geometry.audit.v1",
        "status": "pass" if not failures else "failed",
        "geometry_mode": "native_pdf_paths",
        "artist_count": len(sources),
        "source_count": len(sources),
        "sources": sources,
        "failures": failures,
    }


def _native_vector_clip(page: Any, document: Any, clip: Any, svg_path: Path, pdf_path: Path) -> dict[str, Any]:
    fitz = _fitz()
    svg_root = ET.fromstring(page.get_svg_image(text_as_path=True))
    svg_root.set("width", f"{float(clip.width):.6f}pt")
    svg_root.set("height", f"{float(clip.height):.6f}pt")
    svg_root.set(
        "viewBox",
        f"{float(clip.x0):.6f} {float(clip.y0):.6f} {float(clip.width):.6f} {float(clip.height):.6f}",
    )
    svg_text = ET.tostring(svg_root, encoding="unicode")
    svg_path.write_text(svg_text + "\n", encoding="utf-8")

    output = fitz.open()
    try:
        output_page = output.new_page(width=float(clip.width), height=float(clip.height))
        output_page.show_pdf_page(output_page.rect, document, page.number, clip=clip, keep_proportion=False)
        output.save(pdf_path, garbage=4, deflate=True)
    finally:
        output.close()
    return _svg_path_audit(svg_text)


def _fitz() -> Any:
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("PDF vector tracing requires PyMuPDF (pip install PyMuPDF)") from exc
    return fitz


def _point_xy(point: Any) -> tuple[float, float]:
    return float(point.x), float(point.y)


def _append_move(vertices: list[tuple[float, float]], codes: list[int], point: Any) -> None:
    from matplotlib.path import Path as MplPath

    xy = _point_xy(point)
    if not vertices or not np.allclose(vertices[-1], xy, rtol=0.0, atol=1e-7):
        vertices.append(xy)
        codes.append(MplPath.MOVETO)


def _path_geometry(source_id: str, items: Iterable[Any], close_path: bool) -> SharedPathGeometry:
    from matplotlib.path import Path as MplPath

    vertices: list[tuple[float, float]] = []
    codes: list[int] = []
    subpath_start: tuple[float, float] | None = None
    for item in items:
        command = item[0]
        if command == "l":
            _append_move(vertices, codes, item[1])
            subpath_start = subpath_start or _point_xy(item[1])
            vertices.append(_point_xy(item[2]))
            codes.append(MplPath.LINETO)
        elif command == "c":
            _append_move(vertices, codes, item[1])
            subpath_start = subpath_start or _point_xy(item[1])
            vertices.extend([_point_xy(item[2]), _point_xy(item[3]), _point_xy(item[4])])
            codes.extend([MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4])
        elif command == "re":
            rect = item[1]
            corners = [
                (float(rect.x0), float(rect.y0)),
                (float(rect.x1), float(rect.y0)),
                (float(rect.x1), float(rect.y1)),
                (float(rect.x0), float(rect.y1)),
                (float(rect.x0), float(rect.y0)),
            ]
            vertices.extend(corners)
            codes.extend([MplPath.MOVETO, MplPath.LINETO, MplPath.LINETO, MplPath.LINETO, MplPath.CLOSEPOLY])
            subpath_start = None
        elif command == "qu":
            quad = item[1]
            corners = [_point_xy(quad.ul), _point_xy(quad.ur), _point_xy(quad.lr), _point_xy(quad.ll), _point_xy(quad.ul)]
            vertices.extend(corners)
            codes.extend([MplPath.MOVETO, MplPath.LINETO, MplPath.LINETO, MplPath.LINETO, MplPath.CLOSEPOLY])
            subpath_start = None
        else:
            raise ValueError(f"unsupported PDF path command: {command}")
    if close_path and vertices and codes[-1] != MplPath.CLOSEPOLY:
        vertices.append(subpath_start or vertices[0])
        codes.append(MplPath.CLOSEPOLY)
    if not vertices:
        raise ValueError(f"PDF drawing {source_id} has no supported path items")
    return SharedPathGeometry(source_id, vertices, codes)


def _score(source_path: Path, render_path: Path) -> dict[str, Any]:
    source = Image.open(source_path).convert("RGB")
    render = Image.open(render_path).convert("RGB")
    same_size = source.size == render.size
    if not same_size:
        return {
            "canvas_size_match": False,
            "comparison_valid": False,
            "source_size_px": list(source.size),
            "render_size_px": list(render.size),
            "mae_0_1": None,
            "rmse_0_1": None,
            "failure_reason": "canvas mismatch; images were not resized for scoring",
        }
    source_values = np.asarray(source, dtype=np.float32) / 255.0
    render_values = np.asarray(render, dtype=np.float32) / 255.0
    difference = source_values - render_values
    return {
        "canvas_size_match": same_size,
        "comparison_valid": True,
        "source_size_px": list(source.size),
        "render_size_px": list(render.size),
        "mae_0_1": float(np.mean(np.abs(difference))),
        "rmse_0_1": float(math.sqrt(float(np.mean(difference * difference)))),
        "source_nonwhite_ratio": float(np.mean(np.any(source_values < 0.98, axis=2))),
        "render_nonwhite_ratio": float(np.mean(np.any(render_values < 0.98, axis=2))),
    }


def trace_pdf_clip(
    pdf_path: Path,
    page_number: int,
    clip_values: tuple[float, float, float, float],
    out_dir: Path,
    stem: str,
    *,
    dpi: int = 300,
) -> dict[str, Any]:
    fitz = _fitz()
    out_dir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf_path)
    try:
        page = document[page_number - 1]
        clip = fitz.Rect(*clip_values)
        reference_path = out_dir / f"{stem}_reference.png"
        render_path = out_dir / f"{stem}.png"
        svg_path = out_dir / f"{stem}.svg"
        pdf_out_path = out_dir / f"{stem}.pdf"
        geometry_path = out_dir / f"{stem}_geometry_audit.json"
        qa_path = out_dir / f"{stem}_visual_qa.json"

        matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pixmap = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
        pixmap.save(reference_path)

        _native_vector_clip(page, document, clip, svg_path, pdf_out_path)
        output_scale_x = pixmap.width / float(clip.width)
        output_scale_y = pixmap.height / float(clip.height)
        rendered_document = fitz.open(pdf_out_path)
        try:
            rendered_pixmap = rendered_document[0].get_pixmap(
                matrix=fitz.Matrix(output_scale_x, output_scale_y),
                alpha=False,
            )
            rendered_pixmap.save(render_path)
        finally:
            rendered_document.close()
        geometry_report = _native_source_audit(page, document, clip)
        geometry_report["source_identity_scope"] = (
            "pdf_compound_path" if geometry_report["geometry_mode"] == "native_pdf_paths" else "pdf_image_xobject"
        )
        geometry_path.write_text(json.dumps(geometry_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        visual_score = _score(reference_path, render_path)
        visual_score.update(
            {
                "comparison_pipeline": "source_page_clip_vs_exported_pdf_raster",
                "independent_render": True,
                "render_method": "native_pdf_clip",
                "output_raster_scale": [output_scale_x, output_scale_y],
                "output_canvas_basis": "source_clip_pixel_dimensions",
            }
        )
        qa_path.write_text(json.dumps(visual_score, indent=2) + "\n", encoding="utf-8")
        visual_pass = (
            geometry_report["status"] == "pass"
            and visual_score["comparison_valid"]
            and visual_score["mae_0_1"] is not None
            and float(visual_score["mae_0_1"]) <= 0.08
        )
        return {
            "schema": "sciplot.pdf_vector_trace.v1",
            "status": "visual_trace_pass" if visual_pass else "failed",
            "source_strategy": "pixel_trace",
            "trace_source_format": "vector_pdf",
            "render_method": "native_pdf_clip",
            "representation": "pixel_primitives",
            "semantic_data_recovered": False,
            "page_number": page_number,
            "clip_pdf_points": list(clip_values),
            "dpi": dpi,
            "drawing_count": geometry_report["artist_count"],
            "skipped_drawing_count": 0,
            "shared_geometry_status": geometry_report["status"],
            "visible_source_kind": geometry_report["geometry_mode"],
            "visual_score": visual_score,
            "outputs": {
                "reference_png": reference_path.name,
                "png": render_path.name,
                "svg": svg_path.name,
                "pdf": pdf_out_path.name,
                "geometry_audit": geometry_path.name,
                "visual_qa": qa_path.name,
            },
        }
    finally:
        document.close()


def _clip(value: str) -> tuple[float, float, float, float]:
    numbers = tuple(float(part.strip()) for part in value.split(","))
    if len(numbers) != 4:
        raise argparse.ArgumentTypeError("clip must be x0,y0,x1,y1")
    return numbers  # type: ignore[return-value]


def main() -> int:
    parser = argparse.ArgumentParser(description="Redraw one vector figure clip from a PDF with shared path geometry.")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page", required=True, type=int, help="One-based PDF page number")
    parser.add_argument("--clip", required=True, type=_clip, help="PDF-point rectangle x0,y0,x1,y1")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--stem", required=True)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    manifest = trace_pdf_clip(args.pdf, args.page, args.clip, args.out_dir, args.stem, dpi=args.dpi)
    json_out = args.json_out or args.out_dir / f"{args.stem}_manifest.json"
    json_out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest["status"] == "visual_trace_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
