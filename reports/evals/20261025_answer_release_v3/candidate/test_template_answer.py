"""Section assembly and template gate on the real section index; zero provider calls.

Run from the project root (index at build/index-v3-sections, or MOTOMEDIC_SECTION_INDEX):
python reports/evals/20261025_answer_release_v3/candidate/test_template_answer.py -v
"""
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import section_assembly as sa  # noqa: E402
import template_answer as ta  # noqa: E402

INDEX = Path(os.environ.get('MOTOMEDIC_SECTION_INDEX', ROOT / 'build/index-v3-sections'))
RUNNING_IN = 'At 300 km, does this manual allow full throttle?'
SUPPORT = 'mailto:support@royalenfield.com'


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = sa.SectionIndex(INDEX)

    def sent(self, *phrases):
        """Assemble the section of the first chunk containing every phrase; return (label, assembled)."""
        for cid, chunk in self.index.chunks.items():
            if all(p in chunk['text'] for p in phrases):
                assembled = sa.assemble(self.index, [cid])
                for label, obj in assembled['objects'].items():
                    if all(p in obj['text'] for p in phrases):
                        return label, assembled
        raise AssertionError('no chunk contains ' + ', '.join(phrases))

    def draft(self, label, text, assembled, **overrides):
        value = {'route': 'SUPPORTED', 'coverage': 'COMPLETE', 'answer': [{'text': text, 'evidence_ids': [label]}],
                 'watchout_review': [{'display_id': w, 'decision': 'NOT_APPLICABLE', 'reason': 'not asked'}
                                     for w in assembled['warnings']]}
        value.update(overrides)
        return value

    def rejected(self, draft, assembled, question=RUNNING_IN):
        with self.assertRaises(ta.ReleaseRejected) as ctx:
            ta.gate(draft, assembled, question, SUPPORT)
        return ctx.exception.code

    def test_boxes_join_their_section_and_page_breaks_rejoin(self):
        _label, charger = self.sent('Charger port is located')
        self.assertTrue(charger['warnings'])
        self.assertEqual(len(charger['sections']), 1)
        self.assertIn('(WARNING)', charger['text'])
        _label, language = self.sent('Center press the joystick with the language option')
        self.assertIn('German', language['text'])
        self.assertIn('Italian', language['text'])

    def test_model_input_is_plain_text(self):
        _label, assembled = self.sent('USB 2.0 Type C')
        text = sa.model_input('What output rating is listed for the USB port?', assembled)
        for marker in ('evidence_', 'sha256', 'cref', 'content_layer', '{"', 'review'):
            self.assertNotIn(marker, text)
        self.assertIn('[E', text)

    def test_question_number_is_exempt_but_absent_number_is_rejected(self):
        label, assembled = self.sent('6000', 'full throttle')
        ok = self.draft(label, 'No. At 300 km you are in the 0 to 500 km band: below 6000 rpm and no full throttle.', assembled)
        self.assertEqual(ta.gate(ok, assembled, RUNNING_IN)['route'], 'SUPPORTED')
        self.assertEqual(self.rejected(self.draft(label, 'Keep below 7000 rpm.', assembled), assembled),
                         'NUMBER_NOT_IN_CITED_OBJECT_OR_QUESTION')

    def test_citations_must_be_sent_labels(self):
        label, assembled = self.sent('6000', 'full throttle')
        for ids, code in (([], 'UNCITED_TECHNICAL_ITEM'), (['E999'], 'CITATION_NOT_SENT')):
            draft = self.draft(label, 'No full throttle.', assembled, answer=[{'text': 'No full throttle.', 'evidence_ids': ids}])
            self.assertEqual(self.rejected(draft, assembled), code)
        released = ta.gate(self.draft(label, 'No full throttle.', assembled), assembled, RUNNING_IN)
        self.assertTrue(released['citations'][0]['evidence_id'].startswith('evidence_'))

    def test_every_sent_warning_needs_a_decision(self):
        label, assembled = self.sent('Charger port is located')
        q = 'Where is the charger port?'
        draft = self.draft(label, 'The charger port is on the centre of the handlebar.', assembled)
        self.assertTrue(ta.gate(draft, assembled, q)['text'])
        self.assertEqual(self.rejected(dict(draft, watchout_review=draft['watchout_review'][1:]), assembled, q),
                         'WATCHOUT_NOT_CONSIDERED')
        included = dict(draft, watchout_review=[dict(draft['watchout_review'][0], decision='INCLUDED')]
                        + draft['watchout_review'][1:])
        self.assertEqual(self.rejected(included, assembled, q), 'INCLUDED_WATCHOUT_MISSING')
        first = assembled['warnings'][0]
        included['watchouts'] = [{'text': 'Do not use it in the rain.', 'evidence_ids': [first]}]
        self.assertIn('Watch out: ', ta.gate(included, assembled, q)['text'])

    def test_unsupported_and_nothing_retrieved_use_fixed_fallback(self):
        label, assembled = self.sent('Compression ratio')
        q = 'What compression pressure should a test show?'
        draft = self.draft(label, 'The manual lists a compression ratio of 11.5:1, which is not a test pressure.', assembled,
                           route='UNSUPPORTED', coverage='NONE', disclaimers=[{'text': 'No test pressure is given.'}])
        released = ta.gate(draft, assembled, q, SUPPORT)
        self.assertTrue(released['text'].endswith(ta.FALLBACK_TEXT))
        self.assertEqual((released['escalation_uri'], released['suppressed_disclaimers']), (SUPPORT, 1))
        nothing = ta.no_evidence_release(SUPPORT)
        self.assertEqual((nothing['text'], nothing['provider_calls']), (ta.FALLBACK_TEXT, 0))

    def test_disclaimers_pages_partial_and_caps(self):
        label, assembled = self.sent('6000', 'full throttle')
        for text in ('Another table says 7000 rpm.', 'Page 116 says otherwise.'):
            draft = self.draft(label, 'No full throttle.', assembled, disclaimers=[{'text': text}])
            self.assertEqual(self.rejected(draft, assembled), 'UNCITED_DISCLAIMER_STATES_VALUE_OR_PAGE')
        self.assertEqual(self.rejected(self.draft(label, 'No full throttle (page 12).', assembled), assembled),
                         'PAGE_NOT_OF_CITED_OBJECT')
        self.assertEqual(self.rejected(self.draft(label, 'Below 6000 rpm.', assembled, coverage='PARTIAL'), assembled),
                         'UNDISCLOSED_PARTIAL_ANSWER')
        over = self.draft(label, 'x', assembled, answer=[{'text': 'No full throttle.', 'evidence_ids': [label]}] * 7)
        self.assertEqual(self.rejected(over, assembled), 'TEMPLATE_SECTION_INVALID_OR_OVER_CAP')
        self.assertEqual(self.rejected({'route': 'AMBIGUOUS', 'coverage': 'NONE'}, assembled), 'CLARIFICATION_ROUTE_MISMATCH')


if __name__ == '__main__':
    unittest.main()
