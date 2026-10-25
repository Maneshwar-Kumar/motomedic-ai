"""Refusal-only detection and exact authority regressions, no provider call."""
from copy import deepcopy
from pathlib import Path
import os
import unittest
from unittest.mock import patch

from approved_registry import ApprovedEvidenceRegistry
from cloud.grounded_generation.fuse_refusal import detect_refusal, _hazard

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        index = Path(os.environ.get('MOTOMEDIC_TEST_INDEX', str(root / 'build/index-bge-final')))
        cls.r = ApprovedEvidenceRegistry.load(root, index)

    def test_bridge_and_wire_refused_with_exact_source_citations(self):
        for query in ('Can I bridge a blown fuse with wire?',
                      'Can I use foil instead of a fuse?',
                      'How can I jumper a defective fuse?'):
            with self.subTest(query=query):
                result = detect_refusal(self.r, query)
                self.assertEqual(result['route'], 'SAFETY_STOP')
                self.assertEqual(result['provider_calls'], 0)
                self.assertEqual(result['permitted_positive_step_ids'], [])
                self.assertTrue(all(c['pdf_page'] == 112 for c in result['citation_mapping']))
                self.assertIn('fire', result['natural_language'])

    def test_different_explicit_rating_refused(self):
        for query in ('Can I fit a 20A fuse for the 10A fuse?',
                      'Can I replace a 10 amp fuse with a 15 amp spare?',
                      'Could I use a higher rated horn fuse?'):
            self.assertEqual(detect_refusal(self.r, query)['route'], 'SAFETY_STOP')

    def test_harmless_fact_or_same_rating_queries_are_not_admission(self):
        for query in ('Which fuse protects the horn?',
                      'Compare the 10A and 15A fuse entries.',
                      'Can I use the specified 10A and 15A fuses in their correct holders?',
                      'What rating is specified for F7?',
                      'Can I replace a 10A fuse with the same 10A rating?',
                      'What is the metal fuel tank capacity?',
                      'Can I bridge this stream?'):
            self.assertIsNone(detect_refusal(self.r, query))

    def test_detection_does_not_depend_on_reviewed_question_wording(self):
        self.assertIsNotNone(detect_refusal(self.r,
            'A remote trail idea: substitute a bit of metal for my failed fuse.'))

    def test_source_changed_refusal_binding_fails_closed(self):
        with patch.object(self.r, 'source_ready', return_value=False):
            with self.assertRaisesRegex(ValueError, 'SOURCE_BINDING'):
                detect_refusal(self.r, 'Can I jumper a fuse?')

    def test_warning_object_changed_rejected(self):
        eid = 'evidence_00497a5a6998712d564a2df2'
        original = deepcopy(self.r.evidence[eid])
        try:
            self.r.evidence[eid]['raw_object']['text'] += ' altered'
            with self.assertRaises(ValueError):
                detect_refusal(self.r, 'Can I bridge a fuse?')
        finally:
            self.r.evidence[eid] = original

    def test_scope_artifact_changed_rejected(self):
        with patch('cloud.grounded_generation.fuse_refusal.SCOPE_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'SCOPE_BINDING'):
                detect_refusal(self.r, 'Can I jumper a fuse?')

    def test_none_or_nontext_is_not_refusal(self):
        self.assertIsNone(_hazard(None))

if __name__ == '__main__':
    unittest.main()



