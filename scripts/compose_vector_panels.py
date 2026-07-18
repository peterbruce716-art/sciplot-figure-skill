from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
from advisor_common import load_json, write_json
from audit_mixed_backend import audit_visualspec


def build_composition_manifest(spec: dict[str, Any], panel_outputs: dict[str, Any] | None = None) -> dict[str, Any]:
    audit = audit_visualspec(spec); outputs = panel_outputs or {}; panels = []
    for panel in spec.get('panels', []) or []:
        pid = str(panel.get('id')); required = panel.get('required_output', 'svg')
        panels.append({'panel_id': pid, 'backend': panel.get('backend', 'matplotlib'), 'required_output': required, 'output': outputs.get(pid, {}), 'composition_mode': 'native_vector' if required in {'svg', 'pdf'} else 'declared_raster', 'rasterization_reason': panel.get('rasterization_reason')})
    return {'schema': 'scientificfigure.vector_panel_composition.v1', 'status': 'blocked' if audit['status'] == 'failed' else 'ready', 'audit': audit, 'panels': panels, 'constraints': ['Final output must still pass vector QA.', 'Raster panels require explicit representation and reason.']}


def main() -> int:
    p = argparse.ArgumentParser(description='Build a traceable vector panel composition manifest.')
    p.add_argument('--visualspec', required=True, type=Path); p.add_argument('--panel-output-json', type=Path); p.add_argument('--output', required=True, type=Path)
    a = p.parse_args(); manifest = build_composition_manifest(load_json(a.visualspec), load_json(a.panel_output_json) if a.panel_output_json else None)
    write_json(a.output, manifest); print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)); return 0 if manifest['status'] == 'ready' else 1

if __name__ == '__main__':
    raise SystemExit(main())
