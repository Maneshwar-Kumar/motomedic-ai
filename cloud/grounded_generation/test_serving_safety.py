"""Real pinned approval/source checks with synthetic buffers, zero providers.

No current approved safety step has a manual hazard applicability predicate.
The serving-selection tests prove no policy-only rescue. To exercise durable
proof mutation checks, the buffer fixture explicitly substitutes a synthetic
selector; it grants no production hazard link or source approval.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from approved_registry import ApprovedEvidenceRegistry
from constrained_generator import ValidationFailure
from controller_contracts import Fact, Outcome
from evidence_registry import content_hash
from reviewed_controller import append_attempt
from cloud.grounded_generation.delivery import bind_view, accepted_events, response_hash
from cloud.grounded_generation.serving_questions import Questions
from cloud.grounded_generation.serving_safety import (METHOD, select_known_safety,
    saved_safety_view, validate_saved_safety_view)
from cloud.grounded_generation.serving_source_authority import SourceAuthority
from cloud.grounded_generation.verified_qa import Composer
from cloud.grounded_generation.test_generic_runtime import ScriptedRetriever

ROOT = Path(__file__).resolve().parents[2]
INDEX = Path(os.environ.get('MOTOMEDIC_TEST_INDEX', str(ROOT / 'build/index-bge-final')))


class UnavailableProvider:
    cache_capability = 'unsupported'
    def __init__(self):
        self.calls = 0
    def count(self, body):
        self.calls += 1
        raise AssertionError('No provider operation is available')
    def complete(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError('No provider operation is available')


class OutageRetriever(ScriptedRetriever):
    def __init__(self, authority):
        super().__init__(authority, [])
        self.calls = 0
    def search(self, *args, **kwargs):
        self.calls += 1
        raise RuntimeError('Synthetic authenticated Qdrant unavailable')


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = ApprovedEvidenceRegistry.load(ROOT, INDEX)
        cls.original_authority = SourceAuthority(cls.original, INDEX)

    def setUp(self):
        self.registry = deepcopy(self.original)
        self.authority = deepcopy(self.original_authority)
        self.authority.base = self.registry
        self.authority.evidence = self.registry.evidence
        self.provider = UnavailableProvider()
        self.retriever = OutageRetriever(self.authority)
        self.composer = Composer(self.provider, self.authority)
        self.q = Questions(self.registry, self.retriever, self.composer, self.authority)
        self.session = self.q.new_session()

    def observed(self, **kwargs):
        return append_attempt(self.session, 'EXP011:candidate-v3',
            Outcome.OBSERVED_ABNORMAL, 'synthetic-observation',
            condition_id='EXP011:rule:abs_continuous_above_5',
            facts=(('abs_continuous_above_5', Fact(kwargs.get('value', True), 'BOOLEAN')) ,))

    def fixture(self):
        """Synthetic selector substitution only, exact real approved source text."""
        sid = 'EXP048:candidate-v3'
        scoped = replace(self.observed(), version=3,
                         current_symptoms=tuple(self.registry.step(sid).symptom_tags))
        selection = {'synthetic_selector_fixture': True}
        selected = (scoped, sid, selection)
        with patch('cloud.grounded_generation.serving_safety.select_known_safety',
                   return_value=selected):
            view, _ = saved_safety_view(self.q.controller, self.authority, scoped,
                sid, selection, 'Synthetic question', [{'question': 'Synthetic previous'}],
                'synthetic-operation', self.composer.config.lock)
        return selected, view

    def validate(self, selected, view):
        with patch('cloud.grounded_generation.serving_safety.select_known_safety',
                   return_value=selected):
            return validate_saved_safety_view(self.registry, self.authority, view,
                                              self.composer.config.lock)

    def rebind(self, view):
        """An attacker can recompute ordinary hashes; source approval still gates."""
        proof = view['source_scope_verification']
        delivery = view['verified_delivery']
        delivery['binding_sha256'] = content_hash(proof)
        delivery['presentation_sha256'] = response_hash(view)
        delivery['text_sha256'] = hashlib.sha256(view['response']['natural_language'].encode()).hexdigest()

    def test_current_real_safety_records_have_no_manual_hazard_gate_and_no_query_bypass(self):
        safety = [(sid, raw) for sid, raw in self.registry.candidate['steps'].items()
                  if raw['kind'] == 'SAFETY_STOP']
        self.assertEqual(len(safety), 11)
        for sid, raw in safety:
            for rule_id in self.registry.step(sid).applicability_rule_ids:
                self.assertEqual(self.registry.rule(rule_id).origin, 'PRODUCT_POLICY')
        observed = self.observed()
        self.assertIsNone(self.q.known_safety(observed))
        self.assertIsNone(select_known_safety(self.q.controller, observed))
        updated, view, _ = self.q.answer(observed,
            'The ABS light is continuously on above 5 km/h. What should I do?',
            operation_id='outage-operation')
        self.assertEqual(view['response']['type'], 'SYSTEM_ERROR')
        self.assertFalse(view['response']['release_gate_passed'])
        self.assertNotIn('source_scope_verification', view)
        self.assertEqual(updated.version, observed.version+1)
        self.assertEqual(self.provider.calls, 0)
        self.assertEqual(self.retriever.calls, 1)

    def test_false_unknown_and_unresolved_cannot_create_safety_authority(self):
        self.assertIsNone(select_known_safety(self.q.controller, self.observed(value=False)))
        unresolved = append_attempt(self.session, 'EXP011:candidate-v3',
            Outcome.ACTION_COMPLETED_UNRESOLVED, 'synthetic-unresolved')
        self.assertEqual(unresolved.known_observations(), {})
        self.assertIsNone(select_known_safety(self.q.controller, unresolved))
        unconfirmed = replace(self.observed(), bike_variant=None)
        with self.assertRaisesRegex(ValidationFailure, 'SCOPE_NOT_CONFIRMED'):
            select_known_safety(self.q.controller, unconfirmed)

    def test_synthetic_selector_buffer_preserves_exact_source_text_and_distinct_method(self):
        selected, view = self.fixture()
        recovered = json.loads(json.dumps(view, ensure_ascii=False))
        self.assertEqual(self.validate(selected, recovered), view)
        body = view['response']
        self.assertEqual(body['verification_method'], METHOD)
        self.assertTrue(body['source_scope_verification_passed'])
        self.assertFalse(body['semantic_verification_passed'])
        self.assertFalse(body['semantic_support_proven'])
        self.assertEqual(self.provider.calls, 0)
        self.assertEqual(self.retriever.calls, 0)
        committed = bind_view(view, 'synthetic-operation', self.composer.config.lock)
        events = list(accepted_events(committed, 'synthetic-operation'))
        self.assertEqual(''.join(row['text'] for kind, row in events if kind == 'answer_chunk'),
                         body['natural_language'])
        self.assertNotIn('bbox', str(body['cited_pages']))
        for source in view['source_scope_verification']['exact_scope']['source_objects'].values():
            self.assertEqual(set(source), {'raw_object_sha256', 'provenance_sha256',
                                           'approved_source_sha256'})

    def test_tampered_proof_operation_session_or_runtime_rejected(self):
        selected, original = self.fixture()
        mutations = [('operation', lambda v: v['source_scope_verification'].__setitem__('operation_id', 'wrong')),
            ('runtime', lambda v: v['verified_delivery'].__setitem__('runtime_lock', 'wrong')),
            ('session', lambda v: v['source_scope_verification']['session_snapshot'].__setitem__('version', 999)),
            ('scope', lambda v: v['source_scope_verification']['exact_scope'].__setitem__('record_id', 'wrong'))]
        for label, mutate in mutations:
            with self.subTest(label=label):
                view = deepcopy(original)
                mutate(view)
                self.rebind(view)
                with self.assertRaises(ValidationFailure):
                    self.validate(selected, view)

    def test_changed_wording_with_recomputed_buffer_hashes_rejected(self):
        selected, view = self.fixture()
        view['response']['natural_language'] += ' Unreviewed repair instruction.'
        self.rebind(view)
        with self.assertRaisesRegex(ValidationFailure, 'APPROVED_WORDING_CHANGED'):
            self.validate(selected, view)

    def test_changed_source_or_approved_step_rejected(self):
        selected, view = self.fixture()
        sid = selected[1]
        eid = self.registry.step(sid).required_evidence_ids[0]
        self.registry.evidence[eid]['raw_object']['text'] += ' changed'
        with self.assertRaises(ValidationFailure):
            self.validate(selected, view)

    def test_changed_reviewed_wording_does_not_gain_source_authority(self):
        selected, view = self.fixture()
        self.registry.candidate['steps'][selected[1]]['claims'][0]['text'] += ' altered'
        with self.assertRaisesRegex(ValidationFailure, 'SCOPE_CHANGED'):
            self.validate(selected, view)

    def test_synthetic_selector_proof_has_no_authority_without_eligible_manual_gate(self):
        selected, view = self.fixture()
        with self.assertRaisesRegex(ValidationFailure, 'ELIGIBILITY_CHANGED'):
            validate_saved_safety_view(self.registry, self.authority, view,
                                       self.composer.config.lock)


if __name__ == '__main__':
    unittest.main()
