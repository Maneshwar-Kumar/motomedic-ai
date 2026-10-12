"""Index-free synthetic model-role/count/contract checks, no provider calls."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from evidence_registry import content_hash
from generation_providers import ProviderFailure
from cloud.grounded_generation.role_router import (RoleRouter,GemmaRole,ROUTING_CONTRACT,
    validate_role_plan_binding)
from cloud.grounded_generation.role_contracts import (GEMMA_DRAFT,GEMMA_VERIFIER,
    HAIKU_DRAFT,HAIKU_VERIFIER,haiku_maximum_nanodollars,haiku_actual_cost)
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
    value.update(runtime_contract={'runtime_lock':'1'*64,'draft_model_contract':GEMMA_DRAFT,
        'verifier_contract':HAIKU_VERIFIER},manual_checksum='2'*64,index_id='synthetic-index',
        source_authority_lock='3'*64,full_evidence_payload_sha256='4'*64,
        evidence={'synthetic':{'text':'Complete engineering fixture source.'}},
        required_source_display=[],source_gaps=[])
    return value


class Tests(unittest.TestCase):
    def router(self,count=100):
        g,h,gv,hv=(CountRole(GEMMA_DRAFT,count),CountRole(HAIKU_DRAFT,200),
                   CountRole(GEMMA_VERIFIER,300),CountRole(HAIKU_VERIFIER,400))
        a=Admission();return RoleRouter(g,h,gv,hv,a),a
    def dynamic(self):return {'question':'Unseen engineering question','history':{'operation_id':'op','conversation':[]}}
    def admitted(self):return {'required_display':[],'citation_mapping':[],
        'payload_sha256':'4'*64,'authority_lock':'3'*64}
    def test_threshold_is_selection_and_preserves_complete_sources(self):
        for count,expected in [(8192,'GEMMA_DRAFT_HAIKU_VERIFY'),(8193,'HAIKU_DRAFT_GEMMA_VERIFY')]:
            r,a=self.router(count);source=stable();before=deepcopy(source);p,chosen=r.select(source,self.dynamic())
            self.assertEqual(p.name,expected);self.assertEqual(source,before)
            for key in set(STABLE_FIELDS)-{'runtime_contract'}:self.assertEqual(chosen[key],source[key])
            self.assertNotEqual(p.draft.contract['model'],p.verifier.contract['model'])
            self.assertEqual(chosen['runtime_contract']['draft_model_contract'],p.draft.contract)
            self.assertEqual(chosen['runtime_contract']['verifier_contract'],p.verifier.contract)
            self.assertFalse(a.calls)
    def test_global_config_lock_does_not_depend_on_selected_role(self):
        config=Config(verifier_contract=HAIKU_VERIFIER,routing_contract=ROUTING_CONTRACT);lock=config.lock
        r,_=self.router(100);r.select(stable(),self.dynamic());r.gemma_draft.count_value=9000;r.select(stable(),self.dynamic())
        self.assertEqual(config.lock,lock)
    def test_full_six_slot_plan_covers_retry_correction_and_other_model(self):
        for count,models in [(100,[GEMMA_DRAFT['model'],GEMMA_DRAFT['model'],HAIKU_DRAFT['model'],GEMMA_DRAFT['model'],GEMMA_DRAFT['model'],HAIKU_DRAFT['model']]),
                            (9000,[HAIKU_DRAFT['model'],GEMMA_DRAFT['model'],GEMMA_DRAFT['model'],HAIKU_DRAFT['model'],GEMMA_DRAFT['model'],GEMMA_DRAFT['model']])]:
            r,a=self.router(count);p,s=r.select(stable(),self.dynamic());session=SimpleNamespace(status='CONFIRMED')
            forecast=r.reservation_plan(p,s,self.dynamic(),self.admitted(),session)
            self.assertEqual([x['model'] for x in forecast['slots']],models)
            self.assertEqual(len(forecast['slots']),6)
            for row in forecast['slots']:
                if row['model']==HAIKU_DRAFT['model']:self.assertEqual(row['maximum_nanodollars'],haiku_maximum_nanodollars(row['input_tokens']))
            self.assertFalse(a.calls)
            receipt=r.begin('operation',p,s,self.dynamic(),self.admitted(),session)
            self.assertEqual(len(a.calls[0][1]['slots']),3);self.assertEqual(p.draft.expected,p.initial_request_sha256)
            self.assertTrue(receipt['model_routing']['forecast_is_not_unknown_final_answer_guarantee'])
            r.begin_correction('operation',p,s,self.dynamic(),self.admitted(),session,
                {'rejected_response':{'text':'private rejected fixture'},'verdict':{'correction_possible':True}},
                {'binding':'engineering fixture'})
            self.assertEqual(len(a.calls[1][1]['slots']),3)
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
        for key,value in [('gemma_routing_input_tokens',True),('gemma_routing_input_tokens',100),
                          ('stable_context_sha256','bad'),('verifier_contract_sha256','0'*64)]:
            tampered=p.binding();tampered[key]=value
            with self.assertRaises(ProviderFailure):validate_role_plan_binding(tampered)
        tampered=p.binding();tampered['extra']='unknown'
        with self.assertRaises(ProviderFailure):validate_role_plan_binding(tampered)
    def test_counter_failure_never_selects_other_model(self):
        r,a=self.router()
        def fail(*args,**kwargs):raise ProviderFailure('PROVIDER_HTTP_429')
        r.gemma_draft.context=fail
        with self.assertRaisesRegex(ProviderFailure,'HTTP_429'):r.select(stable(),self.dynamic())
        self.assertFalse(r.haiku_draft.calls);self.assertFalse(a.calls)
    def test_haiku_prices_use_full_input_including_cache_at_tier_boundary(self):
        self.assertEqual(haiku_maximum_nanodollars(100000),13400000)
        self.assertEqual(haiku_maximum_nanodollars(100001),67000625)
        self.assertAlmostEqual(haiku_actual_cost(1,0,100000,100),(.5+100000*.05+100*2.5)/1000000)
        self.assertGreater(haiku_maximum_nanodollars(100001),4*haiku_maximum_nanodollars(100000))
    def test_gemma_native_window_and_actual_project_quota_are_separate(self):
        calls=[]
        def transport(method,path,body,key):calls.append(path);return {'totalTokens':20000}
        role=GemmaRole(lambda *x:None,role='private_draft',transport=transport,key='synthetic')
        self.assertEqual(role.context(DRAFT_POLICY,stable(),{},DRAFT_SCHEMA,_sizing=True)[1],20000)
        with self.assertRaisesRegex(ProviderFailure,'PROJECT_INPUT_TPM_LIMIT'):
            role.context(DRAFT_POLICY,stable(),{},DRAFT_SCHEMA)
        self.assertTrue(all(path.endswith(':countTokens') for path in calls))
        with self.assertRaisesRegex(ProviderFailure,'ROLE_MISMATCH'):
            role.context(VERIFY_POLICY,stable(),{},VERIFY_SCHEMA)
    def test_routing_counter_can_exceed_gemma_window_and_select_haiku(self):
        calls=[]
        def transport(method,path,body,key):
            calls.append(path);return {'totalTokens':300000}
        r,a=self.router()
        r.gemma_draft=GemmaRole(lambda *x:None,role='private_draft',transport=transport,key='synthetic')
        plan,chosen=r.select(stable(),self.dynamic())
        self.assertEqual(plan.name,'HAIKU_DRAFT_GEMMA_VERIFY')
        self.assertEqual(plan.routing_count,300000)
        self.assertEqual(plan.initial_input_tokens,200)
        self.assertEqual(chosen['evidence'],stable()['evidence'])
        self.assertFalse(a.calls)
        self.assertTrue(all(path.endswith(':countTokens') for path in calls))
    def test_unknown_worst_verifier_scaffold_is_diagnostic_and_base_is_gated(self):
        r,a=self.router(9000)
        calls=[]
        def transport(method,path,body,key):
            calls.append(path);return {'totalTokens':20000 if len(calls)%2 else 15000}
        r.gemma_verifier=GemmaRole(lambda *x:None,role='semantic_verifier',transport=transport,key='synthetic')
        plan,chosen=r.select(stable(),self.dynamic())
        forecast=r.reservation_plan(plan,chosen,self.dynamic(),self.admitted(),SimpleNamespace(status='CONFIRMED'))
        self.assertEqual(forecast['fixed_verifier_native_tokens'],20000)
        self.assertEqual(forecast['known_verifier_prefix_native_tokens'],15000)
        self.assertEqual(forecast['slots'][1]['input_tokens'],16000)
        self.assertFalse(a.calls)
        r.gemma_verifier.transport=lambda *x:{'totalTokens':16001}
        with self.assertRaisesRegex(ProviderFailure,'PROJECT_INPUT_TPM_LIMIT'):
            r.reservation_plan(plan,chosen,self.dynamic(),self.admitted(),SimpleNamespace(status='CONFIRMED'))
        self.assertFalse(a.calls)
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
