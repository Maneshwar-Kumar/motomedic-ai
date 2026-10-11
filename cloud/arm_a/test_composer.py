"""Source-bound software regressions; no model calls or local embedding."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cloud.arm_a.composer import ArmAComposer
from approved_registry import ApprovedEvidenceRegistry
from approved_runner import build_approved_runner
from controller_contracts import ResponseType
from diagnose import ReviewedService
from reviewed_controller import ReviewedController, start_session
from session_store import SQLiteSessionStore
from test_approved_integration import ROOT, INDEX, ScriptedRetrieval
from test_text_journeys import ScriptedServiceRetrieval


class ComposerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ApprovedEvidenceRegistry.load(ROOT, INDEX)

    def controller(self, missing=False, outage=False):
        generator = ArmAComposer()
        controller = ReviewedController(self.registry,
            ScriptedRetrieval(self.registry, missing=missing, outage=outage),
            response_generator=generator)
        controller.audience = 'end_user'
        return controller

    def session(self, controller, rid='GEN007', variant='Himalayan BS6'):
        return replace(start_session(self.registry, [rid], variant),
                       generation_lock=controller.response_generator.config.lock)

    def test_exact_wording_zero_calls_and_no_sleep(self):
        c = self.controller()
        with patch('time.sleep', side_effect=AssertionError('Serving may not sleep')):
            _, response, _ = c.next(self.session(c), 'Does this manual allow E20 fuel?')
        self.assertEqual(response.type, ResponseType.SUPPORTED)
        self.assertIn('That does not establish approval for fuel above E20.', response.natural_language)
        self.assertEqual(c.response_generator.last_trace['generation_calls'], 0)
        self.assertEqual(c.response_generator.last_trace['verifier_calls'], 0)
        self.assertTrue(response.cited_pages)

    def test_wrong_variant_is_not_supported(self):
        c = self.controller()
        _, response, _ = c.next(self.session(c, variant='Other bike'), 'E20')
        self.assertNotEqual(response.type, ResponseType.SUPPORTED)

    def test_missing_evidence_is_withheld(self):
        c = self.controller(missing=True)
        _, response, _ = c.next(self.session(c), 'E20')
        self.assertNotEqual(response.type, ResponseType.SUPPORTED)

    def test_retrieval_outage_is_system_error(self):
        c = self.controller(outage=True)
        _, response, _ = c.next(self.session(c), 'E20')
        self.assertEqual(response.type, ResponseType.SYSTEM_ERROR)

    def test_stale_runtime_and_untrusted_cache_fail_closed(self):
        c = self.controller()
        s = self.session(c)
        sid = 'GEN007:candidate-v3'
        response = c.response_generator.compose(c, replace(s, generation_lock='stale'), sid)
        self.assertEqual(response.type, ResponseType.SYSTEM_ERROR)
        response = c.response_generator.compose(c, s, sid, cache_draft={'text':'injection'})
        self.assertEqual(response.type, ResponseType.SYSTEM_ERROR)

    def test_30_frozen_lookup_cases_preserve_source_bound_outputs(self):
        baseline = json.loads((ROOT/'reports/ab30_v2_source_assessment_baseline.json').read_text(encoding='utf-8'))
        blocked = {'GEN025','GEN027','GEN030','GEN039','EXP024','EXP010'}
        for case in baseline['cases']:
            with self.subTest(case=case['record_id']):
                c = self.controller()
                _, response, _ = c.next(self.session(c, case['record_id']), case['query'])
                if case['record_id'] in blocked:
                    self.assertNotEqual(response.type, ResponseType.SUPPORTED)
                else:
                    self.assertEqual(response.type, ResponseType.SUPPORTED)
                    expected = ' '.join(x['required_meaning'] for x in case['required_claims'])
                    self.assertEqual(response.natural_language, expected)

    def test_factory_defaults_to_a(self):
        c = build_approved_runner(INDEX, retriever=ScriptedRetrieval(self.registry))
        self.assertIsInstance(c.response_generator, ArmAComposer)

    def test_service_saves_before_return_and_withholds_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SQLiteSessionStore(Path(folder)/'state.sqlite')
            service = ReviewedService(self.registry, ScriptedServiceRetrieval(self.registry), store)
            self.assertIsInstance(service.controller.response_generator, ArmAComposer)
            s = service.start('GEN007', variant='Himalayan BS6')
            updated, response, _ = service.turn(s.session_id, 'E20')
            self.assertEqual(response.type, ResponseType.SUPPORTED)
            self.assertEqual(store.load(s.session_id).version, updated.version)
            with patch.object(store, 'save', side_effect=OSError('private storage secret')):
                _, response, _ = service.turn(s.session_id, 'E20')
            self.assertEqual(response.type, ResponseType.SYSTEM_ERROR)
            self.assertNotIn('private storage secret', response.natural_language)
            store.close()

if __name__ == '__main__':
    unittest.main()
