"""Immutable execution profile declarations for the unified SciPlot CLI."""

from __future__ import annotations

from dataclasses import dataclass


GATES = (
    "input_exists",
    "input_hash",
    "input_schema",
    "mapping_validation",
    "render_integrity",
    "basic_parseability",
    "path_isolation",
    "canvas_safety",
    "plot_geometry_safety",
    "boxed_text_safety",
    "semantic_audit",
    "vector_validation",
    "basic_checksums",
    "environment_summary",
    "bundle_structure",
    "runtime_freeze",
    "reproduction_entrypoint",
    "data_swap_template",
    "changed_input_proof",
    "bundle_lock",
    "environment_lock",
    "checksum_verification",
    "attestation",
    "portability",
    "portable_path_scan",
    "bundle_verification",
    "source_policy",
    "final_manifest_validation",
    "release_acceptance",
    "pdf_trace",
)


@dataclass(frozen=True)
class ExecutionProfile:
    name: str
    required_gates: tuple[str, ...]
    optional_gates: tuple[str, ...]
    default_outputs: tuple[str, ...]
    create_bundle: bool
    require_data_swap: bool
    require_changed_input_proof: bool


_QUICK = ExecutionProfile(
    name="quick",
    required_gates=(
        "input_exists",
        "input_hash",
        "input_schema",
        "mapping_validation",
        "render_integrity",
        "basic_parseability",
        "path_isolation",
        "canvas_safety",
    ),
    optional_gates=(),
    default_outputs=("png", "svg"),
    create_bundle=False,
    require_data_swap=False,
    require_changed_input_proof=False,
)

_STANDARD = ExecutionProfile(
    name="standard",
    required_gates=(
        *_QUICK.required_gates,
        "semantic_audit",
        "plot_geometry_safety",
        "vector_validation",
        "basic_checksums",
        "environment_summary",
        "final_manifest_validation",
    ),
    optional_gates=("boxed_text_safety",),
    default_outputs=("png", "svg", "pdf"),
    create_bundle=False,
    require_data_swap=False,
    require_changed_input_proof=False,
)

_AUDIT = ExecutionProfile(
    name="audit",
    required_gates=(
        "input_exists",
        "input_hash",
        "input_schema",
        "mapping_validation",
        "render_integrity",
        "basic_parseability",
        "path_isolation",
        "canvas_safety",
        "plot_geometry_safety",
        "semantic_audit",
        "vector_validation",
        "basic_checksums",
        "bundle_structure",
        "runtime_freeze",
        "reproduction_entrypoint",
        "bundle_lock",
        "environment_lock",
        "checksum_verification",
        "attestation",
        "portability",
        "portable_path_scan",
        "bundle_verification",
        "source_policy",
        "final_manifest_validation",
    ),
    optional_gates=("boxed_text_safety", "data_swap_template", "changed_input_proof", "release_acceptance", "pdf_trace"),
    default_outputs=("png", "svg", "pdf"),
    create_bundle=True,
    require_data_swap=False,
    require_changed_input_proof=False,
)

PROFILES = {profile.name: profile for profile in (_QUICK, _STANDARD, _AUDIT)}


def get_profile(name: str) -> ExecutionProfile:
    try:
        return PROFILES[str(name).lower()]
    except KeyError as exc:
        raise ValueError(f"unknown execution profile: {name}") from exc
