from __future__ import annotations
import unittest
import common  # noqa: F401
from advisor_common import ROOT, load_json
from audit_mixed_backend import audit_visualspec
from prepare_ai_visual_review import REVIEW_SCOPE
from resolve_figure_prior import resolve_prior
from validate_figure_prior import validate_prior_payload

PROFILE = {'schema': 'scientificfigure.data_profile.v1', 'schema_version': '1.0', 'source': {'path': 'data.csv', 'sha256': 'sha256:' + '0' * 64, 'sheet': None}, 'row_count': 3, 'columns': [{'name': 'sample_id'}, {'name': 'pc1'}, {'name': 'pc2'}, {'name': 'group'}]}

class FigurePriorMixedBackendTests(unittest.TestCase):
    def test_all_builtin_priors_validate(self) -> None:
        for path in sorted((ROOT / 'styles' / 'figure_priors').glob('*.json')):
            self.assertEqual('pass', validate_prior_payload(load_json(path))['status'], path.name)
    def test_resolve_prior_reports_visualspec_hints(self) -> None:
        report = resolve_prior('pca', data_profile=PROFILE, target_journal='acta_materialia')
        self.assertEqual('pass', report['status']); self.assertIn('style_tokens', report['visualspec_hints'])
    def test_resolve_prior_warns_on_missing_columns(self) -> None:
        self.assertEqual('warning', resolve_prior('grouped_bar', data_profile=PROFILE)['status'])
    def test_mixed_backend_audit_blocks_semantic_vector_png(self) -> None:
        spec = {'schema': 'scientificfigure.visualspec.v2', 'figure': {'size_mm': [183, 90], 'dpi': 300}, 'panels': [{'id': 'a', 'bbox_normalized': [0, 0, 0.5, 1], 'representation': 'semantic_vector', 'backend': 'r', 'required_output': 'png'}]}
        report = audit_visualspec(spec)
        self.assertEqual('failed', report['status']); self.assertIn('semantic_vector_panel_requires_vector_output', {x['code'] for x in report['failures']})
    def test_reviewer_scope_includes_scientific_rubric(self) -> None:
        self.assertIn('scientific_question_clarity', REVIEW_SCOPE); self.assertIn('statistical_transparency', REVIEW_SCOPE)

if __name__ == '__main__':
    unittest.main()
