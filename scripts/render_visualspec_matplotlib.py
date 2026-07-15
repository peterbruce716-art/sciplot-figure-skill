from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from data_resolver import resolve_series
from visualspec import load_json, make_manifest, manifest_overall_status, require_valid_visualspec, write_json

from portable_paths import portable_path
from audit_semantics import extract_matplotlib_semantics


def _series(data: dict[str, Any], key: str, *, base_dir: Path | None = None) -> list[float]:
    return [float(v) for v in resolve_series(data, key, base_dir=base_dir)]


def _apply_axes(ax: Any, panel: dict[str, Any]) -> None:
    axes = panel.get("axes") or {}
    for axis_name, setter, scale_setter in [("x", ax.set_xlim, ax.set_xscale), ("y", ax.set_ylim, ax.set_yscale)]:
        axis = axes.get(axis_name) or {}
        if axis.get("scale"):
            scale_setter(axis["scale"])
        if axis.get("limits"):
            setter(axis["limits"])
        if axis.get("ticks"):
            (ax.set_xticks if axis_name == "x" else ax.set_yticks)(axis["ticks"])
        if axis.get("label"):
            (ax.set_xlabel if axis_name == "x" else ax.set_ylabel)(axis["label"])


def _tag_artist(artist: Any, *, ptype: str, index: int, extra: dict[str, Any] | None = None) -> None:
    try:
        setattr(artist, "_visualspec_plot_type", ptype)
        setattr(artist, "_visualspec_plot_index", index)
        for key, value in (extra or {}).items():
            setattr(artist, key, value)
    except Exception:
        pass


def _draw_plot(ax: Any, plot: dict[str, Any], *, base_dir: Path | None = None, plot_index: int = 0) -> None:
    ptype = plot.get("type")
    data = plot.get("data") or {}
    style = plot.get("style") or {}
    label = plot.get("label")
    color = style.get("color")
    if ptype == "line":
        (line,) = ax.plot(
            _series(data, "x", base_dir=base_dir),
            _series(data, "y", base_dir=base_dir),
            label=label,
            color=color,
            linewidth=style.get("line_width_pt", 1.2),
            linestyle=style.get("line_style", "solid"),
            marker=style.get("marker", None),
            alpha=style.get("alpha", None),
        )
        _tag_artist(line, ptype="line", index=plot_index)
    elif ptype == "scatter":
        artist = ax.scatter(
            _series(data, "x", base_dir=base_dir),
            _series(data, "y", base_dir=base_dir),
            label=label,
            color=color,
            s=style.get("marker_size_pt2", 18),
            marker=style.get("marker", "o"),
            alpha=style.get("alpha", None),
        )
        _tag_artist(artist, ptype="scatter", index=plot_index)
    elif ptype == "errorbar":
        yerr = _series(data, "yerr", base_dir=base_dir)
        container = ax.errorbar(
            _series(data, "x", base_dir=base_dir),
            _series(data, "y", base_dir=base_dir),
            yerr=yerr,
            label=label,
            color=color,
            linewidth=style.get("line_width_pt", 1.0),
            linestyle=style.get("line_style", "solid"),
            marker=style.get("marker", None),
            alpha=style.get("alpha", None),
            capsize=style.get("capsize", 3),
        )
        _tag_artist(container.lines[0], ptype="errorbar", index=plot_index)
        for capline in container.lines[1]:
            _tag_artist(capline, ptype="errorbar_cap", index=plot_index)
        for barlinecol in container.lines[2]:
            _tag_artist(barlinecol, ptype="errorbar_yerr", index=plot_index)
    elif ptype == "fill_between":
        artist = ax.fill_between(_series(data, "x", base_dir=base_dir), _series(data, "y1", base_dir=base_dir), _series(data, "y2", base_dir=base_dir), color=color or "#cccccc", alpha=style.get("alpha", 0.35), label=label)
        _tag_artist(artist, ptype="fill_between", index=plot_index)
    elif ptype == "grouped_bar":
        x = np.asarray(_series(data, "x", base_dir=base_dir))
        groups = data.get("groups") or []
        width = float(style.get("bar_width", 0.28))
        widths = [float(value) for value in style.get("bar_widths", [width] * len(groups))]
        if len(widths) != len(groups):
            raise ValueError("grouped_bar style.bar_widths must match the number of groups")
        mode = style.get("group_mode", "side_by_side")
        group_step = float(style.get("group_offset", 0.0 if mode == "overlap" else width))
        explicit_offsets = style.get("group_offsets")
        if explicit_offsets is not None and len(explicit_offsets) != len(groups):
            raise ValueError("grouped_bar style.group_offsets must match the number of groups")
        for i, group in enumerate(groups):
            values = [float(v) for v in group.get("y", [])]
            center_offset = float(explicit_offsets[i]) if explicit_offsets is not None else (i - (len(groups) - 1) / 2) * group_step
            bars = ax.bar(x + center_offset, values, width=widths[i], label=group.get("label"), color=group.get("color"), alpha=style.get("alpha", None))
            for bar in bars:
                _tag_artist(bar, ptype="grouped_bar", index=plot_index, extra={"_visualspec_group_index": i, "_visualspec_group_count": len(groups)})
                bar._visualspec_group_offset = group_step
                bar._visualspec_group_mode = mode
                bar._visualspec_group_center_offset = center_offset
    elif ptype == "stacked_bar":
        x = np.asarray(_series(data, "x", base_dir=base_dir))
        bottom = np.zeros_like(x, dtype=float)
        for group_index, group in enumerate(data.get("groups") or []):
            values = np.asarray([float(v) for v in group.get("y", [])])
            bars = ax.bar(x, values, bottom=bottom, width=style.get("bar_width", 0.6), label=group.get("label"), color=group.get("color"), alpha=style.get("alpha", None))
            for bar in bars:
                _tag_artist(bar, ptype="stacked_bar", index=plot_index, extra={"_visualspec_group_index": group_index})
            bottom += values
    elif ptype == "heatmap":
        z = np.asarray(data.get("z"), dtype=float)
        image = ax.imshow(z, origin="lower", aspect=style.get("aspect", "auto"), cmap=style.get("cmap", "viridis"), vmin=style.get("vmin"), vmax=style.get("vmax"))
        _tag_artist(image, ptype="heatmap", index=plot_index)
        if plot.get("colorbar", False):
            plt.colorbar(image, ax=ax)
    elif ptype == "contour":
        x = np.asarray(data.get("x"), dtype=float)
        y = np.asarray(data.get("y"), dtype=float)
        z = np.asarray(data.get("z"), dtype=float)
        raw_levels = style.get("levels", 8)
        if isinstance(raw_levels, list):
            levels = [float(value) for value in raw_levels]
        else:
            count = max(2, int(raw_levels))
            levels = [float(value) for value in np.linspace(float(np.nanmin(z)), float(np.nanmax(z)), count)]
        contour = ax.contourf(x, y, z, levels=levels, cmap=style.get("cmap", "viridis"), alpha=style.get("alpha", None))
        collections = getattr(contour, "collections", None) or getattr(contour, "_collections", None) or []
        for collection in collections:
            _tag_artist(collection, ptype="contour", index=plot_index)
        setattr(contour, "_visualspec_plot_type", "contour")
        setattr(contour, "_visualspec_plot_index", plot_index)
        from audit_semantics import _hash_array, _hash_values

        setattr(
            contour,
            "_visualspec_semantics",
            {
                "x_hash": _hash_values([float(value) for value in x.reshape(-1)]),
                "y_hash": _hash_values([float(value) for value in y.reshape(-1)]),
                "z_hash": _hash_array(z),
                "shape": [int(z.shape[0]) if z.ndim else 0, int(z.shape[1]) if z.ndim > 1 else 0],
            },
        )
        ax._visualspec_contour_sets = getattr(ax, "_visualspec_contour_sets", []) + [contour]
        if plot.get("colorbar", False):
            plt.colorbar(contour, ax=ax)
    else:
        raise ValueError(f"unsupported plot type: {ptype}")


def _draw_annotation(ax: Any, annotation: dict[str, Any]) -> None:
    atype = annotation.get("type")
    coords = annotation.get("coordinates", [])
    style = annotation.get("style") or {}
    transform = ax.transAxes if annotation.get("coordinate_space", "data") == "axes_fraction" else ax.transData
    if atype == "text":
        text = ax.text(
            coords[0],
            coords[1],
            annotation.get("text", ""),
            transform=transform,
            fontsize=style.get("font_size_pt", 9),
            color=style.get("color", "black"),
            ha=style.get("ha", "center"),
            va=style.get("va", "center"),
            rotation=style.get("rotation", 0),
            fontweight=style.get("fontweight", "normal"),
            fontstyle=style.get("fontstyle", "normal"),
        )
        text._visualspec_annotation_type = "text"
        text._visualspec_coordinate_space = annotation.get("coordinate_space", "data")
    elif atype == "arrow":
        ann = ax.annotate("", xy=(coords[2], coords[3]), xytext=(coords[0], coords[1]), xycoords=transform, textcoords=transform, arrowprops={"arrowstyle": style.get("arrowstyle", "->"), "color": style.get("color", "black"), "linewidth": style.get("line_width_pt", 1.0)})
        ann._visualspec_annotation_type = "arrow"
        ann._visualspec_coordinate_space = annotation.get("coordinate_space", "data")
        ann.arrow_patch._visualspec_arrowstyle = style.get("arrowstyle", "->")
        ann.arrow_patch._visualspec_coordinate_space = annotation.get("coordinate_space", "data")
    elif atype == "rectangle":
        from matplotlib.patches import Rectangle

        patch = Rectangle((coords[0], coords[1]), coords[2], coords[3], transform=transform, fill=style.get("fill", False), facecolor=style.get("facecolor", "none"), edgecolor=style.get("edgecolor", "black"), linewidth=style.get("line_width_pt", 1.0), linestyle=style.get("line_style", "solid"), alpha=style.get("alpha", None), hatch=style.get("hatch", None), zorder=style.get("zorder", 1))
        patch._visualspec_annotation_type = "rectangle"
        patch._visualspec_coordinate_space = annotation.get("coordinate_space", "data")
        ax.add_patch(patch)
    elif atype == "polygon":
        from matplotlib.patches import Polygon

        points = [(float(x), float(y)) for x, y in coords]
        patch = Polygon(points, transform=transform, closed=True, fill=style.get("fill", False), facecolor=style.get("facecolor", "none"), edgecolor=style.get("edgecolor", "black"), linewidth=style.get("line_width_pt", 1.0), linestyle=style.get("line_style", "solid"), alpha=style.get("alpha", None), hatch=style.get("hatch", None), zorder=style.get("zorder", 1))
        patch._visualspec_annotation_type = "polygon"
        patch._visualspec_coordinate_space = annotation.get("coordinate_space", "data")
        ax.add_patch(patch)
    else:
        raise ValueError(f"unsupported annotation type: {atype}")


def _lock_rcparams(spec: dict[str, Any]) -> None:
    os.environ.setdefault("SOURCE_DATE_EPOCH", "0")
    theme = spec.get("theme") or {}
    font = theme.get("font") or {}
    candidates = font.get("family_candidates") or [font.get("family"), "Liberation Sans", "DejaVu Sans", "STIXGeneral"]
    candidates = [item for item in candidates if item]
    available: list[str] = []
    for candidate in candidates:
        try:
            font_manager.findfont(candidate, fallback_to_default=False)
            available.append(candidate)
        except Exception:
            continue
    if not available:
        available = ["DejaVu Sans"]
    resolved = font_manager.FontProperties(family=available).get_name()
    plt.rcParams.update(
        {
            "font.family": available,
            "font.size": float(font.get("size_pt", 8)),
            "mathtext.fontset": font.get("mathtext_fontset", "stix"),
            "axes.linewidth": float((theme.get("axes") or {}).get("line_width_pt", 0.8)),
            "svg.fonttype": "none",
            "svg.hashsalt": "scientificfigure-v2",
            "pdf.fonttype": 42,
            "savefig.facecolor": (spec.get("figure") or {}).get("background", "white"),
            "savefig.pad_inches": 0,
        }
    )
    spec.setdefault("_resolved_runtime", {})["font"] = resolved


def render_visualspec(spec: dict[str, Any], output_dir: Path, spec_path: str = "", script_path: str | None = None) -> dict[str, Any]:
    require_valid_visualspec(spec)
    output_dir.mkdir(parents=True, exist_ok=True)
    _lock_rcparams(spec)
    figure_cfg = spec["figure"]
    width_mm, height_mm = [float(v) for v in figure_cfg["size_mm"]]
    dpi = int(figure_cfg.get("dpi", 300))
    crop_mode = figure_cfg.get("crop_mode", "fixed_canvas")
    bbox_inches = "tight" if crop_mode == "content_tight" else None
    spec_base = Path(spec_path).resolve().parent if spec_path else None
    fig = plt.figure(figsize=(width_mm / 25.4, height_mm / 25.4), dpi=dpi, facecolor=figure_cfg.get("background", "white"))
    for panel in spec["panels"]:
        ax = fig.add_axes(panel["bbox_normalized"])
        ax._visualspec_panel_id = str(panel.get("id", "panel"))
        _apply_axes(ax, panel)
        for plot_index, plot in enumerate(panel.get("plots", [])):
            _draw_plot(ax, plot, base_dir=spec_base, plot_index=plot_index)
        for annotation in panel.get("annotations", []):
            _draw_annotation(ax, annotation)
        if any(plot.get("label") for plot in panel.get("plots", [])) or any(group.get("label") for plot in panel.get("plots", []) for group in (plot.get("data") or {}).get("groups", [])):
            ax.legend(frameon=False, fontsize=8)
    png = output_dir / "render.png"
    svg = output_dir / "render.svg"
    pdf = output_dir / "render.pdf"
    project_root = output_dir.parent if output_dir.name == "outputs" else output_dir
    metadata = {"Creator": "scientific-figure-reproduction", "Date": None}
    fig.savefig(png, dpi=dpi, bbox_inches=bbox_inches, pad_inches=0, metadata={"Software": "scientific-figure-reproduction"})
    fig.savefig(svg, bbox_inches=bbox_inches, pad_inches=0, metadata=metadata)
    fig.savefig(pdf, bbox_inches=bbox_inches, pad_inches=0, metadata={"Creator": "scientific-figure-reproduction", "Producer": "scientific-figure-reproduction", "CreationDate": None, "ModDate": None})
    semantics = extract_matplotlib_semantics(fig, figure_id=str(figure_cfg.get("id", "figure_1")))
    plt.close(fig)
    write_json(output_dir / "render_semantics.json", semantics)
    manifest = make_manifest(spec_path=portable_path(spec_path, project_root) or "", output_dir=portable_path(output_dir, project_root) or output_dir.name)
    exports_ok = all(path.exists() and path.stat().st_size > 0 for path in [png, svg, pdf])
    panel_sources = [panel.get("source_crop") for panel in spec["panels"] if panel.get("source_crop")]
    panel_strategies = {panel.get("source_strategy", "raw_data") for panel in spec["panels"]}
    panel_representations = {panel.get("representation", "semantic_vector") for panel in spec["panels"]}
    figure_id = str(figure_cfg.get("id", "figure_1"))
    panels = {}
    for panel in spec["panels"]:
        panel_id = panel.get("id", "figure")
        panels[panel_id] = {
            "bbox_normalized": panel.get("bbox_normalized"),
            "source": panel.get("source_crop"),
            "source_strategy": panel.get("source_strategy", "raw_data"),
            "representation": panel.get("representation", "semantic_vector"),
            "qa": {"execution_status": "not_run", "result": "not_applicable", "score_report": None},
        }
    source_strategy = panel_strategies.pop() if len(panel_strategies) == 1 else "mixed"
    representation = panel_representations.pop() if len(panel_representations) == 1 else "mixed"
    figures = {
        figure_id: {
            "source": panel_sources[0] if len(panel_sources) == 1 else None,
            "spec": portable_path(spec_path, project_root) if spec_path else None,
            "script": portable_path(script_path, project_root) if script_path else None,
            "runner": portable_path(Path(__file__).resolve(), project_root),
            "exports": {"png": portable_path(png, project_root), "svg": portable_path(svg, project_root), "pdf": portable_path(pdf, project_root)},
            "qa": {"execution_status": "not_run", "result": "not_applicable", "score_report": None},
            "source_strategy": source_strategy,
            "representation": representation,
            "status": "render_only",
            "panels": panels,
        }
    }
    per_figure_scripts = {figure_id: portable_path(script_path, project_root)} if script_path else {}
    manifest.update(
        {
            "source_code_status": "pass" if script_path else "incomplete",
            "render_status": "pass",
            "raster_export_status": "pass" if png.exists() and png.stat().st_size > 0 else "failed",
            "vector_export_status": "pass" if all(path.exists() and path.stat().st_size > 0 for path in [svg, pdf]) else "failed",
            "export_status": "pass" if exports_ok else "failed",
            "vector_validation_status": "not_run",
            "semantic_reconstruction_status": "not_run",
            "visual_qa_status": "not_run",
            "qa_status": "not_run",
            "status": "render_only",
            "source_strategy": source_strategy,
            "representation": representation,
            "exports": {"png": portable_path(png, project_root), "svg": portable_path(svg, project_root), "pdf": portable_path(pdf, project_root)},
            "semantics": portable_path(output_dir / "render_semantics.json", project_root),
            "figures": figures,
            "per_figure_scripts": per_figure_scripts,
            "backend": "python_matplotlib",
            "crop_mode": crop_mode,
            "resolved_fonts": {"default": spec.get("_resolved_runtime", {}).get("font", "unknown")},
        }
    )
    manifest["overall_status"] = manifest_overall_status(manifest)
    write_json(output_dir / "render_manifest.json", manifest)
    return manifest


def render_file(spec_path: Path | str, output_dir: Path | str, script_path: Path | str | None = None) -> dict[str, Any]:
    spec_file = Path(spec_path)
    return render_visualspec(
        load_json(spec_file),
        Path(output_dir),
        spec_path=str(spec_file),
        script_path=str(script_path) if script_path else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render scientificfigure.visualspec.v2 with Matplotlib.")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--script", type=Path, help="Runnable per-figure script path to record in the manifest.")
    args = parser.parse_args()
    manifest = render_file(args.spec, args.out_dir, script_path=args.script)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["render_status"] == "pass" and manifest["export_status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
