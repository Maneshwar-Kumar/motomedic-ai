"""Serving runtime: hybrid chunks -> source admission -> controller -> answer LLM.

Factual authority never reads authored questions, answers, or StepDefinition
membership. Procedural eligibility retains the exact reviewed controller.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
import time
from controller_contracts import ResponseType, Truth, Outcome
from constrained_generator import ValidationFailure
from evidence_registry import content_hash
from reviewed_controller import append_attempt
from cloud.arm_a.runtime_controls import diagnostic_projection
from cloud.grounded_generation.runtime import Questions as LegacyQuestions, scope_payload
from cloud.grounded_generation.provider import ProviderFailure, MODEL
from cloud.grounded_generation.context import project, VERSION as CONTEXT_VERSION
from cloud.grounded_generation.source_context import context_for
from cloud.grounded_generation.transitions import exhausted_after_unresolved, VERSION as TRANSITIONS
from cloud.grounded_generation.generic_policy import VERSION, POLICY, POLICY_SHA256, SCHEMA
from cloud.grounded_generation.generic_output import check_output


class Config:
    controls_version=VERSION
    def versions(self):
        from cloud.grounded_generation.source_authority import VERSION as SOURCE_VERSION, STRUCTURAL_SHA, FRESH_SHA
        code={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in
            ('generic_runtime.py','generic_output.py','generic_presentation.py','source_authority.py',
             'provider.py','admission.py','transitions.py','response_cache.py')}
        return {'version':VERSION,'model':MODEL,'policy_sha256':POLICY_SHA256,
            'output_schema_sha256':content_hash(SCHEMA),'source_authority':SOURCE_VERSION,
            'source_structure_sha256':STRUCTURAL_SHA,'fresh_source_review_sha256':FRESH_SHA,'code_sha256':code,
            'input_tokens':8192,'request_bytes':65536,'output_tokens':1800,
            'concurrency':1,'max_attempts':2,'retry_rejections':[429,503],
            'context_projection':CONTEXT_VERSION,'transitions':TRANSITIONS,
            'factual_admission':'IMMUTABLE_SOURCE_OBJECT_STRUCTURAL_CLOSURE',
            'action_admission':'REVIEWED_CONTROLLER_ELIGIBILITY_AND_DEPENDENCIES',
            'response_cache':'EXACT_REVIEWED_ACTION_ONLY_MISS_TO_GENERATION_V2',
            'prompt_cache':'EXACT_MODEL_CAPABILITY_UNSUPPORTED_ZERO_SAVINGS',
            'native_structured_output':True,'verifier_calls':0,
            'validation':'DETERMINISTIC_NOT_SEMANTIC_PROOF'}
    @property
    def lock(self):return content_hash(self.versions())


class Composer:
    def __init__(self,provider,source_authority=None):
        self.provider=provider;self.source_authority=source_authority
        self.config=Config();self.last_trace=None;self.last_admitted=None;self.last_source_admission=None
        self.query='';self.scopes=();self.clarifications={}

    def compose(self,controller,session,sid,**kwargs):
        return self.compose_many(controller,session,(sid,),self.query)

    def compose_many(self,controller,session,sids,query,clarifications=None):
        # Controller feedback supplies action authority, never a factual catalogue.
        return self.compose_generic(controller,session,{},sids,query,clarifications)

    def compose_generic(self,controller,session,factual,sids,query,clarifications=None):
        started=time.monotonic();r=controller.registry
        trace={'runtime_lock':self.config.lock,'generation_calls':0,'verifier_calls':0,
            'response_cache':'MISS','deterministic_checks_prove_semantics':False}
        self.last_trace=trace;self.last_admitted=None
        try:
            if session.generation_lock!=self.config.lock:raise ValidationFailure('GENERATION_VERSION_RECONFIRM_REQUIRED')
            if not r.source_ready():raise ValidationFailure('SOURCE_IDENTITY_CHANGED')
            scopes={sid:scope_payload(controller,session,sid) for sid in sids}
            actions={sid:s for sid,s in scopes.items() if s['kind']=='ACTION'}
            safety={sid:s for sid,s in scopes.items() if s['kind']=='SAFETY_STOP'}
            evidence=deepcopy(factual.get('evidence',{}))
            for scope in scopes.values():
                for eid in scope['required_evidence_ids']:
                    evidence[eid]={'type':r.evidence[eid].get('type'),
                        'source_object':project(r.evidence[eid]['raw_object']),
                        'reviewed_source_context':context_for(r,eid),
                        'provenance':deepcopy(r.evidence[eid]['provenance'])}
            if not evidence:raise ValidationFailure('NO_ADMITTED_MANUAL_EVIDENCE')
            if factual:self.source_authority.validate(factual)
            stable={'contract':self.config.versions(),'manual_checksum':r.checksum,'index_id':r.index_id,
                'source_authority_lock':getattr(self.source_authority,'lock',None),
                'registry_lock':r.lock,'variant':session.bike_variant,'edition':session.edition,
                'evidence':evidence,'permitted_actions':actions,'eligible_safety_stops':safety}
            clarifications=clarifications or self.clarifications
            dynamic={'question':query,'typed_state':diagnostic_projection(session),
                'rider_resolvable_clarifications':clarifications}
            trace.update(complete_evidence_count=len(evidence),admitted_evidence_ids=sorted(evidence),
                permitted_action_ids=list(actions),admitted_context_sha256=content_hash(stable))
            # Existing reviewed cache is independent of source admission. Its
            # original schema is adapted only after an exact eligible hit.
            from flask import has_request_context,request
            enabled=has_request_context() and request.environ.get('arm_a_cache_enabled') is True
            cached=None
            if enabled:
                from cloud.grounded_generation.response_cache import ReviewedResponses
                cached=ReviewedResponses(r,self.config.lock).get(query,session,scopes,self.config.lock)
            if cached:
                _,count=self.provider.context(POLICY,stable,dynamic,SCHEMA)
                draft=deepcopy(cached['output']);draft.pop('scope_ids',None)
                trace.update(response_cache='EXACT_REVIEWED_HIT_REVALIDATED',input_tokens_counted=count,
                    response_cache_authority=cached['authority_binding'])
            else:
                result=self.provider.complete(POLICY,stable,dynamic,SCHEMA)
                trace.update(result.telemetry or {});draft=result.output
            check_output(draft,evidence,actions,clarifications,safety)
            if factual:self.source_authority.validate(factual)
            if {sid:scope_payload(controller,session,sid) for sid in sids}!=scopes:
                raise ValidationFailure('ACTION_AUTHORITY_CHANGED')
            if draft['route']=='SAFETY_STOP':return controller.render(session,draft['step_id'],safety=True)
            if draft['route']=='AMBIGUOUS':
                question=clarifications[draft['clarification_id']]['question']
                return controller.response('AMBIGUOUS',question,session,clarification_question=question,
                    reason_codes=('ADMITTED_RIDER_CLARIFICATION',draft['clarification_id']))
            if draft['route']=='UNSUPPORTED':
                return controller.response('UNSUPPORTED','The admitted manual evidence does not support an answer to this question.',
                    session,reason_codes=('MODEL_ABSTAINED_NO_SUPPORTED_ANSWER',))
            used={e for c in draft['claims'] for e in c['evidence_ids']}
            factual_used=used&set(factual.get('evidence',{}))
            selected=self.source_authority.select(factual,factual_used) if factual_used else {}
            mandatory={c['claim_id']:deepcopy(c) for c in selected.get('required_display',[])}
            required=set(selected.get('required_evidence_ids',[]))|used
            sid=draft['step_id']
            if sid:
                required.update(actions[sid]['required_evidence_ids'])
                mandatory.update({c['claim_id']:deepcopy(c) for c in actions[sid]['required_display']})
            claims=[{'claim_id':'generated:'+str(i),**deepcopy(c),'presentation_mode':'GENERATED_PARAPHRASE'}
                for i,c in enumerate(draft['claims'])]+list(mandatory.values())
            pages=[]
            for eid in sorted(required):
                for p in r.evidence[eid]['provenance']:
                    page=p.get('page_no',p.get('pdf_page'))
                    if type(page)is not int or not 1<=page<=r.source['pdf_pages']:
                        raise ValidationFailure('INVALID_SOURCE_PAGE')
                    ref={'evidence_id':eid,'pdf_page':page,'pdf_page_index':page-1,
                        'manual_checksum':r.checksum,'index_id':r.index_id}
                    if ref not in pages:pages.append(ref)
            text=' '.join(c['text'] for c in claims)
            if len(text.encode())>8000:raise ValidationFailure('PRESENTATION_BYTE_BOUND')
            count=self.provider.count({'contents':[{'role':'user','parts':[{'text':text}]}]})
            if count>1800:raise ValidationFailure('PRESENTATION_TOKEN_BOUND_NO_TRUNCATION')
            self.last_admitted={'factual':selected,'required_evidence_ids':sorted(required),
                'mandatory':mandatory,'scopes':{sid:actions[sid]} if sid else {}}
            trace.update(presentation_tokens_counted=count,selected_action_id=sid,
                released_evidence_ids=sorted(required))
            return controller.response('SUPPORTED',text,session,claim_evidence_map=tuple(claims),
                cited_pages=tuple(pages),suggested_step_id=sid or None,
                reason_codes=('GENERIC_GROUNDED_GENERATION_DETERMINISTIC_CHECKED',))
        except (ProviderFailure,ValidationFailure) as exc:
            if isinstance(exc,ProviderFailure):trace.update(getattr(self.provider,'last_trace',None) or {})
            code=str(exc);trace['failure_code']=code
            gap=code in ('NO_ADMITTED_MANUAL_EVIDENCE','SOURCE_REVIEW_REQUIRED','SOURCE_CONTEXT_REVIEW_REQUIRED')
            return controller.response('UNSUPPORTED' if gap else 'SYSTEM_ERROR',
                'Complete reviewed manual evidence is unavailable for this question.' if gap else
                'I am temporarily unable to generate a validated answer.',session,reason_codes=(code,))
        except Exception:
            trace['failure_code']='GENERIC_GENERATION_FAILURE'
            return controller.response('SYSTEM_ERROR','I am temporarily unable to generate a validated answer.',
                session,reason_codes=('GENERIC_GENERATION_FAILURE',))
        finally:trace['server_composition_seconds']=time.monotonic()-started


class Questions(LegacyQuestions):
    def __init__(self,registry,retriever,composer,source_authority=None):
        super().__init__(registry,retriever,composer)
        if source_authority is None:
            from cloud.grounded_generation.source_authority import SourceAuthority
            source_authority=SourceAuthority(registry,retriever.root)
        self.source_authority=source_authority;composer.source_authority=source_authority
        self._safety_bindings={sid:raw.get('canonical_record_id') for sid,raw in registry.candidate['steps'].items()
            if raw['kind']=='SAFETY_STOP'}

    def known_safety(self,session):
        # The legacy registry uses False for both unreviewed and changed scopes.
        # With known observations, corruption must not silently suppress a stop.
        if session.known_observations():
            r=self.registry
            for sid,rid in self._safety_bindings.items():
                if rid in getattr(r,'_bound',{}) and not r._scope_intact(rid):
                    raise ValidationFailure('SAFETY_AUTHORITY_CHANGED')
        return super().known_safety(session)

    def _view(self,session,response):
        from cloud.grounded_generation.generic_presentation import saved_view
        composer=self.controller.response_generator
        view,choices=saved_view(self.registry,session,response,self.source_authority,composer.last_admitted)
        view['runtime_controls']={'composition':composer.last_trace,
            'retrieval':getattr(self.retriever,'last_cache_trace',None),
            'source_admission':composer.last_source_admission}
        view['provider_calls']=(composer.last_trace or {}).get('generation_calls',0)
        return session,view,choices

    def answer(self,session,query):
        c,r=self.controller,self.registry;composer=c.response_generator
        composer.last_trace=None;composer.last_admitted=None;composer.query=query
        composer.last_source_admission=None
        composer.scopes=();composer.clarifications={}
        session=replace(session,version=session.version+1,pending_step_id=None,pending_rule_id=None)
        try:
            if not r.source_ready():raise ValidationFailure('SOURCE_IDENTITY_CHANGED')
            if c.scope_status(session)!='CONFIRMED':raise ValidationFailure('SCOPE_NOT_CONFIRMED')
            safety=self.known_safety(session)
            if safety:return self._view(*safety)
            from cloud.grounded_generation.fuse_refusal import detect_refusal
            refusal=detect_refusal(r,query)
            if refusal:
                from cloud.grounded_generation.presentation import refusal_view
                return session,refusal_view(r,session,c,query,refusal),{}
            bundle=self.retriever.search(query,limit=6,scope=self.scope(),applicability_status='CONFIRMED')
            if bundle.get('manual_checksum')!=r.checksum or bundle.get('index_id')!=r.index_id:
                raise ValidationFailure('INVALID_BUNDLE_IDENTITY')
            if bundle.get('conflicts'):
                return self._view(session,c.response('UNSUPPORTED',
                    'The retrieved manual evidence conflicts, so I cannot give a supported technical answer.',
                    session,reason_codes=('CONFLICTING_SOURCE_EVIDENCE',)))
            factual=self.source_authority.assemble(bundle)
            ids={e for h in bundle.get('hits',[]) for e in h.get('evidence_ids',[])}
            composer.last_source_admission={'source_authority_lock':self.source_authority.lock,
                'retrieved_chunk_ids':[h['id'] for h in bundle.get('hits',[])],
                'retrieved_direct_evidence_ids':sorted(ids),
                'admitted_factual_evidence_ids':factual['required_evidence_ids'],
                'source_gaps':deepcopy(factual['gaps'])}
            # Step registry governs procedures ONLY. Descriptive facts above do
            # not depend on overlap, question wording, step approval, or claims.
            candidates=[sid for sid,raw in r.candidate['steps'].items() if
                raw['kind'] in ('ACTION','SAFETY_STOP') and ids&set(raw['action_evidence_ids'])]
            session=replace(session,current_symptoms=tuple(sorted({tag for sid in candidates for tag in r.step(sid).symptom_tags})))
            exhausted=exhausted_after_unresolved(r,session)
            admitted=[];clarifications={}
            for sid in candidates:
                raw=r.candidate['steps'][sid]
                rid=raw.get('canonical_record_id')
                if rid in getattr(r,'_bound',{}) and not r._scope_intact(rid):
                    raise ValidationFailure('ACTION_AUTHORITY_CHANGED')
                if not r.step_ready(sid):continue
                if exhausted and raw['kind']=='ACTION':continue
                decision=c.eligible(session,sid)
                try:
                    for eid in r.step(sid).required_evidence_ids:context_for(r,eid)
                except ValidationFailure as exc:
                    if str(exc)=='SOURCE_CONTEXT_REVIEW_REQUIRED':continue
                    raise
                if decision.eligibility_status==Truth.UNKNOWN and not exhausted:
                    for row in decision.condition_results:
                        rule=r.rule(row['rule_id'])
                        if (row['result']=='UNKNOWN' and rule.rider_resolvable and rule.clarification_question and
                            all(r.evidence_ready(e) for e in rule.clarification_evidence_ids)):
                            clarifications[rule.rule_id]={'question':rule.clarification_question,'step_id':sid,
                                'scope_kind':raw['kind'],'condition_fact_key':rule.fact_key,
                                'condition_evidence_ids':list(rule.source_evidence_ids)}
                if decision.eligibility_status!=Truth.TRUE:continue
                assembled=self.retriever.search(query,dependency_manifest=r.retrieval_manifest(sid),step_id=sid,
                    scope=self.scope(),applicability_status='CONFIRMED')
                if assembled.get('manual_checksum')!=r.checksum or assembled.get('index_id')!=r.index_id:
                    raise ValidationFailure('INVALID_BUNDLE_IDENTITY')
                if assembled.get('retrieval_action')!='CONTINUE_GATES':raise ValidationFailure('RETRIEVAL_SCHEDULING_UNRESOLVED')
                if (assembled.get('conflicts') or assembled.get('source_review_required') or
                    not assembled.get('coverage_established') or not set(r.step(sid).required_evidence_ids)<=
                    set(assembled.get('attached_evidence_ids',[]))):continue
                admitted.append(sid)
            positions={e:i for i,h in reversed(list(enumerate(bundle.get('hits',[])))) for e in h.get('evidence_ids',[])}
            def rank(sid):return (min((positions.get(e,999) for e in r.step(sid).action_evidence_ids),default=999),sid)
            actions=sorted((s for s in admitted if r.step(s).kind=='ACTION'),key=rank)[:1]
            stops=sorted((s for s in admitted if r.step(s).kind=='SAFETY_STOP'),key=rank)[:2]
            admitted=stops+actions
            composer.scopes=tuple(admitted);composer.clarifications=clarifications
            if factual.get('evidence') or admitted:
                response=composer.compose_generic(c,session,factual,admitted,query,clarifications)
                if response.type==ResponseType.SUPPORTED and response.suggested_step_id:
                    sid=response.suggested_step_id
                    session=append_attempt(session,sid,Outcome.NOT_TRIED,'issued:'+response.trace_id,
                        applicability_symptoms=tuple(r.step(sid).symptom_tags))
                    session=replace(session,pending_step_id=sid)
                elif response.type==ResponseType.AMBIGUOUS:
                    rid=response.reason_codes[-1]
                    session=replace(session,pending_step_id=clarifications[rid]['step_id'],pending_rule_id=rid)
            elif clarifications:
                rid=sorted(clarifications)[0];q=clarifications[rid]
                session=replace(session,pending_step_id=q['step_id'],pending_rule_id=rid)
                response=c.response('AMBIGUOUS',q['question'],session,clarification_question=q['question'],reason_codes=('UNKNOWN_OBSERVATION',))
            else:
                code='NO_APPROVED_NEXT_STEP_AFTER_UNRESOLVED_ACTION' if exhausted else 'NO_ADMITTED_MANUAL_EVIDENCE'
                response=c.response('UNSUPPORTED','I could not assemble complete applicable manual evidence for this question. Contact OEM or authorised service support.',session,reason_codes=(code,))
        except Exception as exc:
            response=c.response('SYSTEM_ERROR','I am temporarily unable to verify the manual evidence.',session,
                reason_codes=(str(exc) if isinstance(exc,ValidationFailure) else 'QUESTION_RETRIEVAL_FAILURE',))
        try:return self._view(session,response)
        except Exception as exc:
            composer.last_admitted=None
            response=c.response('SYSTEM_ERROR','I am temporarily unable to validate the source citations.',session,
                reason_codes=(str(exc) if isinstance(exc,ValidationFailure) else 'PRESENTATION_BINDING_FAILURE',))
            return self._view(session,response)

    def feedback(self,session,query):
        # Safety/integrity checks are inside the error boundary here too.
        c=self.controller;composer=c.response_generator
        composer.query=query;composer.last_trace=None;composer.last_admitted=None
        composer.last_source_admission=None
        try:
            if not self.registry.source_ready():raise ValidationFailure('SOURCE_IDENTITY_CHANGED')
            safety=self.known_safety(session)
            if safety:return self._view(*safety)
            if session.status=='CUSTOMER_REPORTED_RESOLVED':
                return self._view(session,c.response('SUPPORTED','You reported the symptom resolved; the repair and cause have not been mechanically verified.',session))
            if exhausted_after_unresolved(self.registry,session):
                return self._view(session,c.response('UNSUPPORTED','The documented action remains unresolved. No further approved step is available in this path; contact OEM or authorised service support.',session,
                    reason_codes=('NO_APPROVED_NEXT_STEP_AFTER_UNRESOLVED_ACTION',)))
            prior=next((a for a in reversed(session.active_attempts()) if a.step_id in self.registry.candidate['steps']),None)
            if prior:session=replace(session,current_symptoms=tuple(self.registry.step(prior.step_id).symptom_tags))
            session,response,_=c.next(session,query)
            return self._view(session,response)
        except Exception as exc:
            composer.last_admitted=None
            return self._view(session,c.response('SYSTEM_ERROR','I am temporarily unable to verify the documented transition.',session,
                reason_codes=(str(exc) if isinstance(exc,ValidationFailure) else 'FEEDBACK_INTEGRITY_FAILURE',)))
