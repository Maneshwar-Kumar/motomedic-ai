"""Verifier-free release gate: real v5-admitted payloads, zero provider calls.

Run from the project root:
PYTHONPATH=. python reports/evals/20261024_answer_release_v1/candidate/test_answer_release.py -v
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
from cloud.grounded_generation.verified_qa import FALLBACK_TEXT  # noqa: E402

INDEX = ROOT / 'build/index-bge-final'
RUNNING_IN = 'At 300 km, does this manual allow full throttle?'
SUPPORT = 'mailto:support@royalenfield.com'


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

    def rejected(self, draft, payload, question=RUNNING_IN):
        with self.assertRaises(ar.ReleaseRejected) as ctx:
            ar.gate(draft, payload, question, self.cands(payload), SUPPORT)
        return ctx.exception.code

    def test_question_number_is_exempt_but_absent_number_is_rejected(self):
        eid, payload = self.payload_for('6000', '500', 'full throttle')
        ok = self.draft(eid, 'No. At 300 km you are in the 0 - 500 km band: below 6000 rpm and no full throttle.', payload)
        self.assertEqual(ar.gate(ok, payload, RUNNING_IN, self.cands(payload))['route'], 'SUPPORTED')
        self.assertEqual(self.rejected(self.draft(eid, 'Keep below 7000 rpm.', payload), payload),
                         'NUMBER_NOT_IN_CITED_OBJECT_OR_QUESTION')

    def test_uncited_and_unadmitted_citations_fail_closed(self):
        eid, payload = self.payload_for('6000', '500', 'full throttle')
        for ids, code in (([], 'UNCITED_TECHNICAL_ITEM'), (['evidence_not_admitted'], 'CITATION_NOT_ADMITTED')):
            draft = self.draft(eid, 'No full throttle.', payload, answer=[{'text': 'No full throttle.', 'evidence_ids': ids}])
            self.assertEqual(self.rejected(draft, payload), code)

    def test_empty_sections_may_be_omitted_but_decisions_may_not(self):
        eid, payload = self.payload_for('6000', '500', 'full throttle')
        minimal = {'route': 'SUPPORTED', 'coverage': 'COMPLETE',
                   'answer': [{'text': 'No full throttle in the 0 - 500 km band.', 'evidence_ids': [eid]}]}
        if self.cands(payload):
            minimal['watchout_review'] = self.draft(eid, 'x', payload)['watchout_review']
        self.assertEqual(ar.gate(minimal, payload, RUNNING_IN, self.cands(payload))['route'], 'SUPPORTED')
        self.assertEqual(self.rejected({k: v for k, v in minimal.items() if k != 'route'}, payload), 'TEMPLATE_SCHEMA')
        self.assertEqual(self.rejected(dict(minimal, route='AMBIGUOUS', coverage='NONE'), payload),
                         'CLARIFICATION_ROUTE_MISMATCH')
        _eid, usb = self.payload_for('USB 2.0 Type C')
        self.assertTrue(self.cands(usb))
        no_review = {'route': 'UNSUPPORTED', 'coverage': 'NONE'}
        self.assertEqual(self.rejected(no_review, usb, 'What output rating is listed for the USB port?'),
                         'WATCHOUT_NOT_CONSIDERED')

    def test_unsupported_shows_fixed_fallback_and_support_route(self):
        eid, payload = self.payload_for('Compression ratio')
        q = 'What compression pressure should a test show?'
        draft = self.draft(eid, 'The manual lists a compression ratio of 11.5:1, which is not a test pressure.', payload,
                           route='UNSUPPORTED', coverage='NONE',
                           disclaimers=[{'text': 'The admitted evidence does not give a test pressure.'}])
        released = ar.gate(draft, payload, q, self.cands(payload), SUPPORT)
        self.assertTrue(released['text'].endswith(FALLBACK_TEXT))
        self.assertNotIn('admitted evidence', released['text'])
        self.assertEqual((released['escalation_uri'], released['suppressed_disclaimers']), (SUPPORT, 1))
        bare = dict(draft, answer=[], disclaimers=[])
        self.assertEqual(ar.gate(bare, payload, q, self.cands(payload), SUPPORT)['text'], FALLBACK_TEXT)
        nothing = ar.no_evidence_release(SUPPORT)
        self.assertEqual((nothing['text'], nothing['provider_calls'], nothing['escalation_uri']), (FALLBACK_TEXT, 0, SUPPORT))

    def test_disclaimer_with_value_or_page_must_cite(self):
        eid, payload = self.payload_for('6000', '500', 'full throttle')
        for text in ('The table elsewhere says 7000 rpm.', 'Page 116 says otherwise.'):
            draft = self.draft(eid, 'No full throttle.', payload, disclaimers=[{'text': text}])
            self.assertEqual(self.rejected(draft, payload), 'UNCITED_DISCLAIMER_STATES_VALUE_OR_PAGE')
        cited = self.draft(eid, 'No full throttle.', payload,
                           disclaimers=[{'text': 'The 6000 rpm limit applies to the first band only.', 'evidence_ids': [eid]}])
        self.assertTrue(ar.gate(cited, payload, RUNNING_IN, self.cands(payload))['text'])
        wrong_page = self.draft(eid, 'No full throttle (page 12).', payload)
        self.assertEqual(self.rejected(wrong_page, payload), 'PAGE_NOT_OF_CITED_OBJECT')

    def test_every_listed_warning_must_be_considered(self):
        eid, payload = self.payload_for('USB 2.0 Type C')
        q = 'What output rating is listed for the USB port?'
        draft = self.draft(eid, 'The charger port is USB 2.0 Type C with 5 V, 2 A output.', payload)
        self.assertTrue(ar.gate(draft, payload, q, self.cands(payload))['text'])
        skipped = dict(draft, watchout_review=draft['watchout_review'][1:])
        self.assertEqual(self.rejected(skipped, payload, q), 'WATCHOUT_NOT_CONSIDERED')
        first = self.cands(payload)[0]
        included = deepcopy(draft)
        included['watchout_review'][0].update(decision='INCLUDED')
        self.assertEqual(self.rejected(included, payload, q), 'INCLUDED_WATCHOUT_MISSING')
        included['watchouts'] = [{'text': 'Follow the manual warning.', 'evidence_ids': [first['display_id']]}]
        released = ar.gate(included, payload, q, self.cands(payload))
        self.assertIn('Watch out: ', released['text'])
        self.assertEqual(released['provider_calls'], 1)

    def test_partial_requires_disclaimer_and_caps_hold(self):
        eid, payload = self.payload_for('6000', '500', 'full throttle')
        partial = self.draft(eid, 'Below 6000 rpm in the 0 - 500 km band.', payload, coverage='PARTIAL')
        self.assertEqual(self.rejected(partial, payload), 'UNDISCLOSED_PARTIAL_ANSWER')
        over = self.draft(eid, 'x', payload, answer=[{'text': 'No full throttle.', 'evidence_ids': [eid]}] * 7)
        self.assertEqual(self.rejected(over, payload), 'TEMPLATE_SECTION_INVALID_OR_OVER_CAP')


if __name__ == '__main__':
    unittest.main()
