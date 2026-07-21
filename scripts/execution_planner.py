"""Profile selection and machine-readable gate planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution_profiles import GATES, get_profile


class PlannerError(ValueError):
    """Raised when a requested profile and claim cannot be satisfied safely."""


@dataclass(frozen=True)
class ExecutionRequest:
    profile: str = "auto"
    claim: str | None = None
    has_input: bool = False
    has_reference: bool = False
    require_strict: bool = False
    enable_data_swap: bool = False
    verify_data_driven: bool = False
    create_bundle: bool = False
    release_acceptance: bool = False
    pdf_trace: bool = False
    has_boxed_text: bool = False
    preview_only: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExecutionPlan:
    selected_profile: str
    reason: str
    enabled_gates: tuple[str, ...]
    disabled_gates: tuple[str, ...]
    create_bundle: bool
    require_data_swap: bool
    require_changed_input_proof: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "sciplot.execution-plan.v1",
            "selected_profile": self.selected_profile,
            "reason": self.reason,
            "enabled_gates": list(self.enabled_gates),
            "disabled_gates": list(self.disabled_gates),
            "create_bundle": self.create_bundle,
            "require_data_swap": self.require_data_swap,
            "require_changed_input_proof": self.require_changed_input_proof,
        }


def _auto_profile(request: ExecutionRequest) -> tuple[str, str]:
    claim = (request.claim or "").lower()
    if request.pdf_trace:
        return "audit", "PDF trace requires the source-bound audit runner"
    if claim in {"release", "archival"} or request.create_bundle or request.release_acceptance:
        return "audit", "Archival, release, or bundle delivery requires audit gates"
    if claim == "reusable" or request.enable_data_swap or request.verify_data_driven:
        return "audit", "Reusable or explicitly data-driven verification requires audit gates"
    if request.require_strict:
        return "audit", "Strict reference fidelity requires the self-contained audit runner"
    if request.has_reference:
        return "audit", "Reference-backed visual fidelity is handled by the audit runner"
    if request.require_strict or request.has_reference or claim == "manuscript":
        return "standard", "Reference-backed or manuscript delivery needs semantic and vector QA"
    if request.preview_only or claim == "preview":
        return "quick", "Preview-only work does not need manuscript QA"
    return "standard", "Ordinary data-driven figure delivery defaults to standard"


def build_execution_plan(request: ExecutionRequest) -> ExecutionPlan:
    requested = request.profile.lower()
    if requested == "auto":
        selected, reason = _auto_profile(request)
    else:
        selected = requested
        reason = f"Explicit profile requested: {selected}"
        if request.require_strict and selected != "audit":
            raise PlannerError(f"{selected} profile cannot satisfy --require-strict; use audit or --profile auto")
        if request.has_reference and selected != "audit":
            raise PlannerError(f"{selected} profile cannot consume --source; use audit or --profile auto")
        if selected != "audit" and (request.claim or "").lower() in {"release", "archival", "reusable"}:
            raise PlannerError(f"{selected} profile cannot satisfy claim={request.claim}; use audit or --profile auto")
        if selected == "quick" and (request.claim or "").lower() == "manuscript":
            raise PlannerError("quick profile cannot satisfy claim=manuscript; use standard or --profile auto")
        if request.create_bundle and selected != "audit":
            raise PlannerError("bundle creation requires the audit profile; use --profile audit or --profile auto")
    profile = get_profile(selected)
    enabled = list(profile.required_gates)
    if request.has_boxed_text and "boxed_text_safety" not in enabled:
        enabled.append("boxed_text_safety")

    data_swap = request.enable_data_swap or request.verify_data_driven or (request.claim or "").lower() == "reusable"
    changed_proof = data_swap
    if data_swap:
        for gate in ("data_swap_template", "changed_input_proof"):
            if gate not in enabled:
                enabled.append(gate)
    if request.release_acceptance or (request.claim or "").lower() == "release":
        enabled.append("release_acceptance")
    if request.pdf_trace:
        enabled.append("pdf_trace")
    enabled = list(dict.fromkeys(enabled))
    disabled = tuple(gate for gate in GATES if gate not in enabled)
    return ExecutionPlan(
        selected_profile=selected,
        reason=reason,
        enabled_gates=tuple(enabled),
        disabled_gates=disabled,
        create_bundle=profile.create_bundle or request.create_bundle,
        require_data_swap=data_swap,
        require_changed_input_proof=changed_proof,
    )
