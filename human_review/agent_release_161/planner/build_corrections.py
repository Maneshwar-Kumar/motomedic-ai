"""Explicit scope-limited transition proposals for coordinator implementation."""
from pathlib import Path
import json,hashlib
BASE=Path(__file__).resolve().parent
def rd(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def h(o):return hashlib.sha256((json.dumps(o,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()).hexdigest()

inventory=rd(BASE/'plan_inventory.json');proposals=[]
service_ids={'EXP011','EXP013','EXP030','EXP047','EXP049','a_reconnect'}
for entry in inventory['records']:
 p=rd(BASE/'plans'/f"{entry['record_id']}.json");rid=p['record_id'];mapping=p['runtime_mapping'];step=mapping['step'];route=mapping['trusted_route'];kind=step.get('kind') if step else route['route_kind'];case=p['candidate_case'];dep=mapping['dependency']
 # Terminal defaults describe scope, never infer a physical step from narrative.
 if not step:
  initial=route.get('expected_route') or route.get('initial_candidate_route') or case.get('candidate_expected_route')
  endpoint='RETURN_TRUSTED_POLICY_ROUTE'
 elif kind=='SAFETY_STOP':initial='SAFETY_STOP';endpoint='SAFETY_STOP_TERMINAL'
 elif rid in service_ids:initial='SUPPORTED';endpoint='DOCUMENTED_SERVICE_TERMINAL'
 elif kind=='LOOKUP':initial='SUPPORTED';endpoint='LOOKUP_COMPLETE'
 else:initial='SUPPORTED';endpoint='AWAIT_TYPED_OUTCOME'
 transitions={
  'ACTION_COMPLETED_UNRESOLVED':{'state_write':'IMMUTABLE_ATTEMPT_UNRESOLVED','new_health_fact':False,'repeat_current_step':False,'next_step_ids':[],'route':'DOCUMENTED_SERVICE_TERMINAL' if step and step.get('unresolved_evidence_ids') else 'DOCUMENTED_PATH_EXHAUSTED','output_requirement':'Use independently checked exact service claim if present; otherwise state exhausted applicable documented path and verified support route. Never CONTINUE_DOCUMENTED with empty next_step_ids.'},
  'OBSERVED_NORMAL':{'state_write':'RULE_BOUND_OBSERVATION_ONLY','new_health_fact':False,'repeat_current_step':False,'next_step_ids':[],'route':'REASSESS_ONLY_WITH_BOUND_ELIGIBLE_SUCCESSOR_OR_EXHAUSTED','output_requirement':'A lookup answer alone is not an inspection; do not mark all components normal.'},
  'OBSERVED_ABNORMAL':{'state_write':'RULE_BOUND_OBSERVATION_ONLY','new_health_fact':False,'repeat_current_step':False,'next_step_ids':[],'route':'DOCUMENTED_SERVICE_TERMINAL_OR_BOUND_SAFETY_STOP','output_requirement':'Do not invent component diagnosis from abnormal observation.'},
  'NOT_APPLICABLE':{'state_write':'STEP_NOT_APPLICABLE','repeat_current_step':False,'route':'WITHHOLD_DEPENDENT_STEP','output_requirement':'Ask one accessible applicability question only where source/policy makes it rider-resolvable; never request internal evidence IDs.'},
  'UNCLEAR':{'state_write':'UNCLEAR_OBSERVATION','repeat_current_step':False,'route':'ONE_FOCUSED_BOUND_QUESTION_OR_SCOPED_ABSTENTION','output_requirement':'Source-review incompleteness cannot become a rider question.'},
  'RESOLVED':{'state_write':'CUSTOMER_REPORTED_SELECTED_SYMPTOM_RESOLVED','repair_verified':False,'retain_other_open_issues':True,'retain_required_service_inspection':True,'route':'ISSUE_REPORTED_RESOLVED'},
  'CORRECTION':{'state_write':'SUPERSEDING_CORRECTION_KEEP_OLD_ATTEMPT','route':'REASSESS_ELIGIBILITY','repeat_current_step':'ONLY_IF_EXPLICIT_CORRECTION_CHANGES_APPLICABILITY_AND_REVIEWED_RULE_ALLOWS'}}
 if kind!='ACTION':
  transitions['ACTION_COMPLETED_UNRESOLVED']['output_requirement']+=' Current object is a lookup/terminal policy route, so an attempted physical action cannot be inferred from this answer.'
 assert initial in {'SUPPORTED','AMBIGUOUS','UNSUPPORTED','SAFETY_STOP','SYSTEM_ERROR'},rid
 proposal={'record_id':rid,'exact_check_plan_sha256':entry['sha256'],'candidate_case_sha256':p['candidate_case_sha256'],'step_id':step['step_id'] if step else None,'eligible_main_route':initial,'initial_route':route.get('expected_route') or route.get('initial_candidate_route') or initial,'main_response_endpoint':endpoint,'generic_continue_documented_allowed':False,'verified_successor_ids':[],'uncompiled_narrative_branches':'NOT_EXECUTABLE','scope':'Exact final main claims plus separately approved typed branches only; every unbound follow-up abstains or uses independently verified policy/service route.','eligibility':{'rule_objects':mapping['rules'],'TRUE':'Select eligible untried applicable step only; source/controller review status must be approved exact version.','FALSE':'Do not release conditional action; preserve observation and take separately bound false branch or scoped abstention.','UNKNOWN':'Ask exact existing source-derived clarification only when rider_resolvable=true; otherwise abstain to checked service/policy route.','hard_blocks':['Conflicting/missing source support','Unreviewed necessary visual claim','Known unsafe request supersedes ordinary action','Missing mandatory warnings/prerequisites','Source variant mismatch']},'transitions':transitions,'source_limit_scope':p['source_limit_checks'],'case_specific_corrections':[],'coordinator_review_required':True,'not_installed_in_shared_runtime':True}
 specific=proposal['case_specific_corrections']
 if rid in service_ids:specific.append('This is a source-backed service/inspection terminal response. Do not convert service recommendation into customer repair procedure or CONTINUE_DOCUMENTED.')
 if rid=='lookup_oil_grade':specific.append('Exact grade-only lookup and oil caution; no oil quantity/change procedure or generic recommendations-may-change clause.')
 if rid=='lookup_tyre_pressure':specific.append('Pressure-only main endpoint. Replacement selection is separate typed branch requiring tyre construction/rim association; restore kg/cm² encoding and preserve front/rear and solo/pillion scope.')
 if rid in ['lookup_fan_fuse','a_fuse']:specific.append('Fuse lookup and replacement are distinct. Any replacement requires identified defective fuse, ignitionOFF, same rating, anti-bridging/fire warnings and authorised electrical inspection after failure even when operation returns.')
 if rid in ['lookup_starter_duration','a_switches_on']:specific.append('Switch correction is distinct from cranking. Starter max5seconds/about5seconds interval and15–20second recovery after3 successive cranks are bounded source facts; no automatic retries. Page75 post-start caution is a separate newly reviewed scope, not implied by prior record acceptance.')
 if rid=='a_refuel':specific.append('Actual fuel concern vs persistent fuel-display discrepancy remain separate; side stand retracted/ignitionON gauge-refresh context on page63; unresolved refill cannot prove gauge/fuel-system health or authorize repeated refill.')
 if rid=='a_raise_stand':specific.append('Stand physicalposition and indicator discrepancy remain separate; source-backed stand retraction does not authorize sensor diagnosis/bypass. Figure-dependent identification remains disabled unless exact reviewed figure association and permitted display are established.')
 if rid=='a_cool_engine':specific.append('Unknown overheating condition has no source-supported numerical threshold/touchtest/coolingduration or restartclearance. Withhold action eligibility based on guessed engine-hot Boolean; support service-only uncertainty route.')
 if rid=='a_reconnect':specific.append('No guided reconnection; OEM table mentions remedy but lacks reviewed location/access/fitting sequence. Preserve accepted explanation and service route.')
 if rid=='EXP015':specific.append('Reset only when already safely upright and securely supported with source prerequisites; source does not teach lifting fallen motorcycle.')
 if rid=='EXP032':specific.append('Page103 has a chainadjustment procedure but prior parser omission means complete typed execution is unavailable; approve evidence-limit/service response only, not claim entiremanual lacks procedure.')
 if rid=='EXP040':specific.append('Keep unresolved first-notch vs solo3rd-notch applicability conflict; no fabricated reconciliation or adjustment action.')
 if p['figure_necessity_checks']:specific.append('Do not require all cited figures wholesale. Classify each exact claim/branch as text-supported or visually necessary; unneeded figures leave main dependency set. Internal sourceverification does not authorize displaying cropped manual images.')
 proposals.append(proposal)
out={'schema_version':'case-runtime-correction-proposals-v2','planner_actor':'check_planner','records':proposals,'record_count':len(proposals),'bound_plan_inventory_sha256':hashlib.sha256((BASE/'plan_inventory.json').read_bytes()).hexdigest(),'all_empty_successor_continuations_rejected':True,'supersedes_reason':'Explicit expected_route fallback for twelve EXP policy/source-limit cases; distinguish scenario initial route from eligible mainresponse route.','approval_status':'PROPOSED_FOR_COORDINATOR_AND_CHECKER'}
data=(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode();path=BASE/'runtime_correction_proposals_v2.json'
if path.exists():assert path.read_bytes()==data
else:path.write_bytes(data)
print(json.dumps({'records':len(proposals),'sha256':hashlib.sha256(data).hexdigest()}))
