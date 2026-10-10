"""Content-bound check plans; planning is not a source verdict or runtime approval."""
from pathlib import Path
import hashlib,json,re,zipfile,xml.etree.ElementTree as ET
import fitz

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SNAP=ROOT/'human_review/agent_release_161/coordinator/snapshot_v3'
def digest(b):return hashlib.sha256(b).hexdigest()
def enc(o):return (json.dumps(o,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,o):
 b=enc(o);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():assert p.read_bytes()==b, f'Immutable output changed: {p}'
 else:p.write_bytes(b)
 return digest(b)
def pin(p):
 b=p.read_bytes();h=digest(b);q=OUT/'objects'/h;q.parent.mkdir(parents=True,exist_ok=True)
 if q.exists():assert q.read_bytes()==b
 else:q.write_bytes(b)
 return {'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':h,'object_path':str(q.relative_to(ROOT)).replace('\\','/')}

def main():
 context_paths=[ROOT/'AGENTS.md',ROOT/'source_manifest.json',ROOT/'human_review/subagent_feedback.md',ROOT/'human_review/record_id_verification.md']
 context_paths += [ROOT/f for f in ['01_Concept_Architecture.docx','02_PRD.docx','03_TRD.docx','04_To_Build_Evaluation_Decisions.docx']]
 context_paths += [ROOT/'grounding_bindings/expanded-v1'/f for f in ['claim_bindings.json','support_review.json','corrected_candidates.json']]
 context_paths += [ROOT/'registry/reconciled-accepted-eleven'/f for f in ['accepted_examples.json','review_decisions.json']]
 context_paths += [ROOT/'human_review/grounding_refinement/case_specific_v2/suite.json',ROOT/'human_review/agent_release_161/coordinator/snapshot_manifest.json']
 context_paths += sorted(SNAP.glob('*.json'))
 pins=[pin(p) for p in context_paths]
 manifest=read(ROOT/'source_manifest.json');manual=ROOT/manifest['file'];mh=digest(manual.read_bytes());assert mh==manifest['sha256'].lower()
 pdf=fitz.open(manual);assert len(pdf)==149
 texts={i+1:p.get_text() for i,p in enumerate(pdf)}
 transcript={'manual_sha256':mh,'pages':[{'pdf_page':i,'text':t,'text_sha256':digest(t.encode())} for i,t in texts.items()]}
 transcript_sha=save(OUT/'original_page_text.json',transcript)
 # Read every design and accepted feedback byte, retain an inspectable transcript.
 docs={}
 for p in context_paths[:8]:
  if p.suffix=='.docx':
   with zipfile.ZipFile(p) as z:root=ET.fromstring(z.read('word/document.xml'))
   docs[p.name]='\n'.join(''.join(n.itertext()) for n in root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
  else:docs[p.name]=p.read_text(encoding='utf-8-sig')
 save(OUT/'design_and_accepted_context.json',docs)
 suite=read(ROOT/'human_review/grounding_refinement/case_specific_v2/suite.json')
 reg=read(SNAP/'candidate_registry.json');sources=read(SNAP/'source_objects.json')['sources'];routes={r['record_id']:r for r in read(SNAP/'trusted_routes.json')['routes']}
 fixtures={r['record_id']:r for r in read(SNAP/'session_fixtures.json')['records']}
 branches=read(SNAP/'branch_dependencies.json')['branches'];gaps=read(SNAP/'source_gaps.json')['gaps']
 accepted={r['record_id']:r for r in read(ROOT/'registry/reconciled-accepted-eleven/accepted_examples.json')['examples']}
 review=read(ROOT/'grounding_bindings/expanded-v1/support_review.json');prior={r['record_id']:r for r in review['records']}
 binding={r['record_id']:r for r in read(ROOT/'grounding_bindings/expanded-v1/claim_bindings.json')['records']}
 context_sha=digest(enc(pins));inventory=[]
 for case in suite['records']:
  rid=case['record_id'];route=routes[rid];sid=route.get('step_id');step=reg['steps'].get(sid);dep=reg['dependencies'].get(sid)
  rules={k:reg['rules'][k] for k in step.get('applicability_rule_ids',[]) if k in reg['rules']} if step else {}
  casebranches=[b for b in branches if b['branch_id'].startswith(rid+':')]
  claims=step['claims'] if step else case['claims']
  needed=set(case.get('required_candidate_source_ids',[]))
  if dep:needed.update(dep['required_evidence_ids'])
  for c in claims:needed.update(c.get('evidence_ids',c.get('support_evidence_ids',[])))
  objects={k:sources[k] for k in sorted(needed) if k in sources}
  missing=sorted(needed-sources.keys());pages=set();visual=[];checks=[]
  for c in claims:
   exact=c.get('text',c.get('exact_claim_text',''));bindings=[]
   for span in c.get('source_spans',[]):
    eid=span['evidence_id'];obj=sources.get(eid,{});txt=obj.get('exact_text','');start,end=span.get('text_span',[0,len(txt)])
    pp=sorted({p['page_no'] for p in obj.get('provenance',[]) if p.get('page_no')})
    pages.update(pp)
    if obj.get('pdf_page'):pages.add(obj['pdf_page'])
    bindings.append({'source_span':span,'exact_selected_text':txt[start:end],'span_in_bounds':0<=start<=end<=len(txt),'source_text_hash_matches':not span.get('text_sha256') or digest(txt.encode())==span['text_sha256'],'pdf_pages':pp,'object_type':obj.get('object_type'),'authority':obj.get('authority'),'requires_visual_verification':obj.get('requires_visual_verification',False)})
   checks.append({'claim_id':c.get('claim_id'),'exact_claim':exact,'runtime_claim_sha256':digest(enc(c)),'selected_source_bindings':bindings,'required_check':'Read original page and verify entire paraphrase, scope, number/unit and warning; inherited verdict is not evidence.'})
  for eid,obj in objects.items():
   pages.update(p['page_no'] for p in obj.get('provenance',[]) if p.get('page_no'))
   if obj.get('pdf_page'):pages.add(obj['pdf_page'])
   if obj.get('requires_visual_verification') or obj.get('object_type')=='picture':visual.append({'evidence_id':eid,'pdf_pages':sorted({p['page_no'] for p in obj.get('provenance',[]) if p.get('page_no')}),'planning_disposition':'CHECK_ACTUAL_NECESSITY; picture presence alone never establishes a mandatory dependency','required_check':'Identify the precise rider claim/conditional branch needing this figure. Verify labels/legend on original page; remove irrelevant figure dependency, or approve internal association only. No crop display authorization inferred.'})
  plan={'schema_version':'case-check-plan-v1','record_id':rid,'planner_actor':'check_planner','coordinator_snapshot_sha256':digest((ROOT/'human_review/agent_release_161/coordinator/snapshot_manifest.json').read_bytes()),'context_pin_sha256':context_sha,'manual_sha256':mh,'candidate_case':case,'candidate_case_sha256':digest(enc(case)),'canonical_answer_sha256':digest(case['canonical_answer'].encode()),'runtime_mapping':{'trusted_route':route,'step':step,'step_sha256':digest(enc(step)) if step else None,'rules':rules,'dependency':dep,'dependency_sha256':digest(enc(dep)) if dep else None,'procedure':reg['procedures'].get(step.get('parent_procedure_id')) if step else None,'conditional_branches':casebranches,'session_fixture':fixtures[rid]},'source_objects':objects,'missing_source_ids':missing,'original_pdf_pages_to_check':sorted(pages),'claim_checks':checks,'table_number_unit_checks':[{'evidence_id':eid,'object_type':o.get('object_type'),'exact_text':o.get('exact_text',''),'required_check':'Preserve row/header/qualifier associations; compare dimensions, units, warning scope and variant against original PDF.'} for eid,o in objects.items() if o.get('object_type') in ['table','table_row'] or re.search(r'\d\s*(?:psi|kg|cm|mm|Nm|N.m|10W|API|JASO|seconds|V|A\b|bar)',o.get('exact_text',''))],'figure_necessity_checks':visual,'accepted_original_context':accepted.get(rid),'prior_support_context':prior.get(rid),'producer_binding_context':binding.get(rid),'source_limit_checks':[g for g in gaps if g['record_id']==rid],'blanket_hold_interpretation':'DRAFT/review_complete false/human_signoff false are inherited metadata, not a demonstrated content defect. Independent checker must return exact substantive findings. Coordinator has user-authorized final approval; do not fabricate human identity.','state_quality_checks':[{'outcome':'ACTION_COMPLETED_UNRESOLVED','check':'Append immutable unsuccessful attempt, do not infer normality, do not repeat this action automatically.'},{'outcome':'OBSERVED_NORMAL','check':'Require exact eligible inspection rule and typed observation; not equivalent to unresolved action or proof of system health.'},{'outcome':'NOT_APPLICABLE','check':'Withhold dependent branch; clarify bike/control applicability only through observable question.'},{'outcome':'UNCLEAR','check':'One practical source-derived question only if rider-resolvable; source-review gaps route internally or to scoped abstention.'},{'outcome':'RESOLVED','check':'Customer-reported symptom resolution only; other issues and service inspection mandates remain.'},{'outcome':'CORRECTION','check':'Supersede prior observation while preserving attempt history; re-evaluate eligibility without invented order.'}],'quality_and_routing_checks':['Check exact accepted follow-up context, do not collapse entire conversation into terminal answer.','Relevant concise main response; compact setup conditions without assuming completion.','No invented OEM ranking from independent documented checks.','Separate SUPPORTED/AMBIGUOUS/UNSUPPORTED/SAFETY_STOP/SYSTEM_ERROR; a synthetic error fixture is not an actual outage measurement.','Source facts, user observations, policy conditions and unverified mechanical diagnosis remain distinct.','Inspect all branch warnings, prerequisite object links, citations and claim spans; do not use a broad whole-table span as automatic entailment.','Verify branch predicates execute as typed reviewed records; prose is not executable.','No provider/secret reads/deployment/billing/index changes; review release artifacts only.'],'source_manifest_scope':{'applicability_policy':manifest.get('applicability_policy'),'display_policy':manifest.get('display_policy'),'rights_status':manifest.get('rights_status'),'oem_service_route':manifest.get('oem_service_route')},'planning_only':True,'approval_status':'NOT_YET_CHECKED'}
  h=save(OUT/'plans'/f'{rid}.json',plan);inventory.append({'record_id':rid,'path':str((OUT/'plans'/f'{rid}.json').relative_to(ROOT)).replace('\\','/'),'sha256':h,'case_sha256':plan['candidate_case_sha256'],'answer_sha256':plan['canonical_answer_sha256'],'pages':plan['original_pdf_pages_to_check'],'figure_candidates':len(visual),'has_runtime_step':step is not None,'route_kind':route['route_kind'],'source_missing_ids':missing})
 assert len(inventory)==161 and len({r['record_id'] for r in inventory})==161
 report={'schema_version':'check-plan-inventory-v1','planner_actor':'check_planner','manual_sha256':mh,'manual_pages':149,'original_page_text_sha256':transcript_sha,'input_pins':pins,'context_pin_sha256':context_sha,'record_count':161,'runtime_steps_mapped':sum(r['has_runtime_step'] for r in inventory),'trusted_policy_routes_mapped':sum(not r['has_runtime_step'] for r in inventory),'records':inventory,'approval_status':'PLANNING_COMPLETE_PENDING_INDEPENDENT_CHECKER','all_inputs_unchanged':all(digest((ROOT/r['path']).read_bytes())==r['sha256'] for r in pins)}
 h=save(OUT/'plan_inventory.json',report);print(json.dumps({'records':161,'inventory_sha256':h,'all_inputs_unchanged':report['all_inputs_unchanged'],'source_missing_record_count':sum(bool(r['source_missing_ids']) for r in inventory)}))
if __name__=='__main__':main()
