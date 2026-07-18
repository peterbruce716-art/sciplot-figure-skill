from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
from advisor_common import load_json, validate_payload, write_json

VECTOR_OUTPUTS = {'svg', 'pdf', 'mixed'}


def audit_visualspec(spec: dict[str, Any]) -> dict[str, Any]:
    failures = []; warnings = []; panels = []
    for panel in spec.get('panels', []) or []:
        pid = str(panel.get('id')); backend = panel.get('backend', 'matplotlib'); out = panel.get('required_output', 'svg'); rep = panel.get('representation')
        panels.append({'panel_id': pid, 'backend': backend, 'required_output': out, 'representation': rep})
        if backend in {'matplotlib', 'r', 'project'} and rep == 'semantic_vector' and out not in VECTOR_OUTPUTS:
            failures.append({'code': 'semantic_vector_panel_requires_vector_output', 'panel_id': pid, 'backend': backend, 'required_output': out})
        if backend == 'r' and out == 'png' and rep != 'rasterized_panel':
            failures.append({'code': 'r_png_output_must_be_declared_rasterized', 'panel_id': pid})
        if rep == 'rasterized_panel' and not panel.get('rasterization_reason'):
            failures.append({'code': 'rasterized_panel_missing_reason', 'panel_id': pid})
        if backend == 'unknown':
            warnings.append({'code': 'unknown_backend', 'severity': 'warning', 'panel_id': pid})
    report = {'schema': 'scientificfigure.mixed_backend_audit.v1', 'status': 'failed' if failures else ('warning' if warnings else 'pass'), 'panels': panels, 'failures': failures, 'warnings': warnings}
    validate_payload(report, 'mixed-backend-audit-v1.schema.json')
    return report


def main() -> int:
    p = argparse.ArgumentParser(description='Audit VisualSpec mixed backend metadata.')
    p.add_argument('--visualspec', required=True, type=Path); p.add_argument('--report', type=Path)
    a = p.parse_args(); report = audit_visualspec(load_json(a.visualspec))
    if a.report: write_json(a.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)); return 0 if report['status'] != 'failed' else 1

if __name__ == '__main__':
    raise SystemExit(main())
