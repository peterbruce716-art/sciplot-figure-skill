from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib.colors import to_hex

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from portable_paths import portable_path

from capability_model import plot_style_keys
from data_resolver import resolve_series
from visualspec import load_json, write_json


def _hash_values(values: list[float]) -> str:
    normalized = [round(float(value), 12) for value in values]
    payload = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _series(data: dict[str, Any], key: str, *, base_dir: Path | None = None) -> list[float]:
    return [float(value) for value in resolve_series(data, key, base_dir=base_dir)]


def _hash_array(values: Any) -> str:
    arr = np.asarray(values, dtype=float).reshape(-1)
    return _hash_values([float(value) for value in arr])


def _normalize_color(value: Any) -> str | None:
    if value is None or (isinstance(value, str) and value in {"", "none", "None"}):
        return None
    try:
        return to_hex(value, keep_alpha=False).lower()
    except Exception:
        return str(value)


def _normalize_linestyle(value: Any) -> str:
    mapping = {"-": "solid", "--": "dashed", "-.": "dashdot", ":": "dotted", "None": "none", "": "none", " ": "none"}
    return mapping.get(str(value), str(value))


def _normalize_aspect(value: Any) -> Any:
    if value == 1 or value == 1.0:
        return "equal"
    return value


def _resolve_contour_levels(data: dict[str, Any], style: dict[str, Any], *, base_dir: Path | None = None) -> list[float]:
    levels = style.get("levels", 8)
    if isinstance(levels, list):
        return [float(value) for value in levels]
    z = np.asarray(data.get("z") or [], dtype=float)
    if z.size == 0:
        return []
    count = int(levels)
    count = max(2, count)
    return [float(value) for value in np.linspace(float(np.nanmin(z)), float(np.nanmax(z)), count)]


def _axis_semantics(axis: dict[str, Any]) -> dict[str, Any]:
    return {
        "scale": axis.get("scale", "linear"),
        "limits": [float(value) for value in axis.get("limits", [])],
        "ticks": [float(value) for value in axis.get("ticks", [])],
        "label": axis.get("label", ""),
    }


def _expected_style(ptype: str, style: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in plot_style_keys(ptype):
        if key not in style:
            continue
        value = style[key]
        if key in {"color", "facecolor", "edgecolor"}:
            result[key] = _normalize_color(value)
        elif key == "line_style":
            result[key] = _normalize_linestyle(value)
        elif key in {"line_width_pt", "marker_size_pt2", "alpha", "bar_width", "capsize", "vmin", "vmax"}:
            result[key] = float(value)
        elif key == "aspect":
            result[key] = _normalize_aspect(value)
        else:
            result[key] = value
    return result


def _plot_semantics(plot: dict[str, Any], *, base_dir: Path | None = None) -> dict[str, Any]:
    data = plot.get("data") or {}
    ptype = str(plot.get("type"))
    item: dict[str, Any] = {"type": ptype, "label": plot.get("label")}
    style = _expected_style(ptype, plot.get("style") or {})
    if ptype == "contour":
        style.pop("levels", None)
    if style:
        item["style"] = style
    if ptype in {"line", "scatter", "errorbar"}:
        x = _series(data, "x", base_dir=base_dir)
        y = _series(data, "y", base_dir=base_dir)
        item.update({"x_hash": _hash_values(x), "y_hash": _hash_values(y), "point_count": len(x)})
        if ptype == "errorbar":
            item["yerr_hash"] = _hash_values(_series(data, "yerr", base_dir=base_dir))
    elif ptype == "fill_between":
        x = _series(data, "x", base_dir=base_dir)
        item.update(
            {
                "x_hash": _hash_values(x),
                "y1_hash": _hash_values(_series(data, "y1", base_dir=base_dir)),
                "y2_hash": _hash_values(_series(data, "y2", base_dir=base_dir)),
                "point_count": len(x),
            }
        )
    elif ptype in {"grouped_bar", "stacked_bar"}:
        x = _series(data, "x", base_dir=base_dir)
        groups = []
        for group in data.get("groups") or []:
            values = [float(value) for value in group.get("y", [])]
            group_item = {"label": group.get("label"), "y_hash": _hash_values(values), "point_count": len(values)}
            if group.get("color") is not None:
                group_item["color"] = _normalize_color(group.get("color"))
            if style.get("alpha") is not None:
                group_item["alpha"] = float(style["alpha"])
            groups.append(group_item)
        item.update({"x_hash": _hash_values(x), "groups": groups, "point_count": len(x)})
    elif ptype == "heatmap":
        z = data.get("z") or []
        flat = [float(value) for row in z for value in row]
        item.update({"z_hash": _hash_values(flat), "shape": [len(z), len(z[0]) if z else 0]})
    elif ptype == "contour":
        x = _series(data, "x", base_dir=base_dir)
        y = _series(data, "y", base_dir=base_dir)
        z = np.asarray(data.get("z") or [], dtype=float)
        levels = _resolve_contour_levels(data, plot.get("style") or {}, base_dir=base_dir)
        item.update(
            {
                "x_hash": _hash_values(x),
                "y_hash": _hash_values(y),
                "z_hash": _hash_array(z),
                "shape": [int(z.shape[0]) if z.ndim else 0, int(z.shape[1]) if z.ndim > 1 else 0],
                "levels_hash": _hash_values(levels),
                "level_count": len(levels),
            }
        )
    return item


def _expected_annotation(annotation: dict[str, Any]) -> dict[str, Any]:
    atype = str(annotation.get("type"))
    coords = annotation.get("coordinates", [])
    style = annotation.get("style") or {}
    result: dict[str, Any] = {"type": atype, "coordinate_space": annotation.get("coordinate_space", "data")}
    if atype == "text":
        result.update({"text": annotation.get("text", ""), "geometry": {"x": float(coords[0]), "y": float(coords[1])}})
    elif atype == "arrow":
        result["geometry"] = {"x0": float(coords[0]), "y0": float(coords[1]), "x1": float(coords[2]), "y1": float(coords[3])}
    elif atype == "rectangle":
        result["geometry"] = {"x": float(coords[0]), "y": float(coords[1]), "width": float(coords[2]), "height": float(coords[3])}
    elif atype == "polygon":
        result["geometry"] = {"points": [[float(x), float(y)] for x, y in coords]}
    if style:
        normalized: dict[str, Any] = {}
        for key, value in style.items():
            if key in {"color", "facecolor", "edgecolor"}:
                normalized[key] = _normalize_color(value)
            elif key in {"line_width_pt", "font_size_pt", "alpha", "rotation"}:
                normalized[key] = float(value)
            elif key == "line_style":
                normalized[key] = _normalize_linestyle(value)
            else:
                normalized[key] = value
        result["style"] = normalized
    return result


def expected_semantics(spec: dict[str, Any], *, spec_path: Path | None = None) -> dict[str, Any]:
    base_dir = spec_path.resolve().parent if spec_path else None
    figure_id = str((spec.get("figure") or {}).get("id", "figure_1"))
    panels: dict[str, Any] = {}
    for panel in spec.get("panels", []):
        panel_id = str(panel.get("id", "panel"))
        axes = panel.get("axes") or {}
        plots = [_plot_semantics(plot, base_dir=base_dir) for plot in panel.get("plots", [])]
        legend_labels = [plot.get("label") for plot in panel.get("plots", []) if plot.get("label")]
        for plot in panel.get("plots", []):
            for group in (plot.get("data") or {}).get("groups", []) or []:
                if group.get("label"):
                    legend_labels.append(group["label"])
        panels[panel_id] = {
            "axes": {"x": _axis_semantics(axes.get("x") or {}), "y": _axis_semantics(axes.get("y") or {})},
            "plots": plots,
            "legend_labels": legend_labels,
            "annotations": [_expected_annotation(annotation) for annotation in panel.get("annotations", [])],
        }
    return {"schema": "scientificfigure.render_semantics.v1", "figures": {figure_id: {"panels": panels}}}


def _axis_from_matplotlib(ax: Any, axis_name: str) -> dict[str, Any]:
    axis = ax.xaxis if axis_name == "x" else ax.yaxis
    limits = ax.get_xlim() if axis_name == "x" else ax.get_ylim()
    label = ax.get_xlabel() if axis_name == "x" else ax.get_ylabel()
    scale = ax.get_xscale() if axis_name == "x" else ax.get_yscale()
    return {"scale": scale, "limits": [float(limits[0]), float(limits[1])], "ticks": [float(value) for value in axis.get_ticklocs()], "label": label}


def _artist_label(artist: Any) -> Any:
    label = artist.get_label() if hasattr(artist, "get_label") else None
    return None if isinstance(label, str) and label.startswith("_") else label


def _with_provenance(item: dict[str, Any], keys: list[str], source: str = "observed") -> dict[str, Any]:
    provenance = item.setdefault("provenance", {})
    for key in keys:
        provenance[key] = source
    return item


def _line_style_from_artist(line: Any) -> dict[str, Any]:
    style: dict[str, Any] = {"color": _normalize_color(line.get_color()), "line_width_pt": float(line.get_linewidth()), "line_style": _normalize_linestyle(line.get_linestyle())}
    marker = line.get_marker()
    if marker not in {None, "", "None", "none", " "}:
        style["marker"] = marker
    alpha = line.get_alpha()
    if alpha is not None:
        style["alpha"] = float(alpha)
    return style


def _marker_from_path(collection: Any) -> str | None:
    paths = collection.get_paths()
    if not paths:
        return None
    vertices = np.asarray(paths[0].vertices, dtype=float)
    count = len(vertices)
    if count >= 12:
        return "o"
    if count == 5:
        xs = np.unique(np.round(vertices[:, 0], 6))
        ys = np.unique(np.round(vertices[:, 1], 6))
        if len(xs) == 2 and len(ys) == 2:
            return "s"
    if 4 <= count <= 6:
        return "x"
    return None


def extract_line_semantics(line: Any) -> dict[str, Any]:
    x = line.get_xdata(orig=False)
    y = line.get_ydata(orig=False)
    ptype = getattr(line, "_visualspec_plot_type", "line")
    item = {"type": ptype, "label": _artist_label(line), "x_hash": _hash_array(x), "y_hash": _hash_array(y), "point_count": int(len(x)), "style": _line_style_from_artist(line)}
    if hasattr(line, "_visualspec_plot_index"):
        item["plot_index"] = int(getattr(line, "_visualspec_plot_index"))
    provenance = {"type": "observed", "x_hash": "observed", "y_hash": "observed", "point_count": "observed"}
    for key in item["style"]:
        provenance[f"style.{key}"] = "observed"
    item["provenance"] = provenance
    return item


def extract_scatter_semantics(collection: Any) -> dict[str, Any]:
    offsets = np.asarray(collection.get_offsets(), dtype=float)
    style: dict[str, Any] = {}
    facecolors = collection.get_facecolors()
    if len(facecolors):
        style["color"] = _normalize_color(facecolors[0])
        if float(facecolors[0][-1]) < 1.0:
            style["alpha"] = float(facecolors[0][-1])
    sizes = collection.get_sizes()
    if len(sizes):
        style["marker_size_pt2"] = float(sizes[0])
    marker = _marker_from_path(collection)
    if marker:
        style["marker"] = marker
    item = {
        "type": "scatter",
        "label": _artist_label(collection),
        "x_hash": _hash_array(offsets[:, 0] if offsets.size else []),
        "y_hash": _hash_array(offsets[:, 1] if offsets.size else []),
        "point_count": int(len(offsets)),
        "style": style,
    }
    if hasattr(collection, "_visualspec_plot_index"):
        item["plot_index"] = int(getattr(collection, "_visualspec_plot_index"))
    provenance = {"type": "observed", "x_hash": "observed", "y_hash": "observed", "point_count": "observed"}
    for key in style:
        provenance[f"style.{key}"] = "observed"
    item["provenance"] = provenance
    return item


def _yerr_from_segments(segments: list[Any]) -> list[float]:
    values: list[float] = []
    for segment in segments:
        arr = np.asarray(segment, dtype=float)
        if arr.shape[0] >= 2:
            values.append(abs(float(arr[:, 1].max() - arr[:, 1].min())) / 2.0)
    return values


def extract_fill_between_semantics(collection: Any) -> dict[str, Any]:
    path = collection.get_paths()[0]
    vertices = np.asarray(path.vertices, dtype=float)
    if len(vertices) > 1 and np.allclose(vertices[0], vertices[-1]):
        vertices = vertices[:-1]
    start = 1 if len(vertices) > 2 and np.isclose(vertices[0, 0], vertices[1, 0]) else 0
    split = start + 1
    while split < len(vertices):
        prev_x = float(vertices[split - 1, 0])
        next_x = float(vertices[split, 0])
        if next_x < prev_x - 1e-10:
            break
        if np.isclose(next_x, prev_x) and split > start + 1:
            break
        split += 1
    forward = vertices[start:split]
    remainder = vertices[split:]
    xs = [round(float(value), 12) for value in forward[:, 0]]
    y1 = [float(value) for value in forward[:, 1]]
    y2_by_x: dict[float, float] = {}
    for x_value, y_value in remainder:
        key = round(float(x_value), 12)
        if key in xs and key not in y2_by_x:
            y2_by_x[key] = float(y_value)
    if len(y2_by_x) != len(xs):
        for x_value, y_value in vertices:
            key = round(float(x_value), 12)
            if key in xs:
                y2_by_x.setdefault(key, float(y_value))
    y2 = [y2_by_x.get(x, float("nan")) for x in xs]
    facecolors = collection.get_facecolors()
    style: dict[str, Any] = {}
    if len(facecolors):
        style["color"] = _normalize_color(facecolors[0])
        style["alpha"] = float(facecolors[0][-1])
    item = {"type": "fill_between", "label": _artist_label(collection), "x_hash": _hash_values(xs), "y1_hash": _hash_values(y1), "y2_hash": _hash_values(y2), "point_count": len(xs), "style": style}
    if hasattr(collection, "_visualspec_plot_index"):
        item["plot_index"] = int(getattr(collection, "_visualspec_plot_index"))
    item["provenance"] = {"type": "observed", "x_hash": "derived", "y1_hash": "derived", "y2_hash": "derived", "point_count": "derived", **{f"style.{key}": "observed" for key in style}}
    return item


def extract_bar_semantics(patches: list[Any], ptype: str, *, patch_labels: dict[int, str] | None = None) -> dict[str, Any]:
    patch_labels = patch_labels or {}
    groups: dict[int, list[Any]] = {}
    for patch in patches:
        groups.setdefault(int(getattr(patch, "_visualspec_group_index", 0)), []).append(patch)
    group_items: list[dict[str, Any]] = []
    centers: list[float] = []
    for group_index, bars in sorted(groups.items()):
        bars = sorted(bars, key=lambda bar: float(bar.get_x()))
        values = [float(bar.get_height()) for bar in bars]
        labels = [patch_labels.get(id(bar), bar.get_label()) for bar in bars]
        labels = [label for label in labels if label and not str(label).startswith("_")]
        first_bar = bars[0]
        group_item: dict[str, Any] = {"label": labels[0] if labels else None, "y_hash": _hash_values(values), "point_count": len(values)}
        group_item["color"] = _normalize_color(first_bar.get_facecolor())
        edge = _normalize_color(first_bar.get_edgecolor())
        if edge:
            group_item["edgecolor"] = edge
        alpha = first_bar.get_alpha()
        if alpha is not None:
            group_item["alpha"] = float(alpha)
        if not centers:
            group_count = max(1, int(getattr(bars[0], "_visualspec_group_count", len(groups))))
            width = float(bars[0].get_width())
            offset = (group_index - (group_count - 1) / 2.0) * width if ptype == "grouped_bar" else 0.0
            centers = [float(bar.get_x() + bar.get_width() / 2.0 - offset) for bar in bars]
        group_items.append(group_item)
    style = {"bar_width": float(patches[0].get_width())} if patches else {}
    alpha = patches[0].get_alpha() if patches else None
    if alpha is not None:
        style["alpha"] = float(alpha)
    item = {"type": ptype, "label": None, "x_hash": _hash_values(centers), "groups": group_items, "point_count": len(centers), "style": style}
    if patches and hasattr(patches[0], "_visualspec_plot_index"):
        item["plot_index"] = int(getattr(patches[0], "_visualspec_plot_index"))
    item["provenance"] = {"type": "observed", "x_hash": "derived", "groups": "observed", "point_count": "derived", **{f"style.{key}": "observed" for key in style}}
    return item


def extract_heatmap_semantics(image: Any) -> dict[str, Any]:
    arr = np.asarray(image.get_array(), dtype=float)
    clim = image.get_clim()
    style = {"cmap": image.get_cmap().name}
    if clim[0] is not None:
        style["vmin"] = float(clim[0])
    if clim[1] is not None:
        style["vmax"] = float(clim[1])
    style["aspect"] = _normalize_aspect(image.axes.get_aspect())
    item = {"type": "heatmap", "label": _artist_label(image), "z_hash": _hash_array(arr), "shape": [int(arr.shape[0]), int(arr.shape[1]) if arr.ndim > 1 else 0], "style": style}
    if hasattr(image, "_visualspec_plot_index"):
        item["plot_index"] = int(getattr(image, "_visualspec_plot_index"))
    item["provenance"] = {"type": "observed", "z_hash": "observed", "shape": "observed", **{f"style.{key}": "observed" for key in style}}
    return item


def extract_contour_semantics(contour: Any) -> dict[str, Any]:
    levels = [float(value) for value in getattr(contour, "levels", [])]
    style: dict[str, Any] = {"cmap": contour.cmap.name if getattr(contour, "cmap", None) else "unknown"}
    alpha = getattr(contour, "alpha", None)
    if alpha is not None:
        style["alpha"] = float(alpha)
    semantic_payload = getattr(contour, "_visualspec_semantics", {}) or {}
    item = {
        "type": "contour",
        "label": None,
        "x_hash": semantic_payload.get("x_hash"),
        "y_hash": semantic_payload.get("y_hash"),
        "z_hash": semantic_payload.get("z_hash"),
        "shape": semantic_payload.get("shape", [0, 0]),
        "levels_hash": _hash_values(levels),
        "level_count": len(levels),
        "style": style,
    }
    if hasattr(contour, "_visualspec_plot_index"):
        item["plot_index"] = int(getattr(contour, "_visualspec_plot_index"))
    item["provenance"] = {
        "type": "observed",
        "x_hash": "derived" if item.get("x_hash") else "unavailable",
        "y_hash": "derived" if item.get("y_hash") else "unavailable",
        "z_hash": "derived" if item.get("z_hash") else "unavailable",
        "shape": "derived" if item.get("shape") != [0, 0] else "unavailable",
        "levels_hash": "observed",
        "level_count": "observed",
        **{f"style.{key}": "observed" for key in style},
    }
    return item


def _annotation_style_from_patch(patch: Any) -> dict[str, Any]:
    style: dict[str, Any] = {
        "edgecolor": _normalize_color(patch.get_edgecolor()),
        "line_width_pt": float(patch.get_linewidth()),
        "line_style": _normalize_linestyle(patch.get_linestyle()),
        "fill": bool(patch.get_fill()) if hasattr(patch, "get_fill") else False,
    }
    face = _normalize_color(patch.get_facecolor()) if style["fill"] else None
    if face:
        style["facecolor"] = face
    alpha = patch.get_alpha()
    if alpha is not None:
        style["alpha"] = float(alpha)
    hatch = patch.get_hatch() if hasattr(patch, "get_hatch") else None
    if hatch:
        style["hatch"] = hatch
    style["zorder"] = float(patch.get_zorder())
    return style


def _annotation_style_from_arrow(arrow_patch: Any) -> dict[str, Any]:
    style: dict[str, Any] = {
        "color": _normalize_color(arrow_patch.get_edgecolor()),
        "line_width_pt": float(arrow_patch.get_linewidth()),
    }
    arrowstyle = getattr(arrow_patch, "_visualspec_arrowstyle", None)
    if arrowstyle:
        style["arrowstyle"] = arrowstyle
    alpha = arrow_patch.get_alpha()
    if alpha is not None:
        style["alpha"] = float(alpha)
    return style


def extract_annotations(ax: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for text in ax.texts:
        if getattr(text, "_visualspec_annotation_type", None) == "text":
            x, y = text.get_position()
            item = {
                "type": "text",
                "coordinate_space": getattr(text, "_visualspec_coordinate_space", "data"),
                "text": text.get_text(),
                "geometry": {"x": float(x), "y": float(y)},
                "style": {
                    "font_size_pt": float(text.get_fontsize()),
                    "color": _normalize_color(text.get_color()),
                    "ha": text.get_ha(),
                    "va": text.get_va(),
                    "rotation": float(text.get_rotation()),
                    "fontweight": text.get_fontweight(),
                    "fontstyle": text.get_fontstyle(),
                },
                "provenance": {"geometry": "observed", "text": "observed", "style": "observed"},
            }
            result.append(item)
        elif getattr(text, "_visualspec_annotation_type", None) == "arrow":
            arrow_patch = getattr(text, "arrow_patch", None)
            if arrow_patch is None:
                continue
            x1, y1 = text.xy
            x0, y0 = getattr(text, "xyann", text.get_position())
            item = {
                "type": "arrow",
                "coordinate_space": getattr(text, "_visualspec_coordinate_space", "data"),
                "geometry": {"x0": float(x0), "y0": float(y0), "x1": float(x1), "y1": float(y1)},
                "style": _annotation_style_from_arrow(arrow_patch),
                "provenance": {"geometry": "observed", "style": "observed"},
            }
            result.append(item)
    for patch in ax.patches:
        atype = getattr(patch, "_visualspec_annotation_type", None)
        if atype == "rectangle":
            item = {"type": "rectangle", "coordinate_space": getattr(patch, "_visualspec_coordinate_space", "data"), "geometry": {"x": float(patch.get_x()), "y": float(patch.get_y()), "width": float(patch.get_width()), "height": float(patch.get_height())}, "style": _annotation_style_from_patch(patch), "provenance": {"geometry": "observed", "style": "observed"}}
            result.append(item)
        elif atype == "polygon":
            points = [[float(x), float(y)] for x, y in np.asarray(patch.get_xy(), dtype=float)[:-1]]
            item = {"type": "polygon", "coordinate_space": getattr(patch, "_visualspec_coordinate_space", "data"), "geometry": {"points": points}, "style": _annotation_style_from_patch(patch), "provenance": {"geometry": "observed", "style": "observed"}}
            result.append(item)
    return result


def extract_matplotlib_semantics(fig: Any, *, figure_id: str = "figure_1") -> dict[str, Any]:
    panels: dict[str, Any] = {}
    for ax in fig.axes:
        panel_id = getattr(ax, "_visualspec_panel_id", None)
        if not panel_id:
            continue
        plots: list[dict[str, Any]] = []
        errorbar_segments: dict[int, list[Any]] = {}
        errorbar_capsize: dict[int, float] = {}
        bar_patches: dict[tuple[str, int], list[Any]] = {}
        bar_patch_labels: dict[int, str] = {}
        for container in getattr(ax, "containers", []):
            label = container.get_label() if hasattr(container, "get_label") else None
            if not label or str(label).startswith("_"):
                continue
            for patch in getattr(container, "patches", []):
                bar_patch_labels[id(patch)] = str(label)
        for collection in ax.collections:
            ptype = getattr(collection, "_visualspec_plot_type", None)
            if ptype == "scatter":
                plots.append(extract_scatter_semantics(collection))
            elif ptype == "fill_between":
                plots.append(extract_fill_between_semantics(collection))
            elif ptype == "errorbar_yerr":
                errorbar_segments.setdefault(int(getattr(collection, "_visualspec_plot_index", 0)), []).extend(collection.get_segments())
        for patch in ax.patches:
            ptype = getattr(patch, "_visualspec_plot_type", None)
            if ptype in {"grouped_bar", "stacked_bar"}:
                bar_patches.setdefault((ptype, int(getattr(patch, "_visualspec_plot_index", 0))), []).append(patch)
        lines = list(ax.get_lines())
        for line in lines:
            if getattr(line, "_visualspec_plot_type", None) == "errorbar_cap":
                index = int(getattr(line, "_visualspec_plot_index", 0))
                errorbar_capsize[index] = round(float(line.get_markersize()) / 2.0, 12)
        for line in lines:
            if getattr(line, "_visualspec_plot_type", None) == "errorbar_cap":
                continue
            if str(line.get_label()).startswith("_") and not hasattr(line, "_visualspec_plot_type"):
                continue
            item = extract_line_semantics(line)
            if item["type"] == "errorbar":
                index = int(item.get("plot_index", 0))
                segments = errorbar_segments.get(index, [])
                item["yerr_hash"] = _hash_values(_yerr_from_segments(segments))
                item["provenance"]["yerr_hash"] = "derived"
                if index in errorbar_capsize:
                    item.setdefault("style", {})["capsize"] = errorbar_capsize[index]
                    item["provenance"]["style.capsize"] = "derived"
            plots.append(item)
        for (ptype, _index), patches in bar_patches.items():
            plots.append(extract_bar_semantics(patches, ptype, patch_labels=bar_patch_labels))
        for image in ax.images:
            plots.append(extract_heatmap_semantics(image))
        for contour in getattr(ax, "_visualspec_contour_sets", []):
            plots.append(extract_contour_semantics(contour))
        plots.sort(key=lambda item: int(item.get("plot_index", 10**9)))
        for item in plots:
            item.pop("plot_index", None)
        legend = ax.get_legend()
        legend_labels = [text.get_text() for text in legend.get_texts()] if legend else []
        panels[str(panel_id)] = {"axes": {"x": _axis_from_matplotlib(ax, "x"), "y": _axis_from_matplotlib(ax, "y")}, "plots": plots, "legend_labels": legend_labels, "annotations": extract_annotations(ax)}
    return {"schema": "scientificfigure.render_semantics.v1", "figures": {figure_id: {"panels": panels}}}


def _almost_equal(expected: Any, actual: Any, tolerance: float = 1e-6) -> bool:
    try:
        if math.isnan(float(expected)) and math.isnan(float(actual)):
            return True
        return abs(float(expected) - float(actual)) <= tolerance
    except Exception:
        return expected == actual


def _expected_subset(expected: Any, actual: Any, path: str = "") -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for key, value in expected.items():
            if key == "provenance":
                continue
            if key not in actual:
                return False
            if isinstance(value, list) and value == []:
                continue
            if key == "label" and (value is None or value == ""):
                continue
            if not _expected_subset(value, actual[key], f"{path}.{key}" if path else key):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return False
        return all(_expected_subset(exp, act, path) for exp, act in zip(expected, actual))
    return _almost_equal(expected, actual)


def _critical_paths(item: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(item, dict):
        for key, value in item.items():
            if key == "provenance" or (prefix == "" and key in {"label"}):
                continue
            current = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                paths.update(_critical_paths(value, current))
            elif isinstance(value, list):
                if value:
                    paths.add(current)
            elif value is not None:
                paths.add(current)
    return paths


def _provenance_source(provenance: dict[str, Any], path: str) -> Any:
    if path in provenance:
        return provenance[path]
    parts = path.split(".")
    while parts:
        joined = ".".join(parts)
        if joined in provenance:
            return provenance[joined]
        parts.pop()
    return None


def _provenance_failures(expected_item: dict[str, Any], actual_item: dict[str, Any], *, root: str) -> list[dict[str, str]]:
    provenance = actual_item.get("provenance") or {}
    failures: list[dict[str, str]] = []
    for path in sorted(_critical_paths(expected_item)):
        if path in {"type", "label", "coordinate_space"}:
            continue
        source = _provenance_source(provenance, path)
        if source in {"declared", "unavailable", None}:
            failures.append({"check": "provenance", "path": f"{root}.{path}", "source": str(source)})
    return failures


def _panel_provenance_failures(expected_panel: dict[str, Any], actual_panel: dict[str, Any], *, fig_id: str, panel_id: str) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for collection_name in ("plots", "annotations"):
        expected_items = expected_panel.get(collection_name) or []
        actual_items = actual_panel.get(collection_name) or []
        for index, expected_item in enumerate(expected_items):
            if index >= len(actual_items) or not isinstance(expected_item, dict) or not isinstance(actual_items[index], dict):
                failures.append({"check": "coverage", "figure": fig_id, "panel": panel_id, "path": f"{collection_name}[{index}]"})
                continue
            failures.extend(_provenance_failures(expected_item, actual_items[index], root=f"{fig_id}.{panel_id}.{collection_name}[{index}]"))
    return failures


def audit_semantics(spec_path: Path, semantics_path: Path, *, project_root: Path | None = None) -> dict[str, Any]:
    spec = load_json(spec_path)
    expected = expected_semantics(spec, spec_path=spec_path)
    actual = load_json(semantics_path)
    checks = {"axes": "pass", "data": "pass", "labels": "pass", "legend_mapping": "pass", "units": "pass", "annotations": "pass", "coverage": "pass", "provenance": "pass"}
    failures: list[dict[str, str]] = []
    expected_figures = expected.get("figures", {})
    actual_figures = actual.get("figures", {})
    for fig_id, figure in expected_figures.items():
        actual_figure = actual_figures.get(fig_id, {})
        for panel_id, panel in figure.get("panels", {}).items():
            actual_panel = (actual_figure.get("panels") or {}).get(panel_id, {})
            if not _expected_subset(panel.get("axes"), actual_panel.get("axes")):
                checks["axes"] = "failed"
                failures.append({"check": "axes", "figure": fig_id, "panel": panel_id})
            if not _expected_subset(panel.get("plots"), actual_panel.get("plots")):
                checks["data"] = "failed"
                failures.append({"check": "data", "figure": fig_id, "panel": panel_id})
            expected_labels = [axis.get("label", "") for axis in panel.get("axes", {}).values()]
            actual_labels = [axis.get("label", "") for axis in (actual_panel.get("axes") or {}).values()]
            if expected_labels != actual_labels:
                checks["labels"] = "failed"
                checks["units"] = "failed"
            if not _expected_subset(panel.get("legend_labels"), actual_panel.get("legend_labels")):
                checks["legend_mapping"] = "failed"
                failures.append({"check": "legend_mapping", "figure": fig_id, "panel": panel_id})
            if not _expected_subset(panel.get("annotations"), actual_panel.get("annotations")):
                checks["annotations"] = "failed"
                failures.append({"check": "annotations", "figure": fig_id, "panel": panel_id})
            coverage_failures = _panel_provenance_failures(panel, actual_panel, fig_id=fig_id, panel_id=panel_id)
            if coverage_failures:
                checks["coverage"] = "failed"
                checks["provenance"] = "failed"
                failures.extend(coverage_failures)
    overall = "pass" if all(value == "pass" for value in checks.values()) else "failed"
    root = (project_root or spec_path.parent).resolve()
    return {"schema": "scientificfigure.semantic_audit.v2", "spec": portable_path(spec_path, root), "render_semantics": portable_path(semantics_path, root), "checks": checks, "scientific_fidelity": checks, "overall": overall, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit renderer semantics against VisualSpec expectations.")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--semantics", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    result = audit_semantics(args.spec, args.semantics, project_root=args.project_root)
    if args.json_out:
        write_json(args.json_out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["overall"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
