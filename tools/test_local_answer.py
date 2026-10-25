"""The local experiment tool's release step on the synthetic index; no model, network or cloud."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from cloud.grounded_generation import section_assembly as sa
from cloud.grounded_generation import template_answer as ta
from cloud.grounded_generation.test_section_answer import located
from cloud.grounded_generation.test_section_fixture import build
from tools import local_answer


class LocalAnswerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='motomedic-local-answer-'))
        self.index = build(self.tmp / 'index')
        self.out = self.tmp / 'answer'
        self.out.mkdir()
        self.assembled = sa.assemble(sa.SectionIndex(self.index), ['chunk_synthetic_1_0'])
        (self.out / 'question.json').write_text(json.dumps({'question': 'Where is the charger port?', 'history': []}))
        (self.out / 'retrieval.json').write_text(json.dumps({'retrieval': {}, 'assembled': self.assembled}))

    def release(self):
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            local_answer.release(argparse.Namespace(out=str(self.out), index=str(self.index)))
        return json.loads((self.out / 'release.json').read_text(encoding='utf-8')), printed.getvalue()

    def test_a_valid_draft_is_released_by_the_serving_gate(self):
        (self.out / 'draft.json').write_text(json.dumps(located(self.assembled)))
        result, printed = self.release()
        self.assertEqual(result['route'], 'SUPPORTED')
        self.assertIn('ROUTE: SUPPORTED', printed)
        self.assertIn('The charger port is on the centre of the handlebar.', printed)
        self.assertIn('Pages: 64', printed)

    def test_a_bad_or_duplicate_key_draft_is_a_system_error_with_the_gate_code(self):
        bad = dict(located(self.assembled), answer=[{'text': 'Somewhere.', 'evidence_ids': ['E99']}])
        (self.out / 'draft.json').write_text(json.dumps(bad))
        result, printed = self.release()
        self.assertEqual((result['route'], result['reason']), ('SYSTEM_ERROR', 'GATE_CITATION_NOT_SENT'))
        self.assertIn('SYSTEM_ERROR (GATE_CITATION_NOT_SENT)', printed)
        (self.out / 'draft.json').write_text('{"route": "SUPPORTED", "route": "UNSUPPORTED"}')
        result, _ = self.release()
        self.assertEqual(result['reason'], 'GATE_INVALID_DRAFT_JSON')

    def test_nothing_retrieved_needs_no_draft(self):
        (self.out / 'release.json').write_text(json.dumps(ta.no_evidence_release('mailto:support@royalenfield.com')))
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            local_answer.release(argparse.Namespace(out=str(self.out), index=str(self.index)))
        self.assertIn(ta.FALLBACK_TEXT, printed.getvalue())


if __name__ == '__main__':
    unittest.main()
