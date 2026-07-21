from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from benchmark_workflow_profiles import count_command_steps, count_render_steps, reduction_percent


class WorkflowBenchmarkTests(unittest.TestCase):
    def test_count_command_steps_walks_nested_step_reports(self) -> None:
        payload = {
            "steps": {
                "render": {"command": ["python", "render.py"], "status": "pass"},
                "nested": {"steps": {"verify": {"command": ["python", "verify.py"], "status": "pass"}}},
                "portable": {"command": {"executable_role": "python", "script": "audit.py", "arguments": []}},
                "summary": {"status": "pass"},
            }
        }
        self.assertEqual(3, count_command_steps(payload))

    def test_render_count_uses_the_command_script_not_render_named_arguments(self) -> None:
        payload = {
            "render": {"command": {"script": "render.py", "arguments": []}},
            "audit": {"command": {"script": "audit_semantics.py", "arguments": ["render_semantics.json"]}},
        }
        self.assertEqual(1, count_render_steps(payload))

    def test_reduction_percent_is_stable_for_zero_baseline(self) -> None:
        self.assertEqual(75.0, reduction_percent(20, 5))
        self.assertIsNone(reduction_percent(0, 0))


if __name__ == "__main__":
    unittest.main()
