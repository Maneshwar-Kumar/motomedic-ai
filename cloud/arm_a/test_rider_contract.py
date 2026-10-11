"""Presentation/choice binding checks, synthetic retrieval; no live claim."""
from dataclasses import replace
import unittest

from approved_registry import ApprovedEvidenceRegistry
from cloud.arm_a.composer import ArmAComposer
from cloud.arm_a.rider_contract import consume_choice, saved_view
from controller_contracts import Fact, Outcome, Response, ResponseType
from reviewed_controller import start_session
from test_approved_integration import ROOT, INDEX, ScriptedRetrieval
from reviewed_controller import ReviewedController
from rider_ui.client import validate_view


class RiderContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ApprovedEvidenceRegistry.load(ROOT, INDEX)

    def setUp(self):
        self.controller = ReviewedController(self.registry, ScriptedRetrieval(self.registry),
                                             response_generator=ArmAComposer())
        self.controller.audience = 'end_user'
        self.session = replace(start_session(self.registry, ['EXP003'], self.registry.source['variant']),
                               generation_lock=ArmAComposer().config.lock)

    def question(self):
        self.session, response, _ = self.controller.next(self.session, 'cancel signal')
        self.assertEqual(response.type, ResponseType.AMBIGUOUS)
        view, private = saved_view(self.registry, self.session, response)
        validate_view(view)
        return view, private

    def answer(self):
        view, private = self.question()
        key = next(c['id'] for c in view['choices'] if c['outcome'] == 'OBSERVED_NORMAL')
        outcome, fact = consume_choice(self.session, private, key, self.session.version)
        self.session = self.controller.feedback(self.session, outcome, 'centred', fact=fact)
        self.session, response, _ = self.controller.next(self.session, 'cancel signal')
        self.assertEqual(response.type, ResponseType.SUPPORTED)
        view, private = saved_view(self.registry, self.session, response)
        validate_view(view)
        return view, private

    def test_centred_choices_preserve_propositions(self):
        view, private = self.question()
        facts = []
        for c in view['choices']:
            outcome, fact = consume_choice(self.session, private, c['id'], self.session.version)
            facts.append((outcome, fact))
        self.assertIn((Outcome.OBSERVED_NORMAL, Fact(True, 'BOOLEAN')), facts)
        self.assertIn((Outcome.OBSERVED_ABNORMAL, Fact(False, 'BOOLEAN')), facts)
        self.assertIn((Outcome.UNCLEAR, None), facts)

    def test_stale_other_session_and_changed_binding_rejected(self):
        view, private = self.question()
        key = view['choices'][0]['id']
        for session, expected in ((self.session, self.session.version-1),
                                  (replace(self.session, session_id='0'*32), self.session.version),
                                  (replace(self.session, pending_rule_id=None), self.session.version)):
            with self.assertRaises(ValueError):
                consume_choice(session, private, key, expected)
        private[key] = {**private[key], 'fact': {'value': False, 'value_type': 'BOOLEAN'}}
        with self.assertRaises(ValueError):
            consume_choice(self.session, private, key, self.session.version)

    def test_false_and_unsure_do_not_release_action(self):
        for mode in ('OBSERVED_ABNORMAL', 'UNCLEAR'):
            self.setUp()
            view, private = self.question()
            key = next(c['id'] for c in view['choices'] if c['outcome'] == mode)
            outcome, fact = consume_choice(self.session, private, key, self.session.version)
            self.session = self.controller.feedback(self.session, outcome, mode, fact=fact)
            self.session, response, _ = self.controller.next(self.session, 'cancel signal')
            self.assertNotEqual(response.type, ResponseType.SUPPORTED)
            view, _ = saved_view(self.registry, self.session, response)
            validate_view(view)

    def test_unresolved_never_becomes_normal_and_does_not_repeat(self):
        view, private = self.answer()
        original = self.session.known_observations()
        key = next(c['id'] for c in view['choices'] if c['outcome'] == 'ACTION_COMPLETED_UNRESOLVED')
        outcome, fact = consume_choice(self.session, private, key, self.session.version)
        self.assertIsNone(fact)
        self.session = self.controller.feedback(self.session, outcome, 'unresolved')
        for query in ('still flashing', 'repeat it'):
            self.session, response, _ = self.controller.next(self.session, query)
            self.assertEqual(response.type, ResponseType.UNSUPPORTED)
            view, private = saved_view(self.registry, self.session, response)
            self.assertFalse(view['choices'])
            self.assertFalse(private)
            validate_view(view)
        self.assertEqual(self.session.known_observations(), original)
        self.assertIn({'label': 'Action completed; symptom remains'}, view['history'])

    def test_corrected_false_proposition_has_honest_history(self):
        self.answer()
        prior = next(a for a in self.session.active_attempts() if a.condition_id and a.observed_details)
        self.session = self.controller.correct(self.session, prior.attempt_id, Fact(False, 'BOOLEAN'), 'correction')
        response = Response(ResponseType.UNSUPPORTED, 'No applicable step.')
        view, _ = saved_view(self.registry, self.session, response)
        self.assertIn({'label': 'Turn switch reported not centred'}, view['history'])
        self.assertNotIn({'label': 'Turn switch reported centred'}, view['history'])

    def test_unknown_question_does_not_get_generic_boolean_choices(self):
        self.session = replace(self.session, pending_rule_id='GEN003:rule:bike_scope_confirmed',
                               pending_step_id='GEN003:candidate-v3')
        response = Response(ResponseType.AMBIGUOUS, 'Confirm source?')
        view, private = saved_view(self.registry, self.session, response)
        self.assertFalse(view['choices'])
        self.assertFalse(private)

    def test_forged_technical_status_or_safety_assertion_rejected(self):
        for kind in (ResponseType.SUPPORTED, ResponseType.SAFETY_STOP):
            response = Response(kind, 'Unreviewed wording',
                                claim_evidence_map=({'claim_id': 'fake', 'evidence_ids': ['fake']},),
                                cited_pages=({'evidence_id': 'fake', 'pdf_page': 13},))
            with self.assertRaises(ValueError):
                saved_view(self.registry, self.session, response)
            forged = replace(response, reason_codes=('ARM_A_EXACT_REVIEWED_CANONICAL_VALIDATED',))
            with self.assertRaises(ValueError):
                saved_view(self.registry, self.session, forged)

    def test_changed_citation_provenance_and_claim_map_rejected(self):
        self.answer()
        _, response, _ = self.controller.next(self.session, 'cancel signal')
        # The action is still only issued, so this recheck is eligible upstream.
        self.assertEqual(response.type, ResponseType.SUPPORTED)
        for field, value in (('pdf_page', 149), ('manual_checksum', 'wrong'), ('index_id', 'wrong')):
            refs = [dict(c) for c in response.cited_pages]
            refs[0][field] = value
            with self.assertRaises(ValueError):
                saved_view(self.registry, self.session, replace(response, cited_pages=tuple(refs)))
        claims = [dict(c) for c in response.claim_evidence_map]
        claims[0]['evidence_ids'] = ['fake']
        with self.assertRaises(ValueError):
            saved_view(self.registry, self.session, replace(response, claim_evidence_map=tuple(claims)))

    def test_resolved_acknowledgment_never_issues_action_choices(self):
        self.answer()
        closed = replace(self.session, status='CUSTOMER_REPORTED_RESOLVED')
        response = Response(ResponseType.SUPPORTED, 'You reported resolution.')
        view, private = saved_view(self.registry, closed, response)
        self.assertFalse(view['choices'])
        self.assertFalse(private)

    def test_exact_safety_warning_validates_and_has_no_choices(self):
        self.session = replace(self.session, current_symptoms=('GEN001',))
        self.session, response, _ = self.controller.next(self.session, 'towline')
        self.assertEqual(response.type, ResponseType.SAFETY_STOP)
        view, private = saved_view(self.registry, self.session, response)
        self.assertTrue(view['response']['release_gate_passed'])
        self.assertFalse(view['choices'])
        self.assertFalse(private)
        validate_view(view)


if __name__ == '__main__':
    unittest.main()
