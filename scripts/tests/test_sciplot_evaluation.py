from __future__ import annotations

import builtins
import importlib.util
import io
import sys
import unittest
from contextlib import ExitStack, contextmanager, redirect_stdout
from copy import deepcopy
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

PASS_CHECKS = {
    "parseability": {"png": {"status": "pass"}},
    "mapping_validation": {"status": "pass"},
    "canvas_safety": {"status": "pass"},
    "plot_geometry_safety": {"status": "pass"},
    "boxed_text_safety": {"status": "pass"},
    "semantic_audit": {"status": "pass", "overall": "pass"},
    "vector_validation": {"status": "pass"},
}


def load_cli():
    module_spec = importlib.util.spec_from_file_location("sciplot_evaluation_under_test", SCRIPTS / "sciplot.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def dependency(name, **attributes):
    module = ModuleType(name)
    module.__dict__.update(attributes)
    return module


class SciPlotEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = load_cli()
        self.project = (SCRIPTS / "_unused_test_project").resolve()
        self.spec_path = self.project / "visualspec.json"
        self.spec = {"panels": [{"representation": "semantic_vector", "plots": [{"type": "line"}]}]}
        self.checks = deepcopy(PASS_CHECKS)
        self.render_status = "pass"
        self.manifest_status = "pass"

    @contextmanager
    def mocked_project(self):
        mapping = Mock(return_value=self.checks["mapping_validation"])
        semantic = Mock(return_value=self.checks["semantic_audit"])
        render = Mock(return_value={"render_status": self.render_status})
        load_json = Mock(side_effect=lambda path: self.spec if path.name == "visualspec.json" else {"outputs": {"png": "output/figure.png"}})
        dependencies = {
            "audit_semantics": dependency("audit_semantics", audit_mapping_validity=mapping, audit_semantics=semantic),
            "check_boxed_text_safety": dependency("check_boxed_text_safety", analyze_boxed_text=Mock()),
            "check_plot_geometry_safety": dependency("check_plot_geometry_safety", analyze_plot_geometry=Mock()),
            "render_visualspec_matplotlib": dependency("render_visualspec_matplotlib", render_file=render),
            "visualspec": dependency("visualspec", load_json=load_json),
        }
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, dependencies))
            mocks = {"mapping": mapping, "semantic": semantic, "render": render}
            for name, options in {
                "_parse_outputs": {"return_value": self.checks["parseability"]},
                "_canvas_report": {"return_value": self.checks["canvas_safety"]},
                "_vector_report": {"return_value": self.checks["vector_validation"]},
                "_declared_safety_report": {"side_effect": lambda spec, policy, *args: self.checks[policy]},
                "_validate_project_manifest": {"return_value": {"status": self.manifest_status, "failures": []}},
                "_ensure_project_root": {"return_value": self.project},
                "_prepare_visualspec": {"return_value": (self.spec_path, {"input/source.json": "sha256:fixture", "visualspec.json": "sha256:spec"})},
                "_write_rerun_script": {"return_value": self.project / "src" / "render.py"},
                "_project_checksums": {"return_value": {}},
                "write_json": {},
            }.items():
                mocks[name] = stack.enter_context(patch.object(self.cli, name, **options))
            stack.enter_context(patch.object(Path, "mkdir"))
            stack.enter_context(patch.object(Path, "rglob", return_value=()))
            yield SimpleNamespace(**mocks)

    def run_project(self, profile):
        args = self.cli.build_parser().parse_args([
            "run", "--input", str(self.project / "source.json"),
            "--out-dir", str(self.project), "--profile", profile, "--outputs", "png",
        ])
        with patch.object(Path, "is_file", return_value=False):
            return self.cli.run_command(args)

    def validate_project(self, profile):
        args = self.cli.build_parser().parse_args(["validate", "--project", str(self.project), "--profile", profile])
        with patch.object(Path, "is_dir", return_value=True), patch.object(Path, "is_file", return_value=True):
            return self.cli.validate_command(args)

    def assert_quick_checks(self, checks):
        self.assertEqual({"status": "not_run", "overall": "not_run"}, checks["semantic_audit"])
        for name in ("vector_validation", "plot_geometry_safety", "boxed_text_safety"):
            self.assertEqual({"status": "not_run"}, checks[name])

    def test_quick_entrypoints_preserve_contracts_and_skip_heavy_gates(self) -> None:
        with self.mocked_project() as mocks:
            checks, ok = self.cli._evaluate_project(self.project, self.spec, self.spec_path, ("png",), profile="quick")
        self.assertTrue(ok)
        self.assertEqual(set(PASS_CHECKS), set(checks))
        self.assert_quick_checks(checks)
        mocks.mapping.assert_called_once_with(self.spec, spec_path=self.spec_path)
        mocks.semantic.assert_not_called()
        mocks._vector_report.assert_not_called()
        mocks._declared_safety_report.assert_not_called()
        mocks._validate_project_manifest.assert_not_called()

        with self.mocked_project() as mocks:
            result = self.run_project("quick")
        self.assertEqual("sciplot.run-result.v1", result["schema"])
        self.assertEqual("ok", result["status"])
        self.assertEqual({"schema", "status", "selected_profile", "project", "input_hash", "input_hashes", "outputs", "report", "performance", "readability"}, set(result))
        self.assertEqual({"status": "not_run"}, result["readability"])
        report = next(call.args[1] for call in mocks.write_json.call_args_list if call.args[0].name == "quick_report.json")
        self.assertEqual("sciplot.quick-report.v1", report["schema"])
        self.assertEqual(set(PASS_CHECKS) | {"schema", "status", "selected_profile", "enabled_gates", "input_hashes", "output_selection", "readability"}, set(report))
        self.assert_quick_checks(report)
        mocks.semantic.assert_not_called()
        mocks._vector_report.assert_not_called()
        mocks._declared_safety_report.assert_not_called()
        mocks._validate_project_manifest.assert_not_called()
        self.assertFalse(mocks.render.call_args.kwargs["write_support_files"])

        with self.mocked_project() as mocks:
            result = self.validate_project("quick")
        self.assertEqual("sciplot.validation-result.v1", result["schema"])
        self.assertEqual("pass", result["status"])
        self.assertEqual(set(PASS_CHECKS) | {"schema", "status", "profile", "project", "manifest_validation", "readability"}, set(result))
        self.assertEqual({"status": "not_run", "failures": []}, result["manifest_validation"])
        self.assert_quick_checks(result)
        mocks.render.assert_not_called()
        mocks.semantic.assert_not_called()
        mocks._vector_report.assert_not_called()
        mocks._declared_safety_report.assert_not_called()
        mocks._validate_project_manifest.assert_not_called()

    def test_standard_each_required_gate_failure_blocks_both_entrypoints(self) -> None:
        for gate in PASS_CHECKS:
            for status in ("failed", "not_run"):
                for entrypoint in (self.run_project, self.validate_project):
                    with self.subTest(gate=gate, status=status, entrypoint=entrypoint.__name__):
                        self.checks = deepcopy(PASS_CHECKS)
                        report = self.checks[gate]
                        if gate == "parseability":
                            report = report["png"]
                        report["overall" if gate == "semantic_audit" else "status"] = status
                        with self.mocked_project():
                            result = entrypoint("standard")
                        self.assertEqual("failed", result["status"])

        self.checks = deepcopy(PASS_CHECKS)

        self.manifest_status = "failed"
        for entrypoint in (self.run_project, self.validate_project):
            with self.subTest(entrypoint=entrypoint.__name__):
                with self.mocked_project() as mocks:
                    result = entrypoint("standard")
                self.assertEqual("failed", result["status"])
                mocks._validate_project_manifest.assert_called_once()
                if entrypoint.__name__ == "run_project":
                    manifest = next(call.args[1] for call in reversed(mocks.write_json.call_args_list) if call.args[0].name == "manifest.json")
                    self.assertEqual("failed", manifest["status"])

    def test_standard_pass_preserves_contracts_and_legacy_entrypoints(self) -> None:
        with self.mocked_project() as mocks:
            run_result = self.run_project("standard")
            validate_result = self.validate_project("standard")
        self.assertEqual("ok", run_result["status"])
        self.assertEqual("pass", validate_result["status"])
        report = next(call.args[1] for call in mocks.write_json.call_args_list if call.args[0].name == "report.json")
        self.assertEqual("sciplot.qa-report.v1", report["schema"])
        self.assertEqual(set(PASS_CHECKS) | {"schema", "status", "selected_profile", "enabled_gates", "input_hashes", "output_selection", "checksums", "environment_summary", "manifest_validation", "readability"}, set(report))
        for gate in PASS_CHECKS:
            self.assertEqual(PASS_CHECKS[gate], report[gate])
            self.assertEqual(report[gate], validate_result[gate])
        self.assertEqual(2, mocks._validate_project_manifest.call_count)
        self.assertTrue(mocks.render.call_args.kwargs["write_support_files"])

        for name in ("run_command", "validate_command", "finalize_command", "trace_pdf_command", "main", "build_parser", "_run_lightweight", "_parse_outputs", "_vector_report", "_canvas_report", "_declared_safety_report", "_validate_project_manifest"):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(self.cli, name)))

    def test_only_existing_optional_statuses_accept_not_applicable(self) -> None:
        for gate in PASS_CHECKS:
            with self.subTest(gate=gate):
                self.checks = deepcopy(PASS_CHECKS)
                report = self.checks[gate]["png"] if gate == "parseability" else self.checks[gate]
                report["overall" if gate == "semantic_audit" else "status"] = "not_applicable"
                with self.mocked_project():
                    _, ok = self.cli._evaluate_project(self.project, self.spec, self.spec_path, ("png",), profile="standard")
                self.assertEqual(gate in {"vector_validation", "plot_geometry_safety", "boxed_text_safety"}, ok)

    def test_run_retains_separate_render_gate(self) -> None:
        for profile in ("quick", "standard"):
            for render_status in ("failed", None):
                with self.subTest(profile=profile, render_status=render_status):
                    self.render_status = render_status
                    with self.mocked_project():
                        run_result = self.run_project(profile)
                        validate_result = self.validate_project(profile)
                    self.assertEqual("failed", run_result["status"])
                    self.assertEqual("pass", validate_result["status"])



class SciPlotLazyImportTests(unittest.TestCase):
    def test_all_help_entrypoints_avoid_runtime_dependencies(self) -> None:
        blocked = {"PIL", "matplotlib", "numpy", "pandas", "audit_semantics", "check_boxed_text_safety", "check_canvas_safety", "check_plot_geometry_safety", "check_vector_output", "data_resolver", "render_visualspec_matplotlib", "uncertainty_semantics", "visualspec"}
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.split(".", 1)[0] in blocked:
                raise AssertionError(f"Help imported runtime dependency: {name}")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            cli = load_cli()
            for command in ([], ["run"], ["validate"], ["finalize"], ["trace-pdf"]):
                with self.subTest(command=command):
                    output = io.StringIO()
                    with patch.object(sys, "argv", ["sciplot.py", *command, "--help"]), redirect_stdout(output):
                        with self.assertRaises(SystemExit) as caught:
                            cli.main()
                    self.assertEqual(0, caught.exception.code)
                    self.assertIn("usage:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
