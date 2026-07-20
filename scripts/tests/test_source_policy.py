from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from validate_source_policy import validate_source_policy


class SourcePolicyTests(unittest.TestCase):
    def _fixture(self, *, forbidden: bool = False, stale_output: bool = False) -> tuple[Path, Path, Path]:
        temp = Path(tempfile.mkdtemp())
        (temp / "inputs").mkdir()
        reference = temp / "inputs" / "fig3_reference.png"
        reference.write_bytes(b"fresh-reference")
        relative = "inputs/historical_table.csv" if forbidden else "inputs/fig3_reference.png"
        if forbidden:
            (temp / relative).parent.mkdir(parents=True, exist_ok=True)
            (temp / relative).write_bytes(b"stale")
        policy = temp / "source-policy.json"
        fresh_output = temp / "fresh_data" / "fig3_curves.json"
        fresh_output.parent.mkdir()
        fresh_output.write_text(
            json.dumps(
                {
                    "source": "inputs/fig3_reference.png",
                    "source_sha256": "bad" if stale_output else hashlib.sha256(reference.read_bytes()).hexdigest(),
                    "historical_data_consumed": False,
                }
            ),
            encoding="utf-8",
        )
        policy.write_text(
            json.dumps(
                {
                    "data_policy": "fresh_digitization",
                    "historical_data_allowed": False,
                    "allowed_reference_inputs": [relative],
                    "fresh_outputs_required": ["fresh_data/fig3_curves.json"],
                }
            ),
            encoding="utf-8",
        )
        consumed = temp / "consumed-inputs.json"
        consumed.write_text(
            json.dumps(
                {
                    "historical_data_consumed": False,
                    "forbidden_path_tokens": ["historical", "csv"],
                    "inputs": [{"path": relative, "sha256": "bad" if forbidden else hashlib.sha256(reference.read_bytes()).hexdigest()}],
                }
            ),
            encoding="utf-8",
        )
        return temp, policy, consumed

    def test_accepts_fresh_pdf_trace_source_identity(self) -> None:
        root = Path(tempfile.mkdtemp())
        source_pdf = root / "paper.pdf"
        source_pdf.write_bytes(b"fresh-pdf")
        digest = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
        policy = root / "source-policy.json"
        policy.write_text(json.dumps({
            "data_policy": "fresh_pdf_trace",
            "historical_data_allowed": False,
            "historical_data_consumed": False,
            "source_pdf_sha256": digest,
            "figures": ["3"],
        }), encoding="utf-8")
        consumed = root / "consumed.json"
        consumed.write_text(json.dumps({
            "historical_data_consumed": False,
            "source_pdf": {"name": source_pdf.name, "sha256": digest},
            "figure_order": ["3"],
        }), encoding="utf-8")
        report = validate_source_policy(root=root, policy_path=policy, consumed_path=consumed, source_pdf_path=source_pdf)
        self.assertEqual(report["status"], "pass")

    def test_rejects_stale_fresh_pdf_trace_source(self) -> None:
        root = Path(tempfile.mkdtemp())
        source_pdf = root / "paper.pdf"
        source_pdf.write_bytes(b"fresh-pdf")
        policy = root / "source-policy.json"
        policy.write_text(json.dumps({
            "data_policy": "fresh_pdf_trace",
            "historical_data_allowed": False,
            "source_pdf_sha256": "stale",
            "figures": ["3"],
        }), encoding="utf-8")
        consumed = root / "consumed.json"
        consumed.write_text(json.dumps({
            "historical_data_consumed": False,
            "source_pdf": {"name": source_pdf.name, "sha256": "stale"},
            "figure_order": ["3"],
        }), encoding="utf-8")
        report = validate_source_policy(root=root, policy_path=policy, consumed_path=consumed, source_pdf_path=source_pdf)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any(item["check"] == "source_pdf_current_hash" for item in report["failures"]))

    def test_accepts_current_png_and_hash(self) -> None:
        root, policy, consumed = self._fixture()
        report = validate_source_policy(root=root, policy_path=policy, consumed_path=consumed)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["failures"], [])

    def test_rejects_forbidden_historical_input(self) -> None:
        root, policy, consumed = self._fixture(forbidden=True)
        report = validate_source_policy(root=root, policy_path=policy, consumed_path=consumed)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any(item["check"] == "forbidden_path" for item in report["failures"]))

    def test_rejects_path_escape(self) -> None:
        root, policy, consumed = self._fixture()
        payload = json.loads(consumed.read_text(encoding="utf-8"))
        payload["inputs"][0]["path"] = "../outside.png"
        consumed.write_text(json.dumps(payload), encoding="utf-8")
        policy_payload = json.loads(policy.read_text(encoding="utf-8"))
        policy_payload["allowed_reference_inputs"] = ["../outside.png"]
        policy.write_text(json.dumps(policy_payload), encoding="utf-8")
        report = validate_source_policy(root=root, policy_path=policy, consumed_path=consumed)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any(item["check"] == "path_escape" for item in report["failures"]))

    def test_accepts_fresh_output_bound_to_current_reference(self) -> None:
        root, policy, consumed = self._fixture()
        report = validate_source_policy(root=root, policy_path=policy, consumed_path=consumed)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["checked_fresh_outputs"], ["fresh_data/fig3_curves.json"])

    def test_rejects_stale_fresh_output_hash(self) -> None:
        root, policy, consumed = self._fixture(stale_output=True)
        report = validate_source_policy(root=root, policy_path=policy, consumed_path=consumed)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any(item["check"] == "fresh_output_source_hash" for item in report["failures"]))


if __name__ == "__main__":
    unittest.main()
