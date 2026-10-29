"""The regression gate on a synthetic run: identity binding, rebuilt inputs, re-gating and the bar."""
import json
from pathlib import Path
import tempfile
import unittest

from cloud.grounded_generation import section_assembly as sa
from cloud.grounded_generation import template_answer as ta
from cloud.grounded_generation.section_questions import earlier_turns
from cloud.grounded_generation.test_section_answer import located
from cloud.grounded_generation.test_section_fixture import SOURCE_MANIFEST, build
from tools import regression as rg

QUESTION = 'Where is the charger port?'
THRESHOLDS = {'passed_min': 1, 'system_errors_max': 0, 'forbidden_max': 0, 'warnings_shown_min': 0,
              'reference_pages_sent_min': 1}


class RegressionGateTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='motomedic-regression-'))
        index = build(self.root / 'index')
        (self.root / 'source').mkdir()
        (self.root / 'source/source_manifest.json').write_text(json.dumps(SOURCE_MANIFEST), encoding='utf-8')
        case = {'id': 'R01', 'source': 'synthetic', 'question': QUESTION, 'follow_up_of': None, 'pages': [64],
                'routes': ['SUPPORTED'], 'require': [[r'handlebar']], 'forbid': [r'\b\d+\s?mm\b'], 'warnings': []}
        self.write_set([case])
        self.folder = self.root / 'evals/run/runs/R01'
        self.folder.mkdir(parents=True)
        assembled = sa.assemble(sa.SectionIndex(index), ['chunk_synthetic_1_0'])
        files = {'question.json': json.dumps({'question': QUESTION, 'history': []}),
                 'retrieval.json': json.dumps({'retrieval': {'below_relevance_floor': False}, 'assembled': assembled}),
                 'model_input.txt': sa.model_input(QUESTION, assembled, earlier_turns([])),
                 'schema.json': json.dumps(ta.answer_schema(assembled), indent=1),
                 'instructions.md': 'Follow this system prompt exactly:\n' + ta.SYSTEM_PROMPT,
                 'draft.json': json.dumps(located(assembled))}
        for name, text in files.items():
            (self.folder / name).write_bytes(text.encode('utf-8'))
        identity = rg.answer_identity()
        self.receipt({'answer_identity': identity, 'generator': {'model': identity['generation']['model'],
                                                                 'effort': identity['generation']['effort']}})
        self.assembled = assembled

    def write_set(self, cases, thresholds=THRESHOLDS):
        path = self.root / rg.SET
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'schema': 'test', 'thresholds': thresholds, 'cases': cases}), encoding='utf-8')

    def receipt(self, value):
        (self.root / 'evals/run/receipt.json').write_text(json.dumps(value), encoding='utf-8')

    def check(self):
        return rg.check('evals/run', root=self.root)

    def test_a_current_receipt_whose_turns_rebuild_and_pass_meets_the_bar(self):
        result = self.check()
        self.assertTrue(result['passed'], result)
        self.assertEqual((result['totals']['passed'], result['totals']['reference_pages_sent']), (1, 1))

    def test_a_changed_model_input_or_system_prompt_makes_the_run_stale(self):
        (self.folder / 'model_input.txt').write_bytes(b'changed')
        (self.folder / 'instructions.md').write_bytes(b'an older prompt')
        result = self.check()
        self.assertFalse(result['passed'])
        self.assertEqual(result['problems'], ['MODEL_INPUT_CHANGED:R01', 'SYSTEM_PROMPT_CHANGED:R01'])

    def test_a_receipt_for_another_index_or_generator_is_stale(self):
        identity = rg.answer_identity()
        self.receipt({'answer_identity': dict(identity, index_id='index_other'),
                      'generator': {'model': 'claude-sonnet-5-5', 'effort': 'high'}})
        result = self.check()
        self.assertFalse(result['passed'])
        self.assertEqual(result['problems'], ['REGRESSION_RECEIPT_STALE:index_id', 'REGRESSION_GENERATOR_DIFFERS_FROM_CONTRACT'])
        (self.root / 'evals/run/receipt.json').unlink()
        self.assertEqual(self.check()['problems'], ['REGRESSION_RECEIPT_MISSING:' + str(self.root / 'evals/run')])

    def test_the_current_gate_and_set_are_applied_to_saved_drafts(self):
        draft = dict(located(self.assembled), answer=[{'text': 'Somewhere.', 'evidence_ids': ['E99']}])
        (self.folder / 'draft.json').write_text(json.dumps(draft), encoding='utf-8')
        result = self.check()
        self.assertEqual((result['totals']['system_errors'], result['shortfalls']),
                         (1, ['PASSED_BELOW_MIN', 'SYSTEM_ERRORS_ABOVE_MAX']))

    def test_forbidden_values_missing_cases_and_unset_thresholds_fail(self):
        case = {'id': 'R01', 'question': QUESTION, 'follow_up_of': None, 'pages': [64], 'routes': ['SUPPORTED'],
                'require': [], 'forbid': [r'centre of the handlebar'], 'warnings': []}
        self.write_set([case])
        result = self.check()
        self.assertEqual(result['shortfalls'], ['PASSED_BELOW_MIN', 'FORBIDDEN_MATCHES_ABOVE_MAX'])
        self.write_set([{'id': 'R02', 'question': 'x', 'follow_up_of': None, 'pages': [], 'routes': ['SUPPORTED'],
                         'require': [], 'forbid': [], 'warnings': []}], thresholds=None)
        result = self.check()
        self.assertEqual((result['problems'], result['shortfalls']), (['CASE_NOT_RUN:R02'], ['THRESHOLDS_NOT_SET']))

    def test_matching_normalizes_case_dashes_quotes_and_spaces(self):
        case = {'id': 'X', 'routes': ['SUPPORTED'], 'pages': [], 'warnings': [], 'forbid': [],
                'require': [[r'0\.8\s*(?:mm\s*)?(?:-|to)\s*0\.9'], [r"don't"]]}
        row = rg.score_case(case, 'SUPPORTED', 'Gap  0.8–0.9 mm. Don’t guess.', {'objects': {}})
        self.assertTrue(row['passed'], row)


if __name__ == '__main__':
    unittest.main()
