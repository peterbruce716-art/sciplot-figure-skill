"""Advisory checks on rendered artists; not a publication-readiness certificate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.transforms import Bbox


def _luminance(rgb: np.ndarray) -> np.ndarray:
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    return linear @ np.array([0.2126, 0.7152, 0.0722])


def _legend_overlaps(ax: Any, box: Bbox) -> bool:
    # Only visible plot marks count; spines, annotations and the legend do not.
    for artist in [*ax.lines, *ax.patches]:
        kind = getattr(artist, "_visualspec_plot_type", None)
        if kind not in {"line", "errorbar", "grouped_bar", "stacked_bar"}:
            continue
        if not artist.get_visible() or artist.get_alpha() == 0:
            continue
        filled = False
        if artist in ax.patches:
            filled = artist.get_fill() and artist.get_facecolor()[3] > 0
            if not filled and not (artist.get_edgecolor()[3] > 0 and artist.get_linewidth() > 0):
                continue
        elif to_rgba(artist.get_color(), alpha=artist.get_alpha())[3] == 0 or artist.get_linewidth() <= 0 or artist.get_linestyle() in ("None", "none", "", " "):
            continue
        if artist.get_clip_on():
            visible = Bbox.intersection(box, ax.bbox)
            if visible is None:
                continue
        else:
            visible = box
        path = artist.get_transform().transform_path(artist.get_path())
        if path.intersects_bbox(visible, filled=filled):
            return True
    for artist in ax.collections:
        if getattr(artist, "_visualspec_plot_type", None) != "scatter" or not artist.get_visible() or artist.get_alpha() == 0:
            continue
        offsets = artist.get_offset_transform().transform(artist.get_offsets())
        faces, edges, widths, sizes = artist.get_facecolors(), artist.get_edgecolors(), artist.get_linewidths(), artist.get_sizes()
        for index, (x, y) in enumerate(offsets):
            face_visible = len(faces) > 0 and faces[index % len(faces), 3] > 0
            edge_visible = len(edges) > 0 and edges[index % len(edges), 3] > 0 and len(widths) > 0 and widths[index % len(widths)] > 0
            if not (face_visible or edge_visible) or (len(sizes) > 0 and sizes[index % len(sizes)] <= 0):
                continue
            if np.isfinite([x, y]).all() and box.contains(x, y) and (not artist.get_clip_on() or ax.bbox.contains(x, y)):
                return True
    return False


def analyze_readability(fig: Any, spec: dict[str, Any], *, base_dir: Path | None = None) -> dict[str, Any]:
    """Measure likely overlap and annotation contrast without editing the figure.

    Contrast uses a text-free Agg background and median luminance beneath each
    annotation. It is a heuristic: gradients, glyph shapes and complex patches
    still need visual inspection. Filled regions are not treated as legend marks.
    """
    warnings: list[dict[str, Any]] = []
    panels = {str(p["id"]): p for p in spec["panels"]}
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts = []
    for ax in fig.axes:
        panel_id = getattr(ax, "_visualspec_panel_id", None)
        if panel_id not in panels:
            continue  # Colorbar axes are not data panels.
        panel = panels[panel_id]
        legend = ax.get_legend()
        if legend is not None and legend.get_visible() and _legend_overlaps(ax, legend.get_window_extent(renderer)):
            warnings.append({"code": "legend_data_overlap", "panel": panel_id, "message": "Legend intersects data marks; move it to an empty region or outside the axes."})
        plots = panel.get("plots", [])
        if plots and all(p.get("type") == "grouped_bar" for p in plots) and not (panel.get("axes", {}).get("x", {}).get("ticks")):
            # Grouped bars use numeric positions; suggest explicit ticks, never
            # silently reinterpret or round a user's coordinates.
            from data_resolver import resolve_series

            positions = [float(x) for p in plots for x in resolve_series(p["data"], "x", base_dir=base_dir)]
            low, high = sorted(ax.get_xlim())
            if positions and any(low <= tick <= high and not np.isclose(tick, positions).any() for tick in ax.get_xticks()):
                warnings.append({"code": "group_ticks_between_categories", "panel": panel_id, "message": "Automatic ticks include positions between groups; set explicit x ticks at the group positions."})
        for text in ax.texts:
            if text.get_visible() and text.get_text() and text.get_alpha() != 0:
                # Boxed annotations have their own background and safety checker.
                if text.get_bbox_patch() is None:
                    texts.append((panel_id, text, text.get_window_extent(renderer).frozen()))
    if texts:
        try:
            for _, text, _ in texts:
                text.set_visible(False)
            fig.canvas.draw()
            background = np.asarray(fig.canvas.buffer_rgba()).copy()
        finally:
            for _, text, _ in texts:
                text.set_visible(True)
            fig.canvas.draw()
        height, width = background.shape[:2]
        for panel_id, text, box in texts:
            x0, x1 = max(0, int(np.floor(box.x0))), min(width, int(np.ceil(box.x1)))
            y0, y1 = max(0, height - int(np.ceil(box.y1))), min(height, height - int(np.floor(box.y0)))
            if x1 <= x0 or y1 <= y0:
                continue
            rgb = background[y0:y1, x0:x1, :3].astype(float) / 255
            rgba = np.asarray(to_rgba(text.get_color(), alpha=text.get_alpha()))
            foreground = rgba[:3] * rgba[3] + rgb * (1 - rgba[3])
            bg, fg = _luminance(rgb), _luminance(foreground)
            ratios = (np.maximum(bg, fg) + 0.05) / (np.minimum(bg, fg) + 0.05)
            ratio = float(np.median(ratios))
            if ratio < 3:
                warnings.append({"code": "annotation_low_contrast", "panel": panel_id, "text": text.get_text(), "contrast_ratio": round(ratio, 2), "message": "Annotation has low contrast against the plotted background; adjust text color or add a contrasting box."})
    return {
        "status": "warning" if warnings else "no_warnings",
        "warnings": warnings,
        "limitations": "Heuristic legend/line/bar/scatter-center overlap and unboxed annotation contrast checks; no proof of complete readability or publication readiness.",
    }
