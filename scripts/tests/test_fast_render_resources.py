from __future__ import annotations

import copy

from common import ScientificFigureReproductionTestBase, Path, tempfile

import matplotlib.pyplot as plt

from render_visualspec_matplotlib import render_visualspec


class RenderResourceTests(ScientificFigureReproductionTestBase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.initial_figures = set(plt.get_fignums())
        self.addCleanup(self.close_test_figures)
        self.user_figure = plt.figure()
        self.expected_figures = set(plt.get_fignums())

    def close_test_figures(self) -> None:
        for number in set(plt.get_fignums()) - self.initial_figures:
            plt.close(number)

    def test_data_failures_do_not_accumulate_figures(self) -> None:
        spec = self._line_spec()
        spec["panels"][0]["plots"][0]["data"] = {
            "source": "missing.csv", "mapping": {"x": "x", "y": "y"}
        }
        for attempt in range(3):
            with self.subTest(attempt=attempt):
                with self.assertRaises(FileNotFoundError):
                    render_visualspec(spec, self.root / "out", spec_path=str(self.root / "spec.json"))
                self.assertEqual(self.expected_figures, set(plt.get_fignums()))

    def test_export_failure_closes_only_the_renderer_figure(self) -> None:
        output = self.root / "out"
        (output / "render.png").mkdir(parents=True)
        with self.assertRaises(OSError):
            render_visualspec(self._line_spec(), output, output_formats=("png",))
        self.assertEqual(self.expected_figures, set(plt.get_fignums()))

    def test_success_preserves_user_figures_and_support_files(self) -> None:
        output = self.root / "out"
        spec = self._line_spec()
        original = copy.deepcopy(spec)
        for attempt in range(2):
            manifest = render_visualspec(spec, output, output_formats=("png",))
            self.assertEqual("pass", manifest["render_status"])
            self.assertEqual(original, spec)
        self.assertGreater((output / "render.png").stat().st_size, 0)
        self.assertTrue((output / "render_semantics.json").is_file())
        self.assertEqual(self.expected_figures, set(plt.get_fignums()))


if __name__ == "__main__":
    import unittest
    unittest.main()
