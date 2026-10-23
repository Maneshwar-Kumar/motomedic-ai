"""Synthetic owner-grant and persistent accounting checks; never real authority."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import types
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from evidence_registry import content_hash
from generation_providers import ProviderFailure
from cloud.grounded_generation.test_whole_turn_admission import Client, atomic
from cloud.grounded_generation.token_ceiling import (
    ALLOCATION, ALLOCATION_VERSION, GRANT_DOCUMENT, OWNER_SCHEMA, MODEL_SCOPE_SHA,
    DEFAULT_TOKEN_CEILING, MAX_TOKEN_CEILING, HAIKU_ALLOCATION, make_proposal,
    grant_from_owner_evidence, validate_grant, resolve_token_ceiling, apply_authorized_grant)
from cloud.grounded_generation.whole_turn_admission import WholeTurnAdmission, HAIKU
from cloud.grounded_generation.claude_budget import VERSION as HAIKU_VERSION


def fixtures():
    primary = {'version': ALLOCATION_VERSION, 'maximum_attempts': 100, 'maximum_tokens': 999200,
        'reserved_attempts': 28, 'reserved_tokens': 357663}
    money = {'version': HAIKU_VERSION, 'maximum_nanodollars': 1000000000,
        'reserved_nanodollars': 28975875, 'reservation_count': 5}
    rows = [{'case_id': 'synthetic-' + str(index), 'initial_totals': {
        'attempts': 2, 'tokens': 60000, 'haiku_nanodollars': 4000000},
        'conditional_totals': {'attempts': 2, 'tokens': 120000, 'haiku_nanodollars': 8000000}}
        for index in range(6)]
    budget = {'schema': 'motomedic-measured-initial-phase-capacity-v2', 'owner_model_scope_sha256': MODEL_SCOPE_SHA,
        'allocation_reservations_refunded_or_reset': False, 'count_receipt_sha256': 'a' * 64,
        'serving_manifest_sha256': 'b' * 64, 'runtime_lock': 'c' * 64,
        'count_build_id': '12345678-1234-1234-1234-123456789012', 'case_forecasts': rows,
        'retained_floor': {'required': {'attempts': 6, 'tokens': 180000, 'haiku_nanodollars': 12000000}}}
    return budget, {ALLOCATION: primary, HAIKU_ALLOCATION: money}


def synthetic_owner_evidence(proposal, maximum=1050000):
    return json.dumps({'schema': OWNER_SCHEMA, 'authority': 'DIRECT_OWNER_INSTRUCTION',
        'owner_approved': True, 'exact_owner_instruction': 'SYNTHETIC TEST ONLY: approve this exact numeric ceiling.',
        'approved_at_utc': '2026-10-12T00:00:00Z', 'proposal_sha256': proposal['proposal_sha256'],
        'maximum_tokens': maximum, 'only_primary_token_ceiling_change': True,
        'other_budgets_and_historical_charges_unchanged': True,
        'billing_restart_authorized': False, 'refund_or_reset_authorized': False}).encode()


class TokenCeilingTests(unittest.TestCase):
    def setUp(self):
        self.budget, self.ledgers = fixtures()
        self.proposal = make_proposal(self.budget, self.ledgers)
        self.raw = synthetic_owner_evidence(self.proposal)
        self.grant = grant_from_owner_evidence(self.proposal, owner_evidence_raw=self.raw,
            evidence_path='reports/public_evaluator/20261012/haiku_v10_13/synthetic_owner_approval.json')
        self.client = Client();self.client.documents = deepcopy(self.ledgers)
        self.client.documents['grounded-provider-global-v1'] = {'events': []}
        google = types.ModuleType('google');cloud = types.ModuleType('google.cloud')
        cloud.firestore = types.SimpleNamespace(transactional=atomic);google.cloud = cloud
        self.mock = patch.dict('sys.modules', {'google': google, 'google.cloud': cloud});self.mock.start()
        self.addCleanup(self.mock.stop)

    def apply(self):
        return apply_authorized_grant(self.client, self.grant, owner_evidence_raw=self.raw)

    def test_proposal_is_readonly_and_measured_minimum_preserves_largest_conditional_and_floor(self):
        self.assertFalse(self.proposal['owner_approved'])
        self.assertEqual(self.proposal['proposed_maximum_tokens'], 1017663)
        self.assertEqual(self.proposal['counter_writes'], 0)
        full = make_proposal(self.budget, self.ledgers, conditional_strategy='ALL_CONDITIONAL_PHASES')
        self.assertEqual(full['proposed_maximum_tokens'], 1617663)
        self.assertTrue(full['attempts_and_money_eligible'])
        self.assertEqual(self.ledgers, fixtures()[1])

    def test_default_is_unchanged_without_authority_and_unapplied_grant_is_not_activated(self):
        self.assertEqual(resolve_token_ceiling(self.ledgers[ALLOCATION]), (DEFAULT_TOKEN_CEILING, None))
        with self.assertRaisesRegex(ProviderFailure, 'UNAPPLIED_OR_CHANGED_GRANT'):
            resolve_token_ceiling(self.ledgers[ALLOCATION], self.grant)
        self.assertEqual(self.client.documents[ALLOCATION], self.ledgers[ALLOCATION])

    def test_authorized_application_changes_only_primary_numeric_limit_and_exact_grant_binding(self):
        before = deepcopy(self.client.documents);result = self.apply()
        after = self.client.documents[ALLOCATION]
        self.assertFalse(result['already_applied']);self.assertEqual(result['writes'], 2)
        self.assertEqual(after['maximum_tokens'], 1050000)
        self.assertEqual(after['version'], before[ALLOCATION]['version'])
        self.assertEqual(after['reserved_attempts'], 28);self.assertEqual(after['reserved_tokens'], 357663)
        self.assertEqual(after['maximum_attempts'], 100)
        self.assertEqual(self.client.documents[HAIKU_ALLOCATION], before[HAIKU_ALLOCATION])
        self.assertEqual(self.client.documents['grounded-provider-global-v1'], before['grounded-provider-global-v1'])
        self.assertNotIn('expires_at', after);self.assertNotIn('expires_at', self.client.documents[GRANT_DOCUMENT])
        self.assertEqual(resolve_token_ceiling(after, self.client.documents[GRANT_DOCUMENT]),
            (1050000, validate_grant(self.grant)))

    def test_duplicate_authorized_application_is_readonly_and_never_refills_usage(self):
        self.apply();self.client.documents[ALLOCATION]['reserved_tokens'] += 100
        before = deepcopy(self.client.documents);result = self.apply()
        self.assertTrue(result['already_applied']);self.assertEqual(result['writes'], 0)
        self.assertEqual(self.client.documents, before)

    def test_grant_cannot_raise_attempt_money_or_inr_budgets_or_restart_billing(self):
        for key, value in (('maximum_attempts', 101), ('haiku_maximum_nanodollars', 2000000000),
                ('project_lifetime_inr', 2701), ('billing_disconnect_inr', 2541),
                ('billing_restart_authorized', True), ('refund_or_reset_authorized', True),
                ('maximum_tokens', MAX_TOKEN_CEILING + 1), ('maximum_tokens', 999200), ('owner_approved', False)):
            changed = deepcopy(self.grant);changed[key] = value
            changed['scope_sha256'] = content_hash({key: value for key, value in changed.items() if key != 'scope_sha256'})
            with self.subTest(key=key, value=value), self.assertRaises(ProviderFailure):validate_grant(changed)
        self.assertNotIn(GRANT_DOCUMENT, self.client.documents)

    def test_missing_tampered_or_rolled_back_authority_fails_consumption(self):
        self.apply();primary = self.client.documents[ALLOCATION]
        with self.assertRaises(ProviderFailure):resolve_token_ceiling(primary)
        changed = deepcopy(self.grant);changed['maximum_tokens'] -= 1
        with self.assertRaises(ProviderFailure):resolve_token_ceiling(primary, changed)
        changed['scope_sha256'] = content_hash({key: value for key, value in changed.items() if key != 'scope_sha256'})
        with self.assertRaisesRegex(ProviderFailure, 'ALLOCATION_GRANT_BINDING_CHANGED'):
            resolve_token_ceiling(primary, changed)
        lowered = deepcopy(primary);lowered['maximum_tokens'] = 999200
        with self.assertRaises(ProviderFailure):resolve_token_ceiling(lowered, self.grant)
        primary['token_ceiling_authorization']['previous_maximum_tokens'] = 999200.0
        with self.assertRaises(ProviderFailure):resolve_token_ceiling(primary, self.grant)

    def test_new_grant_cannot_overwrite_a_prior_immutable_scope(self):
        self.apply();before = deepcopy(self.client.documents)
        changed = deepcopy(self.grant);changed['maximum_tokens'] += 1
        changed['scope_sha256'] = content_hash({key: value for key, value in changed.items() if key != 'scope_sha256'})
        # Its old owner evidence authorizes exactly the old number.
        with self.assertRaisesRegex(ProviderFailure, 'EXACT_OWNER_APPROVAL_REQUIRED'):
            apply_authorized_grant(self.client, changed, owner_evidence_raw=self.raw)
        self.assertEqual(before, self.client.documents)

    def test_missing_stale_or_unapproved_owner_evidence_never_writes(self):
        before = deepcopy(self.client.documents)
        for mutation in ('missing', 'approval', 'proposal', 'amount', 'billing'):
            value = json.loads(self.raw)
            if mutation == 'missing':raw = b'{}'
            else:
                if mutation == 'approval':value['owner_approved'] = False
                if mutation == 'proposal':value['proposal_sha256'] = '0' * 64
                if mutation == 'amount':value['maximum_tokens'] = self.proposal['proposed_maximum_tokens'] - 1
                if mutation == 'billing':value['billing_restart_authorized'] = True
                raw = json.dumps(value).encode()
            with self.subTest(mutation=mutation), self.assertRaises(ProviderFailure):
                grant_from_owner_evidence(self.proposal, owner_evidence_raw=raw,
                    evidence_path='reports/public_evaluator/20261012/haiku_v10_13/synthetic_owner_approval.json')
        with self.assertRaises(ProviderFailure):apply_authorized_grant(self.client, self.grant, owner_evidence_raw=b'{}')
        self.assertEqual(before, self.client.documents)

    def test_fresh_counter_snapshot_required_without_refund_or_replacing_new_history(self):
        for allocation, field in ((ALLOCATION, 'reserved_tokens'), (ALLOCATION, 'reserved_attempts'),
                                  (HAIKU_ALLOCATION, 'reserved_nanodollars')):
            self.client.documents = deepcopy(self.ledgers);self.client.documents[allocation][field] += 1
            before = deepcopy(self.client.documents)
            with self.subTest(allocation=allocation, field=field), self.assertRaisesRegex(ProviderFailure, 'FRESH_LEDGER_SNAPSHOT_CHANGED'):
                self.apply()
            self.assertEqual(before, self.client.documents)

    def test_unknown_or_old_forecast_cannot_supply_a_new_grant(self):
        for field, value in (('schema', 'motomedic-measured-initial-phase-capacity-v1'),
                             ('owner_model_scope_sha256', '0' * 64), ('count_receipt_sha256', 'bad')):
            budget = deepcopy(self.budget);budget[field] = value
            with self.subTest(field=field), self.assertRaises(ProviderFailure):make_proposal(budget, self.ledgers)

    def test_non_token_attempt_and_shared_money_guards_still_block_proposal_application(self):
        for allocation, key, value in ((ALLOCATION, 'reserved_attempts', 99),
                                      (HAIKU_ALLOCATION, 'reserved_nanodollars', 999999999)):
            ledgers = deepcopy(self.ledgers);ledgers[allocation][key] = value
            proposal = make_proposal(self.budget, ledgers)
            self.assertFalse(proposal['attempts_and_money_eligible'])
            with self.assertRaises(ProviderFailure):grant_from_owner_evidence(proposal,
                owner_evidence_raw=synthetic_owner_evidence(proposal),
                evidence_path='reports/public_evaluator/20261012/haiku_v10_13/synthetic_owner_approval.json')

    def test_serving_retains_new_authority_in_receipt_and_still_charges_both_existing_ledgers(self):
        self.apply();before = deepcopy(self.client.documents)
        now = [datetime(2026, 10, 12, tzinfo=timezone.utc)]
        admission = WholeTurnAdmission(self.client, now=lambda: now[0],
            sleep=lambda seconds: now.__setitem__(0, now[0] + timedelta(seconds=seconds)))
        plan = {'slots': [{'model': HAIKU, 'stage': stage, 'input_tokens': 20000,
            'output_tokens': 1800, 'attempt': 1} for stage in ('draft', 'verify')]}
        receipt = admission.begin_turn('synthetic-authorized', plan=plan)
        self.assertEqual(receipt['primary_token_ceiling'], 1050000)
        self.assertEqual(receipt['token_ceiling_authorization'], validate_grant(self.grant))
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_tokens'], before[ALLOCATION]['reserved_tokens'] + 43600)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 30)
        self.assertEqual(self.client.documents[ALLOCATION]['token_ceiling_authorization'], validate_grant(self.grant))
        self.assertGreater(self.client.documents[HAIKU_ALLOCATION]['reserved_nanodollars'], before[HAIKU_ALLOCATION]['reserved_nanodollars'])
        admission.for_model(HAIKU, role='private_draft')(21800, 'generation')
        events = self.client.documents['grounded-provider-global-v1']['events']
        self.assertEqual(events[0]['token_ceiling_scope_sha256'], self.grant['scope_sha256'])
        events[1]['token_ceiling_scope_sha256'] = '0' * 64
        with self.assertRaisesRegex(ProviderFailure, 'TOKEN_CEILING_RESERVATION_BINDING_CHANGED'):
            admission.for_model(HAIKU, role='semantic_verifier')(21800, 'generation')

    def test_authorized_limit_permits_new_capacity_above_old_ceiling_without_reset(self):
        plan = {'slots': [{'model': HAIKU, 'stage': stage, 'input_tokens': 20000,
            'output_tokens': 1800, 'attempt': 1} for stage in ('draft', 'verify')]}
        self.client.documents[ALLOCATION]['reserved_tokens'] = 998000
        admission = WholeTurnAdmission(self.client)
        with self.assertRaisesRegex(ProviderFailure, 'ALLOCATION_LIMIT'):
            admission.begin_turn('default-not-enough', plan=plan)
        self.client.documents = deepcopy(self.ledgers);self.apply()
        self.client.documents[ALLOCATION]['reserved_tokens'] = 998000
        admission = WholeTurnAdmission(self.client)
        receipt = admission.begin_turn('authorized-headroom', plan=plan)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_tokens'], 1041600)
        self.assertEqual(receipt['primary_token_ceiling'], 1050000)
        self.assertGreater(self.client.documents[ALLOCATION]['reserved_tokens'], 999200)

    def test_expanded_token_limit_does_not_raise_attempt_or_shared_money_guard(self):
        self.apply()
        plan = {'slots': [{'model': HAIKU, 'stage': stage, 'input_tokens': 20000,
            'output_tokens': 1800, 'attempt': 1} for stage in ('draft', 'verify')]}
        self.client.documents[ALLOCATION]['reserved_attempts'] = 100
        before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'ALLOCATION_LIMIT'):
            WholeTurnAdmission(self.client).begin_turn('no-more-attempts', plan=plan)
        self.assertEqual(before, self.client.documents)
        self.client.documents[ALLOCATION]['reserved_attempts'] = 28
        self.client.documents[HAIKU_ALLOCATION]['reserved_nanodollars'] = 999999999
        before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'CLAUDE_SPEND_LIMIT'):
            WholeTurnAdmission(self.client).begin_turn('no-more-money', plan=plan)
        self.assertEqual(before, self.client.documents)

    def test_uncertain_authorization_commit_readback_is_idempotent_and_never_refills(self):
        original = self.client.set
        def uncertain(ref, body):
            original(ref, body)
            if ref.name == ALLOCATION:raise RuntimeError('synthetic uncertain metadata commit')
        self.client.set = uncertain
        with self.assertRaisesRegex(ProviderFailure, 'STORE_UNAVAILABLE_UNCERTAIN_NO_RESET'):self.apply()
        before = deepcopy(self.client.documents);self.client.set = original
        result = self.apply()
        self.assertTrue(result['already_applied']);self.assertEqual(result['writes'], 0)
        self.assertEqual(before, self.client.documents)

    def test_maintainer_cli_cannot_apply_locally_before_loading_evidence_or_credentials(self):
        from tools import manage_primary_token_ceiling as tool
        with tempfile.TemporaryDirectory() as temporary, patch.dict('os.environ',
                {'MOTOMEDIC_HOSTED_TOKEN_LIMIT_MAINTENANCE': 'false'}), \
                patch('sys.argv', ['manage_primary_token_ceiling.py', 'apply-owner-approved',
                    '--proposal', 'missing-proposal.json', '--owner-evidence', 'missing-owner.json',
                    '--output', str(Path(temporary) / 'receipt.json')]):
            with self.assertRaisesRegex(RuntimeError, 'REQUIRES_EXPLICIT_HOSTED_MAINTENANCE_JOB'):tool.main()
            self.assertFalse((Path(temporary) / 'receipt.json').exists())


if __name__ == '__main__':unittest.main()
