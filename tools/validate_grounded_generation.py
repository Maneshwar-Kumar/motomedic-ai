"""Hosted, frozen held-out evaluation. Never imported by serving code."""
from datetime import datetime,timezone
from dataclasses import replace
import hashlib,json,os,time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import Flask
from approved_registry import ApprovedEvidenceRegistry
from online_retrieve import Retriever
from cloud.grounded_generation.runtime import Composer,Questions,Config
from cloud.grounded_generation.provider import GemmaProvider,HTTP,MODEL,ProviderFailure
from cloud.grounded_generation.policy import POLICY,SCHEMA
from controller_contracts import Fact,Outcome
from reviewed_controller import append_attempt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/grounded-generation-result.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assert os.environ.get('MOTOMEDIC_GROUNDED_LIVE_AUTHORIZED')=='1'
    manifest_path=ROOT/os.environ.get('MOTOMEDIC_EVAL_MANIFEST','reports/grounded_generation/v1/runtime_manifest.json')
    manifest=json.loads(manifest_path.read_bytes())
    for path,digest in manifest['file_sha256'].items():assert sha(ROOT/path)==digest,path
    dataset_path=ROOT/manifest.get('heldout_path','reports/grounded_generation/v1/heldout_cases.json')
    assert sha(dataset_path)==manifest['heldout_sha256']
    r=ApprovedEvidenceRegistry.load(ROOT,ROOT/'build/index')
    retriever=Retriever(ROOT/'build/index',rerank=True)
    calls=[];last=[0.0]
    def reserve(tokens,kind):
        assert len(calls)<40 and sum(x['tokens'] for x in calls)+tokens<=399680
        # Evaluation pacing models the documented 6/minute bound. It is not
        # added to production's request path or excluded from timing claims.
        wait=max(0,11-(time.monotonic()-last[0]))
        if wait:time.sleep(wait)
        calls.append({'tokens':tokens,'kind':kind});last[0]=time.monotonic()
    outputs=[]
    class RecordingHTTP(HTTP):
        def __call__(self,method,path,body,key):
            value=super().__call__(method,path,body,key)
            if path.endswith(':generateContent'):
                outputs.append({'evaluation_response':value})
            return value
    provider=GemmaProvider(reserve,transport=RecordingHTTP())
    app=Flask(__name__)
    q=Questions(r,retriever,Composer(provider))
    key=os.environ['MOTOMEDIC_GEMINI_API_KEY']
    capabilities={}
    http=HTTP()
    try:
        model=http('GET','models/'+MODEL,None,key)
        capabilities['supported_generation_methods']=model.get('supportedGenerationMethods',[])
    except ProviderFailure as exc:capabilities['model_metadata_error']=str(exc)
    try:
        cached=http('POST','cachedContents',{'model':'models/'+MODEL,
            'systemInstruction':{'parts':[{'text':POLICY}]},
            'contents':[{'role':'user','parts':[{'text':'Capability probe; no rider information or manual content.'}]}],
            'ttl':'60s'},key)
        capabilities['explicit_cache_probe']='ACCEPTED'
        http('DELETE',cached['name'],None,key)
    except ProviderFailure as exc:capabilities['explicit_cache_probe']=str(exc)
    result={'schema_version':'grounded-generation-heldout-v1','runtime_lock':Config().lock,
        'runtime_manifest_sha256':sha(manifest_path),
        'heldout_sha256':sha(dataset_path),'provider_capabilities':capabilities,
        'manual_checksum':r.checksum,'index_id':r.index_id,'rows':[],
        'semantic_verifier_calls':0,'public_access_opened':False,
        'raw_rider_data':'ONLY_AUTHORED_EVALUATION_QUESTIONS','claim_review_status':'PENDING_INDEPENDENT_ORIGINAL_PAGE_CHECK'}
    def save():
        result['provider_reservations']=calls
        result['evaluation_only_provider_outputs']=outputs
        OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    save()
    original_complete=provider.complete;original_count=provider.count
    for case in json.loads(dataset_path.read_bytes())['cases']:
        session=q.new_session()
        for fact_key,value in case.get('typed_facts',{}).items():
            rules=[rid for rid in r.candidate['rules'] if r.rule(rid).fact_key==fact_key]
            if not rules:continue
            session=append_attempt(session,'eval-observation:'+fact_key,Outcome.OBSERVED_NORMAL,
                'eval:'+case['case_id']+':'+fact_key,condition_id=rules[0],
                facts=((fact_key,Fact(value,'BOOLEAN' if type(value)is bool else 'ENUM')),))
        prior=case.get('prior_attempt')
        if prior:
            sids=[sid for sid in r.candidate['steps'] if r.step(sid).step_id==prior['step_record'] or
                r.candidate['steps'][sid]['canonical_record_id']==prior['step_record']]
            if sids:session=append_attempt(session,sids[0],prior['outcome'],'eval:'+case['case_id']+':prior')
        fault=case.get('fault_injection',{})
        if fault.get('provider')=='timeout_all_bounded_attempts':
            def timeout(*args):raise ProviderFailure('PROVIDER_TRANSPORT_OR_SCHEMA_FAILURE')
            provider.complete=timeout
        elif fault.get('provider')=='otherwise_valid_response_with_unknown_evidence_id':
            from generation_providers import ProviderResult
            def invalid(policy,stable,dynamic,schema):
                sid=next(iter(stable['scopes']))
                return ProviderResult({'route':'SUPPORTED','scope_ids':[sid],'step_id':'','clarification_id':'',
                    'claims':[{'text':'Injected invalid citation.','role':'FACT','evidence_ids':['invented-source-id']}]})
            provider.complete=invalid
        if fault.get('context_budget'):
            provider.count=lambda body:8193
        started=time.monotonic()
        with app.test_request_context(environ_overrides={'arm_a_cache_enabled':False}):
            updated,view,_=q.answer(session,case['rider_question'])
        row={'case_id':case['case_id'],'view':view,'wall_seconds':time.monotonic()-started,
            'route_matches':view['response']['type']==case['expected_route'],
            'source_claim_review':'PENDING','typed_outcomes':[a.outcome_enum.value for a in updated.active_attempts()]}
        result['rows'].append(row);save()
        provider.complete=original_complete;provider.count=original_count
    result['completed_at']=datetime.now(timezone.utc).isoformat()
    result['route_matches']=sum(row['route_matches'] for row in result['rows'])
    result['unseen_supported_reached_llm']=any(row['view']['response']['type']=='SUPPORTED' and
        row['view']['provider_calls']>0 for row in result['rows'][:6])
    save()
    print(json.dumps({'completed':True,'cases':len(result['rows']),
        'route_matches':result['route_matches'],'unseen_supported_reached_llm':result['unseen_supported_reached_llm'],
        'generation_attempts':len(calls),'claim_review':'PENDING'}))

if __name__=='__main__':main()
