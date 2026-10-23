"""Synthetic transactional capacity checks; no cloud or provider requests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import threading
import types
import unittest
from unittest.mock import patch
from dataclasses import replace
from evidence_registry import content_hash
from controller_contracts import DiagnosticSession, Response, ResponseType
import cloud.grounded_generation.test_verified_qa as verified
from cloud.grounded_generation.whole_turn_admission import (WholeTurnAdmission, ALLOCATION,
    operation_deadline, MAX_SLEEP_SECONDS, PACING_VERSION, GEMMA, HAIKU, GEMMA_INPUT_TPM,
    LEGACY_PACING_VERSION, PLAN_VERSION)
from cloud.grounded_generation.claude_budget import ALLOCATION as CLAUDE_ALLOCATION, VERSION as CLAUDE_VERSION
from cloud.grounded_generation.provider import GemmaProvider, ProviderFailure
from cloud.grounded_generation.fallback_provider import FallbackProvider
from cloud.grounded_generation.claude_provider import ClaudeProvider, MAX_CALL_USD


class Reference:
    def __init__(self, client, name):self.client, self.name = client, name
    def get(self, transaction=None):
        if self.client.fail:raise RuntimeError('synthetic outage')
        body=deepcopy(self.client.documents.get(self.name))
        return types.SimpleNamespace(exists=body is not None, to_dict=lambda:body)


class Client:
    def __init__(self):self.documents={};self.lock=threading.RLock();self.fail=False
    def collection(self, name):assert name=='arm_a_usage';return self
    def document(self, name):return Reference(self, name)
    def transaction(self):return self
    def set(self, ref, body):self.documents[ref.name]=deepcopy(body)


def atomic(fn):
    def run(tx):
        with tx.lock:return fn(tx)
    return run


class Tests(unittest.TestCase):
    def setUp(self):
        self.client=Client();self.now=datetime(2026,10,12,tzinfo=timezone.utc)
        self.waits=[]
        def sleep(seconds):
            self.waits.append(seconds);self.now+=timedelta(seconds=seconds)
        self.admit=WholeTurnAdmission(self.client,now=lambda:self.now,sleep=sleep)
        google=types.ModuleType('google');cloud=types.ModuleType('google.cloud')
        cloud.firestore=types.SimpleNamespace(transactional=atomic);google.cloud=cloud
        self.patch=patch.dict('sys.modules',{'google':google,'google.cloud':cloud});self.patch.start()
        self.addCleanup(self.patch.stop)

    def native_plan(self, *, haiku_input=20000):
        return {'slots': [{'model': HAIKU, 'stage': stage, 'input_tokens': haiku_input,
            'output_tokens': 1800, 'attempt': 1}
            for stage in ('draft', 'verify', 'correction', 'reverify')]}

    def phased_plans(self, *, haiku_input=20000):
        full = self.native_plan(haiku_input=haiku_input)
        return {'slots': deepcopy(full['slots'][:2])}, {'slots': deepcopy(full['slots'][2:])}

    def with_role_metadata(self, plan, *, selected_input=None, headroom=0):
        from cloud.grounded_generation.role_contracts import CONTRACT
        result = deepcopy(plan)
        route = 'HAIKU_DRAFT_HAIKU_VERIFY'
        roles = CONTRACT['roles'][route]
        selected_input = selected_input if selected_input is not None else plan['slots'][0]['input_tokens']
        result.update(role_plan={'version': CONTRACT['version'], 'route': route,
            'routing_contract_sha256': content_hash(CONTRACT), 'primary_input_tokens_counted': selected_input,
            'selected_draft_input_tokens': selected_input, 'initial_draft_request_sha256': 'a' * 64,
            'stable_context_sha256': 'b' * 64, 'draft_model_contract_sha256': content_hash(roles['draft']),
            'verifier_contract_sha256': content_hash(roles['verifier'])},
            forecast_method='NATIVE_FIXED_SCAFFOLD_PLUS_BOUNDED_PRIVATE_OUTPUT_BYTES',
            forecast_is_not_unknown_final_answer_guarantee=True, fixed_verifier_native_tokens=1000,
            fixed_correction_native_tokens=1200, unknown_verifier_byte_allowance=33280,
            unknown_correction_byte_allowance=49664, initial_haiku_counter_headroom_tokens=headroom,
            initial_primary_counter_headroom_tokens=0, known_verifier_prefix_native_tokens=900)
        if plan['slots'][0]['stage'] == 'correction':
            result.update(correction_request_sha256='c' * 64,
                rejected_binding_sha256='d' * 64, verdict_sha256='e' * 64)
        return result

    def complete_initial_pair(self, *, count=20000):
        self.admit.for_model(HAIKU, role='private_draft')(count + 1800, 'generation')
        self.admit.for_model(HAIKU, role='semantic_verifier')(count + 1800, 'generation')

    def test_full_role_and_forecast_metadata_is_validated_preserved_and_phase_bound(self):
        initial, correction = self.phased_plans()
        initial['slots'][0]['input_tokens'] += 512
        initial = self.with_role_metadata(initial, selected_input=20000, headroom=512)
        correction = self.with_role_metadata(correction, selected_input=20000, headroom=512)
        receipt = self.admit.begin_turn('metadata', plan=initial)
        self.assertEqual(receipt['role_forecast_sha256'], content_hash(initial))
        self.assertEqual(receipt['role_forecast_binding']['role_plan'], initial['role_plan'])
        self.complete_initial_pair()
        phase = self.admit.reserve_correction('metadata', plan=correction)
        self.assertEqual(phase['plan_sha256'], content_hash(correction))
        self.assertEqual(phase['role_forecast_binding']['correction_request_sha256'], 'c' * 64)
        events = self.client.documents['grounded-provider-global-v1']['events']
        self.assertEqual([e['plan_sha256'] for e in events], [content_hash(initial)] * 2 + [content_hash(correction)] * 2)

    def test_routing_contract_or_role_metadata_cannot_be_silently_dropped_or_changed(self):
        initial = self.with_role_metadata(self.phased_plans()[0])
        for mutation in ('missing-metadata', 'contract-hash', 'model-contract', 'routing-count',
                         'headroom', 'primary-headroom', 'unexpected-field'):
            changed = deepcopy(initial)
            if mutation == 'missing-metadata':changed.pop('forecast_method')
            if mutation == 'contract-hash':changed['role_plan']['routing_contract_sha256'] = '0' * 64
            if mutation == 'model-contract':changed['role_plan']['verifier_contract_sha256'] = '0' * 64
            if mutation == 'routing-count':changed['role_plan']['primary_input_tokens_counted'] += 1
            if mutation == 'headroom':changed['initial_haiku_counter_headroom_tokens'] = 513
            if mutation == 'primary-headroom':changed['initial_primary_counter_headroom_tokens'] = 1
            if mutation == 'unexpected-field':changed['unknown_unbounded_override'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ProviderFailure):
                self.admit.begin_turn('bad-' + mutation, plan=changed)
        self.assertFalse(self.client.documents)

    def test_correction_changed_source_or_phase_hash_refuses_new_spend(self):
        initial, correction = map(self.with_role_metadata, self.phased_plans())
        self.admit.begin_turn('fixed-source', plan=initial)
        self.complete_initial_pair()
        before = deepcopy(self.client.documents)
        correction['role_plan']['stable_context_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ProviderFailure, 'MODEL_ROLE_BINDING_CHANGED'):
            self.admit.reserve_correction('fixed-source', plan=correction)
        self.assertEqual(before, self.client.documents)
        self.client.documents['grounded-provider-global-v1']['events'][0]['plan_sha256'] = '0' * 64
        correction['role_plan']['stable_context_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ProviderFailure, 'NATIVE_PLAN_STORE_CHANGED'):
            self.admit.reserve_correction('fixed-source', plan=correction)

    def test_initial_counter_headroom_and_known_verifier_prefix_are_immutable_across_phases(self):
        initial, correction = self.phased_plans()
        initial['slots'][0]['input_tokens'] += 512
        initial = self.with_role_metadata(initial, selected_input=20000, headroom=512)
        correction = self.with_role_metadata(correction, selected_input=20000, headroom=512)
        self.admit.begin_turn('fixed-counter-forecast', plan=initial)
        self.complete_initial_pair()
        before = deepcopy(self.client.documents)
        for key in ('initial_haiku_counter_headroom_tokens', 'known_verifier_prefix_native_tokens'):
            changed = deepcopy(correction);changed[key] -= 1
            with self.subTest(key=key), self.assertRaisesRegex(ProviderFailure, 'MODEL_ROLE_BINDING_CHANGED'):
                self.admit.reserve_correction('fixed-counter-forecast', plan=changed)
            self.assertEqual(before, self.client.documents)

    def test_production_correction_requires_every_exact_request_rejection_and_verdict_hash(self):
        initial, correction = map(self.with_role_metadata, self.phased_plans())
        self.admit.begin_turn('complete-correction-binding', plan=initial)
        self.complete_initial_pair();before = deepcopy(self.client.documents)
        for key in ('correction_request_sha256', 'rejected_binding_sha256', 'verdict_sha256'):
            changed = deepcopy(correction);changed.pop(key)
            with self.subTest(key=key), self.assertRaisesRegex(ProviderFailure, 'CORRECTION_BINDING_REQUIRED'):
                self.admit.reserve_correction('complete-correction-binding', plan=changed)
            self.assertEqual(before, self.client.documents)

    def test_durable_phase_or_nonce_mutation_blocks_permit_and_sealing(self):
        for key in ('phase', 'phase_nonce'):
            with self.subTest(key=key):
                self.client = Client()
                self.admit = WholeTurnAdmission(self.client, now=lambda: self.now,
                    sleep=lambda seconds: setattr(self, 'now', self.now + timedelta(seconds=seconds)))
                initial, correction = self.phased_plans()
                self.admit.begin_turn('nonce-' + key, plan=initial);self.complete_initial_pair()
                self.admit.reserve_correction('nonce-' + key, plan=correction)
                events = self.client.documents['grounded-provider-global-v1']['events']
                events[2][key] = 'initial' if key == 'phase' else 'f' * 64
                before = deepcopy(self.client.documents)
                with self.assertRaisesRegex(ProviderFailure, 'NATIVE_PLAN_STORE_CHANGED'):
                    self.admit.for_model(HAIKU, role='private_draft')(21800, 'generation')
                self.assertEqual(before, self.client.documents)
                receipt = self.admit.end_turn()
                self.assertEqual(receipt['sealing_status'], 'SEALING_UNCONFIRMED_ACTIVE_POLICY_RETAINED')
                self.assertEqual(before, self.client.documents)

    def test_initial_durable_nonce_mutation_cannot_authorize_correction_spend(self):
        initial, correction = self.phased_plans()
        self.admit.begin_turn('mutated-initial-nonce', plan=initial);self.complete_initial_pair()
        self.client.documents['grounded-provider-global-v1']['events'][0]['phase_nonce'] = 'f' * 64
        before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'NATIVE_PLAN_STORE_CHANGED'):
            self.admit.reserve_correction('mutated-initial-nonce', plan=correction)
        self.assertEqual(before, self.client.documents)

    def test_real_router_forecasts_match_strict_phased_haiku_admission(self):
        from cloud.grounded_generation.test_role_router import Tests as RouterTests, stable
        fixtures = RouterTests()
        router, _ = fixtures.router(9000)
        router.admission = self.admit
        dynamic, admitted = fixtures.dynamic(), fixtures.admitted()
        session = types.SimpleNamespace(status='CONFIRMED')
        plan, chosen = router.select(stable(), dynamic)
        receipt = router.begin('integrated', plan, chosen, dynamic, admitted, session)
        self.assertEqual(receipt['reserved_attempts'], 2)
        self.admit.for_model(HAIKU, role='private_draft')(plan.initial_input_tokens + 1800, 'generation')
        self.admit.for_model(HAIKU, role='semantic_verifier')(plan.verifier.count_value + 1800, 'generation')
        router.begin_correction('integrated', plan, chosen, dynamic, admitted, session,
            {'rejected_response': {'text': 'Private rejected fixture'}, 'verdict': {'correction_possible': True}},
            {'response_sha256': 'f' * 64})
        self.assertEqual(receipt['reserved_attempts'], 4)
        self.assertTrue(receipt['correction_reserved'])
        self.admit.for_model(HAIKU, role='private_draft')(plan.initial_input_tokens + 1800, 'generation')
        self.admit.for_model(HAIKU, role='semantic_verifier')(plan.verifier.count_value + 1800, 'generation')
        router.end()
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 4)

    def test_initial_two_fund_both_roles_before_first_generation(self):
        initial, _ = self.phased_plans()
        receipt = self.admit.begin_turn('initial', plan=initial)
        self.assertEqual(receipt['reserved_attempts'], 2)
        self.assertEqual(receipt['reservation_mode'], 'INITIAL_PAIR_CONDITIONAL_CORRECTION')
        self.assertFalse(receipt['correction_reserved'])
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 2)
        self.assertEqual(len(self.client.documents['grounded-provider-global-v1']['events']), 2)
        self.complete_initial_pair();before = deepcopy(self.client.documents)
        with self.assertRaises(ProviderFailure):
            self.admit.for_model(HAIKU, role='private_draft')(21800, 'generation')
        self.assertEqual(before, self.client.documents)
        self.admit.end_turn()
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 2)

    def test_correction_two_are_fresh_atomic_single_phase_with_same_operation_and_roles(self):
        initial, correction = self.phased_plans()
        receipt = self.admit.begin_turn('phase', plan=initial);self.complete_initial_pair()
        before = deepcopy(self.client.documents[ALLOCATION])
        phase = self.admit.reserve_correction('phase', plan=correction)
        self.assertEqual(phase['phase'], 'correction')
        self.assertNotEqual(phase['phase_nonce'], receipt['phases'][0]['phase_nonce'])
        self.assertNotEqual(phase['plan_sha256'], receipt['phases'][0]['plan_sha256'])
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], before['reserved_attempts'] + 2)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_tokens'], before['reserved_tokens'] + phase['reserved_tokens'])
        self.assertTrue(receipt['correction_reserved']);self.assertEqual(receipt['reserved_attempts'], 4)
        self.assertEqual([e['slot'] for e in self.client.documents['grounded-provider-global-v1']['events']], list(range(4)))
        self.assertEqual(self.admit.for_model(HAIKU, role='private_draft')(21800, 'generation')['stage'], 'correction')
        self.assertEqual(self.admit.for_model(HAIKU, role='semantic_verifier')(21800, 'generation')['stage'], 'reverify')
        old = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'ALREADY_RESERVED_NO_REPLAY'):
            self.admit.reserve_correction('phase', plan=correction)
        self.assertEqual(old, self.client.documents)

    def test_correction_never_strands_verifier_by_reserving_draft_only(self):
        initial, correction = self.phased_plans()
        self.admit.begin_turn('complete-correction-pair', plan=initial);self.complete_initial_pair()
        correction['slots'].pop();before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'NATIVE_PLAN_INVALID'):
            self.admit.reserve_correction('complete-correction-pair', plan=correction)
        self.assertEqual(before, self.client.documents)

    def test_unfunded_correction_no_paid_permit_no_changed_charges_or_refund(self):
        initial, correction = self.phased_plans()
        self.admit.begin_turn('unfunded', plan=initial);self.complete_initial_pair()
        old = self.client.documents[ALLOCATION]
        old['reserved_attempts'] = 99;old['reserved_tokens'] = 900000
        before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'ALLOCATION_LIMIT'):
            self.admit.reserve_correction('unfunded', plan=correction)
        self.assertEqual(before, self.client.documents)
        with self.assertRaises(ProviderFailure):self.admit.for_model(HAIKU, role='private_draft')(21800, 'generation')
        with self.assertRaisesRegex(ProviderFailure, 'ALREADY_RESERVED_NO_REPLAY'):
            self.admit.reserve_correction('unfunded', plan=correction)
        self.admit.end_turn()
        self.assertEqual(self.client.documents[ALLOCATION], before[ALLOCATION])
        self.assertEqual(self.client.documents[CLAUDE_ALLOCATION], before[CLAUDE_ALLOCATION])

    def test_haiku_insufficient_correction_keeps_initial_tokens_and_cost_retained(self):
        initial, correction = self.phased_plans()
        self.admit.begin_turn('money', plan=initial);self.complete_initial_pair()
        self.client.documents[CLAUDE_ALLOCATION]['reserved_nanodollars'] = 999999999
        before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'CLAUDE_SPEND_LIMIT'):
            self.admit.reserve_correction('money', plan=correction)
        self.assertEqual(before, self.client.documents)
        self.assertFalse(self.admit.local.turn['receipt']['correction_reserved'])

    def test_correction_before_verification_wrong_operation_or_swapped_stages_are_rejected(self):
        initial, correction = self.phased_plans()
        self.admit.begin_turn('bound', plan=initial);before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'ALREADY_RESERVED_NO_REPLAY'):
            self.admit.reserve_correction('wrong', plan=correction)
        swapped = deepcopy(correction);swapped['slots'].reverse()
        with self.assertRaisesRegex(ProviderFailure, 'MODEL_ROLE_PLAN_INVALID'):
            self.admit.reserve_correction('bound', plan=swapped)
        with self.assertRaisesRegex(ProviderFailure, 'WITHOUT_VERIFICATION'):
            self.admit.reserve_correction('bound', plan=correction)
        self.assertEqual(before, self.client.documents)

    def test_correction_retains_exact_original_durable_deadline(self):
        initial, correction = self.phased_plans();deadline = self.now + timedelta(seconds=1000)
        with operation_deadline(deadline):
            self.admit.begin_turn('deadline-phases', plan=initial);self.complete_initial_pair()
            before = deepcopy(self.client.documents)
            with operation_deadline(deadline + timedelta(seconds=1)):
                with self.assertRaisesRegex(ProviderFailure, 'DEADLINE_CHANGED'):
                    self.admit.reserve_correction('deadline-phases', plan=correction)
            self.assertEqual(before, self.client.documents);self.now = deadline
            with self.assertRaisesRegex(ProviderFailure, 'DEADLINE_EXCEEDED'):
                self.admit.reserve_correction('deadline-phases', plan=correction)
            self.assertEqual(before, self.client.documents)

    def test_uncertain_correction_commit_is_not_replayed_or_refunded(self):
        initial, correction = self.phased_plans()
        self.admit.begin_turn('uncertain-phase', plan=initial);self.complete_initial_pair()
        original = self.client.set
        def uncertain(ref, body):
            original(ref, body)
            if ref.name == CLAUDE_ALLOCATION:raise RuntimeError('synthetic commit status uncertain')
        self.client.set = uncertain
        with self.assertRaisesRegex(ProviderFailure, 'STORE_UNAVAILABLE'):
            self.admit.reserve_correction('uncertain-phase', plan=correction)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 4)
        before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'ALREADY_RESERVED_NO_REPLAY'):
            self.admit.reserve_correction('uncertain-phase', plan=correction)
        self.assertEqual(before, self.client.documents);self.admit.end_turn()
        self.assertEqual(self.client.documents[ALLOCATION], before[ALLOCATION])

    def test_oversleep_in_conditional_phase_never_returns_stale_paid_permit(self):
        initial, correction = self.phased_plans()
        self.admit.begin_turn('phase-pacing', plan=initial);self.complete_initial_pair()
        self.admit.reserve_correction('phase-pacing', plan=correction)
        self.admit.sleep = lambda seconds: setattr(self, 'now', self.now + timedelta(seconds=seconds + 120))
        self.admit.for_model(HAIKU, role='private_draft')(21800, 'generation')
        consumed = [e['at'] for e in self.client.documents['grounded-provider-global-v1']['events'] if e.get('consumed')]
        self.assertEqual(consumed[-1], self.now)
        self.assertTrue(all((right - left).total_seconds() >= 61 for left, right in zip(consumed, consumed[1:])))
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 4)

    def test_full_four_native_slots_require_explicit_synthetic_compatibility(self):
        with self.assertRaisesRegex(ProviderFailure, 'EXPLICIT_COMPATIBILITY'):
            self.admit.begin_turn('accidental-four', plan=self.native_plan())
        self.assertFalse(self.client.documents)

    def test_model_native_plan_reserves_both_roles_and_both_existing_allocations_atomically(self):
        self.client.documents[ALLOCATION] = {'version': 'whole-turn-capacity-v1',
            'maximum_attempts': 100, 'maximum_tokens': 999200, 'reserved_attempts': 24, 'reserved_tokens': 239808}
        self.client.documents[CLAUDE_ALLOCATION] = {'version': CLAUDE_VERSION, 'model': HAIKU,
            'maximum_nanodollars': 1000000000, 'reserved_nanodollars': 11544000, 'reservation_count': 3}
        plan = self.phased_plans()[0]
        expected_tokens = sum(row['input_tokens'] + row['output_tokens'] for row in plan['slots'])
        expected_cost = 2 * (20000 * 125 + 1800 * 500)
        receipt = self.admit.begin_turn('native', plan=plan)
        self.assertEqual(receipt['plan_version'], PLAN_VERSION)
        self.assertEqual(receipt['reserved_attempts'], 2)
        self.assertEqual(receipt['reserved_tokens'], expected_tokens)
        self.assertEqual(receipt['reserved_nanodollars'], expected_cost)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_tokens'], 239808 + expected_tokens)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 26)
        self.assertEqual(self.client.documents[CLAUDE_ALLOCATION]['reserved_nanodollars'], 11544000 + expected_cost)
        self.assertEqual(self.client.documents[CLAUDE_ALLOCATION]['reservation_count'], 4)
        self.assertNotIn('expires_at', self.client.documents[ALLOCATION])
        self.assertNotIn('expires_at', self.client.documents[CLAUDE_ALLOCATION])
        self.assertEqual(plan, self.phased_plans()[0])

    def test_large_haiku_input_is_permitted_and_cost_tier_reserved_before_calls(self):
        initial, _ = self.phased_plans(haiku_input=120000)
        receipt = self.admit.begin_turn('large', plan=initial)
        expected = 2 * (120000 * 625 + 1800 * 2500)
        self.assertEqual(receipt['reserved_nanodollars'], expected)
        slot = self.admit.for_model(HAIKU, role='private_draft')(121800, 'generation')
        self.assertEqual(slot['maximum_nanodollars'], expected // 2)
        self.assertEqual(slot['input_tokens'], 120000)
        self.assertEqual(slot['stage'], 'draft');self.assertFalse(self.waits)

    def test_same_model_role_permits_cannot_skip_or_self_verify(self):
        initial, correction = self.phased_plans()
        self.admit.begin_turn('roles', plan=initial)
        draft = self.admit.for_model(HAIKU, role='private_draft')
        verifier = self.admit.for_model(HAIKU, role='semantic_verifier')
        before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'MODEL_ROLE_MISMATCH'):verifier(21800, 'generation')
        self.assertEqual(before, self.client.documents)
        first = draft(21800, 'generation');before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'MODEL_ROLE_MISMATCH'):draft(21800, 'generation')
        self.assertEqual(before, self.client.documents)
        checked = verifier(21800, 'generation')
        self.admit.reserve_correction('roles', plan=correction)
        corrected, reverified = draft(21800, 'generation'), verifier(21800, 'generation')
        self.assertEqual([first['stage'], checked['stage'], corrected['stage'], reverified['stage']],
            ['draft', 'verify', 'correction', 'reverify'])
        self.assertEqual([first['attempt'], checked['attempt'], corrected['attempt'], reverified['attempt']], [1]*4)
        self.admit.end_turn();self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 4)

    def test_native_window_is_not_the_retired_google_tpm_or_assembled_evidence_cap(self):
        initial, _ = self.phased_plans(haiku_input=16001)
        self.admit.begin_turn('large-evidence', plan=initial)
        self.assertEqual(self.admit.for_model(HAIKU, role='private_draft')(17801, 'generation')['input_tokens'], 16001)
        self.admit.end_turn();self.now += timedelta(days=2)
        initial['slots'][0]['input_tokens'] = 998201
        before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'NATIVE_PLAN_INVALID'):
            self.admit.begin_turn('native-exceeded', plan=initial)
        self.assertEqual(before, self.client.documents)

    def test_missing_wrong_role_or_changed_envelope_never_gets_paid_permit(self):
        self.admit.begin_turn('hard-envelope', plan=self.phased_plans()[0]);before = deepcopy(self.client.documents)
        for role, tokens, stage in ((None, 21800, None), ('semantic_verifier', 21800, None),
                                   ('private_draft', 21801, None), ('private_draft', 21800, 'verify')):
            with self.subTest(role=role, tokens=tokens, stage=stage), self.assertRaises(ProviderFailure):
                self.admit.for_model(HAIKU, role=role)(tokens, 'generation', stage=stage)
            self.assertEqual(before, self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'MODEL_ROLE_MISMATCH'):self.admit(100, 'generation')
        events = self.client.documents['grounded-provider-global-v1']['events']
        events[0]['input_tokens'] += 1;events[0]['tokens'] += 1
        with self.assertRaisesRegex(ProviderFailure, 'NATIVE_PLAN_STORE_CHANGED'):
            self.admit.for_model(HAIKU, role='private_draft')(21800, 'generation')

    def test_haiku_spend_failure_leaves_all_global_capacity_untouched(self):
        self.client.documents[CLAUDE_ALLOCATION] = {'version': CLAUDE_VERSION,
            'maximum_nanodollars': 1000000000, 'model': HAIKU,
            'reserved_nanodollars': 999999999, 'reservation_count': 3}
        before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'CLAUDE_SPEND_LIMIT'):
            self.admit.begin_turn('no-cost-capacity', plan=self.phased_plans()[0])
        self.assertEqual(before, self.client.documents)

    def test_native_plan_requires_separate_stages_and_no_retry_or_retired_model(self):
        for mutation in ('missing', 'same-stage', 'retry', 'retired-model', 'money-understated'):
            plan = self.phased_plans()[0]
            if mutation == 'missing':plan['slots'].pop()
            if mutation == 'same-stage':plan['slots'][1]['stage'] = 'draft'
            if mutation == 'retry':plan['slots'][0]['attempt'] = 2
            if mutation == 'retired-model':plan['slots'][0]['model'] = GEMMA
            if mutation == 'money-understated':plan['slots'][1]['maximum_nanodollars'] = 1
            with self.subTest(mutation=mutation), self.assertRaises(ProviderFailure):
                self.admit.begin_turn('invalid-' + mutation, plan=plan)
        self.assertFalse(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'MODEL_ROLE_MISMATCH'):self.admit.for_model(GEMMA)

    def test_shared_haiku_budget_observes_other_existing_reservations(self):
        from cloud.grounded_generation.claude_budget import ClaudeBudget
        ClaudeBudget(self.client)('0.25', HAIKU)
        initial, _ = self.phased_plans();receipt = self.admit.begin_turn('shared', plan=initial)
        self.assertEqual(self.client.documents[CLAUDE_ALLOCATION]['reserved_nanodollars'],
            250000000 + receipt['reserved_nanodollars'])
        ClaudeBudget(self.client)('0.25', HAIKU)
        self.assertEqual(self.client.documents[CLAUDE_ALLOCATION]['reserved_nanodollars'],
            500000000 + receipt['reserved_nanodollars'])
        self.assertEqual(set(self.client.documents), {ALLOCATION, CLAUDE_ALLOCATION, 'grounded-provider-global-v1'})

    def test_concurrent_native_pairs_cannot_overrun_shared_money_or_token_counters(self):
        self.client.documents[CLAUDE_ALLOCATION] = {'version': CLAUDE_VERSION, 'model': HAIKU,
            'maximum_nanodollars': 1000000000, 'reserved_nanodollars': 986400000, 'reservation_count': 9}
        results = []
        def reserve(index):
            other = WholeTurnAdmission(self.client, now=lambda: self.now, sleep=lambda _: None)
            try:
                other.begin_turn('concurrent-' + str(index), plan=self.phased_plans()[0])
                results.append('accepted')
            except ProviderFailure as error:
                results.append(str(error))
        workers = [threading.Thread(target=reserve, args=(index,)) for index in range(6)]
        for worker in workers:worker.start()
        for worker in workers:worker.join()
        self.assertEqual(results.count('accepted'), 2)
        self.assertEqual(results.count('CLAUDE_SPEND_LIMIT'), 4)
        self.assertEqual(self.client.documents[CLAUDE_ALLOCATION]['reserved_nanodollars'], 1000000000)
        self.assertEqual(self.client.documents[CLAUDE_ALLOCATION]['reservation_count'], 11)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 4)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_tokens'], 4 * 21800)
        self.assertEqual(len(self.client.documents['grounded-provider-global-v1']['events']), 4)

    def test_uncertain_initial_commit_is_retained_and_not_replayed_by_new_instance(self):
        original = self.client.set
        def uncertain(ref, body):
            original(ref, body)
            if ref.name == CLAUDE_ALLOCATION:raise RuntimeError('synthetic uncertain initial commit')
        self.client.set = uncertain
        initial, _ = self.phased_plans()
        with self.assertRaisesRegex(ProviderFailure, 'STORE_UNAVAILABLE'):
            self.admit.begin_turn('uncertain-initial', plan=initial)
        self.assertIsNone(getattr(self.admit.local, 'turn', None))
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 2)
        before = deepcopy(self.client.documents);self.client.set = original
        other = WholeTurnAdmission(self.client, now=lambda: self.now, sleep=lambda _: None)
        with self.assertRaisesRegex(ProviderFailure, 'ALREADY_RESERVED_NO_REPLAY'):
            other.begin_turn('uncertain-initial', plan=initial)
        self.assertEqual(before, self.client.documents)

    def test_shared_budget_wrong_model_or_invalid_historical_counter_is_rejected(self):
        from cloud.grounded_generation.claude_budget import ClaudeBudget
        for field, value, reason in (('model', GEMMA, 'BINDING_CHANGED'),
                                     ('reservation_count', True, 'STORE_INVALID'),
                                     ('reserved_nanodollars', 1000000001, 'STORE_INVALID')):
            previous = {'version': CLAUDE_VERSION, 'maximum_nanodollars': 1000000000,
                'model': HAIKU, 'reserved_nanodollars': 1, 'reservation_count': 1}
            previous[field] = value;self.client.documents = {CLAUDE_ALLOCATION: previous}
            before = deepcopy(self.client.documents)
            with self.subTest(field=field), self.assertRaisesRegex(ProviderFailure, reason):
                self.admit.begin_turn('invalid-ledger-' + field, plan=self.phased_plans()[0])
            with self.assertRaisesRegex(ProviderFailure, reason):ClaudeBudget(self.client)('.001', HAIKU)
            self.assertEqual(before, self.client.documents)

    def test_invalid_cost_amounts_fail_before_any_persistent_reservation(self):
        from cloud.grounded_generation.claude_budget import ClaudeBudget
        for value in (None, True, 'bad', 'NaN', 'Infinity', 0, -1):
            with self.subTest(value=value), self.assertRaisesRegex(ProviderFailure, 'COST_RESERVATION_INVALID'):
                ClaudeBudget(self.client)(value, HAIKU)
        self.assertFalse(self.client.documents)

    def test_historical_native_events_and_sealing_remain_charged_after_haiku_upgrade(self):
        from cloud.grounded_generation.whole_turn_admission import HISTORICAL_PACING_VERSION, FLASH
        events = [{'at': self.now + timedelta(seconds=61), 'tokens': 15800, 'kind': 'generation',
            'operation_id': 'historical', 'slot': 0, 'consumed': False, 'model': GEMMA,
            'stage': 'draft', 'input_tokens': 14000, 'output_tokens': 1800, 'attempt': 2,
            'state': 'SEALED_UNUSED', 'sealed_at': self.now, 'sealed_version': HISTORICAL_PACING_VERSION},
            {'at': self.now - timedelta(seconds=120), 'tokens': 21800, 'kind': 'generation',
            'operation_id': 'historical-flash', 'slot': 0, 'consumed': True, 'model': FLASH,
            'stage': 'draft', 'input_tokens': 20000, 'output_tokens': 1800, 'attempt': 1}]
        self.client.documents['grounded-provider-global-v1'] = {'events': events}
        self.client.documents[ALLOCATION] = {'version': 'whole-turn-capacity-v1',
            'maximum_attempts': 100, 'maximum_tokens': 999200, 'reserved_attempts': 24, 'reserved_tokens': 239808}
        receipt = self.admit.begin_turn('new-haiku', plan=self.phased_plans()[0])
        self.assertEqual(self.client.documents['grounded-provider-global-v1']['events'][:2], events)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 26)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_tokens'], 239808 + receipt['reserved_tokens'])
        self.admit.for_model(HAIKU, role='private_draft')(21800, 'generation')
        self.assertFalse(self.waits)

    def test_legacy_proved_sealing_remains_honored_without_refunding_old_charges(self):
        self.admit.begin_turn('old');self.admit(9992, 'generation');self.admit.end_turn()
        events = self.client.documents['grounded-provider-global-v1']['events']
        for event in events:
            if event.get('state') == 'SEALED_UNUSED':event['sealed_version'] = LEGACY_PACING_VERSION
        old = deepcopy(self.client.documents[ALLOCATION]);initial, _ = self.phased_plans()
        self.admit.begin_turn('new', plan=initial)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], old['reserved_attempts'] + 2)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_tokens'],
            old['reserved_tokens'] + sum(row['input_tokens'] + row['output_tokens'] for row in initial['slots']))

    def test_reserves_correction_and_retry_capacity_before_first_call(self):
        receipt=self.admit.begin_turn('operation-1')
        self.assertEqual(receipt['reserved_attempts'],8)
        self.assertEqual(receipt['reserved_tokens'],79936)
        self.assertFalse(self.waits)
        times=[]
        for _ in range(8):
            self.admit(9992,'generation');times.append(self.now)
        self.assertEqual([(b-a).total_seconds() for a,b in zip(times,times[1:])],[61]*7)
        self.assertTrue(all(wait<=MAX_SLEEP_SECONDS for wait in self.waits))
        with self.assertRaisesRegex(ProviderFailure,'UNRESERVED'):self.admit(1,'generation')

    def test_delayed_attempts_still_obey_rolling_minute(self):
        self.admit.begin_turn('delayed')
        self.now+=timedelta(seconds=120)
        self.admit(5000,'generation');self.admit(5000,'generation')
        self.assertEqual(sum(self.waits),61)
        events=self.client.documents['grounded-provider-global-v1']['events']
        consumed=[e['at'] for e in events if e.get('consumed')]
        self.assertEqual((consumed[1]-consumed[0]).total_seconds(),61)

    def test_oversleep_repositions_consumed_permit_before_paid_transmission(self):
        def oversleep(seconds):self.now+=timedelta(seconds=seconds+120)
        self.admit.sleep=oversleep
        self.admit.begin_turn('oversleep');times=[]
        for _ in range(3):
            self.admit(9992,'generation');times.append(self.now)
        self.assertTrue(all((b-a).total_seconds()>=60 for a,b in zip(times,times[1:])))
        consumed=[e['at'] for e in self.client.documents['grounded-provider-global-v1']['events'] if e.get('consumed')]
        self.assertEqual(consumed,times)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],8)

    def test_slow_commit_rechecks_before_returning_a_stale_permit(self):
        original=self.client.set;delayed=[]
        def slow_set(ref,body):
            original(ref,body)
            if ref.name=='grounded-provider-global-v1' and any(e.get('consumed') for e in body['events']) and not delayed:
                delayed.append(True);self.now+=timedelta(seconds=120)
        self.client.set=slow_set
        self.admit.begin_turn('slow-commit');self.admit(9992,'generation')
        consumed=[e['at'] for e in self.client.documents['grounded-provider-global-v1']['events'] if e.get('consumed')]
        self.assertEqual(consumed,[self.now])

    def test_deadline_binds_capacity_and_blocks_expired_turn_before_reserving(self):
        before=deepcopy(self.client.documents)
        with operation_deadline(self.now+timedelta(seconds=427)):
            with self.assertRaisesRegex(ProviderFailure,'DEADLINE_EXCEEDED'):self.admit.begin_turn('too-short')
        self.assertEqual(self.client.documents,before)
        with operation_deadline(self.now):
            with self.assertRaisesRegex(ProviderFailure,'DEADLINE_EXCEEDED'):self.admit.begin_turn('expired')
        self.assertEqual(self.client.documents,before)
        self.admit.begin_turn('unscoped-synthetic')

    def test_oversleep_past_deadline_stops_paid_transport_and_retains_reservation(self):
        from cloud.grounded_generation.test_provider import Transport
        transport=Transport();provider=GemmaProvider(self.admit,transport=transport,key='synthetic')
        with operation_deadline(self.now+timedelta(seconds=500)):
            provider.begin_turn('deadline')
            provider.complete('policy',{}, {}, {})
            self.admit.sleep=lambda seconds:setattr(self,'now',self.now+timedelta(seconds=seconds+500))
            with self.assertRaisesRegex(ProviderFailure,'DEADLINE_EXCEEDED'):
                provider.complete('policy',{}, {}, {})
            provider.end_turn()
        self.assertEqual(sum(path.endswith(':generateContent') for path,_ in transport.calls),1)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],8)
        events=self.client.documents['grounded-provider-global-v1']['events']
        self.assertEqual(sum(bool(e.get('consumed')) for e in events),2)

    def test_oversleep_queue_bound_never_restarts_the_wait_budget(self):
        self.admit.begin_turn('queue-bound');self.admit(9992,'generation')
        self.admit.sleep=lambda seconds:setattr(self,'now',self.now+timedelta(seconds=seconds+800))
        with self.assertRaisesRegex(ProviderFailure,'QUEUE_BOUND'):self.admit(9992,'generation')
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],8)

    def test_store_outage_after_wait_keeps_slot_consumed_without_paid_call(self):
        self.admit.begin_turn('wait-outage');self.admit(9992,'generation')
        def failed_wait(seconds):
            self.now+=timedelta(seconds=seconds);self.client.fail=True
        self.admit.sleep=failed_wait
        with self.assertRaisesRegex(ProviderFailure,'STORE_UNAVAILABLE'):self.admit(9992,'generation')
        events=self.client.documents['grounded-provider-global-v1']['events']
        self.assertEqual(sum(bool(e.get('consumed')) for e in events),2)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],8)

    def test_duplicate_and_uncertain_calls_do_not_reopen_reservations(self):
        self.admit.begin_turn('same');self.admit(100,'generation');self.admit.end_turn()
        before=deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure,'NO_REPLAY'):self.admit.begin_turn('same')
        self.assertEqual(before,self.client.documents)

    def test_lifetime_allocation_survives_new_days_and_instances(self):
        for i in range(12):
            self.admit.begin_turn('day-'+str(i));self.admit.end_turn()
            self.now+=timedelta(days=2)
        other=WholeTurnAdmission(self.client,now=lambda:self.now,sleep=lambda _:None)
        with self.assertRaisesRegex(ProviderFailure,'ALLOCATION_LIMIT'):other.begin_turn('exhausted')
        self.assertNotIn('expires_at',self.client.documents[ALLOCATION])

    def test_store_outage_or_entire_turn_limit_blocks_first_generation(self):
        self.client.fail=True
        with self.assertRaisesRegex(ProviderFailure,'STORE_UNAVAILABLE'):self.admit.begin_turn('outage')
        self.assertFalse(self.client.documents)
        self.client.fail=False
        self.client.documents[ALLOCATION]={'version':'changed'}
        with self.assertRaisesRegex(ProviderFailure,'BINDING_CHANGED'):self.admit.begin_turn('binding')

    def test_active_future_slots_still_bound_a_different_worker(self):
        self.admit.begin_turn('first')
        other=WholeTurnAdmission(self.client,now=lambda:self.now,sleep=lambda _:None)
        with self.assertRaisesRegex(ProviderFailure,'QUEUE_BOUND'):other.begin_turn('second')
        self.assertEqual(len(self.client.documents['grounded-provider-global-v1']['events']),8)

    def test_completed_two_call_turn_releases_only_pacing_and_retains_sixteen_reserved_slots(self):
        receipt=self.admit.begin_turn('first')
        self.admit(9992,'generation');self.admit(9992,'generation')
        last_actual=self.now
        allocation_before=deepcopy(self.client.documents[ALLOCATION])
        self.assertIs(self.admit.end_turn(),receipt)
        self.assertEqual(receipt['pacing_version'],PACING_VERSION)
        self.assertEqual(receipt['sealing_status'],'SEALED_UNUSED_CONFIRMED')
        self.assertEqual(receipt['sealed_unused_slots'],6)
        self.assertEqual(self.client.documents[ALLOCATION],allocation_before)
        self.admit.begin_turn('second');self.admit(9992,'generation')
        self.assertEqual((self.now-last_actual).total_seconds(),61)
        events=self.client.documents['grounded-provider-global-v1']['events']
        self.assertEqual(len(events),16)
        self.assertEqual(sum(e.get('state')=='SEALED_UNUSED' for e in events),6)
        self.assertEqual(sum(e['tokens'] for e in events),16*9992)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],16)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_tokens'],16*9992)

    def test_uncertain_consumed_future_permit_stays_active_after_turn_ends(self):
        self.admit.begin_turn('interrupted');self.admit(9992,'generation')
        def worker_interrupted(_):raise RuntimeError('synthetic worker interrupted before transport')
        normal_sleep=self.admit.sleep;self.admit.sleep=worker_interrupted
        with self.assertRaisesRegex(RuntimeError,'interrupted'):self.admit(9992,'generation')
        self.assertEqual(self.now,datetime(2026,10,12,tzinfo=timezone.utc))
        self.admit.end_turn();self.admit.sleep=normal_sleep
        old=self.client.documents['grounded-provider-global-v1']['events']
        self.assertTrue(old[1]['consumed'])
        self.assertNotIn('state',old[1])
        self.admit.begin_turn('next');self.admit(9992,'generation')
        self.assertEqual(self.now,datetime(2026,10,12,tzinfo=timezone.utc)+timedelta(seconds=122))
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],16)

    def test_sealed_slot_cannot_be_consumed_even_if_a_stale_worker_restores_its_turn(self):
        self.admit.begin_turn('sealed');self.admit(9992,'generation');self.admit(9992,'generation')
        stale_turn=dict(self.admit.local.turn)
        self.admit.end_turn()
        before=deepcopy(self.client.documents)
        self.admit.local.turn=stale_turn
        with self.assertRaisesRegex(ProviderFailure,'SEALED_UNUSED_ATTEMPT_FORBIDDEN'):
            self.admit(9992,'generation')
        self.assertEqual(self.client.documents,before)

    def test_sealing_outage_clears_thread_state_preserves_original_error_and_active_events(self):
        receipt=self.admit.begin_turn('seal-outage');self.admit(9992,'generation')
        before=deepcopy(self.client.documents);self.client.fail=True
        with self.assertRaisesRegex(ProviderFailure,'ORIGINAL_GENERATION_ERROR'):
            try:raise ProviderFailure('ORIGINAL_GENERATION_ERROR')
            finally:self.admit.end_turn()
        self.assertIsNone(self.admit.local.turn)
        self.assertEqual(receipt['sealing_status'],'SEALING_UNCONFIRMED_ACTIVE_POLICY_RETAINED')
        self.assertEqual(receipt['sealed_unused_slots'],0)
        self.assertEqual(self.client.documents,before)
        self.client.fail=False
        with self.assertRaisesRegex(ProviderFailure,'QUEUE_BOUND'):self.admit.begin_turn('after-outage')
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],8)

    def test_failed_sealing_write_leaves_all_slots_active(self):
        receipt=self.admit.begin_turn('write-outage');self.admit(9992,'generation')
        before=deepcopy(self.client.documents)
        def unavailable_set(ref,body):raise RuntimeError('synthetic failed commit')
        self.client.set=unavailable_set
        self.admit.end_turn()
        self.assertEqual(self.client.documents,before)
        self.assertEqual(receipt['sealed_unused_slots'],0)
        self.assertEqual(receipt['sealing_status'],'SEALING_UNCONFIRMED_ACTIVE_POLICY_RETAINED')
        self.assertIsNone(self.admit.local.turn)

    def test_consumed_or_unproved_sealing_markers_fail_closed(self):
        self.admit.begin_turn('original');self.admit(9992,'generation');self.admit.end_turn()
        events=self.client.documents['grounded-provider-global-v1']['events']
        events[0].update(state='SEALED_UNUSED',sealed_version=PACING_VERSION,sealed_at=self.now)
        before=deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure,'STORE_INVALID'):self.admit.begin_turn('new')
        self.assertEqual(self.client.documents,before)

    def test_shorter_next_turn_does_not_shorten_retention_of_sealed_future_events(self):
        self.admit.begin_turn('twelve',attempts=12);self.admit.end_turn()
        old_last=self.client.documents['grounded-provider-global-v1']['events'][-1]['at']
        self.admit.begin_turn('eight',attempts=8)
        ledger=self.client.documents['grounded-provider-global-v1']
        self.assertEqual(len(ledger['events']),20)
        self.assertEqual(ledger['expires_at'],old_last+timedelta(hours=24))
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],20)

    def test_unconfigured_primary_count_uses_native_fallback_counter(self):
        calls=[]
        def transport(method,path,body,key):
            calls.append((path,body))
            return {'input_tokens':7}
        primary=GemmaProvider(self.admit,key='')
        primary.key=None
        fallback=ClaudeProvider(self.admit,reserve_cost=lambda n,m:None,
                                transport=transport,key='synthetic')
        chain=FallbackProvider(primary,fallback)
        self.assertEqual(chain.count({'contents':[{'parts':[{'text':'presentation'}]}]}),7)
        self.assertEqual(calls[0][0],'messages/count_tokens')
        self.assertEqual(calls[0][1]['model'],'claude-haiku-5-5')

    def test_enabled_fallback_reserves_all_cost_before_primary_generation(self):
        costs=[]
        primary=GemmaProvider(self.admit,key='synthetic')
        fallback=ClaudeProvider(self.admit,reserve_cost=lambda n,m:costs.append((n,m)),key='synthetic')
        chain=FallbackProvider(primary,fallback)
        receipt=chain.begin_turn('fallback')
        self.assertEqual(receipt['reserved_attempts'],12)
        self.assertEqual(costs,[(4*MAX_CALL_USD,'claude-haiku-5-5')])
        chain.end_turn()


class AdmissionIdentityTests(unittest.TestCase):
    def setup_runtime(self,p):
        """Exercise real composition/delivery with synthetic source boundaries only."""
        # Exercise the real bound model/prompt contract with synthetic sources
        # and providers. A partial Config double cannot represent v10 binding.
        from cloud.grounded_generation.verified_qa import Config
        config=Config()
        eid='synthetic-evidence'
        registry=types.SimpleNamespace(checksum=content_hash({'fixture':'synthetic-manual'}),
            index_id='synthetic-index',source={'pdf_pages':1},source_ready=lambda:True,
            support_uri=lambda:None,evidence={eid:{'provenance':[{'page_no':1}]}})
        admitted={'authority_lock':content_hash({'fixture':'synthetic-authority'}),
            'evidence':{eid:{'source_object':{'content':{'text':'Synthetic fixture value is 7 units.'}}}},
            'required_evidence_ids':[eid],'required_display':[],'gaps':[]}
        admitted['payload_sha256']=content_hash(admitted)
        def select(payload,ids):
            self.assertEqual(ids,{eid});self.assertEqual(payload,admitted)
            return deepcopy(admitted)
        authority=types.SimpleNamespace(validate=lambda payload:self.assertEqual(payload,admitted),select=select)
        composer=verified.Composer(p,authority)
        controller=types.SimpleNamespace(registry=registry,scope_status=lambda session:'CONFIRMED',
            response=lambda kind,text,session,**kwargs:Response(ResponseType(kind),text,
                trace_id='synthetic-trace',session_status=session.status,**kwargs))
        session=DiagnosticSession('a'*32,'synthetic-manual',registry.checksum,
            'synthetic-variant','synthetic-edition',(),'synthetic-source-lock',generation_lock=config.lock)
        def run(current,query,*,operation_id):
            response=composer.compose_open(controller,current,admitted,query,{'operation_id':operation_id})
            view,choices=verified.saved_view(registry,current,response,authority,composer.last_admitted,operation_id)
            return current,view,choices
        return types.SimpleNamespace(answer=run),p,composer,session

    def test_same_rider_key_in_distinct_sessions_has_distinct_admission_and_same_proof_identity(self):
        identities=[];p=verified.Provider([verified.draft('synthetic-evidence','Synthetic fixture value is 7 units.')])
        p.begin_turn=lambda identity:identities.append(identity) or {'synthetic':True}
        q,p,composer,session=self.setup_runtime(p)
        for session_id in ('a'*32,'b'*32):
            current=replace(session,session_id=session_id)
            _,view,_=q.answer(current,'What is the synthetic fixture value?',operation_id='c'*32)
            self.assertEqual(view['response']['type'],'SUPPORTED')
            self.assertEqual(composer.last_admitted['binding']['operation_id'],'c'*32)
            self.assertEqual(view['verified_delivery']['operation_id'],'c'*32)
        self.assertEqual(identities,[content_hash({'session_id':sid,'operation_id':'c'*32}) for sid in ('a'*32,'b'*32)])
        self.assertNotEqual(*identities)
        self.assertEqual([call[0] for call in p.calls],[verified.DRAFT_SCHEMA,verified.VERIFY_SCHEMA]*2)


if __name__=='__main__':unittest.main()
