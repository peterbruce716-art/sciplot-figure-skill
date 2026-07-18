from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
from advisor_common import load_json, validate_payload, write_json


def validate_prior_payload(prior: dict[str, Any]) -> dict[str, Any]:
    try:
        validate_payload(prior, 'figure-prior-v1.schema.json')
    except Exception as exc:
        return {'schema': 'scientificfigure.figure_prior_validation.v1', 'status': 'failed', 'failures': [{'code': 'schema_validation_failed', 'message': str(exc)}], 'warnings': []}
    sig = prior.get('supported_data_signature', {})
    overlap = sorted(set(sig.get('required') or []) & set(sig.get('optional') or []))
    failures = [{'code': 'signature_required_optional_overlap', 'columns': overlap}] if overlap else []
    warnings = []
    prov = prior.get('provenance', {})
    if prov.get('imported_files'):
        warnings.append({'code': 'copied_external_files_require_notice', 'severity': 'warning'})
    return {'schema': 'scientificfigure.figure_prior_validation.v1', 'status': 'failed' if failures else 'pass', 'failures': failures, 'warnings': warnings}


def main() -> int:
    p = argparse.ArgumentParser(description='Validate a VisualSpec-compatible figure prior.')
    p.add_argument('--input', required=True, type=Path); p.add_argument('--report', type=Path)
    a = p.parse_args(); report = validate_prior_payload(load_json(a.input))
    if a.report: write_json(a.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report['status'] == 'pass' else 1

if __name__ == '__main__':
    raise SystemExit(main())
