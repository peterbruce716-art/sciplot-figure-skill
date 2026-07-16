from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def element(id_: str, role: str, primitive: str, bbox: list[float], z: int, **extra) -> dict:
    width, height = 640, 360
    x, y, w, h = bbox
    payload = {"id": id_, "semantic_role": role, "primitive": primitive, "bucket": "editable_vector", "bbox_px": bbox, "bbox_norm": [x / width, y / height, w / width, h / height], "z_order": z, "provenance": "generated", "confidence": 1.0}
    payload.update(extra)
    return payload


def write_case(name: str, image: Image.Image, elements: list[dict]) -> None:
    case = HERE / name
    case.mkdir(parents=True, exist_ok=True)
    source = case / "source.png"
    image.save(source)
    manifest = {"schema": "scientificfigure.object_manifest.v1", "schema_version": "1.0", "source": {"path": "source.png", "width_px": 640, "height_px": 360, "sha256": sha(source)}, "canvas": {"coordinate_space": "source_pixel", "origin": "top_left"}, "manifest_completeness_status": "complete", "elements": elements}
    (case / "object_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def mechanism() -> None:
    image = Image.new("RGB", (640, 360), "white")
    draw = ImageDraw.Draw(image)
    for x, color, label in [(50, "#DCEAF7", "Deformation"), (245, "#E5F2E0", "Subgrain rotation"), (440, "#F8E5D5", "HAGB increase")]:
        draw.rounded_rectangle((x, 125, x + 150, 220), 8, fill=color, outline="#222222", width=2)
        draw.text((x + 20, 165), label, fill="#111111")
    draw.line((200, 172, 245, 172), fill="#333333", width=3)
    draw.line((395, 172, 440, 172), fill="#333333", width=3)
    elements = [element("step-1", "process_box", "rounded_rectangle", [50, 125, 150, 95], 1, style={"fill": "#DCEAF7", "stroke": "#222222"}), element("step-2", "process_box", "rounded_rectangle", [245, 125, 150, 95], 2, style={"fill": "#E5F2E0", "stroke": "#222222"}), element("step-3", "process_box", "rounded_rectangle", [440, 125, 150, 95], 3, style={"fill": "#F8E5D5", "stroke": "#222222"}), element("arrow-1", "connector", "connector", [200, 172, 45, 1], 4, source_anchor={"element_id": "step-1", "side": "right", "offset": 0.5}, target_anchor={"element_id": "step-2", "side": "left", "offset": 0.5}, routing="direct", arrowhead="triangle"), element("arrow-2", "connector", "connector", [395, 172, 45, 1], 5, source_anchor={"element_id": "step-2", "side": "right", "offset": 0.5}, target_anchor={"element_id": "step-3", "side": "left", "offset": 0.5}, routing="direct", arrowhead="triangle")]
    write_case("materials_mechanism", image, elements)


def route() -> None:
    image = Image.new("RGB", (640, 360), "#FAFAFA")
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 55, 250, 125), fill="#FFFFFF", outline="#333333", width=2)
    draw.rectangle((390, 55, 580, 125), fill="#FFFFFF", outline="#333333", width=2)
    draw.rectangle((225, 235, 415, 305), fill="#FFFFFF", outline="#333333", width=2)
    draw.line((250, 90, 390, 90), fill="#006699", width=3)
    draw.line((485, 125, 320, 235), fill="#006699", width=3)
    elements = [element("input", "process_box", "rectangle", [60, 55, 190, 70], 1), element("analysis", "process_box", "rectangle", [390, 55, 190, 70], 2), element("result", "process_box", "rectangle", [225, 235, 190, 70], 3), element("route-a", "connector", "connector", [250, 89, 140, 2], 4, source_anchor={"element_id": "input", "side": "right", "offset": 0.5}, target_anchor={"element_id": "analysis", "side": "left", "offset": 0.5}, routing="direct", arrowhead="triangle"), element("route-b", "connector", "connector", [320, 125, 165, 110], 5, source_anchor={"element_id": "analysis", "side": "bottom", "offset": 0.5}, target_anchor={"element_id": "result", "side": "top", "offset": 0.5}, routing="direct", arrowhead="triangle")]
    write_case("technical_route", image, elements)


def micrograph() -> None:
    random.seed(7)
    image = Image.new("RGB", (640, 360), "#B8B8B8")
    draw = ImageDraw.Draw(image)
    for _ in range(180):
        x, y = random.randrange(640), random.randrange(360)
        r = random.randrange(3, 18)
        gray = random.randrange(70, 210)
        draw.ellipse((x-r, y-r, x+r, y+r), outline=(gray, gray, gray), width=2)
    draw.rectangle((450, 315, 570, 322), fill="white")
    elements = [element("texture", "micrograph", "image", [0, 0, 640, 360], 0, bucket="preserved_raster", asset_path="source.png", asset_sha256="pending", preserve_reason="synthetic texture"), element("scale-bar", "dimension_line", "rectangle", [450, 315, 120, 7], 2, style={"fill": "#FFFFFF", "stroke": "#FFFFFF"})]
    write_case("micrograph_annotation", image, elements)
    path = HERE / "micrograph_annotation" / "object_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["elements"][0]["asset_sha256"] = payload["source"]["sha256"]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    mechanism()
    route()
    micrograph()
    print("generated 3 examples")
