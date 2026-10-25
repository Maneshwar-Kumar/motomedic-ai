"""Synthetic role-cache proof checks; no provider, authority or cloud actions."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
spec=importlib.util.spec_from_file_location('delivery_auditor_v3',HERE/'audit_hosted_delivery_cache_v3.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
from cloud.grounded_generation.cached_verifier import native_role_schema


class CurrentRoleCacheAuditTests(unittest.TestCase):
    def setUp(self):
        self.release=json.loads((ROOT/'reports/public_evaluator/20261012/serving_manifest_v10_13.json').read_bytes())
        self.lock=json.loads((ROOT/'reports/public_evaluator/20261012/expected_runtime_lock_v10_13.json').read_bytes())['runtime_lock']
        self.policies=audit.frozen_role_policies(self.release,self.lock)

    def call(self,role,prefix,created=0,read=0):
        return {'role':role,'prefix_sha256':prefix*64,'cache_creation_input_tokens':created,
                'cache_read_input_tokens':read,'case_id':'SYNTHETIC_ONLY','attempt':0}

    def test_distinct_frozen_policy_and_schema_identity_is_bound(self):
        first,second=(self.policies[role] for role in audit.ROLES)
        self.assertNotEqual(first['policy_sha256'],second['policy_sha256'])
        self.assertNotEqual(first['schema_template_sha256'],second['schema_template_sha256'])
        self.assertNotEqual(first['system_checkpoint_sha256'],second['system_checkpoint_sha256'])
        with self.assertRaises(ValueError):audit.frozen_role_policies(self.release,'0'*64)
        changed=deepcopy(self.release)
        changed['file_sha256']['cloud/grounded_generation/cached_verifier.py']='0'*64
        with self.assertRaises(ValueError):audit.frozen_role_policies(changed,self.lock)

    def test_changed_full_evidence_prefix_still_proves_role_usage_only(self):
        calls=[self.call(role,'a',created=1200) for role in audit.ROLES]
        calls.extend(self.call(role,'b',read=800) for role in audit.ROLES)
        result=audit.role_cache_usage_proofs(calls,self.policies)
        for role in audit.ROLES:
            self.assertTrue(result[role]['current_role_creation_then_read_usage_proven'])
            self.assertFalse(result[role]['pairs'][0]['exact_full_prefix_same'])
            self.assertFalse(result[role]['provider_usage_identifies_exact_checkpoint'])

    def test_exact_full_prefix_pair_is_reported_only_if_present(self):
        role=audit.ROLES[0]
        result=audit.role_cache_usage_proofs([self.call(role,'a',created=1200),self.call(role,'a',read=800)],self.policies)
        self.assertTrue(result[role]['pairs'][0]['exact_full_prefix_same'])
        self.assertFalse(result[audit.ROLES[1]]['current_role_creation_then_read_usage_proven'])

    def test_other_role_creation_never_proves_current_role_read(self):
        calls=[self.call(audit.ROLES[0],'a',created=1200),self.call(audit.ROLES[1],'a',read=800)]
        self.assertFalse(any(row['current_role_creation_then_read_usage_proven'] for row in audit.role_cache_usage_proofs(calls,self.policies).values()))

    def test_creation_must_precede_read_and_zero_read_is_not_proof(self):
        role=audit.ROLES[0]
        for calls in ([self.call(role,'a',read=800),self.call(role,'a',created=1200)],
                      [self.call(role,'a',created=1200),self.call(role,'b')]):
            self.assertFalse(audit.role_cache_usage_proofs(calls,self.policies)[role]['current_role_creation_then_read_usage_proven'])

    def test_exact_native_enum_and_base_schema_hash_are_recomputed(self):
        ids=['literal_synthetic_source_1','literal_synthetic_source_2']
        attempt={}
        for field,role in (('draft_provider',audit.ROLES[0]),('verification_provider',audit.ROLES[1])):
            schema,citable=native_role_schema(self.policies[role]['schema'],{'evidence':{key:{} for key in ids}},role)
            attempt[field]={'role_schema_template_sha256':self.policies[role]['schema_template_sha256'],
                'native_role_schema_sha256':audit.digest(schema),'citable_evidence_ids_sha256':audit.digest(citable)}
        row={'saved_view':{'runtime_controls':{'source_admission':{'admitted_evidence_ids':ids},'composition':{'attempts':[attempt]}}}}
        self.assertEqual(audit.audit_native_role_schema(row,self.policies),[])
        attempt['draft_provider']['native_role_schema_sha256']='0'*64
        self.assertIn('ACTUAL_NATIVE_ENUM_SCHEMA_CHANGED',audit.audit_native_role_schema(row,self.policies))
        attempt['verification_provider']['role_schema_template_sha256']='0'*64
        self.assertIn('FROZEN_ROLE_SCHEMA_TEMPLATE_CHANGED',audit.audit_native_role_schema(row,self.policies))


if __name__=='__main__':unittest.main()
