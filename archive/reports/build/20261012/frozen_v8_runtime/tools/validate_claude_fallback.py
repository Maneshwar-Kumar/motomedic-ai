"""Hosted Haiku fallback validation only; no deployment or source rebuilding."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,os,time,hashlib
from datetime import datetime,timezone
from copy import deepcopy
from flask import Flask
from approved_registry import ApprovedEvidenceRegistry
from online_retrieve import Retriever
from cloud.grounded_generation.verified_qa import Composer,Config
from cloud.grounded_generation.open_questions import Questions
from cloud.grounded_generation.source_authority import SourceAuthority
from cloud.grounded_generation.claude_provider import ClaudeProvider,HTTP,MODEL,MAX_CALL_USD
from cloud.grounded_generation.fallback_provider import FallbackProvider
from cloud.grounded_generation.delivery import bind_view,accepted_events
from generation_providers import ProviderFailure
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/claude-fallback-result.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
class UnavailablePrimary:
    """Synthetic unavailability exercises actual fallback, without a paid Gemma call."""
    last_trace=None
    def count(self,body):raise ProviderFailure('PROVIDER_HTTP_500')
    def complete(self,*args):
        self.last_trace={'model':'gemma-4-26b-a4b-it','generation_calls':0,'synthetic_availability_failure':True}
        raise ProviderFailure('PROVIDER_HTTP_500')
def main():
    if os.environ.get('MOTOMEDIC_CLAUDE_VALIDATION_AUTHORIZED')!='1':raise RuntimeError('CLAUDE_RUN_NOT_AUTHORIZED')
    mp=ROOT/'reports/grounded_generation/v8/runtime_manifest.json';manifest=json.loads(mp.read_bytes())
    for name,digest in manifest['file_sha256'].items():
        if sha(ROOT/name)!=digest:raise RuntimeError('FROZEN_RUNTIME_CHANGED:'+name)
    dp=ROOT/manifest['heldout_path']
    if sha(dp)!=manifest['heldout_sha256']:raise RuntimeError('HELDOUT_CHANGED')
    dataset=json.loads(dp.read_bytes())
    if dataset['serving_freeze_manifest_sha256']!=manifest['serving_freeze_manifest_sha256']:raise RuntimeError('FREEZE_BINDING')
    transports=[];reservations=[];money=[];quota=[];current=[None]
    result={'schema_version':'claude-fallback-hosted-execution-v8','runtime_manifest_sha256':sha(mp),'heldout_sha256':sha(dp),
        'model':MODEL,'primary_availability_fault':'SYNTHETIC_NO_PAID_GEMMA_CALL','fallback_calls':'ACTUAL_ANTHROPIC',
        'maximum_validation_cost_usd':1,'maximum_generation_attempts':24,'maximum_reserved_tokens':239808,
        'retrieval_execution':'HOSTED_IMMUTABLE_INDEX_SNAPSHOT_BGE_M3_BM25','durable_store':'HOSTED_FSYNC_NOT_FIRESTORE',
        'latency_scope':'HOSTED_HARNESS_NOT_DEPLOYED_CLOUD_RUN','deployment_changed':False,'billing_changed':False,
        'acceptance':'PENDING_INDEPENDENT_ORIGINAL_PAGE_REVIEW','rows':[]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    def save():
        result.update(provider_transports=transports,provider_reservations=reservations,cost_reservations=money)
        with OUT.open('w',encoding='utf-8') as f:
            f.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n');f.flush();os.fsync(f.fileno())
    def reserve_cost(amount,model):
        if model!=MODEL or sum(m['reserved_usd']for m in money)+amount>1:raise ProviderFailure('CLAUDE_SPEND_LIMIT')
        money.append({'case_turn':current[0],'reserved_usd':amount,'model':model});save()
    def reserve(tokens,kind):
        if len(reservations)>=24 or sum(r['tokens']for r in reservations)+tokens>239808:raise ProviderFailure('EVALUATION_SPEND_BOUND')
        paced=0.0
        while True:
            now=time.monotonic();quota[:]=[(at,n)for at,n in quota if at>now-60]
            if len(quota)<6 and sum(n for _,n in quota)+tokens<=10000:break
            delay=max(.01,60-(now-quota[0][0]));time.sleep(delay);paced+=delay
        quota.append((time.monotonic(),tokens));reservations.append({'case_turn':current[0],'tokens':tokens,'kind':kind,'evaluation_pacing_seconds':paced});save()
    class RecordingHTTP(HTTP):
        def __call__(self,method,path,body,key):
            at=time.monotonic();record={'case_turn':current[0],'path':path}
            if path=='messages':record['pipeline_role']='VERIFICATION' if 'decision'in body['output_config']['format']['schema']['properties']else'DRAFTING'
            try:
                value=super().__call__(method,path,body,key)
                if path=='messages':record['actual_model_output']=value
                else:record['input_tokens']=value.get('input_tokens')
                return value
            except ProviderFailure as exc:record['failure_code']=str(exc);raise
            finally:record['seconds']=time.monotonic()-at;transports.append(record);save()
    init=time.monotonic();index=ROOT/'build/index'
    registry=ApprovedEvidenceRegistry.load(ROOT,index);authority=SourceAuthority(registry,index);retriever=Retriever(index,rerank=True)
    provider=FallbackProvider(UnavailablePrimary(),ClaudeProvider(reserve,reserve_cost=reserve_cost,transport=RecordingHTTP()))
    questions=Questions(registry,retriever,Composer(provider,source_authority=authority),source_authority=authority)
    result.update(runtime_versions=Config(provider_contract=provider.contract).versions(),runtime_lock=questions.controller.response_generator.config.lock,
        worker_initialization_seconds=time.monotonic()-init)
    app=Flask(__name__);save()
    for case in dataset['cases']:
        session=questions.new_session();history=[]
        for number,turn in enumerate(case['turns'],1):
            current[0]=case['case_id']+':'+str(number);progress=[];at=time.monotonic();before=len(reservations)
            def stage(name):progress.append({'stage':name,'seconds':time.monotonic()-at})
            with app.test_request_context(environ_overrides={'arm_a_cache_enabled':False}):
                updated,view,_=questions.answer(session,turn['rider_question'],history=history,progress=stage,operation_id=current[0])
            private_seconds=time.monotonic()-at;view=bind_view(view,current[0],updated.generation_lock)
            saved_at=time.monotonic();op=ROOT/'build'/('claude-accepted-'+case['case_id']+'-'+str(number)+'.json')
            with op.open('w',encoding='utf-8')as f:f.write(json.dumps(view,ensure_ascii=False));f.flush();os.fsync(f.fileno())
            saved_seconds=time.monotonic()-saved_at;recovered=json.loads(op.read_bytes());chunks=[];first=None;events=[]
            for kind,body in accepted_events(recovered,current[0]):
                events.append(kind)
                if kind=='answer_chunk':
                    if first is None:first=time.monotonic()-at
                    chunks.append(body['text'])
            complete=time.monotonic()-at;released=view['response'].get('release_gate_passed',False)
            parity=recovered==view and (''.join(chunks)==view['response']['natural_language']if released else not chunks)
            if not parity:raise RuntimeError('ACCEPTED_STREAM_RECOVERY_PARITY')
            result['rows'].append({'case_id':case['case_id'],'turn_number':number,'rider_question':turn['rider_question'],
                'actual_rider_output':view['response']['natural_language'],'view':view,'progress_events':progress,
                'private_drafts_and_verifier_decisions':deepcopy(questions.controller.response_generator.last_private_attempts),
                'first_progress_seconds':progress[0]['seconds']if progress else None,
                'first_verified_answer_seconds_including_evaluation_pacing':first,
                'full_completion_seconds_including_evaluation_pacing':complete,'durable_save_seconds':saved_seconds,
                'private_pipeline_seconds_excluding_evaluation_pacing':private_seconds-sum(r['evaluation_pacing_seconds']for r in reservations[before:]),
                'accepted_streamed_recovered_equal':parity,'event_types':events,
                'original_pages_for_independent_review':turn['original_pages'],'expected_route':turn['expected_route'],
                'expected_coverage':turn.get('expected_coverage'),'semantic_claim_review':'PENDING','question_coverage_review':'PENDING'})
            session=updated;history.append({'question':turn['rider_question'],'response':view['response']['natural_language'],'route':view['response']['type']});save()
    result['completed_at_utc']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({'turns':len(result['rows']),'accepted':sum(r['view']['response'].get('release_gate_passed',False)for r in result['rows']),
        'generation_reservations':len(reservations),'reserved_usd':sum(m['reserved_usd']for m in money),'acceptance':result['acceptance']}))
if __name__=='__main__':main()
