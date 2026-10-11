"""Private draft and separate exact-final semantic-verifier boundary tests."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from cloud.grounded_generation.test_generic_runtime import Tests as SourceTests,ScriptedRetriever,BORE,LOCATION
from cloud.grounded_generation.verified_qa import Composer,DRAFT_SCHEMA,VERIFY_SCHEMA,saved_view
from cloud.grounded_generation.open_questions import Questions
from cloud.grounded_generation.provider import ProviderFailure
from constrained_generator import ValidationFailure

def draft(eid=BORE,text='The listed bore is 84 mm.',role='FACT',route='SUPPORTED',coverage='COMPLETE'):
    return {'route':route,'coverage':coverage,'claims':[{'text':text,'role':role,'evidence_ids':[eid] if eid else []}],'unanswered_parts':[],'clarification_question':'','rider_resolvable':False}
class Provider:
    cache_capability='unsupported'
    def __init__(self,drafts=None,verifier=None):self.drafts=drafts or [draft()];self.verifier=verifier;self.calls=[];self.last_trace=None
    def count(self,body):return 100
    def complete(self,policy,stable,dynamic,schema):
        self.calls.append((schema,deepcopy(stable),deepcopy(dynamic)))
        self.last_trace={'generation_calls':1}
        if schema==DRAFT_SCHEMA:
            output=deepcopy(self.drafts[min(sum(c[0]==DRAFT_SCHEMA for c in self.calls)-1,len(self.drafts)-1)])
        else:
            final=dynamic['complete_proposed_response'];route=final['route']
            output={'binding_sha256':dynamic['binding_sha256'],'decision':{'SUPPORTED':('RELEASE_PARTIAL' if dynamic['declared_question_coverage']=='PARTIAL' else 'RELEASE_COMPLETE'),'UNSUPPORTED':'SHOW_FALLBACK','AMBIGUOUS':'RELEASE_CLARIFICATION','SAFETY_STOP':'RELEASE_SAFETY_STOP'}[route],'question_coverage':{'SUPPORTED':dynamic['declared_question_coverage'],'UNSUPPORTED':'UNANSWERABLE','AMBIGUOUS':'NEEDS_CLARIFICATION','SAFETY_STOP':'COMPLETE'}[route],'per_claim_support':[{'claim_id':c['claim_id'],'supported':True,'supported_evidence_ids':c['evidence_ids'],'reason':'Supported by supplied exact source or operational metadata.'} for c in final['claims']],'omissions':[],'conflicts':[],'coverage_limitation_clear':True,'clarification_is_rider_resolvable':route=='AMBIGUOUS','release_eligible':route!='UNSUPPORTED','correction_possible':False}
            if self.verifier:output=self.verifier(output,dynamic,self)
        return SimpleNamespace(output=output,telemetry=self.last_trace)
class VerifiedTests(unittest.TestCase):
    setUpClass=classmethod(SourceTests.setUpClass.__func__)
    setUp=SourceTests.setUp
    chunk=SourceTests.chunk
    def setup_runtime(self,p=None,eid=BORE):
        p=p or Provider();composer=Composer(p,self.authority)
        q=Questions(self.registry,ScriptedRetriever(self.authority,[self.chunk(eid)]),composer,self.authority)
        return q,p,composer,q.new_session()
    def test_unseen_fact_without_authored_step_and_exact_final_delivery(self):
        self.registry.candidate['steps']={}
        q,p,c,s=self.setup_runtime();stages=[]
        s,v,_=q.answer(s,'How wide is the bore?',progress=stages.append,operation_id='op1')
        self.assertEqual(v['response']['type'],'SUPPORTED');self.assertEqual(stages,['retrieving','drafting','verifying'])
        self.assertEqual(len(p.calls),2);self.assertEqual(c.last_trace['provider_calls'],2)
        self.assertEqual(v['response']['natural_language'],p.calls[1][2]['complete_proposed_response']['text'])
        self.assertEqual(c.last_admitted['binding']['operation_id'],'op1')
        self.assertFalse(v['response']['semantic_support_proven'])
        self.assertNotIn('The listed bore',str(c.last_trace))
    def test_registered_action_not_required_for_procedure_wording(self):
        sid=next(k for k,v in self.registry.candidate['steps'].items() if v['kind']=='ACTION' and self.registry.step_ready(k))
        claim=next(c for c in self.registry.step(sid).claims if c['response_role']=='ACTION')
        eid=claim['evidence_ids'][0]
        self.registry.candidate['steps']={}
        q,p,c,s=self.setup_runtime(Provider([draft(eid,claim['text'],'PROCEDURE_STEP')]),eid)
        _,v,_=q.answer(s,'What does the source say?')
        self.assertEqual(v['response']['type'],'SUPPORTED')
        self.assertNotIn('permitted_actions',p.calls[0][1])
    def test_mandatory_warning_is_finalized_before_verifier(self):
        q,p,c,s=self.setup_runtime(Provider([draft(LOCATION,'The socket is in the centre of the handlebar.')]),LOCATION)
        _,v,_=q.answer(s,'Where is my socket?')
        final=p.calls[1][2]['complete_proposed_response']
        self.assertIn('rain',final['text']);self.assertIn('engine is running',final['text'])
        self.assertEqual(final['text'],v['response']['natural_language'])
        self.assertTrue(any(x['origin']=='SOURCE_REQUIRED_DISPLAY' for x in final['claims']))
    def test_rejection_never_leaks_private_draft(self):
        def reject(o,*args):o.update(decision='SHOW_FALLBACK',release_eligible=False,question_coverage='IRRELEVANT');return o
        q,p,c,s=self.setup_runtime(Provider([draft(text='PRIVATE WRONG DRAFT')],reject))
        _,v,_=q.answer(s,'Actual query')
        self.assertEqual(v['response']['type'],'UNSUPPORTED');self.assertIsNone(c.last_admitted)
        self.assertNotIn('PRIVATE WRONG',str(v));self.assertNotIn('PRIVATE WRONG',str(c.last_trace))
    def test_one_correction_and_reverification_bound(self):
        def reject(o,d,p):o.update(decision='SHOW_FALLBACK',release_eligible=False,correction_possible=True);return o
        q,p,c,s=self.setup_runtime(Provider([draft(),draft(text='Second private draft')],reject))
        _,v,_=q.answer(s,'Actual query')
        self.assertEqual(len(p.calls),4);self.assertEqual(c.last_trace['corrections'],1)
        self.assertIsNone(c.last_admitted);self.assertNotIn('Second private',str(v))
    def test_correction_acceptance_exact_second_buffer(self):
        def correct(o,d,p):
            if len(p.calls)==2:o.update(decision='SHOW_FALLBACK',release_eligible=False,correction_possible=True)
            return o
        q,p,c,s=self.setup_runtime(Provider([draft(text='Private rejected draft'),draft()],correct))
        _,v,_=q.answer(s,'Actual query')
        self.assertEqual(v['response']['type'],'SUPPORTED');self.assertEqual(len(p.calls),4)
        self.assertNotIn('Private rejected',str(v));self.assertEqual(v['response']['natural_language'],p.calls[3][2]['complete_proposed_response']['text'])
    def test_malformed_wrong_binding_missing_claim_and_provider_failure_are_errors(self):
        def missing(o,*args):o['per_claim_support']=[];return o
        def binding(o,*args):o['binding_sha256']='wrong';return o
        def outage(o,*args):raise ProviderFailure('PROVIDER_DAILY_OR_RATE_LIMIT')
        for fn in (missing,binding,outage,lambda *args:{}):
            q,p,c,s=self.setup_runtime(Provider(verifier=fn));_,v,_=q.answer(s,'Actual query')
            self.assertEqual(v['response']['type'],'SYSTEM_ERROR');self.assertIsNone(c.last_admitted)
            self.assertNotIn('The listed bore',str(v));self.assertEqual(c.last_trace['provider_calls'],2)
    def test_source_changed_during_verification_withholds(self):
        def mutate(o,*args):self.registry.evidence[BORE]['raw_object']['text']='tampered';return o
        q,p,c,s=self.setup_runtime(Provider(verifier=mutate));_,v,_=q.answer(s,'Actual query')
        self.assertEqual(v['response']['type'],'SYSTEM_ERROR');self.assertIsNone(c.last_admitted)
    def test_empty_evidence_unsupported_still_separately_verified(self):
        q,p,c,s=self.setup_runtime(Provider([draft(None,'The retrieved material does not answer that.','LIMITATION','UNSUPPORTED','NONE')]))
        admitted=self.authority.assemble({'manual_checksum':self.authority.checksum,'index_id':self.authority.index_id,'hits':[]})
        r=c.compose_open(q.controller,s,admitted,'Actual query',{})
        self.assertEqual(r.type.value,'UNSUPPORTED');self.assertEqual(len(p.calls),2);self.assertIsNone(c.last_admitted)
    def test_safety_precedence_and_source_conflict_cannot_be_blessed(self):
        for history in ({'required_route':'SAFETY_STOP','required_safety_evidence_ids':['missing']},{'source_conflicts':['conflict']}):
            q,p,c,s=self.setup_runtime()
            a=self.authority.assemble(q.retriever.search('query'))
            r=c.compose_open(q.controller,s,a,'query',history)
            self.assertEqual(r.type.value,'SYSTEM_ERROR');self.assertIsNone(c.last_admitted)
    def test_safety_route_is_separately_verified_and_cannot_be_replaced_by_fact(self):
        q,p,c,s=self.setup_runtime(Provider([draft(route='SAFETY_STOP')]))
        a=self.authority.assemble(q.retriever.search('query'))
        r=c.compose_open(q.controller,s,a,'query',{'required_route':'SAFETY_STOP','required_safety_evidence_ids':[BORE]})
        self.assertEqual(r.type.value,'SAFETY_STOP');self.assertEqual(len(p.calls),2)
        q,p,c,s=self.setup_runtime();a=self.authority.assemble(q.retriever.search('query'))
        r=c.compose_open(q.controller,s,a,'query',{'required_route':'SAFETY_STOP','required_safety_evidence_ids':[BORE]})
        self.assertEqual(r.type.value,'SYSTEM_ERROR');self.assertIsNone(c.last_admitted)
    def test_history_mutation_after_verdict_withholds_exact_buffer(self):
        history={'conversation':[]}
        def change(o,*args):history['conversation'].append('new turn');return o
        q,p,c,s=self.setup_runtime(Provider(verifier=change));a=self.authority.assemble(q.retriever.search('query'))
        r=c.compose_open(q.controller,s,a,'query',history)
        self.assertEqual(r.type.value,'SYSTEM_ERROR');self.assertIsNone(c.last_admitted)
    def test_release_partial_requires_preverified_visible_limitations(self):
        d=draft(coverage='PARTIAL');d['unanswered_parts']=['Undocumented repair']
        d['claims'].append({'text':'The retrieved evidence does not describe that repair.','role':'LIMITATION','evidence_ids':[]})
        q,p,c,s=self.setup_runtime(Provider([d]));_,v,_=q.answer(s,'Bore and undocumented repair?')
        self.assertEqual(v['response']['type'],'SUPPORTED')
        self.assertEqual(c.last_admitted['verdict']['decision'],'RELEASE_PARTIAL')
        self.assertIn('does not describe that repair',p.calls[1][2]['complete_proposed_response']['text'])
        def dishonest(o,*args):o['coverage_limitation_clear']=False;return o
        q,p,c,s=self.setup_runtime(Provider([d],dishonest));_,v,_=q.answer(s,'Bore and undocumented repair?')
        self.assertEqual(v['response']['type'],'SYSTEM_ERROR');self.assertIsNone(c.last_admitted)
    def test_fallback_and_system_error_exact_owner_wording_without_extra_text(self):
        FALLBACK_TEXT='I couldn\u2019t find relevant information in the selected manual to answer your question. Please contact Royal Enfield or an authorised service centre.'
        SYSTEM_ERROR_TEXT='I couldn\u2019t check the answer right now. Please try again shortly.'
        def reject(o,*args):o.update(decision='SHOW_FALLBACK',release_eligible=False,question_coverage='IRRELEVANT');return o
        q,p,c,s=self.setup_runtime(Provider(verifier=reject));_,v,_=q.answer(s,'query')
        self.assertEqual(v['response']['natural_language'],FALLBACK_TEXT)
        self.assertFalse(v['response'].get('semantic_verification_passed',False));self.assertFalse(v['response'].get('release_gate_passed',False))
        self.assertIn('IRRELEVANT_ANSWER',v['response']['reason_codes'])
        def outage(*args):raise ProviderFailure('PROVIDER_DAILY_OR_RATE_LIMIT')
        q,p,c,s=self.setup_runtime(Provider(verifier=outage));_,v,_=q.answer(s,'query')
        self.assertEqual(v['response']['natural_language'],SYSTEM_ERROR_TEXT)
    def test_fixed_copy_constants_have_exact_independent_unicode_bytes(self):
        from cloud.grounded_generation.verified_qa import FALLBACK_TEXT,SYSTEM_ERROR_TEXT,VERSION
        expected_fallback='I couldn\u2019t find relevant information in the selected manual to answer your question. Please contact Royal Enfield or an authorised service centre.'
        expected_error='I couldn\u2019t check the answer right now. Please try again shortly.'
        self.assertEqual(FALLBACK_TEXT,expected_fallback)
        self.assertEqual(SYSTEM_ERROR_TEXT,expected_error)
        self.assertEqual(FALLBACK_TEXT.encode('utf-8'),expected_fallback.encode('utf-8'))
        self.assertEqual(SYSTEM_ERROR_TEXT.encode('utf-8'),expected_error.encode('utf-8'))
        self.assertEqual(VERSION,'open-manual-draft-verify-v8')
    def test_runtime_source_is_ascii_and_apostrophe_is_source_escape(self):
        import cloud.grounded_generation.verified_qa as module
        from pathlib import Path
        source=Path(module.__file__).read_text(encoding='utf-8')
        self.assertTrue(source.isascii())
        self.assertIn('couldn\\u2019t',source)
    def test_delivery_rejects_text_session_and_operation_mutations(self):
        q,p,c,s=self.setup_runtime();a=self.authority.assemble(q.retriever.search('query'))
        r=c.compose_open(q.controller,s,a,'query',{'operation_id':'original'})
        self.assertEqual(r.type.value,'SUPPORTED')
        for ss,rr,op in ((s,replace(r,natural_language='changed'),'original'),(replace(s,version=s.version+1),r,'original'),(s,r,'other')):
            with self.assertRaises(ValidationFailure):saved_view(self.registry,ss,rr,self.authority,c.last_admitted,op)
        v,_=saved_view(self.registry,s,r,self.authority,c.last_admitted,'original')
        self.assertEqual(v['response']['natural_language'],r.natural_language)
    def test_inconsistent_acceptance_is_system_error(self):
        def wrong(o,*args):o['question_coverage']='IRRELEVANT';return o
        q,p,c,s=self.setup_runtime(Provider(verifier=wrong));_,v,_=q.answer(s,'Actual query')
        self.assertEqual(v['response']['type'],'SYSTEM_ERROR');self.assertIsNone(c.last_admitted)

    def test_compact_projection_restores_every_original_source_content_field(self):
        from cloud.grounded_generation.verified_qa import compact_source_evidence
        q,p,c,s=self.setup_runtime(Provider([draft(LOCATION,'The socket is in the centre of the handlebar.')]),eid=LOCATION)
        admitted=self.authority.assemble(q.retriever.search('USB'))
        original=deepcopy(admitted)
        compact=compact_source_evidence(admitted['evidence'])
        def restore(value):
            if type(value)is list:return [restore(x) for x in value]
            if type(value)is not dict:return value
            result={k:restore(v) for k,v in value.items()}
            if result.pop('orig_same_as_text',False):result['orig']=result['text']
            return result
        for eid,row in admitted['evidence'].items():
            self.assertEqual(restore(compact[eid]['source_object']['content']),row['source_object']['content'])
            self.assertEqual(compact[eid]['provenance'],row['provenance'])
            for key,value in row['reviewed_source_context'].items():
                if key not in ('original_object_sha256','original_raw_object_sha256'):
                    self.assertEqual(compact[eid]['reviewed_source_context'][key],value)
        self.assertEqual(admitted,original)
        _,view,_=q.answer(s,'Where is my socket?')
        self.assertNotIn('code_sha256',p.calls[0][1]['runtime_contract'])
        self.assertEqual(p.calls[0][1]['full_evidence_payload_sha256'],c.last_admitted['source_payload']['payload_sha256'])
        self.assertNotIn('claim_to_evidence_map',p.calls[1][2])
    def test_enabled_provider_contract_is_exactly_bound_through_delivery(self):
        from cloud.grounded_generation.fallback_provider import CONTRACT
        from cloud.grounded_generation.verified_qa import Config
        p=Provider();p.contract=deepcopy(CONTRACT)
        q,p,c,s=self.setup_runtime(p)
        self.assertNotEqual(c.config.lock,Config().lock)
        self.assertEqual(c.config.versions()['provider_max_attempts'],3)
        _,view,_=q.answer(s,'How wide is the bore?')
        self.assertEqual(view['response']['type'],'SUPPORTED')
        self.assertEqual(view['verified_delivery']['runtime_lock'],c.config.lock)
        self.assertEqual(c.last_admitted['provider_contract'],CONTRACT)
        p.contract['fallback']['model']='other'
        self.assertEqual(c.config.provider_contract,CONTRACT)
        with self.assertRaises(ValidationFailure):Config(provider_contract=p.contract)


    def test_special_route_rejection_never_becomes_ordinary_fallback(self):
        for route,correctable in [('SAFETY_STOP',False),('SAFETY_STOP',True),('AMBIGUOUS',False)]:
            with self.subTest(route=route,correctable=correctable):
                proposal=draft(route=route)
                if route=='AMBIGUOUS':
                    proposal=draft(text='Is the displayed value readable?',role='CLARIFICATION',route=route)
                    proposal.update(clarification_question=proposal['claims'][0]['text'],rider_resolvable=True)
                def reject(o,*args):
                    o.update(decision='SHOW_FALLBACK',release_eligible=False,correction_possible=correctable)
                    return o
                q,p,c,s=self.setup_runtime(Provider([proposal],reject))
                a=self.authority.assemble(q.retriever.search('query'))
                history={'required_route':'SAFETY_STOP','required_safety_evidence_ids':[BORE]} if route=='SAFETY_STOP' else {}
                response=c.compose_open(q.controller,s,a,'query',history)
                self.assertEqual(response.type.value,'SYSTEM_ERROR')
                self.assertEqual(c.last_trace['failure_code'],'SPECIAL_ROUTE_VERIFICATION_FAILED')
                self.assertIsNone(c.last_admitted)
                self.assertEqual(c.last_trace['provider_calls'],4 if correctable else 2)

del SourceTests
if __name__=='__main__':unittest.main()
