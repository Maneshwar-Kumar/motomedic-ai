"""Index-free synthetic model-role/count/contract checks, no provider calls."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from evidence_registry import content_hash
from generation_providers import ProviderFailure
from cloud.grounded_generation.role_router import (RoleRouter,ROUTING_CONTRACT,
    validate_role_plan_binding)
from cloud.grounded_generation.role_contracts import (HAIKU_DRAFT,HAIKU_VERIFIER,
    haiku_maximum_nanodollars,haiku_actual_cost)
from cloud.grounded_generation.verified_qa import Config,DRAFT_POLICY,DRAFT_SCHEMA,VERIFY_POLICY,VERIFY_SCHEMA
from cloud.grounded_generation.cached_verifier import CachedDraft,CachedVerifier,STABLE_FIELDS


class CountRole:
    def __init__(self,contract,count):
        self.contract=deepcopy(contract);self.count_value=count;self.calls=[];self.expected=None
    def context(self,policy,stable,dynamic,schema,**kwargs):
        self.calls.append((policy,deepcopy(stable),deepcopy(dynamic),schema,kwargs))
        return {'policy':policy,'stable':stable,'dynamic':dynamic,'schema':schema},self.count_value
    def expect_initial_context(self,value):self.expected=value


class Admission:
    def __init__(self):self.calls=[];self.ended=0
    def begin_turn(self,operation_id,*,plan):
        self.calls.append((operation_id,deepcopy(plan)));return {'reserved_attempts':len(plan['slots'])}
    def end_turn(self):self.ended+=1
    def reserve_correction(self,operation_id,*,plan):
        self.calls.append((operation_id,deepcopy(plan)));return {'reserved_attempts':len(plan['slots'])}


def stable():
    value={k:{} for k in STABLE_FIELDS}
    value.update(runtime_contract={'runtime_lock':'1'*64,'draft_model_contract':HAIKU_DRAFT,
        'verifier_contract':HAIKU_VERIFIER},manual_checksum='2'*64,index_id='synthetic-index',
        source_authority_lock='3'*64,full_evidence_payload_sha256='4'*64,
        source_projection='plain-json-literal-source-objects-v3',
        evidence={'synthetic':{'text':'Complete engineering fixture source.'}},
        required_source_display=[],source_gaps=[])
    return value


class Tests(unittest.TestCase):
    def router(self,count=100):
        draft,verifier=CountRole(HAIKU_DRAFT,count),CountRole(HAIKU_VERIFIER,400)
        a=Admission();return RoleRouter(draft,verifier,a),a
    def dynamic(self):return {'question':'Unseen engineering question','history':{'operation_id':'op','conversation':[]}}
    def admitted(self):return {'required_display':[],'citation_mapping':[],
        'payload_sha256':'4'*64,'authority_lock':'3'*64}
    def test_fixed_roles_preserve_complete_sources_beyond_old_cap(self):
        for count,expected in [(8192,'HAIKU_DRAFT_HAIKU_VERIFY'),(8193,'HAIKU_DRAFT_HAIKU_VERIFY'),(300000,'HAIKU_DRAFT_HAIKU_VERIFY')]:
            r,a=self.router(count);source=stable();before=deepcopy(source);p,chosen=r.select(source,self.dynamic())
            self.assertEqual(p.name,expected);self.assertEqual(source,before)
            for key in set(STABLE_FIELDS)-{'runtime_contract'}:self.assertEqual(chosen[key],source[key])
            self.assertEqual(p.draft.contract['model'],p.verifier.contract['model'])
            self.assertIsNot(p.draft,p.verifier)
            self.assertNotEqual(p.draft.contract['role'],p.verifier.contract['role'])
            self.assertEqual(chosen['runtime_contract']['draft_model_contract'],p.draft.contract)
            self.assertEqual(chosen['runtime_contract']['verifier_contract'],p.verifier.contract)
            self.assertFalse(a.calls)
    def test_global_config_lock_does_not_depend_on_selected_role(self):
        config=Config(verifier_contract=HAIKU_VERIFIER,routing_contract=ROUTING_CONTRACT);lock=config.lock
        r,_=self.router(100);r.select(stable(),self.dynamic());r.haiku_draft.count_value=9000;r.select(stable(),self.dynamic())
        self.assertEqual(config.lock,lock)
    def test_four_slot_forecast_reserves_two_calls_per_phase_without_retry(self):
        r,a=self.router(20000);p,s=r.select(stable(),self.dynamic());session=SimpleNamespace(status='CONFIRMED')
        forecast=r.reservation_plan(p,s,self.dynamic(),self.admitted(),session)
        self.assertEqual([x['stage'] for x in forecast['slots']],['draft','verify','correction','reverify'])
        self.assertEqual([x['model'] for x in forecast['slots']],[HAIKU_DRAFT['model']]*4)
        self.assertEqual([x['attempt'] for x in forecast['slots']],[1]*4)
        self.assertEqual(forecast['initial_haiku_counter_headroom_tokens'],512)
        self.assertEqual(forecast['initial_primary_counter_headroom_tokens'],0)
        for row in forecast['slots']:
            self.assertEqual(row['maximum_nanodollars'],haiku_maximum_nanodollars(row['input_tokens']))
        self.assertFalse(a.calls)
        receipt=r.begin('operation',p,s,self.dynamic(),self.admitted(),session)
        self.assertEqual(len(a.calls[0][1]['slots']),2);self.assertEqual(p.draft.expected,p.initial_request_sha256)
        self.assertTrue(receipt['model_routing']['forecast_is_not_unknown_final_answer_guarantee'])
        r.begin_correction('operation',p,s,self.dynamic(),self.admitted(),session,
            {'rejected_response':{'text':'private rejected fixture'},'verdict':{'correction_possible':True}},
            {'binding':'engineering fixture'})
        self.assertEqual(len(a.calls[1][1]['slots']),2)
        self.assertTrue(all(x['stage'] in ('correction','reverify') for x in a.calls[1][1]['slots']))
        r.end();self.assertEqual(a.ended,1);self.assertIsNone(p.draft.expected)
    def test_stable_contract_or_plan_mutation_rejects_before_admission(self):
        r,a=self.router(9000);p,s=r.select(stable(),self.dynamic());s['evidence']['synthetic']['text']='changed'
        with self.assertRaisesRegex(ProviderFailure,'STABLE_CONTEXT_CHANGED'):
            r.begin('op',p,s,self.dynamic(),self.admitted(),SimpleNamespace(status='CONFIRMED'))
        self.assertFalse(a.calls)
        p.verifier.contract['model']='unknown'
        with self.assertRaisesRegex(ProviderFailure,'ROLE_BINDING_CHANGED'):r.validate(p)
    def test_plan_strict_keys_hashes_threshold_and_contracts(self):
        r,_=self.router(9000);p,_=r.select(stable(),self.dynamic());self.assertEqual(validate_role_plan_binding(p.binding())['draft'],HAIKU_DRAFT)
        for key,value in [('primary_input_tokens_counted',True),('primary_input_tokens_counted',100),
                          ('stable_context_sha256','bad'),('verifier_contract_sha256','0'*64)]:
            tampered=p.binding();tampered[key]=value
            with self.assertRaises(ProviderFailure):validate_role_plan_binding(tampered)
        tampered=p.binding();tampered['extra']='unknown'
        with self.assertRaises(ProviderFailure):validate_role_plan_binding(tampered)
    def test_counter_failure_never_selects_other_model(self):
        r,a=self.router()
        def fail(*args,**kwargs):raise ProviderFailure('PROVIDER_HTTP_429')
        r.haiku_draft.context=fail
        with self.assertRaisesRegex(ProviderFailure,'HTTP_429'):r.select(stable(),self.dynamic())
        self.assertFalse(r.haiku_verifier.calls);self.assertFalse(a.calls)
    def test_haiku_prices_use_full_input_including_cache_at_tier_boundary(self):
        self.assertEqual(haiku_maximum_nanodollars(100000),13400000)
        self.assertEqual(haiku_maximum_nanodollars(100001),67000625)
        self.assertAlmostEqual(haiku_actual_cost(1,0,100000,100),(.5+100000*.05+100*2.5)/1000000)
        self.assertGreater(haiku_maximum_nanodollars(100001),4*haiku_maximum_nanodollars(100000))
    def test_forecast_must_fit_native_window_without_discarding_source(self):
        r,a=self.router(9000);plan,chosen=r.select(stable(),self.dynamic())
        r.haiku_verifier.count_value=998200
        with self.assertRaisesRegex(ProviderFailure,'FUTURE_FORECAST_EXCEEDS_NATIVE_WINDOW'):
            r.reservation_plan(plan,chosen,self.dynamic(),self.admitted(),SimpleNamespace(status='CONFIRMED'))
        self.assertFalse(a.calls)
        self.assertEqual(chosen['evidence'],stable()['evidence'])
    def test_shared_role_instance_or_swapped_contract_is_rejected(self):
        draft=CountRole(HAIKU_DRAFT,100)
        with self.assertRaisesRegex(ProviderFailure,'MODEL_ROLE_CONTRACT_CHANGED'):
            RoleRouter(draft,draft,Admission())
        with self.assertRaisesRegex(ProviderFailure,'MODEL_ROLE_CONTRACT_CHANGED'):
            RoleRouter(CountRole(HAIKU_VERIFIER,100),CountRole(HAIKU_DRAFT,100),Admission())
    def test_both_haiku_roles_keep_question_history_outside_cache(self):
        calls=[]
        def transport(method,path,body,key):calls.append((path,deepcopy(body)));return {'input_tokens':20000}
        for cls,policy,schema,expected in [(CachedDraft,DRAFT_POLICY,DRAFT_SCHEMA,'private_draft'),
                                            (CachedVerifier,VERIFY_POLICY,VERIFY_SCHEMA,'semantic_verifier')]:
            role=cls(lambda *x:None,transport=transport,key='synthetic',pre_reserved=True)
            body,n=role.context(policy,stable(),{'question':'private question','history':['private history']},schema)
            self.assertEqual(n,20000);self.assertEqual(role.last_trace['role'],expected)
            prefix,dynamic=body['messages'][0]['content'];self.assertNotIn('private question',prefix['text'])
            self.assertNotIn('private history',prefix['text']);self.assertIn('cache_control',prefix)
            self.assertNotIn('cache_control',dynamic)


if __name__=='__main__':unittest.main()
