from __future__ import annotations

from common import Path, tempfile, unittest, zipfile
from build_skill_package import build_package


class PackageContentsTests(unittest.TestCase):
    def test_package_inside_source_does_not_include_itself(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            root.mkdir()
            (root / "SKILL.md").write_text("skill")
            output = root / "package.zip"
            for _ in range(2):
                build_package(root, output)
                with zipfile.ZipFile(output) as archive:
                    self.assertEqual(["skill/SKILL.md"], archive.namelist())

    def test_release_dist_is_excluded_but_nested_assets_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            for name in ["SKILL.md", "dist/old.zip", "dist/package_validation.json", "assets/dist/data.txt", "assets/reference.zip"]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture")
            output = build_package(root, root / "dist" / "new.zip")
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(
                    {"skill/SKILL.md", "skill/assets/dist/data.txt", "skill/assets/reference.zip"},
                    set(archive.namelist()),
                )


if __name__ == "__main__":
    unittest.main()
