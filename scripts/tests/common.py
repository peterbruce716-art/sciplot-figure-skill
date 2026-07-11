from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


visualspec = load_module("visualspec", SCRIPTS / "visualspec.py")




_ORIGINAL_SUBPROCESS_RUN = subprocess.run

def _run_with_default_timeout(*args, **kwargs):
    kwargs.setdefault("timeout", 120)
    return _ORIGINAL_SUBPROCESS_RUN(*args, **kwargs)

subprocess.run = _run_with_default_timeout


class ScientificFigureReproductionTestBase(unittest.TestCase):
    def _line_spec(self) -> dict[str, object]:
        return {
            "schema": "scientificfigure.visualspec.v2",
            "figure": {"size_mm": [50.8, 33.8667], "dpi": 300, "crop_mode": "fixed_canvas"},
            "panels": [
                {
                    "id": "A",
                    "bbox_normalized": [0.15, 0.18, 0.75, 0.72],
                    "source_strategy": "raw_data",
                    "representation": "semantic_vector",
                    "axes": {"x": {"limits": [0, 1]}, "y": {"limits": [0, 1]}},
                    "plots": [{"type": "line", "data": {"x": [0, 1], "y": [0, 1]}, "style": {"color": "#000000"}}],
                    "annotations": [],
                }
            ],
        }

    def _single_plot_spec(self, plot: dict[str, object]) -> dict[str, object]:
        spec = self._line_spec()
        spec["figure"] = {"size_mm": [50.8, 33.8667], "dpi": 120, "crop_mode": "fixed_canvas"}
        spec["panels"][0]["plots"] = [plot]
        return spec

