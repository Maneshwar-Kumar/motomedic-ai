"""Durable text journey regressions; scripted riders/providers, no live accuracy claim."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from approved_registry import ApprovedEvidenceRegistry
from controller_contracts import Fact, Outcome, ResponseType
from constrained_generator import ConstrainedGenerator, SemanticSupportAdapter
from diagnose import ReviewedService
from reviewed_controller import ReviewedController
from session_store import SessionConflict, SessionOperationError, SQLiteSessionStore
from test_approved_integration import INDEX, ROOT, ScriptedProvider, ScriptedRetrieval


class ScriptedServiceRetrieval(ScriptedRetrieval):
    def reviewed_controller(self, registry, semantic_verifier=None):
        return ReviewedController(registry, self, semantic_verifier)


class TextJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ApprovedEvidenceRegistry.load(ROOT, INDEX)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'rider-sessions.sqlite'
        self.store = SQLiteSessionStore(self.path)
        self.provider, self.judge = ScriptedProvider(), ScriptedProvider(judge=True)
        self.pipeline = ConstrainedGenerator(self.provider, SemanticSupportAdapter(self.judge))
        self.service = self.make_service(self.store)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def make_service(self, store):
        registry = deepcopy(self.registry)
        retrieval = ScriptedServiceRetrieval(registry)
        return ReviewedService(registry, retrieval, store, response_generator=self.pipeline)

    def centred_action(self):
        s = self.service.start('EXP003', self.registry.source['variant'])
        s, response, _ = self.service.turn(s.session_id, 'How do I cancel the turn signal?')
        self.assertEqual(response.type, ResponseType.AMBIGUOUS)
        s = self.service.feedback(s.session_id, Outcome.OBSERVED_NORMAL, 'centred',
                                  fact=Fact(True, 'BOOLEAN'))
        s, response, _ = self.service.turn(s.session_id, 'It has returned to centre.')
        self.assertEqual(response.type, ResponseType.SUPPORTED)
        self.assertEqual(response.suggested_step_id, 'EXP003:candidate-v3')
        return s, response

    def test_gen003_durable_lookup_valid_metadata_and_redacted_trace(self):
        s = self.service.start('GEN003', self.registry.source['variant'])
        self.assertFalse(s.known_observations())
        s, response, _ = self.service.turn(s.session_id, 'PRIVATE_RIDER_TEXT mirror distance')
        self.assertEqual(response.type, ResponseType.SUPPORTED)
        self.assertEqual(self.store.load(s.session_id), s)
        self.assertTrue(all(p['pdf_page'] == 13 for p in response.cited_pages))
        self.assertNotIn('PRIVATE_RIDER_TEXT', json.dumps(self.service.last_trace))
        self.assertNotIn('raw_object', json.dumps(response.cited_pages))
        self.assertEqual((self.provider.calls, self.judge.calls), (1, 1))

    def test_exp003_reopens_persisted_outcomes_and_escalates_without_repeat(self):
        s, response = self.centred_action()
        observations = s.known_observations()
        s = self.service.feedback(s.session_id, Outcome.ACTION_COMPLETED_UNRESOLVED, 'still-on')
        self.assertEqual(s.known_observations(), observations)
        self.assertEqual(s.active_attempts()[-1].outcome_enum, Outcome.ACTION_COMPLETED_UNRESOLVED)
        self.assertEqual(s.active_attempts()[-1].observed_details, ())
        self.store.close()
        self.store = SQLiteSessionStore(self.path)
        self.service = self.make_service(self.store)
        self.assertEqual(self.store.load(s.session_id), s)
        for query in ('It still flashes.', 'Try that same step again.'):
            s, response, _ = self.service.turn(s.session_id, query)
            self.assertEqual(response.type, ResponseType.UNSUPPORTED)
            self.assertIsNone(response.suggested_step_id)
            self.assertEqual(response.escalation_uri, 'mailto:support@royalenfield.com')
        completed = [a for a in s.active_attempts() if a.condition_id is None]
        self.assertEqual(len(completed), 1)
        self.assertEqual((self.provider.calls, self.judge.calls), (1, 1))

    def test_normal_observation_and_unresolved_action_remain_distinct_events(self):
        s, _ = self.centred_action()
        s = self.service.feedback(s.session_id, Outcome.ACTION_COMPLETED_UNRESOLVED, 'unresolved')
        history = self.store.load(s.session_id).history()
        normal = [a for a, superseded in history if a.outcome_enum == Outcome.OBSERVED_NORMAL]
        unresolved = [a for a, superseded in history if a.outcome_enum == Outcome.ACTION_COMPLETED_UNRESOLVED]
        self.assertEqual(len(normal), 1)
        self.assertEqual(len(unresolved), 1)
        self.assertIsNotNone(normal[0].condition_id)
        self.assertIsNone(unresolved[0].condition_id)
        self.assertTrue(normal[0].observed_details)
        self.assertFalse(unresolved[0].observed_details)

    def test_false_and_unclear_observations_never_release_action(self):
        for mode in ('false', 'unclear'):
            with self.subTest(mode=mode):
                s = self.service.start('EXP003', self.registry.source['variant'])
                s, _, _ = self.service.turn(s.session_id, 'cancel signal')
                if mode == 'false':
                    s = self.service.feedback(s.session_id, Outcome.OBSERVED_ABNORMAL, 'false',
                                              fact=Fact(False, 'BOOLEAN'))
                else:
                    s = self.service.feedback(s.session_id, Outcome.UNCLEAR, 'unclear')
                _, response, _ = self.service.turn(s.session_id, 'still uncertain')
                self.assertNotEqual(response.type, ResponseType.SUPPORTED)
                self.assertIsNone(response.suggested_step_id)
        self.assertEqual((self.provider.calls, self.judge.calls), (0, 0))

    def test_resolution_is_customer_reported_and_never_mechanical_success(self):
        s, _ = self.centred_action()
        s = self.service.feedback(s.session_id, Outcome.RESOLVED, 'fixed')
        _, response, _ = self.service.turn(s.session_id, 'The light is off now.')
        self.assertEqual(response.session_status, 'CUSTOMER_REPORTED_RESOLVED')
        self.assertIn('not been mechanically verified', response.natural_language)
        self.assertIsNone(response.suggested_step_id)
        self.assertEqual((self.provider.calls, self.judge.calls), (1, 1))

    def test_store_rejects_attempt_history_rewrite_and_scope_switch(self):
        s, _ = self.centred_action()
        for mutation in (replace(s, attempted_steps=(), version=s.version + 1),
                         replace(s, bike_variant='wrong', version=s.version + 1)):
            with self.assertRaises(SessionConflict):
                self.store.save(mutation, expected_version=s.version)
        self.assertEqual(self.store.load(s.session_id), s)

    def test_unsupported_and_retrieval_failure_have_distinct_persisted_routes(self):
        s = self.service.start('GEN003', self.registry.source['variant'])
        s, response, _ = self.service.turn(s.session_id, 'undocumented repair', unsupported_request=True)
        self.assertEqual(response.type, ResponseType.UNSUPPORTED)
        self.service.controller.retriever.outage = True
        s, response, _ = self.service.turn(s.session_id, 'mirror distance')
        self.assertEqual(response.type, ResponseType.SYSTEM_ERROR)
        self.assertEqual(self.store.load(s.session_id), s)
        self.assertEqual((self.provider.calls, self.judge.calls), (0, 0))

    def test_session_load_error_is_canonical_and_redacted(self):
        s, response, decisions = self.service.turn('missing-session', 'private text')
        self.assertIsNone(s)
        self.assertEqual(response.type, ResponseType.SYSTEM_ERROR)
        self.assertEqual(response.reason_codes, ('SESSION_LOAD_FAILURE',))
        self.assertEqual(decisions, [])
        self.assertEqual((self.provider.calls, self.judge.calls), (0, 0))
        self.assertNotIn('missing-session', json.dumps(self.service.last_trace))

    def test_failed_action_state_save_withholds_generated_technical_text(self):
        s = self.service.start('EXP003', self.registry.source['variant'])
        s, _, _ = self.service.turn(s.session_id, 'cancel')
        s = self.service.feedback(s.session_id, Outcome.OBSERVED_NORMAL, 'centred', fact=Fact(True, 'BOOLEAN'))
        before = self.store.load(s.session_id)
        with patch.object(self.store, 'save', side_effect=OSError('PRIVATE_STORAGE_BODY')):
            returned, response, decisions = self.service.turn(s.session_id, 'It is centred.')
        self.assertEqual(returned, before)
        self.assertEqual(response.type, ResponseType.SYSTEM_ERROR)
        self.assertEqual(response.reason_codes, ('SESSION_SAVE_FAILURE',))
        self.assertIsNone(response.suggested_step_id)
        self.assertFalse(response.claim_evidence_map)
        self.assertFalse(response.cited_pages)
        self.assertNotIn('push it inward', response.natural_language)
        self.assertEqual(self.store.load(s.session_id), before)
        self.assertNotIn('PRIVATE_STORAGE_BODY', json.dumps(self.service.last_trace))

    def test_feedback_and_start_save_errors_are_sanitized_without_partial_commit(self):
        with patch.object(self.store, 'save', side_effect=OSError('PRIVATE_STORAGE_BODY')):
            with self.assertRaisesRegex(SessionOperationError, '^SESSION_SAVE_FAILURE$'):
                self.service.start('GEN003', self.registry.source['variant'])
        s, _ = self.centred_action()
        before = self.store.load(s.session_id)
        with patch.object(self.store, 'save', side_effect=OSError('PRIVATE_STORAGE_BODY')):
            with self.assertRaisesRegex(SessionOperationError, '^SESSION_SAVE_FAILURE$'):
                self.service.feedback(s.session_id, Outcome.ACTION_COMPLETED_UNRESOLVED, 'unresolved')
        self.assertEqual(self.store.load(s.session_id), before)
        with self.assertRaisesRegex(SessionOperationError, '^SESSION_LOAD_FAILURE$'):
            self.service.feedback('missing', Outcome.ACTION_COMPLETED_UNRESOLVED, 'unresolved')

    def test_known_safety_warning_survives_store_and_trace_failures(self):
        for failure in ('store', 'trace'):
            with self.subTest(failure=failure):
                s = self.service.start('GEN001', self.registry.source['variant'])
                def fail(*args, **kwargs):
                    raise OSError('PRIVATE_BODY')
                if failure == 'store':
                    with patch.object(self.store, 'save', side_effect=fail):
                        _, response, _ = self.service.turn(s.session_id, 'towline')
                else:
                    self.service.trace_sink = fail
                    _, response, _ = self.service.turn(s.session_id, 'towline')
                    self.service.trace_sink = None
                self.assertEqual(response.type, ResponseType.SAFETY_STOP)
                self.assertIn('Do not tow', response.natural_language)
                self.assertIn('SESSION_SAVE_FAILURE' if failure == 'store' else 'TRACE_SAVE_FAILURE',
                              response.reason_codes)
                self.assertNotIn('PRIVATE_BODY', json.dumps(self.service.last_trace))
        self.assertEqual((self.provider.calls, self.judge.calls), (0, 0))

    def test_invalid_feedback_and_corrections_cannot_invent_typed_state(self):
        s = self.service.start('EXP003', self.registry.source['variant'])
        s, _, _ = self.service.turn(s.session_id, 'cancel')
        before = self.store.load(s.session_id)
        with self.assertRaises(ValueError):
            self.service.feedback(s.session_id, Outcome.ACTION_COMPLETED_UNRESOLVED, 'not-an-action')
        with self.assertRaises(ValueError):
            self.service.feedback(s.session_id, Outcome.OBSERVED_NORMAL, 'invalid-fact', fact=Fact('normal', 'BOOLEAN'))
        with self.assertRaises(ValueError):
            self.service.correct(s.session_id, 'invented-attempt', Fact(True, 'BOOLEAN'), 'invented')
        self.assertEqual(self.store.load(s.session_id), before)


if __name__ == '__main__':
    unittest.main()
