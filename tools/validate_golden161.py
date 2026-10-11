"""Hosted golden161 regression against exact deployed question core, seven-second gaps."""
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,os,time
from pathlib import Path
import sys
sys.path.insert(0,'/app')
from approved_registry import ApprovedEvidenceRegistry
from cloud.arm_a.questions import Questions,proposition_key
from online_retrieve import Retriever
ROOT=Path('/app')
RELEASE='e2806fe205e6d5a1b81d1cc87b788e648818a8449d12c0b252b0d212a41956c0'
RUN='golden161-ui-arm-a-20261011-v1'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def emit(event,**values):print(json.dumps({'event':event,'run_id':RUN,**values},ensure_ascii=True,allow_nan=False),flush=True)
def main():
 if os.environ.get('MOTOMEDIC_VALIDATION_HOSTED')!='cloudbuild':raise RuntimeError('HOSTED_ONLY')
 lockpath=ROOT/'arm_a_release.json';assert digest(lockpath.read_bytes())==RELEASE
 lock=json.loads(lockpath.read_bytes())
 for name,sha in lock['file_sha256'].items():assert digest((ROOT/name).read_bytes())==sha,name
 started=time.perf_counter();r=ApprovedEvidenceRegistry.load(ROOT,ROOT/'build/index');consumer=r._consumer
 assert len(consumer.records)==161
 retriever=Retriever(ROOT/'build/index',rerank=True);q=Questions(r,retriever)
 original=retriever.search;captures=[]
 def captured(query,**kwargs):
  bundle=original(query,**kwargs)
  captures.append({'step_id':kwargs.get('step_id'),'hits':[{'evidence_ids':h.get('evidence_ids',[])} for h in bundle.get('hits',[])],'sufficiency_status':bundle.get('sufficiency_status'),'dependency_status':bundle.get('dependency_status')})
  return bundle
 retriever.search=captured
 emit('golden161_start',record_count=161,release_sha256=RELEASE,manual_checksum=r.checksum,index_id=r.index_id,gap_seconds=7,provider_calls=0,initial_state='UI-confirmed Himalayan BS6; no hidden diagnostic facts',scope='Exact production image question core, real hybrid retrieval, end-user gates; no production HTTP/store or injected failure claims')
 rows=[];previous_completed=None
 for number,(rid,record) in enumerate(consumer.records.items(),1):
  if previous_completed is not None:time.sleep(7)
  began=time.perf_counter();gap=None if previous_completed is None else began-previous_completed
  planner=json.loads((ROOT/record['planner_file']).read_bytes())['candidate_case']
  query=planner.get('branch_context',{}).get('producer',{}).get('question') or planner.get('question')
  assert isinstance(query,str) and query.strip(),rid
  sid=record['artifact_bindings'].get('step_id');category='source_step' if sid else 'trusted_policy_fixture'
  expected=record['initial_route'];captures.clear();error=None
  try:
   session,view,choices=q.answer(q.new_session(),query);response=view['response'];actual=response['type']
   technical=response['technical_content'];citations=response['cited_pages'];selected=list(session.current_symptoms)
   checks={'route_matches':actual==expected,'technical_scope_matches':not technical or selected==[rid], 'source_bindings_valid':all(c['manual_checksum']==r.checksum and c['index_id']==r.index_id and c['pdf_page_index']==c['pdf_page']-1 for c in citations),'display_gate':not technical or response['release_gate_passed'] is True}
   expected_answer=consumer.locate(record['artifact_bindings']['canonical_answer_locator'])
   exact=None;complete=None;clarification=None
   if technical:
    text=' '.join(c['text'] for c in expected_answer) if isinstance(expected_answer,list) else expected_answer
    support=(r.source.get('oem_service_route') or {}).get('wording')
    if expected=='SAFETY_STOP' and support and support not in text:text+=' '+support
    exact=response['natural_language']==text
    required=set(r.step(sid).required_evidence_ids) if sid else set()
    complete=bool(sid) and required <= {c['evidence_id'] for c in citations}
    checks.update(exact_golden_wording=exact,complete_golden_evidence=complete)
   if expected=='AMBIGUOUS' and actual=='AMBIGUOUS' and sid:
    step=r.step(sid);questions=[r.rule(rule).clarification_question for rule in step.applicability_rule_ids if r.rule(rule).rider_resolvable and r.rule(rule).clarification_question]
    clarification=any(response['natural_language'].startswith(text) for text in questions)
    checks['source_authored_clarification']=clarification
   if actual in ('UNSUPPORTED','AMBIGUOUS','SYSTEM_ERROR'):checks['no_technical_release']=not technical
   passed=all(checks.values())
   answer_hash=digest(response['natural_language'].encode());pages=sorted({c['pdf_page'] for c in citations})
   query_admitted=[d['rid'] for d in q.descriptors.values() if proposition_key(query) in d['propositions']]
  except Exception as exc:
   actual='EXCEPTION';passed=False;technical=False;selected=[];checks={'uncaught_exception':False};answer_hash=None;pages=[];query_admitted=[];error=type(exc).__name__
  completed=time.perf_counter();previous_completed=completed
  row={'ordinal':number,'record_id':rid,'category':category,'case_kind':planner.get('case_kind'),'query_sha256':digest(query.encode()),'expected_route':expected,'actual_route':actual,'passed':passed,'checks':checks,'technical_content':technical,'selected_records':selected,'accepted_propositions':query_admitted,'answer_sha256':answer_hash,'source_pages':pages,'seconds':completed-began,'gap_since_previous_completion_seconds':gap,'retrieval_calls':len(captures),'retrieved_candidate_evidence_ids':sorted({e for h in (captures[0]['hits'] if captures else []) for e in h['evidence_ids']}),'error':error,'trusted_fixture_injected':False}
  rows.append(row);emit('golden161_case',**row)
 counts=Counter(row['actual_route'] for row in rows);confusion=Counter((row['expected_route'],row['actual_route']) for row in rows)
 summary={'record_count':len(rows),'passed':sum(x['passed'] for x in rows),'failed':sum(not x['passed'] for x in rows),'route_matches':sum(x['checks'].get('route_matches',False) for x in rows),'actual_routes':dict(counts),'expected_routes':dict(Counter(x['expected_route'] for x in rows)),'confusion':[{'expected':k[0],'actual':k[1],'count':v} for k,v in sorted(confusion.items())],'source_step':{'count':sum(x['category']=='source_step' for x in rows),'passed':sum(x['category']=='source_step' and x['passed'] for x in rows)},'trusted_policy_fixture':{'count':sum(x['category']=='trusted_policy_fixture' for x in rows),'raw_prompt_route_matches':sum(x['category']=='trusted_policy_fixture' and x['checks'].get('route_matches',False) for x in rows),'failure_injection_tested':False},'technical_releases':sum(x['technical_content'] for x in rows),'wrong_scope_technical_releases':sum(not x['checks'].get('technical_scope_matches',True) for x in rows),'system_errors':counts.get('SYSTEM_ERROR',0),'uncaught_exceptions':counts.get('EXCEPTION',0),'minimum_gap_seconds':min(x['gap_since_previous_completion_seconds'] for x in rows[1:]),'elapsed_seconds':time.perf_counter()-started,'provider_calls':0,'retries':0,'held_out':False,'production_http_latency_measured':False}
 emit('golden161_summary',**summary)
 assert len(rows)==161
if __name__=='__main__':main()
