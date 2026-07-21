from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from execution_planner import ExecutionRequest, PlannerError, build_execution_plan
from execution_profiles import get_profile
from output_policy import resolve_outputs


class ExecutionProfileTests(unittest.TestCase):
    def test_profiles_keep_lightweight_and_audit_gates_separate(self) -> None:
        quick = get_profile("quick")
        standard = get_profile("standard")
        audit = get_profile("audit")

        self.assertIn("input_hash", quick.required_gates)
        self.assertNotIn("semantic_audit", quick.required_gates)
        self.assertIn("semantic_audit", standard.required_gates)
        self.assertIn("vector_validation", standard.required_gates)
        self.assertNotIn("changed_input_proof", standard.required_gates)
        self.assertIn("bundle_lock", audit.required_gates)
        self.assertIn("attestation", audit.required_gates)
        self.assertIn("runtime_freeze", audit.required_gates)
        self.assertIn("checksum_verification", audit.required_gates)
        self.assertIn("portable_path_scan", audit.required_gates)
        self.assertNotIn("data_swap_template", audit.required_gates)

    def test_auto_routes_preview_manuscript_reusable_and_release(self) -> None:
        preview = build_execution_plan(ExecutionRequest(profile="auto", claim="preview"))
        manuscript = build_execution_plan(ExecutionRequest(profile="auto", claim="manuscript"))
        reusable = build_execution_plan(ExecutionRequest(profile="auto", claim="reusable"))
        release = build_execution_plan(ExecutionRequest(profile="auto", claim="release"))
        strict = build_execution_plan(ExecutionRequest(profile="auto", require_strict=True))
        reference = build_execution_plan(ExecutionRequest(profile="auto", has_reference=True))

        self.assertEqual("quick", preview.selected_profile)
        self.assertEqual("standard", manuscript.selected_profile)
        self.assertEqual("audit", reusable.selected_profile)
        self.assertEqual("audit", release.selected_profile)
        self.assertEqual("audit", strict.selected_profile)
        self.assertEqual("audit", reference.selected_profile)
        self.assertIn("release_acceptance", release.enabled_gates)

    def test_data_swap_and_changed_input_are_conditional(self) -> None:
        ordinary = build_execution_plan(ExecutionRequest(profile="standard"))
        enabled = build_execution_plan(ExecutionRequest(profile="standard", enable_data_swap=True))
        reusable = build_execution_plan(ExecutionRequest(profile="audit", claim="reusable"))

        self.assertNotIn("data_swap_template", ordinary.enabled_gates)
        self.assertNotIn("changed_input_proof", ordinary.enabled_gates)
        self.assertIn("data_swap_template", enabled.enabled_gates)
        self.assertIn("changed_input_proof", enabled.enabled_gates)
        self.assertIn("data_swap_template", reusable.enabled_gates)
        self.assertIn("changed_input_proof", reusable.enabled_gates)

    def test_explicit_profile_overrides_auto_but_rejects_unsafe_conflict(self) -> None:
        plan = build_execution_plan(ExecutionRequest(profile="standard", claim="preview"))
        self.assertEqual("standard", plan.selected_profile)
        with self.assertRaises(PlannerError):
            build_execution_plan(ExecutionRequest(profile="quick", require_strict=True))
        with self.assertRaises(PlannerError):
            build_execution_plan(ExecutionRequest(profile="standard", claim="release"))
        with self.assertRaises(PlannerError):
            build_execution_plan(ExecutionRequest(profile="standard", create_bundle=True))
        with self.assertRaises(PlannerError):
            build_execution_plan(ExecutionRequest(profile="quick", claim="release"))
        with self.assertRaises(PlannerError):
            build_execution_plan(ExecutionRequest(profile="quick", claim="reusable"))
        with self.assertRaises(PlannerError):
            build_execution_plan(ExecutionRequest(profile="quick", claim="manuscript"))
        with self.assertRaises(PlannerError):
            build_execution_plan(ExecutionRequest(profile="standard", has_reference=True))

    def test_execution_plan_is_machine_readable(self) -> None:
        payload = build_execution_plan(ExecutionRequest(profile="auto", claim="manuscript")).to_dict()
        self.assertEqual("sciplot.execution-plan.v1", payload["schema"])
        self.assertEqual("standard", payload["selected_profile"])
        self.assertTrue(payload["enabled_gates"])
        self.assertIn("data_swap_template", payload["disabled_gates"])


class OutputPolicyTests(unittest.TestCase):
    def test_auto_outputs_follow_plot_representation(self) -> None:
        self.assertEqual(("png", "svg"), resolve_outputs("auto", profile="quick", plot_kinds={"line"}).formats)
        self.assertEqual(("png", "svg", "pdf"), resolve_outputs("auto", profile="standard", plot_kinds={"line"}).formats)
        self.assertEqual(("png",), resolve_outputs("auto", profile="quick", plot_kinds={"heatmap"}).formats)
        self.assertEqual(("png", "pdf"), resolve_outputs("auto", profile="standard", plot_kinds={"heatmap"}).formats)

    def test_preview_and_pdf_trace_do_not_create_fake_vector_output(self) -> None:
        preview = resolve_outputs("auto", profile="quick", plot_kinds={"line"}, preview_only=True)
        trace = resolve_outputs("auto", profile="audit", plot_kinds=set(), pdf_trace=True)
        self.assertEqual(("png",), preview.formats)
        self.assertEqual(("png", "pdf"), trace.formats)
        self.assertNotIn("svg", trace.formats)

    def test_explicit_outputs_are_normalized_and_deduplicated(self) -> None:
        result = resolve_outputs("png,svg,png", profile="standard", plot_kinds={"line"})
        self.assertEqual(("png", "svg"), result.formats)
        with self.assertRaises(ValueError):
            resolve_outputs("png,exe", profile="quick", plot_kinds={"line"})


if __name__ == "__main__":
    unittest.main()
