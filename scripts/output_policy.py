"""Output format selection for profile-aware SciPlot runs."""

from __future__ import annotations

from dataclasses import dataclass


VALID_OUTPUTS = ("png", "svg", "pdf")
VECTOR_KINDS = {"line", "scatter", "bar", "errorbar", "grouped_bar", "stacked_bar", "mechanism", "schematic"}
RASTER_KINDS = {"heatmap", "contour", "micrograph", "ebsd", "image", "color_region_extraction"}


@dataclass(frozen=True)
class OutputSelection:
    requested: str
    formats: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"requested": self.requested, "resolved": list(self.formats), "reason": self.reason}


def _normalize(value: str) -> tuple[str, ...]:
    values = tuple(dict.fromkeys(item.strip().lower() for item in value.split(",") if item.strip()))
    invalid = sorted(set(values) - set(VALID_OUTPUTS))
    if invalid:
        raise ValueError(f"unsupported output format(s): {', '.join(invalid)}")
    if not values:
        raise ValueError("at least one output format is required")
    return values


def resolve_outputs(
    requested: str,
    *,
    profile: str,
    plot_kinds: set[str],
    preview_only: bool = False,
    pdf_trace: bool = False,
) -> OutputSelection:
    requested = requested.lower()
    if requested != "auto":
        formats = _normalize(requested)
        return OutputSelection(requested=requested, formats=formats, reason="Explicit output formats")
    if pdf_trace:
        return OutputSelection(requested="auto", formats=("png", "pdf"), reason="PDF trace preserves raster evidence and the PDF contract")
    if preview_only:
        return OutputSelection(requested="auto", formats=("png",), reason="Preview-only output")
    raster_dominant = bool(plot_kinds) and plot_kinds.issubset(RASTER_KINDS)
    if raster_dominant:
        formats = ("png",) if profile == "quick" else ("png", "pdf")
        return OutputSelection(requested="auto", formats=formats, reason="Raster-dominant scientific image")
    formats = ("png", "svg") if profile == "quick" else ("png", "svg", "pdf")
    return OutputSelection(requested="auto", formats=formats, reason="Semantic vector-compatible plot")
