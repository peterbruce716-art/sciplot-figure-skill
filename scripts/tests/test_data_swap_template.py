from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_data_swap import (  # noqa: E402
    DataSwapValidationError,
    ensure_output_isolated,
    resolve_output_path_safely,
    run_data_swap,
)
from validate_data_swap_template import validate_template  # noqa: E402
from verify_data_swap_change import verify_data_swap_change  # noqa: E402


class DataSwapTemplateTests(unittest.TestCase):
    def _write_fixture(
        self,
        root: Path,
        *,
        historical: bool = False,
        bad_path: bool = False,
        outputs: tuple[str, ...] = ("png", "svg", "pdf"),
        renderer_mode: str = "valid",
        allow_unchanged_outputs: bool = False,
        unchanged_outputs_reason: str | None = "Documented invariant output for this template.",
    ) -> Path:
        (root / "schemas").mkdir()
        (root / "data").mkdir()
        (root / "scripts").mkdir()
        (root / "schemas" / "fig.schema.json").write_text(
            json.dumps({"type": "object", "required": ["value"], "properties": {"value": {"type": "number"}}}),
            encoding="utf-8",
        )
        (root / "data" / "fig.json").write_text('{"value": 1}\n', encoding="utf-8")
        (root / "data" / "fig_changed.json").write_text('{"value": 2}\n', encoding="utf-8")
        renderer = root / "scripts" / "renderer.py"
        renderer.write_text(
            f"""
from pathlib import Path
import argparse, hashlib, json, sys

MODE = {renderer_mode!r}
TEMPLATE_OUTPUTS = {list(outputs)!r}

parser = argparse.ArgumentParser()
parser.add_argument('--figure')
parser.add_argument('--data')
parser.add_argument('--out-dir')
parser.add_argument('--input-mode')
args = parser.parse_args()

out = Path(args.out_dir)
out.mkdir(parents=True, exist_ok=True)
data = Path(args.data)
payload = data.read_bytes()
content_seed = b'constant-render' if MODE == 'constant' else payload
missing_output_format = 'pdf' if MODE == 'missing_output' else None
if MODE.startswith('missing_output_'):
    missing_output_format = MODE.rsplit('_', 1)[-1]

if MODE in {'noisy', 'fail_noisy'}:
    print('renderer stdout log')
    print('renderer stderr log', file=sys.stderr)
if MODE == 'fail_noisy':
    raise SystemExit(7)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

written = {{}}
for fmt in TEMPLATE_OUTPUTS:
    if missing_output_format == fmt:
        continue
    target = out / f'fig.{{fmt}}'
    target.write_bytes(content_seed + b':' + fmt.encode('ascii'))
    written[fmt] = target

manifest_outputs = {{}}
manifest_formats = ['png'] if MODE == 'missing_format' else TEMPLATE_OUTPUTS
for fmt in manifest_formats:
    raw_path = f'fig.{{fmt}}'
    if MODE == 'escape_output' and fmt == 'png':
        raw_path = '../outside.png'
        outside = out.parent / 'outside.png'
        outside.write_bytes(content_seed + b':outside')
        sha = digest(outside)
    elif fmt in written:
        sha = digest(written[fmt])
    else:
        sha = '0' * 64
    if MODE == 'wrong_output_hash' and fmt == 'png':
        sha = 'f' * 64
    manifest_outputs[fmt] = {{'path': raw_path, 'sha256': sha}}

input_sha = digest(data)
if MODE == 'wrong_input_hash':
    input_sha = 'e' * 64
if MODE == 'tamper_input_after_hash':
    data.write_text('{{"value": 3}}\\n', encoding='utf-8')

manifest = {{
    'schema': 'scientificfigure.data-swap-run.v1',
    'figure': args.figure,
    'input_mode': args.input_mode,
    'historical_data_consumed': False,
    'input': {{'path': data.name, 'sha256': input_sha}},
    'outputs': manifest_outputs,
}}
(out / 'data_swap_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
if MODE == 'tamper_output_after_manifest':
    written['png'].write_bytes(b'tampered-after-manifest')
""",
            encoding="utf-8",
        )
        figure_record = {
            "data_schema": "schemas/fig.schema.json",
            "example_data": "../bad.json" if bad_path else "data/fig.json",
            "renderer": "scripts/renderer.py",
            "outputs": list(outputs),
        }
        if allow_unchanged_outputs:
            figure_record["allow_unchanged_outputs"] = True
            if unchanged_outputs_reason is not None:
                figure_record["unchanged_outputs_reason"] = unchanged_outputs_reason
        template = {
            "schema": "scientificfigure.data-swap-template.v1",
            "template_id": "unit-test",
            "template_version": "1.0.0",
            "renderer_entrypoint": "scripts/renderer.py",
            "input_mode": "user_supplied",
            "historical_data_consumed": historical,
            "figures": {"fig": figure_record},
        }
        path = root / "template_manifest.json"
        path.write_text(json.dumps(template), encoding="utf-8")
        return path

    def _run(self, root: Path, template: Path, out: Path) -> dict[str, object]:
        return run_data_swap(
            root=root,
            template_path=template,
            figure_id="fig",
            data_path=root / "data" / "fig.json",
            out_dir=out,
            input_mode="user_supplied",
        )

    def test_valid_template_and_generic_runner_verify_hashes_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root)
            self.assertEqual(validate_template(template, root=root)["status"], "pass")
            out = root / "outputs" / "run"
            result = self._run(root, template, out)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(set(result["outputs"]), {"png", "svg", "pdf"})
            self.assertEqual(result["input_sha256"], hashlib.sha256((root / "data" / "fig.json").read_bytes()).hexdigest())
            self.assertTrue((out / "data_swap_manifest.json").is_file())

    def test_unified_reusable_finalize_archives_template_and_changed_input_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root)
            project = root / "project"
            bundle = root / "bundle"
            spec = ROOT.parent / "examples" / "line_plot" / "visualspec_v2.json"
            run = subprocess.run(
                [sys.executable, str(ROOT / "sciplot.py"), "run", "--spec", str(spec), "--profile", "standard", "--out-dir", str(project), "--json"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=180,
            )
            self.assertEqual(0, run.returncode, run.stdout + run.stderr)
            finalize = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "sciplot.py"),
                    "finalize",
                    "--project",
                    str(project),
                    "--profile",
                    "audit",
                    "--claim",
                    "reusable",
                    "--template",
                    str(template),
                    "--figure",
                    "fig",
                    "--baseline-data",
                    str(root / "data" / "fig.json"),
                    "--changed-data",
                    str(root / "data" / "fig_changed.json"),
                    "--bundle",
                    str(bundle),
                    "--json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=300,
            )
            self.assertEqual(0, finalize.returncode, finalize.stdout + finalize.stderr)
            payload = json.loads(finalize.stdout)
            self.assertEqual("pass", payload["data_swap_proof"]["status"])
            manifest = json.loads((bundle / "reproduction_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("data_swap/data_swap_template.json", manifest["data_swap_template"])
            self.assertEqual("data_swap/data_swap_change_proof.json", manifest["data_swap_change_proof"])
            self.assertTrue((bundle / manifest["data_swap_template"]).is_file())
            self.assertTrue((bundle / manifest["data_swap_change_proof"]).is_file())
            verify = subprocess.run([sys.executable, str(bundle / "verify.py")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
            self.assertEqual(0, verify.returncode, verify.stdout + verify.stderr)

    def test_cli_stdout_stays_json_when_renderer_is_noisy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root, renderer_mode="noisy")
            out = root / "outputs" / "noisy"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "run_data_swap.py"),
                    "--root",
                    str(root),
                    "--template",
                    str(template),
                    "--figure",
                    "fig",
                    "--data",
                    str(root / "data" / "fig.json"),
                    "--out-dir",
                    str(out),
                    "--input-mode",
                    "user_supplied",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(completed.stderr, "")
            self.assertEqual(payload["renderer_logs"]["stdout"], "runner_logs/renderer_stdout.txt")
            self.assertEqual(payload["renderer_logs"]["stderr"], "runner_logs/renderer_stderr.txt")
            self.assertIn("renderer stdout log", (out / "runner_logs" / "renderer_stdout.txt").read_text(encoding="utf-8"))

    def test_cli_failure_stays_json_when_renderer_fails_noisily(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root, renderer_mode="fail_noisy")
            out = root / "outputs" / "fail-noisy"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "run_data_swap.py"),
                    "--root",
                    str(root),
                    "--template",
                    str(template),
                    "--figure",
                    "fig",
                    "--data",
                    str(root / "data" / "fig.json"),
                    "--out-dir",
                    str(out),
                    "--input-mode",
                    "user_supplied",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(completed.returncode, 2)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["error"]["code"], "renderer_failed")
            self.assertEqual(completed.stderr, "")
            self.assertTrue((out / "runner_logs" / "renderer_stdout.txt").is_file())
            self.assertTrue((out / "runner_logs" / "renderer_stderr.txt").is_file())

    def test_replacement_data_schema_failure_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root)
            invalid = root / "data" / "invalid.json"
            invalid.write_text('{"value": "wrong"}\n', encoding="utf-8")
            with self.assertRaises(DataSwapValidationError) as caught:
                run_data_swap(
                    root=root,
                    template_path=template,
                    figure_id="fig",
                    data_path=invalid,
                    out_dir=root / "outputs" / "invalid",
                    input_mode="user_supplied",
                )
            self.assertEqual(caught.exception.code, "data_schema_validation_failed")

    def test_historical_data_and_parent_paths_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            historical = self._write_fixture(root, historical=True)
            self.assertEqual(validate_template(historical, root=root)["status"], "failed")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unsafe = self._write_fixture(root, bad_path=True)
            report = validate_template(unsafe, root=root)
            self.assertEqual(report["status"], "failed")
            self.assertTrue(any("parent path" in item["message"] for item in report["failures"]))

    def test_template_rejects_nonportable_duplicate_and_unexplained_invariant_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            duplicate = self._write_fixture(root, outputs=("png", "png"))
            report = validate_template(duplicate, root=root)
            self.assertEqual(report["status"], "failed")
            self.assertTrue(any(item["check"] == "outputs" and "duplicate" in item["message"] for item in report["failures"]))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unexplained = self._write_fixture(root, renderer_mode="constant", allow_unchanged_outputs=True, unchanged_outputs_reason=None)
            report = validate_template(unexplained, root=root)
            self.assertEqual(report["status"], "failed")
            self.assertTrue(any(item["check"] == "unchanged_outputs_reason" for item in report["failures"]))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root)
            payload = json.loads(template.read_text(encoding="utf-8"))
            payload["figures"]["fig"]["example_data"] = r"data\fig.json"
            template.write_text(json.dumps(payload), encoding="utf-8")
            report = validate_template(template, root=root)
            self.assertEqual(report["status"], "failed")
            self.assertTrue(any(item["check"] == "fig.example_data" for item in report["failures"]))

    def test_template_rejects_symlink_paths_that_escape_root_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / "project"
            root.mkdir()
            template = self._write_fixture(root)
            outside_renderer = workspace / "outside_renderer.py"
            outside_renderer.write_text("print('outside')\n", encoding="utf-8")
            link = root / "scripts" / "outside_renderer.py"
            try:
                os.symlink(outside_renderer, link)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            payload = json.loads(template.read_text(encoding="utf-8"))
            payload["figures"]["fig"]["renderer"] = "scripts/outside_renderer.py"
            template.write_text(json.dumps(payload), encoding="utf-8")
            report = validate_template(template, root=root)
            self.assertEqual(report["status"], "failed")
            self.assertTrue(any(item["check"] == "fig.renderer" and "outside project root" in item["message"] for item in report["failures"]))

    def test_output_isolation_rejects_input_directory_descendants_and_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir()
            data_file = data_dir / "input.json"
            data_file.write_text("{}\n", encoding="utf-8")
            rejected = [data_dir / "output", data_dir, data_file, data_dir / ".." / "data" / "output"]
            for out_dir in rejected:
                with self.subTest(out_dir=out_dir):
                    with self.assertRaises(DataSwapValidationError) as caught:
                        ensure_output_isolated(data_file, out_dir)
                    self.assertIn(caught.exception.code, {"output_equals_input_data", "output_directory_inside_input_data"})
            ensure_output_isolated(data_file, root / "outputs" / "run1")

    def test_output_isolation_rejects_symlink_to_input_directory_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir()
            data_file = data_dir / "input.json"
            data_file.write_text("{}\n", encoding="utf-8")
            link = root / "linked-output"
            try:
                os.symlink(data_dir, link, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaises(DataSwapValidationError) as caught:
                ensure_output_isolated(data_file, link)
            self.assertEqual(caught.exception.code, "output_directory_inside_input_data")

    def test_runner_rejects_manifest_input_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root, renderer_mode="wrong_input_hash")
            with self.assertRaises(DataSwapValidationError) as caught:
                self._run(root, template, root / "outputs" / "wrong-input")
            self.assertEqual(caught.exception.code, "input_sha256_mismatch")

    def test_runner_rejects_each_missing_declared_output(self) -> None:
        for fmt in ("png", "svg", "pdf"):
            with self.subTest(format=fmt):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    template = self._write_fixture(root, renderer_mode=f"missing_output_{fmt}")
                    with self.assertRaises(DataSwapValidationError) as caught:
                        self._run(root, template, root / "outputs" / f"missing-output-{fmt}")
                    self.assertEqual(caught.exception.code, "missing_declared_output")

    def test_runner_rejects_output_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root, renderer_mode="wrong_output_hash")
            with self.assertRaises(DataSwapValidationError) as caught:
                self._run(root, template, root / "outputs" / "wrong-output")
            self.assertEqual(caught.exception.code, "output_sha256_mismatch")

    def test_runner_rejects_input_and_output_tampering_after_renderer_starts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root, renderer_mode="tamper_input_after_hash")
            with self.assertRaises(DataSwapValidationError) as caught:
                self._run(root, template, root / "outputs" / "tampered-input")
            self.assertEqual(caught.exception.code, "input_sha256_mismatch")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root, renderer_mode="tamper_output_after_manifest")
            with self.assertRaises(DataSwapValidationError) as caught:
                self._run(root, template, root / "outputs" / "tampered-output")
            self.assertEqual(caught.exception.code, "output_sha256_mismatch")

    def test_runner_rejects_output_path_escape_and_format_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root, renderer_mode="escape_output")
            with self.assertRaises(DataSwapValidationError) as caught:
                self._run(root, template, root / "outputs" / "escape")
            self.assertEqual(caught.exception.code, "output_path_escape")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root, renderer_mode="missing_format")
            with self.assertRaises(DataSwapValidationError) as caught:
                self._run(root, template, root / "outputs" / "missing-format")
            self.assertEqual(caught.exception.code, "output_format_mismatch")

    def test_output_path_symlink_escape_fails_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "outputs" / "run"
            out.mkdir(parents=True)
            data_dir = root / "data"
            data_dir.mkdir()
            data_file = data_dir / "input.json"
            data_file.write_text("{}\n", encoding="utf-8")
            outside = root / "outside.png"
            outside.write_text("outside\n", encoding="utf-8")
            link = out / "fig.png"
            try:
                os.symlink(outside, link)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaises(DataSwapValidationError) as caught:
                resolve_output_path_safely(out, "fig.png", data_path=data_file)
            self.assertEqual(caught.exception.code, "output_path_escape")

    def test_output_path_rejects_windows_absolute_and_backslash_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "outputs" / "run"
            out.mkdir(parents=True)
            data_dir = root / "data"
            data_dir.mkdir()
            data_file = data_dir / "input.json"
            data_file.write_text("{}\n", encoding="utf-8")
            rejected = (r"C:\temp\fig.png", r"C:fig.png", r"nested\fig.png", r"\\server\share\fig.png", "/absolute/fig.png")
            for raw_path in rejected:
                with self.subTest(raw_path=raw_path):
                    with self.assertRaises(DataSwapValidationError) as caught:
                        resolve_output_path_safely(out, raw_path, data_path=data_file)
                    self.assertEqual(caught.exception.code, "output_path_escape")

    def test_changed_input_proof_passes_and_detects_static_renderers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root)
            proof = verify_data_swap_change(
                root=root,
                template_path=template,
                figure_id="fig",
                baseline_data=root / "data" / "fig.json",
                changed_data=root / "data" / "fig_changed.json",
                baseline_out_dir=root / "outputs" / "baseline",
                changed_out_dir=root / "outputs" / "changed",
                input_mode="user_supplied",
            )
            self.assertEqual(proof["status"], "pass")
            self.assertEqual(set(proof["changed_outputs"]), {"png", "svg", "pdf"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root, renderer_mode="constant")
            with self.assertRaises(DataSwapValidationError) as caught:
                verify_data_swap_change(
                    root=root,
                    template_path=template,
                    figure_id="fig",
                    baseline_data=root / "data" / "fig.json",
                    changed_data=root / "data" / "fig_changed.json",
                    baseline_out_dir=root / "outputs" / "baseline",
                    changed_out_dir=root / "outputs" / "changed",
                    input_mode="user_supplied",
                )
            self.assertEqual(caught.exception.code, "outputs_unchanged")

    def test_changed_input_proof_rejects_same_input_and_reused_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root)
            with self.assertRaises(DataSwapValidationError) as caught:
                verify_data_swap_change(
                    root=root,
                    template_path=template,
                    figure_id="fig",
                    baseline_data=root / "data" / "fig.json",
                    changed_data=root / "data" / "fig.json",
                    baseline_out_dir=root / "outputs" / "baseline",
                    changed_out_dir=root / "outputs" / "changed",
                    input_mode="user_supplied",
                )
            self.assertEqual(caught.exception.code, "input_sha256_not_changed")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root)
            shared = root / "outputs" / "shared"
            with self.assertRaises(DataSwapValidationError) as caught:
                verify_data_swap_change(
                    root=root,
                    template_path=template,
                    figure_id="fig",
                    baseline_data=root / "data" / "fig.json",
                    changed_data=root / "data" / "fig_changed.json",
                    baseline_out_dir=shared,
                    changed_out_dir=shared,
                    input_mode="user_supplied",
                )
            self.assertEqual(caught.exception.code, "output_directory_reused")

    def test_changed_input_proof_can_be_explicitly_allowed_for_invariant_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root, renderer_mode="constant", allow_unchanged_outputs=True)
            proof = verify_data_swap_change(
                root=root,
                template_path=template,
                figure_id="fig",
                baseline_data=root / "data" / "fig.json",
                changed_data=root / "data" / "fig_changed.json",
                baseline_out_dir=root / "outputs" / "baseline",
                changed_out_dir=root / "outputs" / "changed",
                input_mode="user_supplied",
            )
            self.assertEqual(proof["status"], "pass")
            self.assertEqual(proof["changed_outputs"], [])
            self.assertIn("unchanged_outputs_allowed_reason", proof)


if __name__ == "__main__":
    unittest.main()
