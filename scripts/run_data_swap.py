from __future__ import annotations

"""Run a declared data-swap renderer in an isolated output directory."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path, PureWindowsPath
from typing import Any

from validate_data_swap_template import validate_template
from visualspec import _json_schema_errors, schema_path


class DataSwapValidationError(ValueError):
    """Fail-closed error with a stable machine-readable code."""

    def __init__(self, code: str, message: str, *, figure: str | None = None, format: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.figure = figure
        self.format = format

    def to_payload(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.figure is not None:
            error["figure"] = self.figure
        if self.format is not None:
            error["format"] = self.format
        return {"status": "failed", "error": error}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_renderer_logs(out_dir: Path, completed: subprocess.CompletedProcess[str]) -> dict[str, str]:
    """Persist renderer chatter so this runner's stdout stays machine-readable JSON."""

    log_paths: dict[str, str] = {}
    logs_dir = out_dir / "runner_logs"
    for stream_name, text in (("stdout", completed.stdout), ("stderr", completed.stderr)):
        if not text:
            continue
        logs_dir.mkdir(parents=True, exist_ok=True)
        path = logs_dir / f"renderer_{stream_name}.txt"
        path.write_text(text, encoding="utf-8")
        log_paths[stream_name] = path.relative_to(out_dir).as_posix()
    return log_paths


def _norm(path: Path) -> str:
    return os.path.normcase(str(path))


def _same_path(left: Path, right: Path) -> bool:
    return _norm(left) == _norm(right)


def _same_or_descendant(candidate: Path, parent: Path) -> bool:
    candidate_text = _norm(candidate)
    parent_text = _norm(parent)
    if candidate_text == parent_text:
        return True
    try:
        return os.path.commonpath([candidate_text, parent_text]) == parent_text
    except ValueError:
        return False



def _manifest_path_uses_portable_relative_syntax(raw_path: str) -> bool:
    """Return True only for portable POSIX-style relative manifest paths."""

    if "\\" in raw_path:
        return False
    windows_path = PureWindowsPath(raw_path)
    if windows_path.drive or windows_path.root:
        return False
    return True


def ensure_output_isolated(data_path: Path, out_dir: Path) -> None:
    """Reject outputs that equal or live under the input data directory."""

    data_file = data_path.resolve(strict=True)
    data_dir = data_file.parent
    output = out_dir.resolve(strict=False)

    if _same_path(output, data_file):
        raise DataSwapValidationError(
            "output_equals_input_data",
            "Output directory cannot equal the input data file.",
        )
    if _same_or_descendant(output, data_dir):
        raise DataSwapValidationError(
            "output_directory_inside_input_data",
            "Output directory must be outside the input data directory.",
        )


def resolve_output_path_safely(out_dir: Path, raw_path: str, *, data_path: Path) -> Path:
    """Resolve a manifest output path and prove it remains inside out_dir."""

    if not isinstance(raw_path, str) or not raw_path:
        raise DataSwapValidationError("output_path_invalid", "Output path must be a non-empty relative path.")
    if not _manifest_path_uses_portable_relative_syntax(raw_path):
        raise DataSwapValidationError(
            "output_path_escape",
            "Output path must be a portable POSIX-style relative path, not a Windows or backslash-separated path.",
        )
    raw = Path(raw_path)
    if raw.is_absolute() or ".." in raw.parts:
        raise DataSwapValidationError("output_path_escape", "Output path must be relative and must not contain parent components.")

    output_root = out_dir.resolve(strict=True)
    candidate = output_root / raw
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise DataSwapValidationError("missing_declared_output", "Template-declared output file is missing.") from exc

    if not _same_or_descendant(resolved, output_root):
        raise DataSwapValidationError("output_path_escape", "Output path resolves outside the isolated output directory.")
    if not resolved.is_file():
        raise DataSwapValidationError("missing_declared_output", "Template-declared output path is not a file.")

    data_file = data_path.resolve(strict=True)
    data_dir = data_file.parent
    if _same_path(resolved, data_file) or _same_or_descendant(resolved, data_dir):
        raise DataSwapValidationError("output_path_points_to_input", "Output path must not point to the input file or input data directory.")
    return resolved


def validate_run_manifest(
    manifest: dict[str, Any],
    *,
    template_record: dict[str, Any],
    figure_id: str,
    data_path: Path,
    expected_input_sha256: str,
    out_dir: Path,
    input_mode: str,
) -> dict[str, Any]:
    """Validate a renderer-emitted data-swap manifest using independent hashes."""

    schema_errors = _json_schema_errors(manifest, schema_path("data-swap-run-v1.schema.json"))
    if schema_errors:
        raise DataSwapValidationError(
            "run_manifest_schema_invalid",
            "Data-swap run manifest failed schema validation: " + "; ".join(schema_errors),
            figure=figure_id,
        )
    if manifest.get("figure") != figure_id:
        raise DataSwapValidationError("manifest_figure_mismatch", "Renderer manifest figure does not match the requested figure.", figure=figure_id)
    if manifest.get("input_mode") != input_mode:
        raise DataSwapValidationError("input_mode_mismatch", "Renderer manifest input_mode mismatch.", figure=figure_id)
    if manifest.get("historical_data_consumed") is not False:
        raise DataSwapValidationError("historical_data_consumed", "Renderer manifest must set historical_data_consumed=false.", figure=figure_id)

    actual_input_sha256 = sha256_file(data_path)
    if actual_input_sha256 != expected_input_sha256:
        raise DataSwapValidationError("input_sha256_mismatch", "Input data file changed during data-swap execution.", figure=figure_id)
    declared_input = manifest.get("input", {})
    if declared_input.get("sha256") != expected_input_sha256:
        raise DataSwapValidationError("input_sha256_mismatch", "Declared input hash does not match the original input file.", figure=figure_id)

    expected_outputs = set(template_record.get("outputs", []))
    declared_outputs = manifest.get("outputs", {})
    actual_formats = set(declared_outputs)
    if actual_formats != expected_outputs:
        raise DataSwapValidationError("output_format_mismatch", "Renderer manifest outputs must exactly match the template-declared formats.", figure=figure_id)

    checked_outputs: dict[str, dict[str, str]] = {}
    output_root = out_dir.resolve(strict=True)
    for fmt in sorted(expected_outputs):
        record = declared_outputs.get(fmt)
        if not isinstance(record, dict):
            raise DataSwapValidationError("missing_declared_output", "Template-declared output record is missing.", figure=figure_id, format=fmt)
        output_path = resolve_output_path_safely(output_root, str(record.get("path", "")), data_path=data_path)
        actual_output_sha256 = sha256_file(output_path)
        if record.get("sha256") != actual_output_sha256:
            raise DataSwapValidationError("output_sha256_mismatch", "Declared output hash does not match the generated file.", figure=figure_id, format=fmt)
        checked_outputs[fmt] = {
            "path": output_path.relative_to(output_root).as_posix(),
            "sha256": actual_output_sha256,
        }

    return {"input_sha256": actual_input_sha256, "outputs": checked_outputs}


def run_data_swap(*, root: Path, template_path: Path, figure_id: str, data_path: Path, out_dir: Path, input_mode: str) -> dict[str, Any]:
    root = root.resolve()
    template_path = template_path.resolve()
    try:
        data_file = data_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise DataSwapValidationError("input_data_missing", "Input data file is missing.", figure=figure_id) from exc

    validation = validate_template(template_path, root=root)
    if validation["status"] != "pass":
        raise DataSwapValidationError("template_validation_failed", "Template validation failed.")

    template = _load(template_path)
    figures = template["figures"]
    if figure_id not in figures:
        raise DataSwapValidationError("figure_not_declared", "Figure is not declared by template.", figure=figure_id)
    record = figures[figure_id]

    renderer = (root / record["renderer"]).resolve(strict=True)
    data_schema = (root / record["data_schema"]).resolve(strict=True)
    if not data_file.is_file():
        raise DataSwapValidationError("input_data_missing", "Input data file is missing.", figure=figure_id)

    data_errors = _json_schema_errors(_load(data_file), data_schema)
    if data_errors:
        raise DataSwapValidationError(
            "data_schema_validation_failed",
            "Replacement data schema validation failed: " + "; ".join(data_errors),
            figure=figure_id,
        )
    original_input_sha256 = sha256_file(data_file)

    ensure_output_isolated(data_file, out_dir)
    isolated_out = out_dir.resolve(strict=False)
    if isolated_out.exists() and any(isolated_out.iterdir()):
        raise DataSwapValidationError("output_directory_not_empty", "Output directory must be new or empty.", figure=figure_id)
    isolated_out.mkdir(parents=True, exist_ok=True)

    command = [sys.executable, str(renderer), "--figure", figure_id, "--data", str(data_file), "--out-dir", str(isolated_out), "--input-mode", input_mode]
    completed = subprocess.run(command, cwd=root, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    renderer_logs = _write_renderer_logs(isolated_out, completed)
    if completed.returncode != 0:
        message = f"Renderer failed with exit code {completed.returncode}."
        if renderer_logs:
            message += " Renderer stdout/stderr were captured under runner_logs/."
        raise DataSwapValidationError("renderer_failed", message, figure=figure_id)

    manifest_path = isolated_out / "data_swap_manifest.json"
    if not manifest_path.is_file():
        raise DataSwapValidationError("manifest_missing", "Renderer did not emit data_swap_manifest.json.", figure=figure_id)

    manifest = _load(manifest_path)
    checked = validate_run_manifest(
        manifest,
        template_record=record,
        figure_id=figure_id,
        data_path=data_file,
        expected_input_sha256=original_input_sha256,
        out_dir=isolated_out,
        input_mode=input_mode,
    )
    result: dict[str, Any] = {
        "schema": "scientificfigure.data-swap-runner-report.v1",
        "status": "pass",
        "manifest": "data_swap_manifest.json",
        "figure": figure_id,
        "input_sha256": checked["input_sha256"],
        "outputs": checked["outputs"],
    }
    if renderer_logs:
        result["renderer_logs"] = renderer_logs
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--input-mode", choices=("user_supplied", "fresh_digitization"), default="user_supplied")
    args = parser.parse_args()
    try:
        result = run_data_swap(root=args.root, template_path=args.template, figure_id=args.figure, data_path=args.data, out_dir=args.out_dir, input_mode=args.input_mode)
    except DataSwapValidationError as exc:
        print(json.dumps(exc.to_payload(), indent=2))
        return 2
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError):
        payload = DataSwapValidationError("runner_error", "Data-swap runner failed before validation completed.").to_payload()
        print(json.dumps(payload, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
