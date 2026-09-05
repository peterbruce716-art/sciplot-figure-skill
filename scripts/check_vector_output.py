from __future__ import annotations

import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from portable_paths import portable_path


_SVG_NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
_SVG_ABSOLUTE_UNITS = {"": 1.0, "px": 1.0, "in": 96.0, "cm": 96.0 / 2.54, "mm": 96.0 / 25.4, "q": 96.0 / 101.6, "pt": 96.0 / 72.0, "pc": 16.0}


def _svg_tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _svg_number(value: str | None, reference: float | None = None) -> float | None:
    if value is None:
        return None
    match = re.fullmatch(f"({_SVG_NUMBER})([a-zA-Z%]*)", str(value).strip())
    if not match:
        return None
    number, unit = float(match.group(1)), match.group(2).lower()
    if unit == "%":
        resolved = (number / 100.0) * reference if reference is not None else None
    else:
        factor = _SVG_ABSOLUTE_UNITS.get(unit)
        resolved = number * factor if factor is not None else None
    return resolved if resolved is not None and math.isfinite(resolved) else None


def _svg_canvas_bounds(root: ET.Element) -> tuple[float, float, float | None, float | None]:
    viewbox = root.attrib.get("viewBox")
    if viewbox is not None:
        tokens = re.split(r"[ \t\r\n]*,[ \t\r\n]*|[ \t\r\n]+", viewbox.strip(" \t\r\n"))
        if len(tokens) != 4 or not all(re.fullmatch(_SVG_NUMBER, item) for item in tokens):
            raise ValueError("svg_viewbox_invalid")
        parts = [float(item) for item in tokens]
        if not all(math.isfinite(item) for item in parts) or parts[2] <= 0 or parts[3] <= 0:
            raise ValueError("svg_viewbox_invalid")
        # Image coordinates use viewBox units, not the physical page dimensions.
        return parts[0], parts[1], parts[2], parts[3]
    return 0.0, 0.0, _svg_number(root.attrib.get("width")), _svg_number(root.attrib.get("height"))


def _intersect_ratio(x: float, y: float, width: float, height: float, canvas_width: float, canvas_height: float) -> float:
    left = max(0.0, x)
    top = max(0.0, y)
    right = min(canvas_width, x + width)
    bottom = min(canvas_height, y + height)
    # Normalize each dimension before multiplying to avoid area under/overflow.
    return (max(0.0, right - left) / canvas_width) * (max(0.0, bottom - top) / canvas_height)


def check_svg(path: Path, *, representation: str, project_root: Path | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": portable_path(path, project_root) if project_root else str(path),
        "status": "failed",
        "parseable": False,
        "paths": 0,
        "lines": 0,
        "text_elements": 0,
        "raster_images": 0,
        "raster_coverage_ratio": 0.0,
        "external_resources": [],
        "failure_reasons": [],
    }
    if not path.exists() or path.stat().st_size == 0:
        result["failure_reasons"].append("svg_missing_or_empty")
        return result
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        result["failure_reasons"].append(f"svg_parse_error:{exc}")
        return result
    if root.tag not in {"svg", "{http://www.w3.org/2000/svg}svg"}:
        result["failure_reasons"].append("svg_root_invalid")
        return result
    result["parseable"] = True
    try:
        canvas_x, canvas_y, canvas_width, canvas_height = _svg_canvas_bounds(root)
    except ValueError as exc:
        result["failure_reasons"].append(str(exc))
        return result
    raster_coverage = 0.0
    raster_geometry_unknown = False
    for element in root.iter():
        tag = _svg_tag(element)
        if tag == "path":
            result["paths"] += 1
        elif tag == "line":
            result["lines"] += 1
        elif tag in {"text", "tspan"}:
            result["text_elements"] += 1
        elif tag == "image":
            result["raster_images"] += 1
            href = element.attrib.get("href") or element.attrib.get("{http://www.w3.org/1999/xlink}href")
            if href and not href.startswith("data:"):
                result["external_resources"].append(href)
            image_width = _svg_number(element.attrib.get("width"), canvas_width)
            image_height = _svg_number(element.attrib.get("height"), canvas_height)
            image_x = _svg_number(element.attrib.get("x", "0"), canvas_width)
            image_y = _svg_number(element.attrib.get("y", "0"), canvas_height)
            if (canvas_width is not None and canvas_width > 0 and canvas_height is not None and canvas_height > 0
                    and image_width is not None and image_width >= 0 and image_height is not None and image_height >= 0
                    and image_x is not None and image_y is not None):
                raster_coverage += _intersect_ratio(image_x - canvas_x, image_y - canvas_y, image_width, image_height, canvas_width, canvas_height)
            elif element.attrib.get("width") == "100%" and element.attrib.get("height") == "100%":
                raster_coverage = 1.0
            else:
                raster_geometry_unknown = True
    result["raster_coverage_ratio"] = round(min(1.0, raster_coverage), 6)
    vector_count = int(result["paths"]) + int(result["lines"]) + int(result["text_elements"])
    if result["external_resources"]:
        result["failure_reasons"].append("svg_has_external_resources")
    if representation == "semantic_vector" and int(result["raster_images"]) > 0 and vector_count == 0:
        result["failure_reasons"].append("semantic_vector_svg_is_raster_only")
    if representation == "semantic_vector" and vector_count == 0:
        result["failure_reasons"].append("semantic_vector_svg_has_no_vector_content")
    if representation == "semantic_vector" and raster_geometry_unknown:
        result["failure_reasons"].append("semantic_vector_svg_raster_geometry_unknown")
    if representation == "semantic_vector" and float(result["raster_coverage_ratio"]) > 0.05:
        result["failure_reasons"].append("semantic_vector_svg_raster_coverage_exceeds_0_05")
    result["status"] = "pass" if not result["failure_reasons"] else "failed"
    return result


def check_pdf(path: Path, *, representation: str, project_root: Path | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": portable_path(path, project_root) if project_root else str(path),
        "status": "failed",
        "parseable": False,
        "pages": 0,
        "fonts": [],
        "image_objects": 0,
        "raster_coverage_ratio": 0.0,
        "failure_reasons": [],
    }
    if not path.exists() or path.stat().st_size == 0:
        result["failure_reasons"].append("pdf_missing_or_empty")
        return result
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        result["failure_reasons"].append("pdf_header_missing")
        return result
    text = data.decode("latin-1", errors="ignore")
    if b"startxref" not in data or b"%%EOF" not in data:
        result["failure_reasons"].append("pdf_parse_error:missing_xref_or_eof")
        return result
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError:
        if representation == "semantic_vector":
            result["failure_reasons"].append("pypdf_missing_for_semantic_vector_pdf_validation")
            return result
        result["parseable"] = True
        result["pages"] = len(re.findall(r"/Type\s*/Page\b", text))
        result["image_objects"] = len(re.findall(r"/Subtype\s*/Image\b", text))
        result["fonts"] = sorted(set(re.findall(r"/BaseFont\s*/([A-Za-z0-9+_.-]+)", text)))
    else:
        try:
            with path.open("rb") as handle:
                reader = PdfReader(handle, strict=True)
                result["pages"] = len(reader.pages)
                for page in reader.pages:
                    _ = page.mediabox
                    resources = page.get("/Resources") or {}
                    xobjects = resources.get("/XObject") or {}
                    for obj in xobjects.values():
                        try:
                            if obj.get_object().get("/Subtype") == "/Image":
                                result["image_objects"] += 1
                        except Exception:
                            continue
                    fonts = resources.get("/Font") or {}
                    result["fonts"].extend(str(key).lstrip("/") for key in fonts.keys())
            result["parseable"] = True
        except Exception as exc:
            result["failure_reasons"].append(f"pdf_parse_error:{exc}")
            return result
    result["raster_coverage_ratio"] = 1.0 if int(result["image_objects"]) > 0 else 0.0
    result["fonts"] = sorted(set(result["fonts"]) or set(re.findall(r"/BaseFont\s*/([A-Za-z0-9+_.-]+)", text)))
    if result["pages"] < 1:
        result["failure_reasons"].append("pdf_has_no_page_objects")
    if representation == "semantic_vector" and int(result["image_objects"]) > 0 and not result["fonts"]:
        result["failure_reasons"].append("semantic_vector_pdf_is_raster_only")
    if representation == "semantic_vector" and float(result["raster_coverage_ratio"]) > 0.05:
        result["failure_reasons"].append("semantic_vector_pdf_raster_coverage_unknown_or_exceeds_0_05")
    result["status"] = "pass" if not result["failure_reasons"] else "failed"
    return result


def check_vector_outputs(svg_path: Path, pdf_path: Path, *, representation: str = "semantic_vector", project_root: Path | None = None) -> dict[str, Any]:
    svg = check_svg(svg_path, representation=representation, project_root=project_root)
    pdf = check_pdf(pdf_path, representation=representation, project_root=project_root)
    status = "pass" if svg["status"] == "pass" and pdf["status"] == "pass" else "failed"
    return {
        "schema": "scientificfigure.vector_validation.v1",
        "status": status,
        "representation": representation,
        "svg": svg,
        "pdf": pdf,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check SVG/PDF vector deliverables.")
    parser.add_argument("--svg", required=True, type=Path)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--representation", default="semantic_vector")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    result = check_vector_outputs(args.svg, args.pdf, representation=args.representation, project_root=args.project_root)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
