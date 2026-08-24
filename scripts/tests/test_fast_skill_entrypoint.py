from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "SKILL.md"


class SkillEntrypointTests(unittest.TestCase):
    def test_skill_entrypoint_stays_compact(self):
        self.assertLessEqual(len(SKILL.read_bytes()), 9_000)

    def test_frontmatter_is_trigger_focused(self):
        text = SKILL.read_text(encoding="utf-8")
        match = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        self.assertIsNotNone(match)
        description = match.group(1).strip()
        self.assertTrue(description.startswith("Use when "))
        self.assertLess(len(description), 500)

    def test_core_routing_survives_compression(self):
        text = SKILL.read_text(encoding="utf-8")
        required = [
            "scripts/sciplot.py",
            "quick",
            "standard",
            "audit",
            "references/WORKFLOW_PROFILES.md",
            "references/DIGITIZATION_WORKFLOW.md",
            "references/DATA_SWAP_PROTOCOL.md",
            "references/SHARED_GEOMETRY_PROTOCOL.md",
            "references/STATISTICAL_REPORTING_PROTOCOL.md",
            "semantic_strict_pass",
            "visual_trace_pass",
        ]
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_progressive_loading_is_explicit(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("Do not read every reference up front", text)
        self.assertIn("smallest workflow", text)


if __name__ == "__main__":
    unittest.main()
