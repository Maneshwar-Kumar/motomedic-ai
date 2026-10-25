"""Synthetic audit-consumer checks; fixtures confer no owner authority."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
spec=importlib.util.spec_from_file_location('delivery_auditor_v2',HERE/'audit_hosted_delivery_cache_v2.py')
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

from cloud.grounded_generation.test_token_ceiling import fixtures,synthetic_owner_evidence
from cloud.grounded_generation.token_ceiling import (ALLOCATION,HAIKU_ALLOCATION,GRANT_DOCUMENT,
    make_proposal,grant_from_owner_evidence,validate_grant)


class ReadonlyLedgerAuditTests(unittest.TestCase):
    def setUp(self):
        manifest=ROOT/'reports/public_evaluator/20261012/serving_manifest_v10_13.json'
        self.release=json.loads(manifest.read_text(encoding='utf-8'))
        self.sha=hashlib.sha256(manifest.read_bytes()).hexdigest()
        budget,self.before=fixtures()
        budget['serving_manifest_sha256']=self.sha
        self.runtime=budget['runtime_lock']
        proposal=make_proposal(budget,self.before)
        self.grant=grant_from_owner_evidence(proposal,owner_evidence_raw=synthetic_owner_evidence(proposal),
            evidence_path='reports/public_evaluator/20261012/haiku_v10_13_runtime/synthetic_owner_approval.json')

    def approved(self):
        value=deepcopy(self.before)
        value[GRANT_DOCUMENT]=deepcopy(self.grant)
        value[ALLOCATION]['maximum_tokens']=self.grant['maximum_tokens']
        value[ALLOCATION]['token_ceiling_authorization']=validate_grant(self.grant)
        return value

    def check(self,before,after,release=None):
        untouched=deepcopy((before,after))
        result=audit.audit_ledgers(before,after,release or self.release,
            manifest_sha=self.sha,runtime_lock=self.runtime)
        self.assertEqual((before,after),untouched)
        return result

    def test_default_baseline_retains_all_charges_without_grant(self):
        after=deepcopy(self.before)
        after[ALLOCATION]['reserved_tokens']+=40000
        after[ALLOCATION]['reserved_attempts']+=2
        after[HAIKU_ALLOCATION]['reserved_nanodollars']+=2000000
        after[HAIKU_ALLOCATION]['reservation_count']+=1
        result=self.check(self.before,after)
        self.assertTrue(result['passed'],result['errors'])
        self.assertEqual(result['primary_token_ceiling'],999200)
        self.assertIsNone(result['token_ceiling_authorization'])

    def test_approved_ceiling_allows_above_default_with_same_exact_binding(self):
        before=self.approved();after=deepcopy(before)
        after[ALLOCATION].update(reserved_tokens=1040000,reserved_attempts=40)
        after[HAIKU_ALLOCATION].update(reserved_nanodollars=90000000,reservation_count=12)
        result=self.check(before,after)
        self.assertTrue(result['passed'],result['errors'])
        self.assertEqual(result['primary_token_ceiling'],1050000)
        self.assertEqual(result['token_ceiling_authorization'],validate_grant(self.grant))

    def test_missing_or_tampered_grant_fails(self):
        before=self.approved()
        for field in ('missing','maximum','scope','allocation_binding'):
            after=deepcopy(before)
            if field=='missing':del after[GRANT_DOCUMENT]
            if field=='maximum':after[GRANT_DOCUMENT]['maximum_tokens']+=1
            if field=='scope':after[GRANT_DOCUMENT]['scope_sha256']='0'*64
            if field=='allocation_binding':after[ALLOCATION]['token_ceiling_authorization']['scope_sha256']='0'*64
            with self.subTest(field=field):
                self.assertIn('PRIMARY_TOKEN_GRANT_INVALID',self.check(before,after)['errors'])

    def test_default_cannot_activate_unapplied_grant(self):
        after=deepcopy(self.before);after[GRANT_DOCUMENT]=deepcopy(self.grant)
        self.assertIn('PRIMARY_TOKEN_GRANT_INVALID',self.check(self.before,after)['errors'])

    def test_grant_cannot_change_during_the_hosted_run(self):
        result=self.check(self.before,self.approved())
        self.assertIn('PRIMARY_TOKEN_AUTHORITY_CHANGED_DURING_RUN',result['errors'])
        self.assertIn('EXACT_PRIMARY_GRANT_CHANGED_DURING_RUN',result['errors'])

    def test_attempt_money_limits_and_counter_reset_stay_rejected(self):
        for document,key,value,code in (
            (ALLOCATION,'maximum_attempts',101,'PERMANENT_LEDGER_LIMIT_CHANGED'),
            (HAIKU_ALLOCATION,'maximum_nanodollars',2000000000,'PERMANENT_LEDGER_LIMIT_CHANGED'),
            (ALLOCATION,'reserved_tokens',1,'PERMANENT_CHARGES_RESET_OR_INVALID'),
            (HAIKU_ALLOCATION,'reserved_nanodollars',1,'PERMANENT_CHARGES_RESET_OR_INVALID')):
            before=self.approved();after=deepcopy(before);after[document][key]=value
            with self.subTest(key=key):self.assertIn(code,self.check(before,after)['errors'])

    def test_measured_manifest_and_runtime_are_exactly_bound(self):
        before=self.approved()
        result=audit.audit_ledgers(before,before,self.release,manifest_sha='0'*64,runtime_lock=self.runtime)
        self.assertIn('PRIMARY_GRANT_MEASURED_RUNTIME_CHANGED',result['errors'])
        result=audit.audit_ledgers(before,before,self.release,manifest_sha=self.sha,runtime_lock='0'*64)
        self.assertIn('PRIMARY_GRANT_MEASURED_RUNTIME_CHANGED',result['errors'])

    def test_frozen_consumer_hash_cannot_be_replaced(self):
        release=deepcopy(self.release)
        release['file_sha256']['cloud/grounded_generation/token_ceiling.py']='0'*64
        self.assertIn('FROZEN_TOKEN_POLICY_SOURCE_CHANGED',self.check(self.before,self.before,release)['errors'])

    def test_new_event_scope_binds_grant_and_preserves_historical_events(self):
        before=self.approved()
        old={'operation_id':'historical','slot':0,'primary_token_ceiling':999200,
             'token_ceiling_scope_sha256':None,'at':'2026-10-12T00:00:00Z'}
        before['grounded-provider-global-v1']={'events':[old],'expires_at':'2026-10-13T00:00:00Z'}
        after=deepcopy(before)
        new={'operation_id':'current','slot':0,'phase':'initial','phase_nonce':'1'*64,
             'plan_sha256':'2'*64,'primary_token_ceiling':1050000,
             'token_ceiling_scope_sha256':self.grant['scope_sha256'],'at':'2026-10-12T01:00:00.123456Z'}
        after['grounded-provider-global-v1']['events'].append(new)
        result=self.check(before,after)
        self.assertTrue(result['passed'],result['errors'])
        self.assertEqual(result['new_event_scopes_checked'],1)
        new['token_ceiling_scope_sha256']='0'*64
        self.assertIn('NEW_PERMIT_EVENT_TOKEN_AUTHORITY_CHANGED',self.check(before,after)['errors'])

    def test_omitted_global_events_are_reported_without_invented_proof(self):
        result=self.check(self.before,self.before)
        self.assertFalse(result['event_readback_present'])
        self.assertEqual(result['new_event_scopes_checked'],0)

    def test_operation_reservation_scope_matches_ledger(self):
        before=self.approved();proof=self.check(before,before)
        reservation={'primary_token_ceiling':1050000,'token_ceiling_authorization':validate_grant(self.grant)}
        row={'saved_view':{'runtime_controls':{'composition':{'whole_turn_reservation':reservation}}}}
        self.assertEqual(audit.audit_reservation_scope(row,proof),[])
        reservation['token_ceiling_authorization']['scope_sha256']='0'*64
        self.assertEqual(audit.audit_reservation_scope(row,proof),['OPERATION_RESERVATION_TOKEN_AUTHORITY_CHANGED'])
        self.assertEqual(audit.audit_reservation_scope({},proof),['V13_WHOLE_TURN_SCOPE_RECEIPT_MISSING'])


if __name__=='__main__':unittest.main()
