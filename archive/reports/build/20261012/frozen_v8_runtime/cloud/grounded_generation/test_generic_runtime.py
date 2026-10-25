"""Generic runtime boundaries using real immutable source chunks and fake generation."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json,unittest,os
from approved_registry import ApprovedEvidenceRegistry
from controller_contracts import Outcome,Fact
from reviewed_controller import append_attempt
from constrained_generator import ValidationFailure
from cloud.grounded_generation.source_authority import SourceAuthority
from cloud.grounded_generation.generic_runtime import Composer,Questions
from cloud.grounded_generation.provider import ProviderFailure
ROOT=Path(__file__).resolve().parents[2]
INDEX=Path(os.environ.get('MOTOMEDIC_TEST_INDEX',str(ROOT/'build/index-bge-final')))
BORE='evidence_13ff401422c8fc0d784d7e92'
LOCATION='evidence_46ea7e82545c259cf4ed23b3'
class ScriptedRetriever:
    def __init__(self,authority,chunks):
        self.root=INDEX;self.authority=authority;self.chosen=chunks
        self.manifest=json.loads((INDEX/'manifest.json').read_text(encoding='utf-8'))
        self.last_cache_trace=None
    def search(self,query,**kwargs):
        result={'manual_checksum':self.authority.checksum,'index_id':self.authority.index_id,
            'hits':[deepcopy(c) for c in self.chosen],'query':query}
        manifest=kwargs.get('dependency_manifest')
        if manifest:
            dep=manifest['steps'][kwargs['step_id']]
            result.update(retrieval_action='CONTINUE_GATES',conflicts=[],source_review_required=False,
                coverage_established=True,attached_evidence_ids=dep['required_evidence_ids'])
        return result
class ScriptedProvider:
    def __init__(self,eid=BORE,text='The listed bore is 84 mm.',failure=None):
        self.eid=eid;self.text=text;self.failure=failure;self.calls=0;self.last_trace=None
    def complete(self,policy,stable,dynamic,schema):
        self.calls+=1;self.stable=stable;self.dynamic=dynamic;self.schema=schema
        self.last_trace={'generation_calls':1,'verifier_calls':0}
        if self.failure:raise ProviderFailure(self.failure)
        return SimpleNamespace(output={'route':'SUPPORTED','step_id':'','clarification_id':'',
            'claims':[{'text':self.text,'role':'FACT','evidence_ids':[self.eid]}]},telemetry=self.last_trace)
    def count(self,body):return 100
class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=ApprovedEvidenceRegistry.load(ROOT,INDEX)
        cls.original_authority=SourceAuthority(cls.original,INDEX)
    def setUp(self):
        self.registry=deepcopy(self.original);self.authority=deepcopy(self.original_authority)
        self.authority.base=self.registry;self.authority.evidence=self.registry.evidence
    def chunk(self,eid):
        return next(c for c in self.authority.chunks.values() if eid in c['evidence_ids'])
    def runtime(self,provider=None,chunks=None):
        p=provider or ScriptedProvider()
        r=ScriptedRetriever(self.authority,chunks or [self.chunk(BORE)])
        q=Questions(self.registry,r,Composer(p),self.authority)
        return q,p,q.new_session()
    def test_unseen_fact_reaches_generation_with_no_authored_step_catalogue(self):
        self.registry.candidate['steps']={}
        q,p,s=self.runtime()
        _,v,_=q.answer(s,'I am curious how wide the cylinder is inside this engine?')
        self.assertEqual(v['response']['type'],'SUPPORTED')
        self.assertEqual(p.calls,1)
        self.assertIn(BORE,p.stable['evidence'])
        self.assertEqual(p.stable['permitted_actions'],{})
        self.assertNotIn('scopes',p.stable)
        self.assertNotIn('scope_ids',p.schema['properties'])
        self.assertFalse(v['response']['semantic_support_proven'])
    def test_mandatory_charger_warnings_and_server_page_survive(self):
        self.registry.candidate['steps']={}
        q,p,s=self.runtime(ScriptedProvider(LOCATION,'The charging port is in the centre of the handlebar.'),[self.chunk(LOCATION)])
        _,v,_=q.answer(s,'Where is the socket for my phone?')
        self.assertEqual(v['response']['type'],'SUPPORTED')
        text=v['response']['natural_language']
        self.assertIn('rain',text)
        self.assertIn('engine is running',text)
        citations=v['response']['cited_pages']
        self.assertTrue(any(c['evidence_id']==LOCATION and c['pdf_page']==64 for c in citations))
        self.assertTrue(all(c['manual_checksum']==self.registry.checksum for c in citations))
    def test_changed_source_is_system_error_without_generation(self):
        q,p,s=self.runtime()
        self.registry.evidence[BORE]['raw_object']['text']='unreviewed replacement'
        _,v,_=q.answer(s,'What is the bore?')
        self.assertEqual(v['response']['type'],'SYSTEM_ERROR');self.assertEqual(p.calls,0)
    def test_invalid_model_citation_withheld(self):
        q,p,s=self.runtime(ScriptedProvider('invented'))
        _,v,_=q.answer(s,'What is the bore?')
        self.assertEqual(v['response']['type'],'SYSTEM_ERROR');self.assertEqual(p.calls,1)
        self.assertNotIn('The listed bore',v['response']['natural_language'])
    def test_provider_and_budget_failure_are_not_unsupported(self):
        for code in ['PROVIDER_HTTP_500','PROVIDER_DAILY_OR_RATE_LIMIT','COMPLETE_CONTEXT_TOKEN_BOUND_NO_TRUNCATION']:
            q,p,s=self.runtime(ScriptedProvider(failure=code))
            _,v,_=q.answer(s,'What is the bore?')
            self.assertEqual(v['response']['type'],'SYSTEM_ERROR')
            self.assertIn(code,v['response']['reason_codes'])
    def test_known_safety_binding_errors_handled_in_answer_and_feedback(self):
        q,p,s=self.runtime()
        def failure(*args):raise ValidationFailure('SOURCE_AUTHORITY_OBJECT_CHANGED')
        q.known_safety=failure
        for method in [q.answer,q.feedback]:
            _,v,_=method(s,'Still happening')
            self.assertEqual(v['response']['type'],'SYSTEM_ERROR')
        self.assertEqual(p.calls,0)
    def test_superseded_unresolved_history_blocks_actions_and_questions_but_keeps_facts(self):
        sid=next(s for s,x in self.registry.candidate['steps'].items() if x['kind']=='ACTION' and self.registry.step_ready(s))
        core=set(self.registry.step(sid).action_evidence_ids)
        action_chunk=next(c for c in self.authority.chunks.values() if core&set(c['evidence_ids']))
        q,p,s=self.runtime(chunks=[self.chunk(BORE),action_chunk])
        s=append_attempt(s,sid,Outcome.ACTION_COMPLETED_UNRESOLVED,'unresolved')
        first=s.attempted_steps[-1].attempt_id
        s=append_attempt(s,sid,Outcome.OBSERVED_NORMAL,'correction',supersedes=first)
        _,v,_=q.answer(s,'Different wording now; what else can I check?')
        self.assertEqual(v['response']['type'],'SUPPORTED')
        self.assertEqual(p.stable['permitted_actions'],{})
        self.assertEqual(p.dynamic['rider_resolvable_clarifications'],{})
        self.assertEqual(len(s.attempted_steps),2)

    def test_corrupted_bound_safety_scope_cannot_silently_disappear(self):
        q,p,s=self.runtime()
        sid=next(s for s,x in self.registry.candidate['steps'].items() if x['kind']=='SAFETY_STOP' and self.registry.step_ready(s))
        s=append_attempt(s,sid,Outcome.OBSERVED_ABNORMAL,'known-observation',condition_id='confirmed-observation',facts=(('rider_observation',Fact(True,'BOOLEAN')),))
        self.registry.candidate['steps'][sid]['claims'][0]['text']+=' unreviewed mutation'
        _,v,_=q.answer(s,'What is the bore?')
        self.assertEqual(v['response']['type'],'SYSTEM_ERROR')
        self.assertEqual(p.calls,0)

    def test_action_only_output_with_unrelated_factual_bundle_does_not_select_empty_facts(self):
        from dataclasses import replace
        from cloud.grounded_generation.runtime import scope_payload
        sid='EXP003:candidate-v3'
        q,p,s=self.runtime()
        s=replace(s,current_symptoms=tuple(self.registry.step(sid).symptom_tags))
        rid=next(r for r in self.registry.step(sid).applicability_rule_ids if self.registry.rule(r).origin=='MANUAL')
        rule=self.registry.rule(rid)
        s=append_attempt(s,sid,Outcome.OBSERVED_NORMAL,'centred',condition_id=rid,facts=((rule.fact_key,Fact(rule.expected_value,rule.predicate_type,rule.unit)),))
        scope=scope_payload(q.controller,s,sid)
        factual=self.authority.assemble(q.retriever.search('Unrelated engine fact'))
        action_claim=next(c for c in self.registry.step(sid).claims if c['response_role']=='ACTION')
        self.assertFalse(set(action_claim['evidence_ids'])&set(factual['evidence']))
        original_complete=p.complete
        def action_complete(*args):
            result=original_complete(*args)
            result.output={'route':'SUPPORTED','step_id':sid,'clarification_id':'','claims':[{'text':action_claim['text'],'role':'ACTION','evidence_ids':action_claim['evidence_ids']}]}
            return result
        p.complete=action_complete
        result=q.controller.response_generator.compose_generic(q.controller,s,factual,[sid],'How do I cancel the turn signal?')
        self.assertEqual(result.type.value,'SUPPORTED')
        self.assertEqual(p.calls,1)
        self.assertEqual(result.suggested_step_id,sid)
        self.assertEqual(q.controller.response_generator.last_admitted['factual'],{})
    def test_outer_evidence_type_corruption_is_system_error_not_source_gap(self):
        q,p,s=self.runtime()
        self.registry.evidence[BORE]['type']='picture'
        _,v,_=q.answer(s,'What is the bore?')
        self.assertEqual(v['response']['type'],'SYSTEM_ERROR')
        self.assertEqual(p.calls,0)
    def test_retrieval_conflict_withholds_generation(self):
        q,p,s=self.runtime()
        original=q.retriever.search
        def conflict(*args,**kwargs):
            bundle=original(*args,**kwargs);bundle['conflicts']=[{'type':'CONTRADICTORY_SOURCE'}]
            return bundle
        q.retriever.search=conflict
        _,v,_=q.answer(s,'What is the bore?')
        self.assertEqual(v['response']['type'],'UNSUPPORTED')
        self.assertEqual(p.calls,0)
