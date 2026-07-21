from __future__ import annotations

import unittest
from pathlib import Path

from common import ROOT
from check_version_consistency import find_versions
from build_policy_context_from_render import build_context


class AIAndVersionTest(unittest.TestCase):
    def test_local_version_declarations_are_consistent(self):
        versions = find_versions(ROOT)
        self.assertTrue(versions)
        self.assertEqual(set(versions.values()), {"2.9.3"})

    def test_policy_context_uses_render_objects(self):
        context = build_context({"panels": [{"id": "A"}], "artists": [{"kind": "line", "y_axis": "left"}, {"kind": "text"}], "theme": {"font": {"family": "DejaVu Sans", "size": 8}}})
        self.assertEqual(context["artist_count"], 2)
        self.assertEqual(context["text_artist_count"], 1)
        self.assertEqual(context["font_family"], "DejaVu Sans")

    def test_release_acceptance_covers_profile_and_unified_cli_tests(self):
        source = (ROOT / "scripts" / "release_acceptance.py").read_text(encoding="utf-8")
        self.assertIn('("execution_profiles"', source)
        self.assertIn('("unified_cli"', source)


if __name__ == "__main__":
    unittest.main()
