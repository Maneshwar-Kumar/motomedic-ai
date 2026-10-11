"""Open-question evidence admission and grounded composition.

Schema/citation/step checks are deterministic boundaries, NOT entailment proof.
Original-page claim review happens offline in evaluation; no online verifier.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
import re
import time
from controller_contracts import ResponseType, Truth, Outcome
from constrained_generator import ValidationFailure, envelope
from evidence_registry import content_hash
from reviewed_controller import ReviewedController, start_session, append_attempt
from cloud.arm_a.runtime_controls import diagnostic_projection
from cloud.grounded_generation.policy import VERSION, POLICY, POLICY_SHA256, SCHEMA
from cloud.grounded_generation.provider import GemmaProvider, ProviderFailure, MODEL

@dataclass(frozen=True)
class Config:
    controls_version: str = VERSION
    def versions(self):
        return {'version':VERSION,'model':MODEL,'policy_sha256':POLICY_SHA256,
            'input_tokens':8192,'request_bytes':24000,'output_tokens':1800,
            'question_admission':'RETRIEVED_REVIEWED_EVIDENCE_NOT_QUESTION_WORDING',
            'response_cache':'REVIEWED_EXACT_QUERY_SCOPE_STATE_ONLY_V1',
            'prompt_cache':'CAPABILITY_GATED_VERSIONED_EVIDENCE_PREFIX_V1',
            'verifier_calls':0,'validation':'DETERMINISTIC_NOT_SEMANTIC_PROOF'}
    @property
    def lock(self): return content_hash(self.versions())

def scope_payload(controller, session, sid):
    # Reuse binding/eligibility/dependency/mandatory-role checks. Exact wording
    # membership is deliberately NOT applied to generated technical claims.
    allowed=envelope(controller,session,sid,allow_approved_policy_caveats=True)
    step=controller.registry.step(sid)
    required=[deepcopy(c) for c in step.claims if c['response_role'] in ('WARNING','PREREQUISITE')
              or not c['evidence_ids']]
    return {'scope_id':sid,'kind':step.kind,'required_evidence_ids':list(step.required_evidence_ids),
        'permitted_action_evidence_ids':list(step.action_evidence_ids) if step.kind=='ACTION' else [],
        'required_display':required,'citation_mapping':allowed['citations']}

def check_output(draft, scopes, clarifications):
    if type(draft) is not dict or set(draft)!=set(SCHEMA['properties']): raise ValidationFailure('OUTPUT_SCHEMA')
    if draft['route'] not in ('SUPPORTED','AMBIGUOUS','UNSUPPORTED','SAFETY_STOP'): raise ValidationFailure('OUTPUT_ROUTE')
    if (type(draft['scope_ids']) is not list or type(draft['claims']) is not list or
        type(draft['step_id']) is not str or type(draft['clarification_id']) is not str or
        any(type(s) is not str for s in draft['scope_ids'])): raise ValidationFailure('OUTPUT_SCHEMA')
    if draft['route']=='SAFETY_STOP':
        if (draft['claims'] or draft['clarification_id'] or draft['scope_ids']!=[draft['step_id']] or
            draft['step_id'] not in scopes or scopes[draft['step_id']]['kind']!='SAFETY_STOP'):
            raise ValidationFailure('UNADMITTED_SAFETY_STOP')
        return draft
    if draft['route']!='SUPPORTED':
        if draft['claims'] or draft['scope_ids'] or draft['step_id']: raise ValidationFailure('NON_SUPPORTED_TECHNICAL_CONTENT')
        if draft['route']=='AMBIGUOUS':
            if draft['clarification_id'] not in clarifications: raise ValidationFailure('UNADMITTED_CLARIFICATION')
        elif draft['clarification_id']: raise ValidationFailure('OUTPUT_SCHEMA')
        return draft
    selected=draft['scope_ids']
    if not selected or len(set(selected))!=len(selected) or not set(selected)<=set(scopes) or any(scopes[s]['kind']=='SAFETY_STOP' for s in selected): raise ValidationFailure('UNADMITTED_SCOPE')
    if draft['clarification_id'] or not 1<=len(draft['claims'])<=12: raise ValidationFailure('OUTPUT_SCHEMA')
    actions=[sid for sid in selected if scopes[sid]['kind']=='ACTION']
    if len(actions)>1 or draft['step_id']!=(actions[0] if actions else ''): raise ValidationFailure('UNPERMITTED_STEP')
    permitted=set(e for sid in selected for e in scopes[sid]['required_evidence_ids'])
    for claim in draft['claims']:
        if type(claim) is not dict or set(claim)!={'text','role','evidence_ids'}: raise ValidationFailure('OUTPUT_SCHEMA')
        text,ids=claim['text'],claim['evidence_ids']
        if (type(text) is not str or not text.strip() or len(text)>2400 or '?' in text or
            type(ids) is not list or not ids or any(type(e) is not str for e in ids) or
            len(ids)!=len(set(ids)) or not set(ids)<=permitted): raise ValidationFailure('INVALID_CLAIM_CITATION')
        if claim['role'] not in ('FACT','ACTION'): raise ValidationFailure('UNPERMITTED_ROLE')
        if claim['role']=='ACTION' and (not actions or not set(ids)&set(scopes[actions[0]]['permitted_action_evidence_ids'])):
            raise ValidationFailure('UNPERMITTED_STEP')
    if sum(c['role']=='ACTION' for c in draft['claims'])!=len(actions): raise ValidationFailure('ONE_STEP_DISCIPLINE')
    # All selected scopes must contribute a cited claim; selection cannot smuggle
    # an irrelevant action into presentation or claim unearned source coverage.
    used=set(e for c in draft['claims'] for e in c['evidence_ids'])
    if any(not used&set(scopes[s]['required_evidence_ids']) for s in selected): raise ValidationFailure('UNUSED_SCOPE')
    return draft

class Composer:
    def __init__(self, provider, reviewed_cache=None):
        if reviewed_cache is not None: raise ValueError('Unbound response-cache entries are prohibited')
        self.config=Config()
        self.provider=provider
        # No generated response is auto-approved for response caching.
        self.reviewed_cache=reviewed_cache or {}
        self.last_trace=None
        self.query=''
        self.scopes=()
        self.clarifications={}

    def compose(self, controller, session, sid, **kwargs):
        return self.compose_many(controller,session,(sid,),self.query)

    def compose_many(self, controller, session, sids, query, clarifications=None):
        started=time.monotonic()
        trace={'runtime_lock':self.config.lock,'generation_calls':0,'verifier_calls':0,
            'response_cache':'MISS','deterministic_checks_prove_semantics':False}
        self.last_trace=trace
        try:
            if session.generation_lock!=self.config.lock: raise ValidationFailure('GENERATION_VERSION_RECONFIRM_REQUIRED')
            r=controller.registry
            scopes={sid:scope_payload(controller,session,sid) for sid in sids}
            required=set(e for s in scopes.values() for e in s['required_evidence_ids'])
            evidence={eid:{'type':r.evidence[eid].get('type'),
                'raw_object':deepcopy(r.evidence[eid]['raw_object']),
                'provenance':deepcopy(r.evidence[eid]['provenance'])} for eid in sorted(required)}
            stable={'contract':self.config.versions(),'manual_checksum':r.checksum,
                'index_id':r.index_id,'registry_lock':r.lock,'variant':session.bike_variant,
                'edition':session.edition,'scopes':scopes,'evidence':evidence}
            clarifications=clarifications or self.clarifications
            dynamic={'question':query,'typed_state':diagnostic_projection(session),
                'rider_resolvable_clarifications':clarifications}
            key=content_hash({'stable':stable,'dynamic':dynamic})
            if True:
                from flask import has_request_context,request
                enabled=has_request_context() and request.environ.get('arm_a_cache_enabled') is True
                from cloud.grounded_generation.response_cache import ReviewedResponses
                reviewed=ReviewedResponses(r,self.config.lock).get(query,session,scopes,self.config.lock) if enabled else None
                if reviewed:
                    _,count=self.provider.context(POLICY,stable,dynamic,SCHEMA)
                    trace.update(response_cache='EXACT_REVIEWED_HIT_REVALIDATED',
                        response_cache_authority=reviewed['authority_binding'],input_tokens_counted=count)
                    draft=reviewed['output']
                else:
                    result=self.provider.complete(POLICY,stable,dynamic,SCHEMA)
                    trace.update(result.telemetry or {})
                    draft=result.output
            check_output(draft,scopes,clarifications)
            # Fresh authority and full typed eligibility after the provider call.
            if {sid:scope_payload(controller,session,sid) for sid in sids}!=scopes:
                raise ValidationFailure('ADMITTED_CONTEXT_CHANGED')
            if any(not r.evidence_ready(eid) for eid in required): raise ValidationFailure('SOURCE_REVIEW_REQUIRED')
            if draft['route']=='SAFETY_STOP':
                return controller.render(session,draft['step_id'],safety=True)
            if draft['route']=='AMBIGUOUS':
                question=clarifications[draft['clarification_id']]['question']
                return controller.response('AMBIGUOUS',question,session,clarification_question=question,
                    reason_codes=('ADMITTED_RIDER_CLARIFICATION',draft['clarification_id']))
            if draft['route']=='UNSUPPORTED':
                return controller.response('UNSUPPORTED','The admitted manual evidence does not support an answer to this question.',
                    session,reason_codes=('MODEL_ABSTAINED_NO_SUPPORTED_ANSWER',))
            claims=[];pages=[]
            for i,c in enumerate(draft['claims']):
                claims.append({'claim_id':'generated:'+str(i),**deepcopy(c),
                    'presentation_mode':'GENERATED_PARAPHRASE'})
            mandatory={}
            for selected in draft['scope_ids']:
                for c in scopes[selected]['required_display']:
                    mandatory[c['claim_id']]=deepcopy(c)
                for page in scopes[selected]['citation_mapping']:
                    ref={**page,'manual_checksum':r.checksum,'index_id':r.index_id,'pdf_page_index':page['pdf_page']-1}
                    if ref not in pages: pages.append(ref)
            claims.extend(mandatory.values())
            full_text=' '.join(c['text'] for c in claims)
            if len(full_text.encode())>8000: raise ValidationFailure('PRESENTATION_BYTE_BOUND')
            final_count=self.provider.count({'contents':[{'role':'user','parts':[{'text':full_text}]}]})
            trace['presentation_tokens_counted']=final_count
            if final_count>1800: raise ValidationFailure('PRESENTATION_TOKEN_BOUND_NO_TRUNCATION')
            trace['selected_scope_ids']=draft['scope_ids']
            trace['complete_context_sha256']=content_hash(stable)
            response=controller.response('SUPPORTED',full_text,session,claim_evidence_map=tuple(claims),
                cited_pages=tuple(pages),suggested_step_id=draft['step_id'] or None,
                reason_codes=('GROUNDED_GENERATION_DETERMINISTIC_CHECKED',)+tuple('scope:'+s for s in draft['scope_ids']))
            return response
        except (ProviderFailure,ValidationFailure) as exc:
            if isinstance(exc,ProviderFailure): trace.update(getattr(self.provider,'last_trace',None) or {})
            code=str(exc)
            return controller.response('UNSUPPORTED' if code=='SOURCE_REVIEW_REQUIRED' else 'SYSTEM_ERROR',
                'The source scope needs review.' if code=='SOURCE_REVIEW_REQUIRED' else
                'I am temporarily unable to generate a validated answer.',session,reason_codes=(code,))
        except Exception:
            return controller.response('SYSTEM_ERROR','I am temporarily unable to generate a validated answer.',
                session,reason_codes=('GROUNDED_GENERATION_FAILURE',))
        finally: trace['server_composition_seconds']=time.monotonic()-started

class Questions:
    def __init__(self,registry,retriever,composer):
        self.registry,self.retriever=registry,retriever
        self.controller=ReviewedController(registry,retriever,response_generator=composer)
        self.controller.audience='end_user'
    def scope(self):
        r=self.registry
        return {'source_sha256':r.checksum,'manual_id':r.source['manual_id'],
            'variant':r.source['variant'],'edition':r.source['edition'],
            'language':r.source['language'],'motorcycle':r.source['motorcycle']}
    def new_session(self):
        return replace(start_session(self.registry,(),self.registry.source['variant'],self.registry.source['edition']),
            generation_lock=self.controller.response_generator.config.lock)
    def answer(self,session,query):
        c,r=self.controller,self.registry
        composer=c.response_generator
        composer.last_trace=None;composer.query=query;composer.scopes=();composer.clarifications={}
        session=replace(session,version=session.version+1,pending_step_id=None,pending_rule_id=None)
        try:
            if c.scope_status(session)!='CONFIRMED': raise ValidationFailure('SCOPE_NOT_CONFIRMED')
            bundle=self.retriever.search(query,limit=6,scope=self.scope(),applicability_status='CONFIRMED')
            if bundle.get('manual_checksum')!=r.checksum or bundle.get('index_id')!=r.index_id:
                raise ValidationFailure('INVALID_BUNDLE_IDENTITY')
            ids=set(e for hit in bundle.get('hits',[]) for e in hit.get('evidence_ids',[]))
            prior_unresolved=[a for a in session.active_attempts() if a.outcome_enum==Outcome.ACTION_COMPLETED_UNRESOLVED and
                a.step_id in r.candidate['steps'] and ids&set(r.step(a.step_id).action_evidence_ids)]
            if prior_unresolved:
                return self.feedback(session,query)
            # Runtime admission uses evidence identity only. No canonical question,
            # paraphrase, expected answer or lexical proposition comparison.
            candidates=[sid for sid in r.candidate['steps'] if
                ids&set(r.step(sid).action_evidence_ids) and r.step_ready(sid)]
            session=replace(session,current_symptoms=tuple(sorted(set(tag for sid in candidates for tag in r.step(sid).symptom_tags))))
            decisions=[c.eligible(session,sid) for sid in candidates]
            if True:
                admitted=[];clarifications={}
                for decision in decisions:
                    sid=decision.step_id
                    if decision.eligibility_status==Truth.UNKNOWN:
                        for row in decision.condition_results:
                            rule=r.rule(row['rule_id'])
                            if row['result']=='UNKNOWN' and rule.rider_resolvable and rule.clarification_question and all(r.evidence_ready(e) for e in rule.clarification_evidence_ids):
                                clarifications[rule.rule_id]={'question':rule.clarification_question,'step_id':sid}
                    if decision.eligibility_status!=Truth.TRUE: continue
                    assembled=self.retriever.search(query,dependency_manifest=r.retrieval_manifest(sid),
                        step_id=sid,scope=self.scope(),applicability_status='CONFIRMED')
                    if (assembled.get('manual_checksum')!=r.checksum or assembled.get('index_id')!=r.index_id): raise ValidationFailure('INVALID_BUNDLE_IDENTITY')
                    if (assembled.get('conflicts') or assembled.get('source_review_required') or not assembled.get('evidence_sufficient') or
                        not set(r.step(sid).required_evidence_ids)<=set(assembled.get('attached_evidence_ids',[]))): continue
                    admitted.append(sid)
                # One action per turn; deterministic stable product ordering, not
                # a claim about OEM ranking. All admitted factual scopes can combine.
                actions=sorted(sid for sid in admitted if r.step(sid).kind=='ACTION')
                admitted=sorted(sid for sid in admitted if r.step(sid).kind in ('LOOKUP','SAFETY_STOP'))+actions[:1]
                composer.scopes=tuple(admitted);composer.clarifications=clarifications
                if admitted:
                    response=composer.compose_many(c,session,admitted,query,clarifications)
                    if response.type==ResponseType.SUPPORTED and response.suggested_step_id:
                        sid=response.suggested_step_id
                        session=append_attempt(session,sid,Outcome.NOT_TRIED,'issued:'+response.trace_id,
                            applicability_symptoms=tuple(r.step(sid).symptom_tags))
                        session=replace(session,pending_step_id=sid)
                    elif response.type==ResponseType.AMBIGUOUS:
                        rule_id=response.reason_codes[-1]
                        session=replace(session,pending_step_id=clarifications[rule_id]['step_id'],pending_rule_id=rule_id)
                elif clarifications:
                    rule_id=sorted(clarifications)[0];q=clarifications[rule_id]
                    session=replace(session,pending_step_id=q['step_id'],pending_rule_id=rule_id)
                    response=c.response('AMBIGUOUS',q['question'],session,clarification_question=q['question'],reason_codes=('UNKNOWN_OBSERVATION',))
                else:
                    response=c.response('UNSUPPORTED','I could not assemble complete, applicable reviewed manual evidence for this question.',
                        session,reason_codes=('NO_ADMITTED_MANUAL_EVIDENCE',))
        except Exception as exc:
            response=c.response('SYSTEM_ERROR','I am temporarily unable to verify the manual evidence.',session,
                reason_codes=(str(exc) if isinstance(exc,ValidationFailure) else 'QUESTION_RETRIEVAL_FAILURE',))
        from cloud.grounded_generation.presentation import saved_view
        view,choices=saved_view(r,session,response)
        view['runtime_controls']={'composition':composer.last_trace,'retrieval':getattr(self.retriever,'last_cache_trace',None)}
        view['provider_calls']=(composer.last_trace or {}).get('generation_calls',0)
        return session,view,choices

    def feedback(self,session,query):
        composer=self.controller.response_generator
        composer.query=query;composer.scopes=();composer.clarifications={};composer.last_trace=None
        session,response,_=self.controller.next(session,query)
        from cloud.grounded_generation.presentation import saved_view
        view,choices=saved_view(self.registry,session,response)
        view['runtime_controls']={'composition':composer.last_trace}
        view['provider_calls']=(composer.last_trace or {}).get('generation_calls',0)
        return session,view,choices
