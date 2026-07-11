from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlotCapability:
    name: str
    renderer: str
    semantic_extractor: str
    required_data: frozenset[str]
    style_fields: frozenset[str]
    strict_fields: frozenset[str]
    status: str
    strict_supported: bool


PLOT_CAPABILITIES = {
    "line": PlotCapability("line", "draw_line", "extract_line_semantics", frozenset({"x", "y"}), frozenset({"color", "line_width_pt", "line_style", "marker", "alpha"}), frozenset({"x_hash", "y_hash", "point_count"}), "strict_supported", True),
    "scatter": PlotCapability("scatter", "draw_scatter", "extract_scatter_semantics", frozenset({"x", "y"}), frozenset({"color", "marker_size_pt2", "marker", "alpha"}), frozenset({"x_hash", "y_hash", "point_count"}), "strict_supported", True),
    "errorbar": PlotCapability("errorbar", "draw_errorbar", "extract_errorbar_semantics", frozenset({"x", "y", "yerr"}), frozenset({"color", "line_width_pt", "line_style", "capsize", "marker", "alpha"}), frozenset({"x_hash", "y_hash", "yerr_hash", "point_count"}), "strict_supported", True),
    "fill_between": PlotCapability("fill_between", "draw_fill_between", "extract_fill_between_semantics", frozenset({"x", "y1", "y2"}), frozenset({"color", "alpha"}), frozenset({"x_hash", "y1_hash", "y2_hash", "point_count"}), "strict_supported", True),
    "grouped_bar": PlotCapability("grouped_bar", "draw_grouped_bar", "extract_bar_semantics", frozenset({"x", "groups"}), frozenset({"bar_width", "alpha"}), frozenset({"x_hash", "groups", "point_count"}), "strict_supported", True),
    "stacked_bar": PlotCapability("stacked_bar", "draw_stacked_bar", "extract_bar_semantics", frozenset({"x", "groups"}), frozenset({"bar_width", "alpha"}), frozenset({"x_hash", "groups", "point_count"}), "strict_supported", True),
    "heatmap": PlotCapability("heatmap", "draw_heatmap", "extract_heatmap_semantics", frozenset({"z"}), frozenset({"aspect", "cmap", "vmin", "vmax"}), frozenset({"z_hash", "shape"}), "strict_supported", True),
    "contour": PlotCapability("contour", "draw_contour", "extract_contour_semantics", frozenset({"x", "y", "z"}), frozenset({"levels", "cmap", "alpha"}), frozenset({"x_hash", "y_hash", "z_hash", "shape", "levels_hash", "level_count"}), "strict_supported", True),
}


ANNOTATION_CAPABILITIES = {
    "text": {"renderer": "draw_text", "semantic_extractor": "extract_text_annotation", "status": "strict_supported"},
    "arrow": {"renderer": "draw_arrow", "semantic_extractor": "extract_arrow_annotation", "status": "strict_supported"},
    "rectangle": {"renderer": "draw_rectangle", "semantic_extractor": "extract_rectangle_annotation", "status": "strict_supported"},
    "polygon": {"renderer": "draw_polygon", "semantic_extractor": "extract_polygon_annotation", "status": "strict_supported"},
}


SUPPORTED_PLOT_TYPES = frozenset(PLOT_CAPABILITIES)
SUPPORTED_ANNOTATION_TYPES = frozenset(ANNOTATION_CAPABILITIES)


def plot_style_keys(plot_type: str) -> frozenset[str]:
    capability = PLOT_CAPABILITIES.get(plot_type)
    return capability.style_fields if capability else frozenset()


def plot_strict_fields(plot_type: str) -> frozenset[str]:
    capability = PLOT_CAPABILITIES.get(plot_type)
    return capability.strict_fields if capability else frozenset()
