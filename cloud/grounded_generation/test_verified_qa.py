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
    def __init__(self,drafts=None,verifier=None):self.drafts=drafts or [draft()];self.verifier=verifier;self.calls=[];self.wire_calls=[];self.last_trace=None
    def count(self,body):return 100
    def complete(self,policy,stable,dynamic,schema):
        from cloud.grounded_generation.verified_qa import expand_model_context,expand_stable_context,CONTEXT_ENCODING
        self.wire_calls.append((schema,deepcopy(stable),deepcopy(dynamic)))
        if type(stable.get('source_projection'))is dict and stable['source_projection'].get('encoding')==CONTEXT_ENCODING:
            stable=expand_stable_context(stable)
        if dynamic.get('encoding')==CONTEXT_ENCODING:
            dynamic=expand_model_context(dynamic)
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
        self.assertEqual(VERSION,'open-manual-draft-verify-v10')
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
                if key not in ('original_object_sha256','original_raw_object_sha256','component_review_sha256'):
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

class PairedProviderTests(unittest.TestCase):
    """Index-free engineering fixtures for separately selected model roles."""
    def setUp(self):
        from controller_contracts import DiagnosticSession,Response,ResponseType
        from evidence_registry import content_hash
        from cloud.grounded_generation.provider import MODEL
        from cloud.grounded_generation.cached_verifier import CONTRACT
        self.hash=content_hash
        self.eid='synthetic-evidence-only'
        evidence={self.eid:{'provenance':[{'page_no':1}],
            'source_object':{'content':{'text':'Synthetic fixture, never serving authority.'}}}}
        self.admitted={'payload_sha256':content_hash(evidence),'authority_lock':'synthetic-authority',
            'evidence':evidence,'required_display':[],'gaps':[]}
        self.expected=content_hash(self.admitted)
        owner=self
        class Authority:
            def validate(self,value):
                if value is owner.admitted and content_hash(value)!=owner.expected:
                    raise ValidationFailure('SYNTHETIC_SOURCE_CHANGED')
            def select(self,value,used):
                return {'required_evidence_ids':list(used),'required_display':[{
                    'claim_id':'fixture-warning','text':'Preserve the synthetic source condition.',
                    'response_role':'WARNING','evidence_ids':[owner.eid]}]}
        self.authority=Authority()
        registry=SimpleNamespace(checksum='synthetic-manual',index_id='synthetic-index',
            source={'pdf_pages':1},evidence=evidence,source_ready=lambda:True,support_uri=lambda:None)
        self.controller=SimpleNamespace(registry=registry,scope_status=lambda s:'CONFIRMED',
            response=lambda route,text,session,**kw:Response(ResponseType(route),text,**kw))
        class RoleProvider(Provider):
            def __init__(self,model,*,cached=False,**kw):
                super().__init__(drafts=[draft(owner.eid,'Synthetic approved fixture.')],**kw)
                self.model=model;self.lifecycle=[]
                if cached:self.contract=deepcopy(CONTRACT);self.cache_capability='explicit'
            def begin_turn(self,*args):
                self.lifecycle.append(('begin',args));return {'engineering_fixture':True}
            def end_turn(self):self.lifecycle.append(('end',()))
            def complete(self,policy,stable,dynamic,schema):
                if (self.model==MODEL)!=(schema==DRAFT_SCHEMA):
                    raise AssertionError('Selected provider received the wrong role')
                result=super().complete(policy,stable,dynamic,schema)
                result.telemetry['model']=self.model
                return result
        self.draft=RoleProvider(MODEL)
        self.verifier=RoleProvider(CONTRACT['model'],cached=True)
        self.composer=Composer(self.draft,self.authority,verifier=self.verifier)
        self.session=DiagnosticSession('synthetic-session','synthetic-manual-id','synthetic-manual',
            'Himalayan BS6',None,(),'synthetic-selection',generation_lock=self.composer.config.lock)
        self.history={'operation_id':'synthetic-operation','conversation':['private fixture history']}
    def call(self):
        return self.composer.compose_open(self.controller,self.session,self.admitted,
            'Synthetic question only.',self.history)
    def test_distinct_models_route_exact_finalized_response_including_server_warning(self):
        response=self.call()
        self.assertEqual(response.type.value,'SUPPORTED')
        self.assertEqual(len(self.draft.calls),1);self.assertEqual(len(self.verifier.calls),1)
        final=self.verifier.calls[0][2]['complete_proposed_response']
        self.assertEqual(final['text'],response.natural_language)
        self.assertIn('synthetic source condition',final['text'])
        self.assertEqual(len(final['claims']),2)
        stable=self.verifier.calls[0][1]
        self.assertNotIn('question',stable);self.assertNotIn('history',stable)
        self.assertNotIn('private fixture history',str(stable))
        self.assertNotEqual(self.composer.last_trace['draft_model'],self.composer.last_trace['verifier_model'])
        self.assertEqual(self.composer.last_trace['provider_calls'],2)
        self.assertEqual([event[0] for event in self.draft.lifecycle],['begin','end'])
        self.assertEqual([event[0] for event in self.verifier.lifecycle],['begin','end'])
    def test_both_role_contracts_bound_to_verdict_and_saved_admission(self):
        self.call()
        admitted=self.composer.last_admitted
        self.assertEqual(admitted['binding']['draft_model_contract_sha256'],self.hash(self.composer.config.draft_contract))
        self.assertEqual(admitted['binding']['verifier_contract_sha256'],self.hash(self.composer.config.verifier_contract))
        self.assertEqual(admitted['verifier_contract'],self.verifier.contract)
        self.assertEqual(admitted['verdict']['binding_sha256'],admitted['binding_sha256'])
        changed=deepcopy(self.verifier.contract);changed['cache_ttl']='1h'
        from cloud.grounded_generation.verified_qa import Config
        with self.assertRaisesRegex(ValidationFailure,'VERIFIER_CONTRACT'):
            Config(verifier_contract=changed)
    def test_delivery_requires_the_same_selected_verifier_contract(self):
        from unittest.mock import patch
        response=self.call()
        with patch('cloud.grounded_generation.verified_qa.legacy_view',
                   return_value=({'response':{},'manual_checksum':'synthetic-manual','index_id':'synthetic-index'},{})):
            result,_=saved_view(self.controller.registry,self.session,response,self.authority,
                               self.composer.last_admitted,'synthetic-operation')
            self.assertEqual(result['response']['natural_language'],response.natural_language)
            self.assertEqual(result['verified_delivery']['runtime_lock'],self.composer.config.lock)
            changed=deepcopy(self.composer.last_admitted);changed['verifier_contract']=None
            with self.assertRaisesRegex(ValidationFailure,'DELIVERY_EVIDENCE_OR_VERSION_CHANGED'):
                saved_view(self.controller.registry,self.session,response,self.authority,changed,'synthetic-operation')
    def test_reused_verdict_after_cached_prefix_cannot_authorize_another_question(self):
        self.call()
        previous=deepcopy(self.composer.last_admitted['verdict'])
        self.verifier.verifier=lambda *args:deepcopy(previous)
        response=self.composer.compose_open(self.controller,self.session,self.admitted,
            'Another synthetic question.',self.history)
        self.assertEqual(response.type.value,'SYSTEM_ERROR')
        self.assertEqual(self.composer.last_trace['failure_code'],'VERIFIER_BINDING')
        self.assertIsNone(self.composer.last_admitted)
        self.assertEqual(len(self.draft.calls),2);self.assertEqual(len(self.verifier.calls),2)
    def test_selected_verifier_contract_or_cache_change_blocks_before_paid_calls(self):
        self.verifier.contract['model']='other'
        self.assertEqual(self.call().type.value,'SYSTEM_ERROR')
        self.assertFalse(self.draft.calls);self.assertFalse(self.verifier.calls)
    def test_shared_provider_and_unknown_verifier_forbidden(self):
        with self.assertRaisesRegex(ValidationFailure,'SEPARATE_PROVIDER'):
            Composer(self.draft,self.authority,verifier=self.draft)
        with self.assertRaisesRegex(ValidationFailure,'CONTRACT_REQUIRED'):
            Composer(self.draft,self.authority,verifier=Provider())
    def test_verifier_wrong_model_withheld_after_exact_private_draft(self):
        original=self.verifier.complete
        def mismatch(*args):
            result=original(*args);result.telemetry['model']='other';return result
        self.verifier.complete=mismatch
        self.assertEqual(self.call().type.value,'SYSTEM_ERROR')
        self.assertEqual(self.composer.last_trace['failure_code'],'VERIFIER_PROVIDER_MODEL_MISMATCH')
        self.assertIsNone(self.composer.last_admitted)
    def test_draft_wrong_model_cannot_reach_verifier(self):
        original=self.draft.complete
        def mismatch(*args):
            result=original(*args);result.telemetry['model']='other';return result
        self.draft.complete=mismatch
        self.assertEqual(self.call().type.value,'SYSTEM_ERROR')
        self.assertEqual(self.composer.last_trace['failure_code'],'DRAFT_PROVIDER_MODEL_MISMATCH')
        self.assertFalse(self.verifier.calls)
    def test_verifier_uncertain_failure_has_own_trace_and_no_retry(self):
        def failure(*args):
            self.verifier.last_trace={'generation_calls':1,'model':self.verifier.model,'failure_code':'SYNTHETIC_TIMEOUT'}
            raise ProviderFailure('SYNTHETIC_TIMEOUT')
        self.verifier.complete=failure
        self.assertEqual(self.call().type.value,'SYSTEM_ERROR')
        trace=self.composer.last_trace
        self.assertEqual(trace['provider_calls'],2)
        self.assertEqual(trace['failed_provider_trace']['model'],self.verifier.model)
        self.assertEqual(len(self.draft.calls),1)
        self.assertIsNone(self.composer.last_admitted)
    def test_spend_guard_failure_prevents_any_generation_and_cleans_both_roles(self):
        def failure():raise ProviderFailure('SYNTHETIC_COST_GUARD')
        self.verifier.begin_turn=failure
        self.assertEqual(self.call().type.value,'SYSTEM_ERROR')
        self.assertFalse(self.draft.calls);self.assertFalse(self.verifier.calls)
        self.assertEqual(self.draft.lifecycle[-1][0],'end')
        self.assertEqual(self.verifier.lifecycle[-1][0],'end')
    def test_one_correction_goes_to_draft_and_fresh_verifier_binding(self):
        def reject_first(verdict,dynamic,provider):
            if len(provider.calls)==1:verdict.update(decision='SHOW_FALLBACK',release_eligible=False,correction_possible=True)
            return verdict
        self.verifier.verifier=reject_first
        self.assertEqual(self.call().type.value,'SUPPORTED')
        self.assertEqual(len(self.draft.calls),2);self.assertEqual(len(self.verifier.calls),2)
        self.assertIn('correction_feedback',self.draft.calls[1][2])
        self.assertEqual(self.composer.last_trace['corrections'],1)
        self.assertEqual(self.composer.last_trace['provider_calls'],4)
    def test_source_mutation_during_separate_verification_rejects(self):
        def mutate(verdict,*args):
            self.admitted['evidence'][self.eid]['source_object']['content']['text']='changed source'
            return verdict
        self.verifier.verifier=mutate
        self.assertEqual(self.call().type.value,'SYSTEM_ERROR')
        self.assertIsNone(self.composer.last_admitted)

class RoutedProviderTests(unittest.TestCase):
    """Index-free exact-buffer and authority fixtures for both selected pairs."""
    def setUp(self):
        PairedProviderTests.setUp(self)
        from cloud.grounded_generation.role_router import RoleRouter
        from cloud.grounded_generation.role_contracts import GEMMA_DRAFT,GEMMA_VERIFIER,HAIKU_DRAFT,HAIKU_VERIFIER
        self.admitted['citation_mapping']=[{'evidence_id':self.eid,'pdf_page':1}]
        self.expected=self.hash(self.admitted)
        owner=self
        class Role(Provider):
            def __init__(self,contract,count):
                super().__init__([draft(owner.eid,'Synthetic source-supported fixture.')])
                self.contract=deepcopy(contract);self.count_value=count;self.expected=None
                self.cache_capability='explicit' if contract['provider']=='anthropic' else 'unsupported'
            def context(self,policy,stable,dynamic,schema,**kw):
                return {'policy':policy,'stable':deepcopy(stable),'dynamic':deepcopy(dynamic),'schema':schema},self.count_value
            def expect_initial_context(self,value):self.expected=value
            def complete(self,policy,stable,dynamic,schema):
                body,_=self.context(policy,stable,dynamic,schema)
                if self.expected is not None:
                    if owner.hash(body)!=self.expected:raise ProviderFailure('ROUTER_INITIAL_REQUEST_BINDING_CHANGED')
                    self.expected=None
                result=super().complete(policy,stable,dynamic,schema)
                result.telemetry.update(model=self.contract['model'],role=self.contract['role'])
                return result
        class Admission:
            def __init__(self):self.initial=[];self.corrections=[];self.ended=0;self.fail_correction=False
            def begin_turn(self,op,*,plan):self.initial.append((op,deepcopy(plan)));return {'reserved_attempts':3}
            def reserve_correction(self,op,*,plan):
                if self.fail_correction:raise ProviderFailure('PROVIDER_WHOLE_TURN_ALLOCATION_LIMIT')
                self.corrections.append((op,deepcopy(plan)));return {'reserved_attempts':3}
            def end_turn(self):self.ended+=1
        self.gd,self.hd,self.gv,self.hv=(Role(GEMMA_DRAFT,100),Role(HAIKU_DRAFT,200),
                                        Role(GEMMA_VERIFIER,300),Role(HAIKU_VERIFIER,400))
        self.admission=Admission();self.router=RoleRouter(self.gd,self.hd,self.gv,self.hv,self.admission)
        self.composer=Composer(source_authority=self.authority,router=self.router)
        self.session=replace(self.session,generation_lock=self.composer.config.lock)
    call=PairedProviderTests.call
    def test_both_routes_bind_exact_selected_models_and_complete_final_buffer(self):
        for large in (False,True):
            self.setUp();self.gd.count_value=9000 if large else 100
            lock=self.composer.config.lock;response=self.call();self.assertEqual(response.type.value,'SUPPORTED')
            drafter,verifier=(self.hd,self.gv) if large else (self.gd,self.hv)
            self.assertEqual(len(drafter.calls),1);self.assertEqual(len(verifier.calls),1)
            self.assertEqual(verifier.calls[0][2]['complete_proposed_response']['text'],response.natural_language)
            self.assertIn('synthetic source condition',response.natural_language)
            accepted=self.composer.last_admitted;plan=accepted['binding']['role_plan']
            self.assertEqual(plan['draft_model_contract_sha256'],self.hash(drafter.contract))
            self.assertEqual(plan['verifier_contract_sha256'],self.hash(verifier.contract))
            self.assertEqual(accepted['binding']['runtime_lock'],lock);self.assertEqual(self.composer.config.lock,lock)
            self.assertEqual(len(self.admission.initial),1);self.assertFalse(self.admission.corrections)
            self.assertEqual(self.admission.ended,1)
    def test_correction_keeps_roles_and_requires_new_atomic_phase(self):
        self.gd.count_value=9000
        def revise(v,d,p):
            if len(p.calls)==1:v.update(decision='SHOW_FALLBACK',release_eligible=False,correction_possible=True)
            return v
        self.gv.verifier=revise;response=self.call()
        self.assertEqual(response.type.value,'SUPPORTED');self.assertEqual(len(self.hd.calls),2)
        self.assertEqual(len(self.gv.calls),2);self.assertFalse(self.gd.calls);self.assertFalse(self.hv.calls)
        self.assertEqual(len(self.admission.corrections),1)
        initial=self.admission.initial[0];correction=self.admission.corrections[0]
        self.assertEqual(initial[0],correction[0]);self.assertEqual(initial[1]['role_plan'],correction[1]['role_plan'])
        self.assertIn('correction_request_sha256',correction[1]);self.assertEqual(self.composer.last_trace['corrections'],1)
    def test_underfunded_correction_is_operational_error_with_private_draft_hidden(self):
        def revise(v,*args):v.update(decision='SHOW_FALLBACK',release_eligible=False,correction_possible=True);return v
        self.hv.verifier=revise;self.admission.fail_correction=True;response=self.call()
        self.assertEqual(response.type.value,'SYSTEM_ERROR');self.assertEqual(len(self.gd.calls),1)
        self.assertEqual(self.composer.last_trace['failure_code'],'PROVIDER_WHOLE_TURN_ALLOCATION_LIMIT')
        self.assertIsNone(self.composer.last_admitted);self.assertNotIn('Synthetic source-supported',response.natural_language)
    def test_semantic_rejection_and_quota_failure_do_not_switch_role_pair(self):
        def reject(v,*args):v.update(decision='SHOW_FALLBACK',release_eligible=False);return v
        self.hv.verifier=reject;response=self.call();self.assertEqual(response.type.value,'UNSUPPORTED')
        self.assertFalse(self.hd.calls);self.assertFalse(self.gv.calls)
        self.setUp()
        def outage(*args):raise ProviderFailure('PROVIDER_HTTP_429')
        self.hv.verifier=outage;response=self.call();self.assertEqual(response.type.value,'SYSTEM_ERROR')
        self.assertFalse(self.hd.calls);self.assertFalse(self.gv.calls)
    def test_delivery_rejects_changed_selected_role_contract(self):
        from unittest.mock import patch
        self.gd.count_value=9000;response=self.call();accepted=self.composer.last_admitted
        with patch('cloud.grounded_generation.verified_qa.legacy_view',return_value=({'response':{},'schema_version':'fixture'},{})):
            view,_=saved_view(self.controller.registry,self.session,response,self.authority,accepted)
            self.assertEqual(view['verified_delivery']['draft_model'],self.hd.contract['model'])
            self.assertEqual(view['verified_delivery']['verifier_model'],self.gv.contract['model'])
            changed=deepcopy(accepted);changed['selected_draft_contract']=deepcopy(self.gd.contract)
            with self.assertRaisesRegex(ValidationFailure,'MODEL_ROLE_BINDING_CHANGED'):
                saved_view(self.controller.registry,self.session,response,self.authority,changed)


class SharedProjectionTests(unittest.TestCase):
    """Index-free synthetic checks of representation, never answer quality."""
    def helpers(self):
        from cloud.grounded_generation.verified_qa import compact_model_context,expand_model_context
        return compact_model_context,expand_model_context

    def test_every_source_value_and_table_position_survives_roundtrip(self):
        import json
        compact,expand=self.helpers()
        warning='Synthetic caution text: retain every condition, unit and reference. '*5
        source={'objects':{'evidence_'+'a'*24:{'orig':'distinct original text',
            'text':'different displayed text','section':['Synthetic section','Synthetic table'],
            'table':{'fields':['text','column_header','row_header','row_span','col_span'],
                'rows':[['3 L +/- 0.5 L',False,True,1,2],[None,False,False,2,1]],
                'missing':{'1':[0]},'row_lengths':[2,1]},'warnings':[warning]*5,
            'refs':['#/texts/10','#/tables/2'],'nullable':None,'false':False,'number':-0.0}},
            'gaps':[{'type':'SOURCE_CONTEXT_REVIEW_REQUIRED','rider_resolvable':False}],
            'required_display':[{'text':warning,'evidence_ids':['evidence_'+'a'*24]}]*4}
        before=deepcopy(source);packed=compact(source)
        self.assertEqual(json.dumps(expand(packed),sort_keys=True),json.dumps(source,sort_keys=True))
        self.assertEqual(source,before)
        self.assertLess(len(json.dumps(packed)),len(json.dumps(source)))

    def test_repeated_field_schemas_and_values_are_readable_and_exact(self):
        compact,expand=self.helpers()
        rows=[{'long_warning_field_name':'Complete synthetic warning text. '*10,
               'long_section_field_name':['Synthetic chapter','Synthetic subsection'],
               'long_position_field_name':i} for i in range(12)]
        packed=compact(rows)
        self.assertEqual(expand(packed),rows)
        self.assertTrue(any(type(value)is list and 'long_warning_field_name' in value
                            for value in packed['shared']))
        self.assertTrue(any(type(value)is str and 'Complete synthetic warning text.' in value
                            for value in packed['shared']))

    def test_reserved_source_field_names_are_escaped_without_semantic_changes(self):
        compact,expand=self.helpers()
        source={'$ref':0,'$literal':{'$record':2,'values':['literal source list']},
                'nested':[{'$ref':True},{'$literal':{'$ref':4}}]}
        self.assertEqual(expand(compact(source)),source)

    def test_cyclic_boolean_unknown_and_out_of_range_refs_fail_closed(self):
        _,expand=self.helpers()
        from cloud.grounded_generation.verified_qa import CONTEXT_ENCODING
        fixtures=[{'shared':[],'value':{'$ref':0}},
                  {'shared':['text'],'value':{'$ref':True}},
                  {'shared':['text'],'value':{'$ref':-1}},
                  {'shared':[{'$ref':0}],'value':{'$ref':0}},
                  {'shared':[['field','field']],'value':{'$record':0,'values':[1,2]}},
                  {'shared':[['field']],'value':{'$record':0,'values':[]}},
                  {'shared':[],'value':{'$ref':0,'other':'unescaped'}}]
        for fixture in fixtures:
            with self.subTest(fixture=fixture),self.assertRaises(ValidationFailure):
                expand({'encoding':CONTEXT_ENCODING,**fixture})

    def test_citation_ids_and_hash_echo_remain_literal_and_alias_outputs_are_rejected(self):
        compact,expand=self.helpers()
        from cloud.grounded_generation.verified_qa import validate_draft
        eid='evidence_'+'a'*24;sha='b'*64
        source={'evidence':{eid:{'evidence_id':eid,'text':'Synthetic text.'}},
                'same_id':[eid]*8,'binding_sha256':sha,'binding':{'sha':sha}}
        packed=compact(source)
        self.assertEqual(expand(packed),source)
        self.assertNotIn(eid,packed['shared']);self.assertNotIn(sha,packed['shared'])
        for alias in ('0','$ref:0'):
            with self.assertRaisesRegex(ValidationFailure,'INVALID_DRAFT_CITATION'):
                validate_draft(draft(alias),{eid:source['evidence'][eid]})

    def test_stable_fields_displays_and_gaps_restore_with_uncached_dynamic_separate(self):
        from cloud.grounded_generation.verified_qa import compact_stable_context,expand_stable_context
        from cloud.grounded_generation.cached_verifier import STABLE_FIELDS
        compact,expand=self.helpers()
        stable={k:None for k in STABLE_FIELDS}
        stable.update(evidence={'evidence_'+'a'*24:{'text':'Synthetic source'}},
            required_source_display=[{'text':'Synthetic warning','evidence_ids':['evidence_'+'a'*24]}],
            source_gaps=[{'rider_resolvable':False,'type':'SOURCE_REVIEW_REQUIRED'}],
            source_projection='lossless-identical-orig-reference-v1')
        packed=compact_stable_context(stable)
        self.assertEqual(set(packed),STABLE_FIELDS)
        self.assertEqual(expand_stable_context(packed),stable)
        history={'conversation':[{'response':'PRIVATE_DYNAMIC_RESPONSE','query':'PRIVATE_DYNAMIC_QUESTION'}]*5,
                 'typed_outcomes':{'result':'ACTION_COMPLETED_UNRESOLVED'}}
        request={'question':'PRIVATE_DYNAMIC_QUESTION','history':history,
                 'complete_proposed_response':{'text':'PRIVATE_DYNAMIC_RESPONSE','claims':[]},
                 'binding':{'history_sha256':'c'*64},'binding_sha256':'d'*64}
        self.assertEqual(expand(compact(request)),request)
        self.assertNotIn('PRIVATE_DYNAMIC',str(packed))

    def test_reordering_input_object_keys_does_not_change_projection(self):
        compact,expand=self.helpers()
        first={'b':[{'second_field_name':2,'first_field_name':'repeat '*20}]*6,'a':None}
        second={'a':None,'b':[{'first_field_name':'repeat '*20,'second_field_name':2}]*6}
        self.assertEqual(compact(first),compact(second))
        self.assertEqual(expand(compact(first)),first)

    def test_only_approved_proof_layout_fields_are_omitted_and_original_payload_is_bound(self):
        from cloud.grounded_generation.verified_qa import (compact_source_evidence,
            compact_required_source_display,model_source_context,expand_stable_context)
        from evidence_registry import content_hash
        eid='evidence_'+'a'*24
        text='Complete synthetic warning, prerequisites, 3 L +/- 0.5 L, and reference.'
        evidence={eid:{'source_object':{'content':{'text':text,'orig':text+' distinct original'},
                                      'original_object_sha256':'c'*64},
            'reviewed_source_context':{'section_path':['Synthetic full section'],
                'parent_text_authorized':False,'component_review_sha256':'d'*64,
                'original_object_sha256':'c'*64},'provenance':[{'page_no':1}]}}
        display=[{'text':text,'evidence_ids':[eid],'source_spans':[{'evidence_id':eid,
            'exact_text':text,'visual_page':1,'text_sha256':'e'*64,'text_span':[0,len(text)],
            'provenance':[{'page_no':1,'bbox':{'l':1,'r':2},'charspan':[0,len(text)],
                           'other_semantic_field':'unchanged'}]}]}]
        original=deepcopy({'evidence':evidence,'required_display':display})
        projected_evidence=compact_source_evidence(evidence)
        projected_display=compact_required_source_display(display)
        self.assertEqual(projected_evidence[eid]['source_object']['content'],evidence[eid]['source_object']['content'])
        self.assertEqual(projected_evidence[eid]['reviewed_source_context']['section_path'],['Synthetic full section'])
        span=projected_display[0]['source_spans'][0]
        self.assertEqual(span['exact_text'],text);self.assertEqual(span['evidence_id'],eid)
        self.assertEqual(span['visual_page'],1)
        self.assertEqual(span['provenance'],[{'page_no':1,'other_semantic_field':'unchanged'}])
        self.assertNotIn('text_sha256',span);self.assertNotIn('text_span',span)
        self.assertEqual({'evidence':evidence,'required_display':display},original)
        admitted={'evidence':evidence,'required_display':display,'gaps':[],
                  'authority_lock':'f'*64,'payload_sha256':content_hash(original)}
        config=SimpleNamespace(lock='b'*64,draft_contract={},verifier_contract={},provider_contract=None)
        registry=SimpleNamespace(checksum='a'*64,index_id='synthetic-index',source={})
        restored=expand_stable_context(model_source_context(config,registry,admitted))
        self.assertEqual(restored['full_evidence_payload_sha256'],content_hash(original))
        self.assertEqual(restored['evidence'],projected_evidence)
        self.assertEqual(restored['required_source_display'],projected_display)
        self.assertEqual(admitted['evidence'][eid]['reviewed_source_context']['component_review_sha256'],'d'*64)

del SourceTests
if __name__=='__main__':unittest.main()
