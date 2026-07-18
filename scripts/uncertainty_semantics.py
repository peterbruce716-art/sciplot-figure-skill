from __future__ import annotations

import math
import re
from typing import Any, Iterable


TOKEN_SEMANTICS = {
    "sd": "standard deviation",
    "std": "standard deviation",
    "stdev": "standard deviation",
    "standard_deviation": "standard deviation",
    "se": "standard error",
    "sem": "standard error",
    "stderr": "standard error",
    "standard_error": "standard error",
    "ci": "confidence interval",
    "ci95": "95% confidence interval",
    "95ci": "95% confidence interval",
    "95_ci": "95% confidence interval",
    "confidence_interval": "confidence interval",
    "error": "measurement uncertainty",
    "error_bar": "measurement uncertainty",
    "uncertainty": "measurement uncertainty",
    "sigma": "standard deviation",
    "yerr": "y uncertainty",
    "xerr": "x uncertainty",
    "误差": "measurement uncertainty",
    "标准差": "standard deviation",
    "标准误": "standard error",
    "置信区间": "confidence interval",
}

_PHRASES = sorted(TOKEN_SEMANTICS, key=lambda item: (-item.count("_"), -len(item), item))
_SINGLE_TOKENS = {item for item in TOKEN_SEMANTICS if "_" not in item}
_CHINESE_TERMS = [item for item in TOKEN_SEMANTICS if any("\u4e00" <= char <= "\u9fff" for char in item)]


class UncertaintySemanticError(ValueError):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), **self.details}


def normalize_column_name(name: str) -> tuple[str, list[str]]:
    text = str(name).strip()
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", text)
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", text).strip("_").lower()
    return normalized, [token for token in normalized.split("_") if token]


def infer_uncertainty_name(name: str) -> dict[str, Any]:
    normalized, tokens = normalize_column_name(name)
    matched: str | None = None
    match_type = "none"
    for term in _CHINESE_TERMS:
        if term in normalized:
            matched = term
            match_type = "phrase"
            break
    if matched is None:
        for phrase in _PHRASES:
            if "_" in phrase and (normalized == phrase or f"_{phrase}_" in f"_{normalized}_"):
                matched = phrase
                match_type = "token_sequence"
                break
    if matched is None:
        for token in tokens:
            if token in _SINGLE_TOKENS:
                matched = token
                match_type = "token"
                break
    return {
        "is_uncertainty": matched is not None,
        "match_type": match_type,
        "matched_token": matched,
        "confidence": 0.95 if matched is not None else 0.0,
        "source": "name_inference",
        "normalized_name": normalized,
        "semantics": TOKEN_SEMANTICS.get(matched) if matched else None,
    }


def _override_enabled(override: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(override, dict)
        and override.get("enabled") is True
        and override.get("user_specified") is True
        and isinstance(override.get("reason"), str)
        and override["reason"].strip()
    )


def _finite_numbers(values: Iterable[Any]) -> list[float]:
    result: list[float] = []
    for value in values:
        if isinstance(value, bool):
            raise ValueError
        number = float(value)
        if not math.isfinite(number):
            raise ValueError
        result.append(number)
    return result


def _validate_evidence_trace(evidence: dict[str, Any], *, uncertainty_column: str) -> None:
    source = evidence.get("source")
    if source not in {"explicit", "name_inference", "metadata"}:
        raise UncertaintySemanticError("uncertainty_evidence_missing", "uncertainty evidence source must be explicit, name_inference, or metadata")
    if source == "explicit" and evidence.get("column") not in {None, uncertainty_column} and not evidence.get("user_specified"):
        raise UncertaintySemanticError("uncertainty_source_mismatch", "explicit uncertainty evidence names a different source column")
    if source == "name_inference":
        if not evidence.get("matched_token") or evidence.get("match_type") in {None, "none"} or float(evidence.get("confidence") or 0.0) <= 0.0:
            raise UncertaintySemanticError("uncertainty_evidence_missing", "name-inferred uncertainty requires matched token, match type, and positive confidence")


def validate_uncertainty_values(
    measurement_values: Iterable[Any],
    uncertainty_values: Iterable[Any],
    *,
    measurement_column: str,
    uncertainty_column: str,
    evidence: dict[str, Any] | None,
    override: dict[str, Any] | None = None,
    require_semantics: bool = True,
) -> dict[str, Any]:
    allow_override = _override_enabled(override)
    measurement = list(measurement_values)
    uncertainty = list(uncertainty_values)
    if measurement_column == uncertainty_column and not allow_override:
        raise UncertaintySemanticError(
            "uncertainty_same_as_measurement",
            "measurement and uncertainty must use independent source columns",
            measurement_column=measurement_column,
            uncertainty_column=uncertainty_column,
        )
    if len(measurement) != len(uncertainty):
        raise UncertaintySemanticError(
            "uncertainty_length_mismatch",
            "uncertainty values must have the same row count as the measurement",
            measurement_count=len(measurement),
            uncertainty_count=len(uncertainty),
        )
    try:
        measurement_numbers = _finite_numbers(measurement)
        uncertainty_numbers = _finite_numbers(uncertainty)
    except (TypeError, ValueError):
        raise UncertaintySemanticError("uncertainty_non_numeric", "uncertainty values must be finite numeric values") from None
    if any(value < 0 for value in uncertainty_numbers):
        raise UncertaintySemanticError("uncertainty_negative", "uncertainty values must be non-negative")
    if measurement_numbers == uncertainty_numbers and not allow_override:
        raise UncertaintySemanticError(
            "uncertainty_duplicates_measurement",
            "uncertainty values are an exact row-wise copy of the measurement values",
            measurement_column=measurement_column,
            uncertainty_column=uncertainty_column,
        )
    if not isinstance(evidence, dict):
        raise UncertaintySemanticError("uncertainty_evidence_missing", "uncertainty mapping requires traceable identification evidence")
    semantics = evidence.get("semantics")
    if require_semantics and (not isinstance(semantics, str) or not semantics.strip() or semantics.strip().lower() == "unknown"):
        raise UncertaintySemanticError("uncertainty_definition_unknown", "error bars require a declared or auditable uncertainty definition")
    _validate_evidence_trace(evidence, uncertainty_column=uncertainty_column)
    return {
        "status": "pass",
        "measurement_column": measurement_column,
        "uncertainty_column": uncertainty_column,
        "row_count": len(measurement_numbers),
        "checks": {
            "independent_source_column": "pass" if measurement_column != uncertainty_column else "overridden",
            "numeric": "pass",
            "length_match": "pass",
            "non_negative": "pass",
            "not_measurement_copy": "pass" if measurement_numbers != uncertainty_numbers else "overridden",
            "definition_known": "pass" if require_semantics else ("pass" if isinstance(semantics, str) and semantics.strip() and semantics.strip().lower() != "unknown" else "pending_confirmation"),
            "traceable_source": "pass",
        },
        "evidence": evidence,
        "override": override if allow_override else None,
    }


def inspect_uncertainty_values(
    measurement_values: Iterable[Any],
    uncertainty_values: Iterable[Any],
    *,
    measurement_column: str,
    uncertainty_column: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    try:
        return validate_uncertainty_values(
            measurement_values,
            uncertainty_values,
            measurement_column=measurement_column,
            uncertainty_column=uncertainty_column,
            evidence=evidence,
            require_semantics=False,
        )
    except UncertaintySemanticError as exc:
        return {"status": "failed", "errors": [exc.as_dict()]}
