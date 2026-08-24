from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


class ReleaseWorkflowTests(unittest.TestCase):
    def test_release_workflow_is_version_gated_and_fail_closed(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        required = [
            "branches: [main]",
            "- VERSION",
            "contents: write",
            "scripts/release_acceptance.py",
            "scripts/build_skill_package.py",
            "scripts/validate_skill_package.py",
            "gh release create",
            "--notes-file",
        ]
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
