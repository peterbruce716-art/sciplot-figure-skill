from __future__ import annotations

from common import *


class ScoreBatchTests(ScientificFigureReproductionTestBase):
    def test_complete_batch_passes_and_writes_per_figure_evidence(self) -> None:
        module = load_module("score_batch", SCRIPTS / "score_batch.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (24, 16), "white").save(root / "source.png")
            Image.new("RGB", (24, 16), "white").save(root / "actual.png")
            manifest = {
                "schema": "scientificfigure.visual_batch.v1",
                "figures": [{"id": "fig-a", "source": "source.png", "actual": "actual.png", "thresholds": {"max_mae_0_1": 0.0, "min_ssim_score": 1.0}}],
            }
            manifest_path = root / "batch.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            report = module.score_batch(manifest_path, root / "qa", project_root=root)
            self.assertEqual("pass", report["status"])
            self.assertTrue((root / "qa" / "fig-a.score.json").is_file())
            self.assertTrue((root / "qa" / "fig-a" / "overlay_50.png").is_file())

    def test_missing_figure_and_threshold_regression_fail_closed(self) -> None:
        module = load_module("score_batch_fail", SCRIPTS / "score_batch.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (20, 20), "white").save(root / "source.png")
            Image.new("RGB", (20, 20), "black").save(root / "actual.png")
            manifest = {
                "schema": "scientificfigure.visual_batch.v1",
                "figures": [
                    {"id": "changed", "source": "source.png", "actual": "actual.png", "thresholds": {"max_mae_0_1": 0.1}},
                    {"id": "missing", "source": "source.png", "actual": "missing.png"},
                ],
            }
            manifest_path = root / "batch.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            report = module.score_batch(manifest_path, root / "qa")
            self.assertEqual("failed", report["status"])
            self.assertTrue(any(item.startswith("changed:") for item in report["failures"]))
            self.assertTrue(any(item.startswith("missing:") for item in report["failures"]))

    def test_duplicate_figure_ids_are_rejected(self) -> None:
        module = load_module("score_batch_duplicate", SCRIPTS / "score_batch.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {"schema": "scientificfigure.visual_batch.v1", "figures": [{"id": "a", "source": "s", "actual": "a"}, {"id": "a", "source": "s", "actual": "a"}]}
            manifest_path = root / "batch.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate figure id"):
                module.score_batch(manifest_path, root / "qa")
