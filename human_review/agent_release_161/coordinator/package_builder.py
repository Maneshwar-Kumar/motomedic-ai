from pathlib import Path as _ReleasePath
if (_ReleasePath(__file__).resolve().parent / "release_manifest.json").exists():
    raise RuntimeError("Approved package immutable: create a new version for revisions")
import json,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent; S=H/'snapshot_v3'; O=H/'approved_package';O.mkdir(exist_ok=True)
def read(n):return json.loads((S/n).read_text(encoding='utf-8'))
def write(n,d):
 b=(json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode();(O/n).write_bytes(b);return hashlib.sha256(b).hexdigest()
r=read('candidate_registry.json');t=read('trusted_routes.json');b=read('branch_dependencies.json');fixes=[]
for sid,s in r['steps'].items():
 fixes.append({'step_id':sid,'old_unresolved_route':s.get('unresolved_route'),'new_unresolved_route':'ESCALATE_NO_APPROVED_NEXT_STEP'})
 s.update(unresolved_route='ESCALATE_NO_APPROVED_NEXT_STEP',next_step_ids=[],next_step_evidence_ids=[],repeat_rule_ids=[],runtime_authorized=False,adaptive_continuation_authorized=False)
for x in t['routes']:
 x.update(release_authority='AGENT_COORDINATOR',runtime_authorized=False,requires_exact_scope_approval=True);x.pop('requires_actual_formal_approval',None)
 if x.get('step_id'):
  st=r['steps'][x['step_id']];old=x.get('initial_candidate_route');x['initial_candidate_route']='SAFETY_STOP' if st['kind']=='SAFETY_STOP' else 'SUPPORTED'
  if old!=x['initial_candidate_route']:fixes.append({'record_id':x['record_id'],'old_route':old,'new_route':x['initial_candidate_route']})
for x in b['branches']:x.update(runtime_authorized=False,execution_scope='REFERENCE_TEXT_ONLY_NOT_EXECUTABLE_BRANCH')
contract={'schema_version':'agent-scoped-execution-contract-v1','authority':'AGENT_COORDINATOR','source_checksum':r['manual_checksum'],'case_selection':'Exact case ID plus confirmed intent; synthetic fixtures not live classifiers','eligibility':'All required predicates TRUE; FALSE blocks; UNKNOWN clarifies only via reviewed source-derived question; absent question withholds action','dependencies':'Exact approved hashes; mandatory source, warning, units and context retained','attempts':'Immutable typed attempts; unresolved never means normal; corrections supersede','repeat':'No automatic repeat or adaptive next step authorized','followup':'With no approved next edge, refer to authorised service; retain separate unresolved issues','resolved':'Rider-reported symptom resolution only; preserve mandatory service inspection and other open issues','figure_display':'No end-user PDF/excerpts/crops authorized by this package','visual_review':'Finite original manual image-grounded text may be approved; no general rider-photo model validation implied','safety':'Approved known safety stop retains warning and precedes operational failures','provider_calls_authorized':False,'deployment_authorized':False,'case_approval_required':True}
for d in (r,t,b):d['runtime_authorized']=False;d['release_authority']='AGENT_COORDINATOR'
out={}
for n,d in [('candidate_registry.json',r),('trusted_routes.json',t),('branch_dependencies.json',b),('source_objects.json',read('source_objects.json')),('execution_contract.json',contract),('corrections.json',fixes),('session_fixtures.json',read('session_fixtures.json'))]:out[n]=write(n,d)
write('package_manifest.json',{'outputs':out,'approval_status':'AWAITING_INDEPENDENT_FINAL_CHECK'});print(json.dumps(out,indent=2))
