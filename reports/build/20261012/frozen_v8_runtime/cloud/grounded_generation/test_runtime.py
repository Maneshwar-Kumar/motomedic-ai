"""Actual source authority; synthetic retrieval/provider boundary regressions."""
from copy import deepcopy
from dataclasses import replace
import unittest
from flask import Flask
from approved_registry import ApprovedEvidenceRegistry
from test_approved_integration import ROOT,INDEX,ScriptedRetrieval
from cloud.grounded_generation.runtime import Questions,Composer,check_output
from cloud.grounded_generation.provider import ProviderFailure
from generation_providers import ProviderResult
from controller_contracts import Outcome
from reviewed_controller import append_attempt

class Retrieval(ScriptedRetrieval):
    def __init__(self,r): super().__init__(r);self.r=r;self.missing=False;self.rids=['GEN007']
    def search(self,query,**kwargs):
        if kwargs.get('step_id'):return super().search(query,**kwargs)
        return {'manual_checksum':self.r.checksum,'index_id':self.r.index_id,
            'hits':[{'evidence_ids':list(self.r.step(rid+':candidate-v3').action_evidence_ids)} for rid in self.rids]}

class Provider:
    def __init__(self):self.calls=0;self.failure=False;self.invalid=False;self.last_trace=None
    def count(self,body):return 100
    def context(self,*args):return {},100
    def complete(self,policy,stable,dynamic,schema):
        self.calls+=1
        if self.failure:raise ProviderFailure('PROVIDER_TRANSPORT_OR_SCHEMA_FAILURE')
        sid=next(sid for sid,s in stable['scopes'].items() if s['kind']=='LOOKUP')
        ids=stable['scopes'][sid]['required_evidence_ids']
        output={'route':'SUPPORTED','scope_ids':[sid],'step_id':'','clarification_id':'',
            'claims':[{'text':'The selected motorcycle is compatible with E20 fuel.',
                'role':'FACT','evidence_ids':['invented'] if self.invalid else [ids[0]]}]}
        return ProviderResult(output,100,40,None,{'generation_calls':1,'verifier_calls':0})

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=ApprovedEvidenceRegistry.load(ROOT,INDEX)
    def setUp(self):
        self.provider=Provider();self.retriever=Retrieval(self.r)
        self.q=Questions(self.r,self.retriever,Composer(self.provider))
        self.app=Flask(__name__)
    def answer(self,query='An unseen wording about ethanol compatibility, please.'):
        with self.app.test_request_context():return self.q.answer(self.q.new_session(),query)
    def test_unseen_question_reaches_generator_and_new_wording_survives(self):
        _,view,_=self.answer();self.assertEqual(view['response']['type'],'SUPPORTED')
        self.assertEqual(self.provider.calls,1);self.assertEqual(view['provider_calls'],1)
        self.assertTrue(view['response']['cited_pages']);self.assertFalse(view['response']['semantic_support_proven'])
    def test_invalid_citation_withheld(self):
        self.provider.invalid=True;_,view,_=self.answer()
        self.assertEqual(view['response']['type'],'SYSTEM_ERROR');self.assertFalse(view['response']['technical_content'])
    def test_provider_outage_distinct_from_source_gap(self):
        self.provider.failure=True;_,view,_=self.answer()
        self.assertEqual(view['response']['type'],'SYSTEM_ERROR')
    def test_complete_bundle_missing_no_provider(self):
        self.retriever.missing=True;_,view,_=self.answer()
        self.assertEqual(view['response']['type'],'UNSUPPORTED');self.assertEqual(self.provider.calls,0)
    def test_reviewed_exact_cache_is_not_admission(self):
        from cloud.grounded_generation.response_cache import ReviewedResponses
        cache=ReviewedResponses(self.r,self.q.controller.response_generator.config.lock)
        query=next(q for q,rows in cache.entries.items() if any(sid=='GEN007:candidate-v3' for sid,_ in rows))
        with self.app.test_request_context(environ_overrides={'arm_a_cache_enabled':True}):
            _,view,_=self.q.answer(self.q.new_session(),query)
            self.assertEqual(view['response']['type'],'SUPPORTED');self.assertEqual(self.provider.calls,0)
            self.assertEqual(view['runtime_controls']['composition']['response_cache'],'EXACT_REVIEWED_HIT_REVALIDATED')
            self.q.answer(self.q.new_session(),'A new phrasing about fuel compatibility?')
            self.assertEqual(self.provider.calls,1)
    def test_typed_unresolved_cannot_become_normal_or_hit_initial_cache(self):
        from cloud.grounded_generation.response_cache import ReviewedResponses
        s=append_attempt(self.q.new_session(),'EXP003:candidate-v3',Outcome.ACTION_COMPLETED_UNRESOLVED,'test-turn')
        self.assertEqual(s.active_attempts()[0].outcome_enum,Outcome.ACTION_COMPLETED_UNRESOLVED)
        self.assertEqual(s.known_observations(),{})
        self.assertIsNone(ReviewedResponses(self.r,self.q.controller.response_generator.config.lock).get(
            'Can I use E20 petrol?',s,{},s.generation_lock))
    def test_permitted_step_schema_bound(self):
        scopes={'s':{'kind':'LOOKUP','required_evidence_ids':['e'],'permitted_action_evidence_ids':[]}}
        draft={'route':'SUPPORTED','scope_ids':['s'],'step_id':'','clarification_id':'',
            'claims':[{'text':'Do a repair.','role':'ACTION','evidence_ids':['e']}]}
        with self.assertRaisesRegex(Exception,'UNPERMITTED_STEP'):check_output(draft,scopes,{})
    def test_unadmitted_clarification_rejected(self):
        with self.assertRaisesRegex(Exception,'CLARIFICATION'):
            check_output({'route':'AMBIGUOUS','scope_ids':[],'step_id':'','clarification_id':'invented','claims':[]},{},{})
    def test_resolved_status_not_reopened_by_question(self):
        s=replace(self.q.new_session(),status='CUSTOMER_REPORTED_RESOLVED')
        with self.app.test_request_context():s,_,_=self.q.answer(s,'fuel question')
        self.assertEqual(s.status,'CUSTOMER_REPORTED_RESOLVED')
    def test_known_safety_advances_version_without_retrieval_or_provider(self):
        def known(session):
            return session,self.q.controller.response('SAFETY_STOP','Stop and seek authorised service support.',session)
        self.q.known_safety=known
        def outage(*args,**kwargs):raise AssertionError('Known hazard must precede retrieval')
        self.retriever.search=outage
        session=replace(self.q.new_session(),version=7)
        with self.app.test_request_context():updated,view,_=self.q.answer(session,'another question')
        self.assertEqual(updated.version,8);self.assertEqual(view['version'],8)
        self.assertEqual(view['response']['type'],'SAFETY_STOP');self.assertEqual(self.provider.calls,0)
    def test_policy_only_scope_cannot_be_known_hazard_from_retrieval_tags(self):
        safety=next(sid for sid,raw in self.r.candidate['steps'].items() if raw['kind']=='SAFETY_STOP')
        session=replace(self.q.new_session(),current_symptoms=tuple(self.r.step(safety).symptom_tags))
        self.assertIsNone(self.q.known_safety(session))

if __name__=='__main__':unittest.main()
