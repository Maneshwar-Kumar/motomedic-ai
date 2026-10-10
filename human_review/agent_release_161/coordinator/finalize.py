import json,hashlib,collections
from pathlib import Path
H=Path(__file__).resolve().parent;ROOT=H.parents[2];P=H/'approved_package';A=H.parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def rawh(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
# Independent checker must publish this file only after final artifact inspection.
C=A/'checker'/'review_inventory.json'
review=read(C)
for n,h in review['package_outputs'].items():assert rawh(P/n)==h,(n,'reviewed package changed')
checkrecords={x['record_id']:x for x in review['records']}
reg=read(P/'candidate_registry.json');routes={x['record_id']:x for x in read(P/'trusted_routes.json')['routes']};fixtures={x['record_id']:x for x in read(P/'session_fixtures.json')['records']};sources=read(P/'source_objects.json')['sources'];constraints={x['record_id']:x for x in read(P/'case_constraints.json')['records']}
inv=read(A/'planner'/'plan_inventory.json');plans=inv.get('records',inv.get('plans'));assert len(plans)==161
authority=rawh(A/'owner_authority.json');records=[]
procedure_review=read(A/'checker'/'procedure_review.json');procedure_checks={x['procedure_id']:x for x in procedure_review['records']}
for pid,obj in reg['procedures'].items():assert procedure_checks[pid]['verdict']=='APPROVED_INITIAL_ACTION_BOUNDARY' and procedure_checks[pid]['procedure_sha256']==canon(obj),(pid,'procedure review mismatch')
for item in plans:
 rid=item['record_id'];fp=ROOT/item['path'];plan=read(fp); cr=checkrecords[rid]; route=routes[rid]; sid=route.get('step_id');step=reg['steps'].get(sid); dep=reg['dependencies'].get(sid);fixture=fixtures[rid]
 ids=set(plan['source_objects']); ids.update(route.get('source_support_ids',[]))
 if step:
  ids.update(step['required_evidence_ids']);ids.update(step['action_evidence_ids']);ids.update(step.get('unresolved_evidence_ids',[]))
  for rule_id in step['applicability_rule_ids']: ids.update(reg['rules'][rule_id].get('source_evidence_ids',[]));ids.update(reg['rules'][rule_id].get('policy_source_ids',[]))
  for claim in step['claims']:ids.update(claim.get('evidence_ids',[]));ids.update(claim.get('policy_support_ids',[]))
  if step.get('parent_procedure_id'):ids.update(reg['procedures'][step['parent_procedure_id']].get('evidence_ids',[]))
 missing=ids-set(sources);assert not missing,(rid,missing)
 binding={'case_locator':{'file':rel(P/'session_fixtures.json'),'key':rid},'case_sha256':canon(fixture),'planner_case_locator':{'file':rel(fp),'key':'candidate_case'},'planner_case_sha256':canon(plan['candidate_case']),'original_canonical_answer_sha256':hashlib.sha256(plan['candidate_case']['canonical_answer'].encode()).hexdigest(),'canonical_answer_locator':{'file':rel(P/'candidate_registry.json') if step else rel(P/'trusted_routes.json'),'key':sid if step else rid,'field':'claims' if step else 'canonical_candidate'},'canonical_answer_sha256':canon(step['claims']) if step else hashlib.sha256(route['canonical_candidate'].encode()).hexdigest(),'step_id':sid,'step_sha256':canon(step) if step else None,'rule_sha256s':{k:canon(reg['rules'][k]) for k in (step['applicability_rule_ids'] if step else [])},'dependency_id':sid,'dependency_sha256':canon(dep) if dep else None,'source_sha256s':{k:canon(sources[k]) for k in sorted(ids)},'route_id':rid,'route_sha256':canon(route),'constraint_id':rid,'constraint_sha256':canon(constraints[rid]),'procedure_id':step.get('parent_procedure_id') if step else None,'procedure_sha256':canon(reg['procedures'][step['parent_procedure_id']]) if step and step.get('parent_procedure_id') else None}
 assert rawh(ROOT/cr['path'])==cr['sha256'],(rid,'checker bytes changed')
 assert cr['plan_sha256']==rawh(fp),(rid,'plan changed')
 assert cr['final_route_sha256']==canon(route),(rid,'route review changed')
 if step:
  assert cr['final_step_sha256']==canon(step) and cr['final_dependency_sha256']==canon(dep),(rid,'step/dependency review changed')
 verdict=cr['final_check_verdict'];ok=verdict=='PASS_SCOPED_RELEASE'
 records.append({'record_id':rid,'final_disposition':'APPROVED_AGENT_RELEASE' if ok else 'BLOCKED_SPECIFIC_GAP','authority':'AGENT_COORDINATOR','authority_sha256':authority,'approved_scopes':['SOURCE_CONTENT','INITIAL_ROUTE'] if ok else [],'blocked_scopes':['ADAPTIVE_TRANSITIONS','DISPLAY_FIGURES'],'approved_scope_description':'Exact initial source/policy response after typed eligibility; terminal service/no automatic continuation; no figure display or general vision approval','artifact_bindings':binding,'planner_file':rel(fp),'planner_file_sha256':rawh(fp),'checker_report_locator':{'file':cr['path'],'key':rid},'checker_report_sha256':cr['sha256'],'checker_inventory_sha256':rawh(C),'procedure_boundary_approved':bool(step and step.get('parent_procedure_id')),'checker_findings':cr.get('findings',[]),'finding_dispositions':[{'finding':f,'disposition':'RESOLVED_OR_PRESERVED_AS_EXPLICIT_SCOPE_LIMIT','final_artifact_verified':True,'checker_file':cr['path']} for f in cr.get('findings',[])],'specific_limits':cr.get('specific_limits',[]),'initial_route':constraints[rid]['initial_route'],'eligible_main_route':constraints[rid]['eligible_main_route']})
assert len(records)==161 and len({x['record_id'] for x in records})==161
outputs={rel(p):rawh(p) for p in sorted(P.glob('*.json'))};outputs.update({x['path']:x['sha256'] for x in review['records']});outputs[rel(C)]=rawh(C);outputs[rel(A/'checker'/'procedure_review.json')]=rawh(A/'checker'/'procedure_review.json');outputs[rel(A/'planner'/'plan_inventory.json')]=rawh(A/'planner'/'plan_inventory.json');outputs[rel(A/'planner'/'runtime_correction_proposals_v2.json')]=rawh(A/'planner'/'runtime_correction_proposals_v2.json');outputs[rel(A/'owner_authority.json')]=authority
manifest={'schema_version':'agent-coordinator-release-v1','authority':'AGENT_COORDINATOR','authority_sha256':authority,'hash_scheme':'SHA256 raw files; subobjects UTF8 json.dumps(sort_keys=True,separators=(comma,colon),ensure_ascii=False,allow_nan=False)','record_count':161,'manual_sha256':reg['manual_checksum'],'records':records,'outputs':outputs,'counts':dict(collections.Counter(x['final_disposition'] for x in records)),'human_review_required':False,'shared_runtime_installed':False,'live_provider_calls':0,'public_deployment_authorized':False,'approved_package':rel(P),'display_figures_approved':False,'adaptive_continuation_approved':False}
save(H/'release_manifest.json',manifest);print(json.dumps(manifest['counts']))
