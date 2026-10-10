"""Offline tests for real gates, failed dialogue progression and spend accounting."""
from copy import deepcopy
from pathlib import Path
import json
import os
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
os.environ['MOTOMEDIC_TEST_INDEX'] = str(HERE / 'registry_index')
import arm_a
from claude_transport import cost, ClaudeTransport


class TemplateTransport:
    model = 'claude-haiku-4-5-20251001'

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def complete_json(self, policy, payload, schema, **kwargs):
        self.calls.append(deepcopy(payload))
        if self.fail:
            raise RuntimeError('DO_NOT_LEAK_PRIVATE_ERROR_DETAIL')
        if 'wording' in payload.get('claims', [{}])[0]:
            output = {k: deepcopy(payload[k]) for k in ('schema_version','route','step_id','kind','citations')}
            output['claims'] = [{'claim_id': c['claim_id'], 'text': c['wording'][0], 'evidence_ids': c['evidence_ids']} for c in payload['claims']]
        else:
            self_test_types = [v['type'] for v in payload['evidence'].values()]
            if any(t != 'markitdown_page_context' for t in self_test_types):
                raise AssertionError('Verifier source is richer than common Markdown')
            output = {'claims':[{'claim_id':c['claim_id'],'supported':True} for c in payload['claims']], 'unsupported_additions':False}
        return {'output':output,'usage':{},'total_seconds':0,'ttft_seconds':0,'estimated_cost_usd':0,'raw_text':'SOFTWARE_ONLY'}


class ExperimentBoundaries(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((HERE / 'rider_inputs.json').read_text(encoding='utf-8'))['cases']

    def test_real_controller_preserves_source_gaps_and_unresolved_history(self):
        transport = TemplateTransport()
        rows = arm_a.run_cases(transport, self.cases, 'offline-test')
        self.assertEqual(len(rows), 10)
        self.assertEqual(len(transport.calls), 4)
        for row in rows:
            if row['record_id'] in ['lookup_oil_grade', 'EXP040', 'EXP047']:
                self.assertEqual(row['provider_request_count'], 0)
                self.assertEqual(row['output']['type'].value, 'UNSUPPORTED')
                self.assertFalse(row['output']['clarification_question'])
        last = [r for r in rows if r['record_id'] == 'EXP003'][-1]
        self.assertEqual(last['output']['type'].value, 'UNSUPPORTED')
        self.assertIsNone(last['output']['suggested_step_id'])
        outcomes = [a['outcome_enum'].value for a in last['session']['attempted_steps']]
        self.assertIn('ACTION_COMPLETED_UNRESOLVED', outcomes)

    def test_failed_model_does_not_fabricate_attempt_or_lose_later_cases(self):
        rows = arm_a.run_cases(TemplateTransport(fail=True), self.cases, 'offline-failure')
        self.assertEqual(len(rows), 10)
        unresolved = [r for r in rows if r['record_id'] == 'EXP003'][-1]
        self.assertEqual(unresolved['scripted_feedback_not_applied'], 'SCENARIO_NOT_PROGRESSED_NO_MATCHING_PENDING_STEP')
        self.assertNotIn('DO_NOT_LEAK_PRIVATE_ERROR_DETAIL', json.dumps(rows, default=lambda x: getattr(x, 'value', str(x))))

    def test_cache_cost_and_long_prompt_boundary(self):
        self.assertAlmostEqual(cost('claude-haiku-4-5-20251001', {'cache_read_input_tokens':50000,'input_tokens':1000,'output_tokens':500}), .0085)
        self.assertAlmostEqual(cost('claude-haiku-5-5', {'cache_read_input_tokens':100000}), .001)
        self.assertAlmostEqual(cost('claude-haiku-5-5', {'cache_read_input_tokens':100001}), .00500005)

    def test_incomplete_stream_halts_further_spending_and_records_unknown_upper(self):
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'OFFLINE_PLACEHOLDER'}):
            transport = ClaudeTransport('claude-haiku-4-5-20251001')
        with patch.object(transport, 'count', return_value=50000), \
             patch.object(transport, 'request', side_effect=RuntimeError('offline failure')), \
             patch.object(transport, 'save_ledger'):
            with self.assertRaises(RuntimeError):
                transport.complete_messages([{'role':'user','content':'.'}], max_tokens=1800)
            self.assertTrue(transport.halted)
            self.assertAlmostEqual(transport.unknown_charge_upper_usd, .0715)
            with self.assertRaises(RuntimeError):
                transport.complete_messages([{'role':'user','content':'.'}])
            self.assertEqual(transport.dispatched, 1)


if __name__ == '__main__':
    unittest.main()
