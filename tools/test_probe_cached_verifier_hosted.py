"""Provider-free checks of the hosted cache proof's exact acceptance boundary."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from generation_providers import ProviderFailure
from cloud.grounded_generation.cached_verifier import CONTRACT
from cloud.grounded_generation.verified_qa import VERIFY_SCHEMA,VERIFY_POLICY
from tools.probe_cached_verifier_hosted import run_probe, ping


class Admission:
    def __init__(self): self.calls=[]
    def begin_turn(self,operation_id,attempts):self.calls.append(('begin',operation_id,attempts))
    def end_turn(self):self.calls.append(('end',))


class Provider:
    def __init__(self):
        self.calls=[];self.last_trace=None;self.lifetime=[];self.hit=True;self.bad_binding=False
    def context(self,*args):
        self.calls.append(('context',));return {},1000
    def begin_turn(self):self.lifetime.append('begin')
    def end_turn(self):self.lifetime.append('end')
    def complete(self,policy,stable,dynamic,schema):
        assert policy==VERIFY_POLICY and schema==VERIFY_SCHEMA
        self.calls.append(('generation',deepcopy(stable),deepcopy(dynamic)))
        number=sum(row[0]=='generation' for row in self.calls)
        self.last_trace={'model':CONTRACT['model'],'generation_calls':1,'role':'semantic_verifier',
            'cached_prefix_sha256':'fixed-engineering-prefix',
            'cache_creation_input_tokens':900 if number==1 else 0,
            'cache_read_input_tokens':900 if number==2 and self.hit else 0,
            'estimated_cost_usd':.0001}
        output={'binding_sha256':'wrong' if self.bad_binding else dynamic['binding_sha256'],
            'decision':'SHOW_FALLBACK','question_coverage':'UNANSWERABLE',
            'per_claim_support':[{'claim_id':c['claim_id'],'supported':True,
                'supported_evidence_ids':[],'reason':'Engineering fixture only.'}
                for c in dynamic['complete_proposed_response']['claims']],
            'omissions':[],'conflicts':[],'coverage_limitation_clear':True,
            'clarification_is_rider_resolvable':False,'release_eligible':False,
            'correction_possible':False}
        return SimpleNamespace(output=output,telemetry=deepcopy(self.last_trace))


class Tests(unittest.TestCase):
    def setUp(self):
        self.provider=Provider();self.admission=Admission()
        self.stable={'full_evidence_payload_sha256':'synthetic-evidence-sha',
            'source_authority_lock':'synthetic-source-lock','manual_checksum':'synthetic-manual',
            'index_id':'synthetic-index','evidence':{'synthetic-id':'DO NOT LOG SOURCE BODY'}}
    def run_probe(self):return run_probe(self.provider,self.admission,self.stable,'synthetic-operation')
    def test_both_calls_exact_schema_bindings_and_cache_hit_required(self):
        receipt=self.run_probe()
        self.assertEqual(receipt['status'],'PASS');self.assertTrue(receipt['cache_hit_proven'])
        self.assertEqual(receipt['provider_calls'],2)
        self.assertEqual(self.admission.calls[0][2],8)
        self.assertEqual(self.admission.calls[-1],('end',))
        self.assertEqual(self.provider.lifetime,['begin','end'])
        calls=[c for c in self.provider.calls if c[0]=='generation']
        self.assertEqual(calls[0][1],calls[1][1])
        self.assertNotEqual(calls[0][2]['binding_sha256'],calls[1][2]['binding_sha256'])
        self.assertFalse(receipt['quality_acceptance']);self.assertFalse(receipt['rider_answer_released'])
        self.assertNotIn('DO NOT LOG SOURCE BODY',str(receipt))
        self.assertNotIn('Engineering fixture only.',str(receipt))
    def test_explicit_cache_configuration_without_actual_read_is_not_success(self):
        self.provider.hit=False
        receipt=self.run_probe()
        self.assertEqual(receipt['status'],'FAIL')
        self.assertEqual(receipt['failure_code'],'CAPABILITY_PROBE_CACHE_HIT_NOT_DEMONSTRATED')
        self.assertFalse(receipt['cache_hit_proven'])
    def test_verdict_wrong_binding_rejected_before_second_call(self):
        self.provider.bad_binding=True
        receipt=self.run_probe()
        self.assertEqual(receipt['status'],'FAIL');self.assertEqual(receipt['failure_code'],'VERIFIER_BINDING')
        self.assertEqual(receipt['provider_calls'],1)
        self.assertEqual(len([c for c in self.provider.calls if c[0]=='generation']),1)
    def test_uncertain_call_count_and_cleanup_preserved(self):
        def uncertain(*args):
            self.provider.last_trace={'generation_calls':1}
            raise ProviderFailure('ENGINEERING_UNCERTAIN_CALL')
        self.provider.complete=uncertain
        receipt=self.run_probe()
        self.assertEqual(receipt['provider_calls'],1)
        self.assertEqual(receipt['status'],'FAIL')
        self.assertEqual(self.provider.lifetime,['begin','end'])
        self.assertEqual(self.admission.calls[-1],('end',))
    def test_neutral_ping_contains_no_technical_claims(self):
        value=ping(self.stable,'synthetic-operation',1)
        self.assertEqual(value['complete_proposed_response']['route'],'UNSUPPORTED')
        self.assertTrue(all(c['role']=='LIMITATION' and not c['evidence_ids']
            for c in value['complete_proposed_response']['claims']))


if __name__=='__main__':unittest.main()
