"""Hosted generic rider acceptance; this module is never imported by serving code.

Runtime is frozen before evaluation questions are authored. Original-page claim
adjudication is a separate offline step; route matches cannot grant acceptance.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import Flask
from approved_registry import ApprovedEvidenceRegistry
from online_retrieve import Retriever
from cloud.grounded_generation.verified_qa import Composer, Config, DRAFT_SCHEMA, VERIFY_SCHEMA
from cloud.grounded_generation.open_questions import Questions
from cloud.grounded_generation.delivery import bind_view, accepted_events, response_hash
from cloud.grounded_generation.source_authority import SourceAuthority
from cloud.grounded_generation.provider import GemmaProvider, HTTP, MODEL, ProviderFailure
from generation_providers import ProviderResult
from controller_contracts import Fact, Outcome
from reviewed_controller import append_attempt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/draft-verify-stream-result.json'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def jsonable(value):
    return json.loads(json.dumps(value, default=lambda x:x.value if hasattr(x,'value') else str(x)))

def main():
    if os.environ.get('MOTOMEDIC_GROUNDED_LIVE_AUTHORIZED')!='1':
        raise RuntimeError('HOSTED_PROVIDER_RUN_NOT_AUTHORIZED')
    manifest_path=ROOT/os.environ.get('MOTOMEDIC_EVAL_MANIFEST','reports/grounded_generation/v6/runtime_manifest.json')
    manifest=json.loads(manifest_path.read_bytes())
    for name,digest in manifest['file_sha256'].items():
        if sha(ROOT/name)!=digest: raise RuntimeError('FROZEN_RUNTIME_CHANGED:'+name)
    dataset_path=ROOT/manifest['heldout_path']
    if sha(dataset_path)!=manifest['heldout_sha256']: raise RuntimeError('HELDOUT_CHANGED')
    dataset=json.loads(dataset_path.read_bytes())
    if dataset['serving_freeze_manifest_sha256']!=manifest['serving_freeze_manifest_sha256']:
        raise RuntimeError('HOLDOUT_FREEZE_BINDING')
    index=ROOT/'build/index'
    initialization_at=time.monotonic()
    registry=ApprovedEvidenceRegistry.load(ROOT,index)
    authority=SourceAuthority(registry,index)
    retriever=Retriever(index,rerank=True)
    reservations=[]
    reservation_rejections=[]
    synthetic_outputs=[]
    quota_window=[]
    transports=[]
    injected=[None]
    current=[None]

    def reserve(tokens,kind):
        if injected[0]=='reservation_budget':
            reservation_rejections.append({'case_turn':current[0],'tokens':tokens,'kind':kind,'reason':'PROVIDER_DAILY_OR_RATE_LIMIT'})
            raise ProviderFailure('PROVIDER_DAILY_OR_RATE_LIMIT')
        if injected[0]=='reservation_store':
            reservation_rejections.append({'case_turn':current[0],'tokens':tokens,'kind':kind,'reason':'PROVIDER_ADMISSION_STORE_UNAVAILABLE'})
            raise ProviderFailure('PROVIDER_ADMISSION_STORE_UNAVAILABLE')
        if len(reservations)>=50 or sum(x['tokens'] for x in reservations)+tokens>499600:
            raise ProviderFailure('EVALUATION_SPEND_BOUND')
        # Hosted evaluation-only pacing. Keep pacing duration in the record;
        # it is not a production latency result or a verified account entitlement.
        paced=0.0
        while True:
            now=time.monotonic()
            quota_window[:]=[(at,n) for at,n in quota_window if at>now-60]
            if sum(n for _,n in quota_window)+tokens<=10000 and len(quota_window)<6:break
            delay=max(0.01,60-(now-quota_window[0][0]))
            time.sleep(delay);paced+=delay
        quota_window.append((time.monotonic(),tokens))
        reservations.append({'case_turn':current[0],'tokens':tokens,'kind':kind,'evaluation_pacing_seconds':paced})

    class RecordingHTTP(HTTP):
        def __call__(self,method,path,body,key):
            is_generation=path.endswith(':generateContent')
            record={'case_turn':current[0],'method':method,'path':path}
            if is_generation:
                # No request/key retained. Output contains only authored test
                # turns and engineering-authorized manual context.
                record['generation_config']=body.get('generationConfig',{})
                record['pipeline_role']='VERIFICATION' if 'decision' in body.get('generationConfig',{}).get('responseJsonSchema',{}).get('properties',{}) else 'DRAFTING'
            started=time.monotonic()
            try:
                if is_generation and (injected[0]=='provider_timeout' or injected[0]=='verifier_timeout' and record.get('pipeline_role')=='VERIFICATION'):
                    raise ProviderFailure('PROVIDER_TRANSPORT_OR_SCHEMA_FAILURE')
                if is_generation and injected[0]=='provider_500':
                    raise ProviderFailure('PROVIDER_HTTP_500')
                value=super().__call__(method,path,body,key)
                if is_generation:record['actual_model_output']=value
                elif path.endswith(':countTokens'):record['total_tokens']=value.get('totalTokens')
                return value
            except ProviderFailure as exc:
                record['failure_reason']=str(exc);raise
            finally:
                record['seconds']=time.monotonic()-started
                transports.append(record)

    provider=GemmaProvider(reserve,transport=RecordingHTTP(),cache_capability='unsupported')
    questions=Questions(registry,retriever,Composer(provider,source_authority=authority),source_authority=authority)
    app=Flask(__name__)
    worker_initialization_seconds=time.monotonic()-initialization_at
    result={'schema_version':'draft-verify-stream-acceptance-v6','model':MODEL,
        'runtime_lock':Config().lock,'runtime_manifest_sha256':sha(manifest_path),
        'serving_freeze_manifest_sha256':manifest['serving_freeze_manifest_sha256'],
        'heldout_sha256':sha(dataset_path),'manual_checksum':registry.checksum,'index_id':registry.index_id,
        'semantic_verifier_calls':'MEASURED_PER_ROW','build_environment':'GITHUB_HOSTED',
        'retrieval_execution':'HOSTED_IMMUTABLE_INDEX_SNAPSHOT_BGE_M3_BM25_SAME_SELECTED_INDEX',
        'qdrant_service_changed':False,'deployment_changed':False,
        'monetary_cost':'NOT_OBSERVED_NO_PRICE_OR_CORRECTNESS_ASSUMPTION',
        'latency_scope':'HOSTED_EVALUATION_PIPELINE_NOT_DEPLOYED_CLOUD_RUN',
        'reserved_call_cap':50,'reserved_token_cap':499600,'public_access_opened':False,
        'provider_prompt_cache':{'capability':'UNSUPPORTED_EXACT_MODEL_ACCOUNT_PREVIOUS_404','cached_tokens':0,'savings_claimed':False},
        'worker_initialization_seconds':worker_initialization_seconds,
        'claim_review_status':'PENDING_INDEPENDENT_ORIGINAL_PAGE_REVIEW',
        'acceptance':'PENDING_QUALITY_REVIEW_NOT_GRANTED_BY_SOFTWARE_SUCCESS','rows':[]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    def save():
        result['provider_reservations']=reservations
        result['provider_transports']=transports
        result['reservation_rejections']=reservation_rejections
        result['synthetic_outputs']=synthetic_outputs
        OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        lines=['# Generic rider acceptance: actual execution', '',
            'Acceptance: '+result['acceptance']+'. Public access remains closed.', '',
            'Route execution is separate from completeness and original-page claim support. Synthetic faults are separate from natural question coverage.', '']
        for row in result['rows']:
            lines.extend(['## '+row['case_id']+' turn '+str(row['turn_number']), '',
                'Cohort: '+row['cohort']+'. Expected route: '+row['expected_route']+'. Actual route: '+row['view']['response']['type']+'.', '',
                'Rider: '+row['rider_question'], '',
                'Actual served output: '+row['actual_rider_output'], '',
                'Original-page completeness and claim review: PENDING.', ''])
            if row['withheld']:
                lines.extend(['Withheld reasons / execution trace:', '```json',
                    json.dumps(row['withheld_reasons'],indent=2,ensure_ascii=False),'```',''])
            for output in row['actual_provider_outputs']:
                lines.extend(['Actual model output (evaluation-only, including output withheld by runtime):',
                    '```json',json.dumps(output['actual_model_output'],indent=2,ensure_ascii=False),'```',''])
        (OUT.parent/'draft-verify-stream-report.md').write_text('\n'.join(lines),encoding='utf-8')

    original_count=provider.count
    original_complete=provider.complete
    probe_used=[False]
    save()
    for case in dataset['cases']:
        session=questions.new_session()
        conversation=[]
        for key,value in case.get('typed_facts',{}).items():
            rules=[rid for rid in registry.candidate['rules'] if registry.rule(rid).fact_key==key]
            if not rules:raise RuntimeError('FIXTURE_FACT_NOT_REGISTERED:'+key)
            session=append_attempt(session,'eval-observation:'+key,Outcome.OBSERVED_NORMAL,
                'eval:'+case['case_id']+':'+key,condition_id=rules[0],
                facts=((key,Fact(value,'BOOLEAN' if type(value)is bool else 'ENUM')),))
        prior=case.get('prior_attempt')
        if prior:
            sids=[sid for sid in registry.candidate['steps'] if registry.step(sid).step_id==prior['step_record'] or
                registry.candidate['steps'][sid]['canonical_record_id']==prior['step_record']]
            if len(sids)!=1:raise RuntimeError('FIXTURE_STEP_NOT_UNIQUE:'+prior['step_record'])
            session=append_attempt(session,sids[0],Outcome(prior['outcome']),'eval:'+case['case_id']+':prior')
        for turn_number,turn in enumerate(case['turns'],1):
            current[0]=case['case_id']+':'+str(turn_number)
            injected[0]=turn.get('fault_injection')
            probe_used[0]=False
            probe=turn.get('verifier_probe')
            if probe:
                def forced_draft(policy,evidence,dynamic,schema):
                    if schema!=DRAFT_SCHEMA or probe_used[0]:
                        return original_complete(policy,evidence,dynamic,schema)
                    probe_used[0]=True
                    ids=list(evidence['evidence'])
                    if not ids:raise RuntimeError('PROBE_HAS_NO_ADMITTED_SOURCE')
                    eid=next((e for e in ids if probe['source_hint'].casefold() in json.dumps(evidence['evidence'][e]).casefold()),ids[0])
                    output={'route':probe.get('route','SUPPORTED'),'coverage':'COMPLETE',
                        'claims':[{'text':probe['private_proposed_text'],'role':probe.get('role','FACT'),'evidence_ids':[eid]}],
                        'unanswered_parts':[],'clarification_question':'','rider_resolvable':False}
                    synthetic_outputs.append({'case_turn':current[0],'output':output,'actual_model_output':False,'purpose':'INDEPENDENT_REAL_VERIFIER_CHALLENGE'})
                    return ProviderResult(output,telemetry={'generation_calls':0,'synthetic_draft_only':True})
                provider.complete=forced_draft
            if injected[0]=='context_overflow':provider.count=lambda body:8193
            if injected[0]=='legacy_v5_unknown_citation_unused':
                def invalid(policy,evidence,dynamic,schema):
                    output={'route':'SUPPORTED','step_id':'','clarification_id':'',
                        'claims':[{'text':'Injected citation fault.','role':'FACT','evidence_ids':['invented-source-id']}]}
                    synthetic_outputs.append({'case_turn':current[0],'output':output,'actual_model_output':False})
                    return ProviderResult(output)
                provider.complete=invalid
            before_transport=len(transports);before_reserve=len(reservations)
            started=time.monotonic()
            progress=[]
            final_view_seconds=[0.0]
            original_view=questions._view
            def timed_view(*args,**kwargs):
                at=time.monotonic()
                try:return original_view(*args,**kwargs)
                finally:final_view_seconds[0]+=time.monotonic()-at
            questions._view=timed_view
            def record_progress(stage):
                progress.append({'stage':stage,'seconds':time.monotonic()-started})
            with app.test_request_context(environ_overrides={'arm_a_cache_enabled':False}):
                updated,view,_=questions.answer(session,turn['rider_question'],history=conversation,progress=record_progress,operation_id=current[0])
            elapsed=time.monotonic()-started
            questions._view=original_view
            integrity_at=time.monotonic()
            view=bind_view(view,current[0],updated.generation_lock)
            final_integrity_seconds=time.monotonic()-integrity_at
            save_at=time.monotonic()
            operation_path=ROOT/'build'/('accepted-operation-'+case['case_id']+'-'+str(turn_number)+'.json')
            with operation_path.open('w',encoding='utf-8') as handle:
                handle.write(json.dumps(view,ensure_ascii=False));handle.flush();os.fsync(handle.fileno())
            durable_save_seconds=time.monotonic()-save_at
            recovered=json.loads(operation_path.read_text(encoding='utf-8'))
            events=[];first_answer=None
            for event in accepted_events(recovered,current[0]):
                if event[0]=='answer_chunk' and first_answer is None:
                    first_answer=time.monotonic()-started
                events.append(event)
            completion_seconds=time.monotonic()-started
            streamed=''.join(body['text'] for kind,body in events if kind=='answer_chunk')
            # First verified answer is recorded at actual buffer event emission, never progress.
            parity=(recovered==view and (streamed==view['response']['natural_language'] if view['response'].get('release_gate_passed') else not streamed))
            if not parity:raise RuntimeError('ACCEPTED_STREAM_RECOVERY_PARITY')
            private=deepcopy(questions.controller.response_generator.last_private_attempts)
            row={'case_id':case['case_id'],'cohort':case['cohort'],'turn_number':turn_number,
                'rider_question':turn['rider_question'],'actual_rider_output':view['response']['natural_language'],
                'view':view,'wall_seconds_including_eval_pacing':elapsed,
                'progress_events':progress,'first_progress_seconds':progress[0]['seconds'] if progress else None,
                'first_verified_answer_seconds_including_eval_pacing':first_answer,
                'worker_temperature':'COLD_FIRST_QUERY_AFTER_INITIALIZATION' if not result['rows'] else 'WARM_REUSED_WORKER',
                'full_answer_completion_seconds_including_eval_pacing':completion_seconds,
                'final_view_validation_seconds':final_view_seconds[0],
                'final_integrity_seconds':final_integrity_seconds,'durable_save_seconds':durable_save_seconds,
                'durable_store':'HOSTED_EVALUATION_FSYNC_FILE_NOT_PRODUCTION_FIRESTORE',
                'accepted_streamed_recovered_equal':parity,
                'private_drafts_and_verifier_decisions':private,
                'runtime_controls':view.get('runtime_controls',{}),
                'expected_route':turn['expected_route'],'route_matches':view['response']['type']==turn['expected_route'],
                'answerable_denominator':turn.get('answerable_denominator',False),
                'fault_injection':injected[0],'verifier_probe':probe,
                'expected_initial_verifier_decision':turn.get('expected_initial_verifier_decision'),
                'initial_verifier_decision':private[0].get('verdict',{}).get('decision') if private else None,
                'pipeline_latency_excluding_evaluation_pacing_seconds':elapsed-sum(r['evaluation_pacing_seconds'] for r in reservations[before_reserve:]),'actual_provider_outputs':[t for t in transports[before_transport:] if 'actual_model_output' in t],
                'provider_transport_records':transports[before_transport:],
                'reservation_records':reservations[before_reserve:],
                'reservation_rejections':[r for r in reservation_rejections if r['case_turn']==current[0]],
                'synthetic_provider_outputs':[r for r in synthetic_outputs if r['case_turn']==current[0]],
                'typed_history_before':jsonable([asdict(a) for a in session.attempted_steps]),
                'typed_history_after':jsonable([asdict(a) for a in updated.attempted_steps]),
                'active_outcomes_after':[a.outcome_enum.value for a in updated.active_attempts()],
                'semantic_claim_review':'PENDING','complete_answer_review':'PENDING',
                'withheld':view['response']['type'] in ('SYSTEM_ERROR','UNSUPPORTED'),
                'withheld_reasons':view.get('runtime_controls',{})}
            result['rows'].append(row);save()
            session=updated
            conversation.append({'question':turn['rider_question'],'response':view['response']['natural_language'],'route':view['response']['type']})
            provider.count=original_count;provider.complete=original_complete;injected[0]=None
    result['completed_at_utc']=datetime.now(timezone.utc).isoformat()
    result['route_matches']=sum(r['route_matches'] for r in result['rows'])
    answerable=[r for r in result['rows'] if r['answerable_denominator']]
    result['answerable_route_coverage']={'supported':sum(r['view']['response']['type']=='SUPPORTED' for r in answerable),'total':len(answerable)}
    result['answerable_complete_coverage']='PENDING_ORIGINAL_PAGE_QUALITY_REVIEW'
    result['unsupported_claims']='PENDING_ORIGINAL_PAGE_QUALITY_REVIEW'
    result['fresh_unseen_supported_reached_answer_llm']=any(r['cohort']=='fresh_holdout' and
        r['view']['response']['type']=='SUPPORTED' and r['view'].get('provider_calls',0)>0 for r in result['rows'])
    save()
    print(json.dumps({'execution_completed':True,'turns':len(result['rows']),'route_matches':result['route_matches'],
        'fresh_unseen_supported_reached_answer_llm':result['fresh_unseen_supported_reached_answer_llm'],
        'generation_reservations':len(reservations),'acceptance':'PENDING_QUALITY_REVIEW'}))

if __name__=='__main__':main()
