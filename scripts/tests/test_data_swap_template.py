from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_data_swap import run_data_swap
from validate_data_swap_template import validate_template


class DataSwapTemplateTests(unittest.TestCase):
    def _write_fixture(self, root: Path, *, historical: bool = False, bad_path: bool = False) -> Path:
        (root / "schemas").mkdir()
        (root / "data").mkdir()
        (root / "scripts").mkdir()
        (root / "schemas" / "fig.schema.json").write_text(
            json.dumps({"type": "object", "required": ["value"], "properties": {"value": {"type": "number"}}}),
            encoding="utf-8",
        )
        (root / "data" / "fig.json").write_text('{"value": 1}\n', encoding="utf-8")
        renderer = root / "scripts" / "renderer.py"
        renderer.write_text(
            """from pathlib import Path\nimport argparse, hashlib, json\np=argparse.ArgumentParser(); p.add_argument('--figure'); p.add_argument('--data'); p.add_argument('--out-dir'); p.add_argument('--input-mode'); a=p.parse_args()\nout=Path(a.out_dir); out.mkdir(parents=True, exist_ok=True); (out/'fig').mkdir(exist_ok=True)\nsource=Path(a.data).read_bytes(); target=out/'fig'/'fig.png'; target.write_bytes(source)\nmanifest={'schema':'scientificfigure.data-swap-run.v1','input_mode':a.input_mode,'historical_data_consumed':False,'figures':{'fig':{'output_sha256':{'png':hashlib.sha256(source).hexdigest()}}}}\n(out/'data_swap_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')\n""",
            encoding="utf-8",
        )
        template = {
            "schema": "scientificfigure.data-swap-template.v1",
            "template_id": "unit-test",
            "template_version": "1.0.0",
            "renderer_entrypoint": "scripts/renderer.py",
            "input_mode": "user_supplied",
            "historical_data_consumed": historical,
            "figures": {
                "fig": {
                    "data_schema": "schemas/fig.schema.json",
                    "example_data": "../bad.json" if bad_path else "data/fig.json",
                    "renderer": "scripts/renderer.py",
                    "outputs": ["png"],
                }
            },
        }
        path = root / "template_manifest.json"
        path.write_text(json.dumps(template), encoding="utf-8")
        return path

    def test_valid_template_and_generic_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = self._write_fixture(root)
            report = validate_template(template, root=root)
            self.assertEqual(report["status"], "pass")
            out = root / "out"
            result = run_data_swap(
                root=root,
                template_path=template,
                figure_id="fig",
                data_path=root / "data" / "fig.json",
                out_dir=out,
                input_mode="user_supplied",
            )
            self.assertEqual(result["status"], "pass")
            self.assertTrue((out / "data_swap_manifest.json").is_file())
            invalid = root / "data" / "invalid.json"
            invalid.write_text('{"value": "wrong"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema validation failed"):
                run_data_swap(
                    root=root,
                    template_path=template,
                    figure_id="fig",
                    data_path=invalid,
                    out_dir=root / "invalid-out",
                    input_mode="user_supplied",
                )

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


if __name__ == "__main__":
    unittest.main()
