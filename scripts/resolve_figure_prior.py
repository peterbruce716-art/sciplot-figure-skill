from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
from advisor_common import ROOT, load_json, write_json
from validate_figure_prior import validate_prior_payload

ALIASES = {'line': 'line_with_uncertainty', 'line_with_error_band': 'line_with_uncertainty', 'bar': 'grouped_bar', 'scatter': 'scatter_regression', 'box': 'box_violin', 'violin': 'box_violin'}


def _columns(profile: dict[str, Any] | None) -> set[str]:
    return {str(c.get('name')) for c in (profile or {}).get('columns', []) if c.get('name')}


def resolve_prior(figure_type: str, *, data_profile: dict[str, Any] | None = None, target_journal: str | None = None) -> dict[str, Any]:
    canonical = ALIASES.get(figure_type, figure_type)
    path = ROOT / 'styles' / 'figure_priors' / f'{canonical}.json'
    if not path.exists():
        raise FileNotFoundError(f'unknown figure prior: {figure_type}')
    prior = load_json(path); validation = validate_prior_payload(prior)
    if validation['status'] != 'pass':
        raise ValueError(json.dumps(validation, ensure_ascii=False))
    available = _columns(data_profile); required = list(prior['supported_data_signature']['required'])
    missing = [c for c in required if c not in available] if available else []
    return {'schema': 'scientificfigure.figure_prior_resolution.v1', 'status': 'warning' if missing else 'pass', 'figure_type': canonical, 'target_journal': target_journal, 'visualspec_hints': {'style_tokens': prior['style_tokens'], 'layout_priors': prior['layout_priors']}, 'prior': prior, 'warnings': [{'code': 'missing_required_columns', 'columns': missing}] if missing else [], 'provenance': prior['provenance']}


def main() -> int:
    p = argparse.ArgumentParser(description='Resolve a figure prior into VisualSpec-compatible hints.')
    p.add_argument('--figure-type', required=True); p.add_argument('--data-profile', type=Path); p.add_argument('--target-journal'); p.add_argument('--output', type=Path)
    a = p.parse_args(); report = resolve_prior(a.figure_type, data_profile=load_json(a.data_profile) if a.data_profile else None, target_journal=a.target_journal)
    if a.output: write_json(a.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)); return 0

if __name__ == '__main__':
    raise SystemExit(main())
