from __future__ import annotations

from capability_model import ANNOTATION_CAPABILITIES, PLOT_CAPABILITIES, SUPPORTED_ANNOTATION_TYPES, SUPPORTED_PLOT_TYPES

PLOT_RENDERERS = {name: capability.renderer for name, capability in PLOT_CAPABILITIES.items()}
PLOT_SEMANTIC_EXTRACTORS = {name: capability.semantic_extractor for name, capability in PLOT_CAPABILITIES.items()}
PLOT_CAPABILITY_STATUS = {name: capability.status for name, capability in PLOT_CAPABILITIES.items()}
PLOT_STRICT_FIELDS = {name: sorted(capability.strict_fields) for name, capability in PLOT_CAPABILITIES.items()}

ANNOTATION_RENDERERS = {name: str(capability["renderer"]) for name, capability in ANNOTATION_CAPABILITIES.items()}
ANNOTATION_SEMANTIC_EXTRACTORS = {name: str(capability["semantic_extractor"]) for name, capability in ANNOTATION_CAPABILITIES.items()}

PROJECT_SCRIPT_ONLY_ANNOTATIONS = {
    "region_fill",
    "gradient_fill",
    "masked_image",
    "clip_path",
    "hatch_region",
    "poly_collection",
    "path_patch",
    "circle",
    "ellipse",
    "arc",
    "bezier_path",
    "dimension_arrow",
}
