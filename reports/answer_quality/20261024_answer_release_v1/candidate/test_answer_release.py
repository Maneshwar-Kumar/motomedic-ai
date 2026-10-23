"""Verifier-free release gate: real v5-admitted payloads, zero provider calls.

Run from the project root:
PYTHONPATH=. python reports/answer_quality/20261024_answer_release_v1/candidate/test_answer_release.py -v
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'reports/grounded_generation/structural_review_v2/candidate'))
import answer_release as ar  # noqa: E402
import serving_source_authority_v5 as v5  # noqa: E402
from approved_registry import ApprovedEvidenceRegistry  # noqa: E402

INDEX = ROOT / 'build/index-bge-final'
RUNNING_IN = 'At 300 km, does this manual allow full throttle?'


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        cls.sa = v5.SourceAuthority(ApprovedEvidenceRegistry.load(ROOT, INDEX), INDEX)
        parents = [json.loads(line) for line in (INDEX / 'parents.jsonl').open(encoding='utf-8')]
        cls.paths = {e: p['section_path'] for p in parents for e in p['evidence_ids']}

    def cands(self, payload):
        return ar.watchout_candidates(payload, self.paths)

    def payload_for(self, *phrases):
        """First reviewed (admittable) object containing every phrase, with its real admitted payload."""
        for eid, row in sorted(self.sa.index_evidence.items()):
            raw = str(row.get('raw_object'))
            if any(p not in raw for p in phrases) or eid not in self.sa.complete_context_ids:
                continue
            chunk = next(c for c in self.sa.chunks.values() if eid in c['evidence_ids'])
            payload = self.sa.assemble({'index_id': self.sa.index_id, 'manual_checksum': self.sa.checksum,
                                        'hits': [deepcopy(chunk)]})
            if eid in payload['evidence']:
                return eid, payload
        raise AssertionError('no admitted object contains ' + ', '.join(phrases))

    def draft(self, eid, text, payload, **overrides):
        value = {'route': 'SUPPORTED', 'coverage': 'COMPLETE', 'answer': [{'text': text, 'evidence_ids': [eid]}],
                 'policy': [], 'watchouts': [], 'disclaimers': [], 'clarification_question': '',
                 'watchout_review': [{'display_id': c['display_id'], 'decision': 'NOT_APPLICABLE', 'reason': 'not asked'}
                                     for c in self.cands(payload)]}
        value.update(overrides)
        return value

    def test_question_number_is_exempt_but_absent_number_is_rejected(self):
        eid, payload = self.payload_for('6000', '500', 'full throttle')
        ok = self.draft(eid, 'No. At 300 km you are in the 0 - 500 km band: below 6000 rpm and no full throttle.', payload)
        self.assertEqual(ar.gate(ok, payload, RUNNING_IN, self.cands(payload))['route'], 'SUPPORTED')
        bad = self.draft(eid, 'Keep below 7000 rpm.', payload)
        with self.assertRaises(ar.ReleaseRejected) as ctx:
            ar.gate(bad, payload, RUNNING_IN, self.cands(payload))
        self.assertEqual(ctx.exception.code, 'NUMBER_NOT_IN_CITED_OBJECT_OR_QUESTION')

    def test_uncited_and_unadmitted_citations_fail_closed(self):
        eid, payload = self.payload_for('6000', '500', 'full throttle')
        for ids, code in (([], 'UNCITED_TECHNICAL_ITEM'), (['evidence_not_admitted'], 'CITATION_NOT_ADMITTED')):
            draft = self.draft(eid, 'No full throttle.', payload, answer=[{'text': 'No full throttle.', 'evidence_ids': ids}])
            with self.assertRaises(ar.ReleaseRejected) as ctx:
                ar.gate(draft, payload, RUNNING_IN, self.cands(payload))
            self.assertEqual(ctx.exception.code, code)

    def test_unsupported_may_carry_cited_fact_with_disclaimer(self):
        eid, payload = self.payload_for('Compression ratio')
        draft = self.draft(eid, 'The manual lists a compression ratio of 11.5:1, which is not a test pressure.', payload,
                           route='UNSUPPORTED', coverage='NONE',
                           disclaimers=[{'text': 'The manual does not give a compression test pressure.'}])
        self.assertEqual(ar.gate(draft, payload, 'What compression pressure should a test show?', self.cands(payload))['route'], 'UNSUPPORTED')
        no_disclaimer = dict(draft, disclaimers=[])
        with self.assertRaises(ar.ReleaseRejected):
            ar.gate(no_disclaimer, payload, 'What compression pressure should a test show?', self.cands(payload))

    def test_every_listed_warning_must_be_considered(self):
        eid, payload = self.payload_for('USB 2.0 Type C')
        self.assertTrue(self.cands(payload))
        draft = self.draft(eid, 'The charger port is USB 2.0 Type C with 5 V, 2 A output.', payload)
        self.assertTrue(ar.gate(draft, payload, 'What output rating is listed for the USB port?', self.cands(payload))['text'])
        skipped = dict(draft, watchout_review=draft['watchout_review'][1:])
        with self.assertRaises(ar.ReleaseRejected) as ctx:
            ar.gate(skipped, payload, 'What output rating is listed for the USB port?', self.cands(payload))
        self.assertEqual(ctx.exception.code, 'WATCHOUT_NOT_CONSIDERED')
        first = self.cands(payload)[0]
        included = deepcopy(draft)
        included['watchout_review'][0].update(decision='INCLUDED')
        with self.assertRaises(ar.ReleaseRejected) as ctx:
            ar.gate(included, payload, 'What output rating is listed for the USB port?', self.cands(payload))
        self.assertEqual(ctx.exception.code, 'INCLUDED_WATCHOUT_MISSING')
        included['watchouts'] = [{'text': 'Follow the manual warning.', 'evidence_ids': [first['display_id']]}]
        released = ar.gate(included, payload, 'What output rating is listed for the USB port?', self.cands(payload))
        self.assertIn('Watch out: ', released['text'])
        self.assertEqual(released['provider_calls'], 1)

    def test_partial_requires_disclaimer_and_caps_hold(self):
        eid, payload = self.payload_for('6000', '500', 'full throttle')
        partial = self.draft(eid, 'Below 6000 rpm in the 0 - 500 km band.', payload, coverage='PARTIAL')
        with self.assertRaises(ar.ReleaseRejected) as ctx:
            ar.gate(partial, payload, RUNNING_IN, self.cands(payload))
        self.assertEqual(ctx.exception.code, 'UNDISCLOSED_PARTIAL_ANSWER')
        over = self.draft(eid, 'x', payload, answer=[{'text': 'No full throttle.', 'evidence_ids': [eid]}] * 7)
        with self.assertRaises(ar.ReleaseRejected) as ctx:
            ar.gate(over, payload, RUNNING_IN, self.cands(payload))
        self.assertEqual(ctx.exception.code, 'TEMPLATE_SECTION_INVALID_OR_OVER_CAP')


if __name__ == '__main__':
    unittest.main()
