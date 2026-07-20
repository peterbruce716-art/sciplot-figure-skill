from __future__ import annotations

"""Machine-check that changed replacement data changes a data-swap output."""

import argparse
import json
from pathlib import Path
from typing import Any

from run_data_swap import DataSwapValidationError, _load, _same_or_descendant, run_data_swap, sha256_file


def _allow_unchanged_outputs(template_path: Path, figure_id: str) -> str | None:
    template = _load(template_path)
    record = template.get("figures", {}).get(figure_id, {})
    if record.get("allow_unchanged_outputs") is True:
        reason = record.get("unchanged_outputs_reason")
        if isinstance(reason, str) and reason.strip():
            return reason.strip()
    return None


def verify_data_swap_change(
    *,
    root: Path,
    template_path: Path,
    figure_id: str,
    baseline_data: Path,
    changed_data: Path,
    baseline_out_dir: Path,
    changed_out_dir: Path,
    input_mode: str,
) -> dict[str, Any]:
    baseline_output = baseline_out_dir.resolve(strict=False)
    changed_output = changed_out_dir.resolve(strict=False)
    if baseline_output == changed_output or _same_or_descendant(baseline_output, changed_output) or _same_or_descendant(changed_output, baseline_output):
        raise DataSwapValidationError("output_directory_reused", "Baseline and changed runs must use different isolated output directories.", figure=figure_id)

    baseline_input_sha256 = sha256_file(baseline_data.resolve(strict=True))
    changed_input_sha256 = sha256_file(changed_data.resolve(strict=True))
    if baseline_input_sha256 == changed_input_sha256:
        raise DataSwapValidationError("input_sha256_not_changed", "Changed-input proof requires different input file hashes.", figure=figure_id)

    baseline = run_data_swap(
        root=root,
        template_path=template_path,
        figure_id=figure_id,
        data_path=baseline_data,
        out_dir=baseline_out_dir,
        input_mode=input_mode,
    )
    changed = run_data_swap(
        root=root,
        template_path=template_path,
        figure_id=figure_id,
        data_path=changed_data,
        out_dir=changed_out_dir,
        input_mode=input_mode,
    )

    baseline_outputs = baseline["outputs"]
    changed_outputs = changed["outputs"]
    changed_formats: list[str] = []
    unchanged_formats: list[str] = []
    for fmt in sorted(baseline_outputs):
        if baseline_outputs[fmt]["sha256"] != changed_outputs[fmt]["sha256"]:
            changed_formats.append(fmt)
        else:
            unchanged_formats.append(fmt)

    allow_reason = _allow_unchanged_outputs(template_path, figure_id)
    if not changed_formats and allow_reason is None:
        raise DataSwapValidationError("outputs_unchanged", "Input changed but all template-declared outputs were unchanged.", figure=figure_id)

    result: dict[str, Any] = {
        "schema": "scientificfigure.data-swap-change-proof.v1",
        "status": "pass",
        "figure": figure_id,
        "baseline_input_sha256": baseline_input_sha256,
        "changed_input_sha256": changed_input_sha256,
        "changed_outputs": changed_formats,
        "unchanged_outputs": unchanged_formats,
        "baseline_manifest": "data_swap_manifest.json",
        "changed_manifest": "data_swap_manifest.json",
    }
    if allow_reason is not None:
        result["unchanged_outputs_allowed_reason"] = allow_reason
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--baseline-data", type=Path, required=True)
    parser.add_argument("--changed-data", type=Path, required=True)
    parser.add_argument("--baseline-out-dir", type=Path, required=True)
    parser.add_argument("--changed-out-dir", type=Path, required=True)
    parser.add_argument("--input-mode", choices=("user_supplied", "fresh_digitization"), default="user_supplied")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    try:
        result = verify_data_swap_change(
            root=args.root.resolve(),
            template_path=args.template.resolve(),
            figure_id=args.figure,
            baseline_data=args.baseline_data,
            changed_data=args.changed_data,
            baseline_out_dir=args.baseline_out_dir,
            changed_out_dir=args.changed_out_dir,
            input_mode=args.input_mode,
        )
    except DataSwapValidationError as exc:
        payload = exc.to_payload()
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 2
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError):
        payload = DataSwapValidationError("change_proof_error", "Data-swap change proof failed before validation completed.", figure=args.figure).to_payload()
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 2

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
