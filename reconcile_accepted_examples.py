"""Reconcile accepted conversation examples into DRAFT overlays; never approve them."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from evidence_registry import EvidenceRegistry, content_hash

BASE_TEXT = {
"lookup_oil_grade": "For the selected Himalayan BS6 manual, the specified engine oil is 10W40, API SN, JASO MA2, semi-synthetic.",
"lookup_tyre_pressure": "For the selected Himalayan BS6, the manual lists 32 psi (2.24 kg/cmÂ²) for both front and rear tyres, whether riding solo or with a pillion.",
"lookup_fan_fuse": "The fan uses F3, a red 10 A mini-blade fuse.",
"lookup_starter_duration": "Hold the starter until the engine starts, for a maximum of 5 seconds, provided the starting setup is satisfied. If no start within 5 seconds, release and wait about 5 seconds before another attempt.",
"lookup_usb_charging": "The USB charger works only while the engine is running.",
"a_fuse": "With ignition OFF, replace only a defective, positively identified fuse with a new fuse of the same specified rating. Do not guess the circuit or rating from colour alone.",
"a_switches_on": "Set only the reported OFF ignition or engine kill switch to the documented ON or RUN position. This does not establish that the remaining starting conditions are satisfied.",
"a_refuel": "Read the guidance before refuelling and return to the chat after completion. Open the fuel cap slowly and top up only to the bottom of the anti-splash plate, leaving expansion space; do not fill to the brim.",
"a_reconnect": "The manual lists reconnection as a remedy, but it does not provide the location, access or step-by-step reconnection guidance needed to walk you through it. Please have your nearest authorised Royal Enfield service centre check and reconnect the parts.",
"a_raise_stand": "Fully retract the side stand before starting or moving. The manual describes the stand cutoff as stopping the engine when gear is engaged for rider safety.",
"a_cool_engine": "Switch the engine OFF and allow it to cool. The manual does not specify a cooling time or temperature at which restarting is safe. If unsure, have an authorised Royal Enfield service centre assess it.",
}
PAGES = {"lookup_oil_grade":[21], "lookup_tyre_pressure":[90,18], "lookup_fan_fuse":[112],
"lookup_starter_duration":[72,73,74,121], "lookup_usb_charging":[65], "a_fuse":[111,112,121],
"a_switches_on":[28,72,73,74,121], "a_refuel":[8,27,28,63,73,121], "a_reconnect":[23,24,25,121],
"a_raise_stand":[25,58,59,74,121,122], "a_cool_engine":[37,38,121,122]}
COMMON = {"ACTION_COMPLETED_UNRESOLVED":"Preserve an immutable unresolved attempt; never infer normality or repeat automatically.",
          "NOT_APPLICABLE":"Withhold mismatched guidance and reconfirm manual/bike scope.",
          "RESOLVED":"Record only customer-reported resolution of the specified symptom; retain other open issues."}
BRANCHES = {
"lookup_oil_grade": {"end":"Grade lookup ends after the specification and caution; no quantity, oil-changing procedure or substitute recommendation."},
"lookup_tyre_pressure": {"replacement":"Ask fitted tyre construction separately from rim type. In tube and tubeless branches show front CEAT Gripp RE F â€” 90/90-21 M/C 54H, rear CEAT Gripp Rad steel RE â€” 140/80R17 M/C 69H. Tube-type rim requires tyre fitted with tube; tubeless-type rim requires only tubeless-type tyre. Ask rim confirmation. These models are not labelled by construction in this source.","unknown_or_alternative":"Show both rim requirements when unknown. Do not infer alternate-brand/version compatibility or current fitment. Refer to Royal Enfield support.","pressure_only":"Do not ask construction questions for the pressure-only lookup."},
"lookup_fan_fuse": {"failure_or_replacement":"Advise authorised-service electrical inspection and immediate fault correction after any fuse failure, even if replacement works. Replacement guidance may also be shared: ignition OFF, new same 10 A rating, no jumper/conductive substitutes, fire/short-circuit and wrong-rating/low-grade damage cautions, replenish used spare. No access procedure is established by page112 alone."},
"lookup_starter_duration": {"setup":"One compact conditional checklist: neutral and neutral lamp; ignition ON; right-hand kill switch RUN; adequate fuel and no continuously blinking final bar; clutch pulled in and held; stand fully retracted. Ask focused follow-ups for missing/failed observations; no attempt until eligibility established.","unresolved":"Keep unresolved attempt; ask documented dim-lights/weak-horn clue if unknown. Negative clue does not prove battery health. Other checks require their own review, no OEM ranking.","unclear_sound":"Clarify starter versus horn; starter-sound description is not a supported diagnostic rule.","post_start_mil":"Only after reported start, indicator not turning OFF as described requires service; do not clear EFI while no start persists."},
"lookup_usb_charging": {"running_engine_failure":"Ask standard approved high-quality cable, then damaged/unsealed cap. Refer reported cap condition to service without asserting causation or warranty eligibility. Conditional >2.5 A shutdown warning and phone-current-rating caution are not a current observation or nominal output rating.","unresolved":"No further repair procedure established; use Royal Enfield support, do not invent reset or test."},
"a_fuse": {"discovery":"A blown fuse is one documented possibility, not a no-start diagnosis. Ignition OFF; carrier under rider seat, documented keyed seat access. Show scoped inline fuse-location schematic after figure review. Ask position, colour and sticker function label; blue alone is ambiguous (ignition, EFI relay, ABS motor and spare). Only confirmed IGNITION slot maps internally to blue15 A.","uncertain_condition":"Please have the fuses and electrical system checked at your nearest authorised Royal Enfield service centre. Kindly write to Royal Enfield at support@royalenfield.com if you need help locating one. No continuity/filament test invented.","unresolved":"After failed replacement, stop at authorised service per121; do not continue to spark-plug reconnection.","reported_success":"Keep mandatory after-failure electrical inspection even if customer says it works."},
"a_switches_on": {"already_correct":"Do not repeat switching; retain confirmed observations and address remaining eligible unknown conditions.","cannot_identify":"Show reviewed page28 right-hand switch drawing and ON/OFF legend inline, ask if position can now be identified. If controls differ reconfirm applicability; persistent uncertainty goes to service without guessing.","finishing_checks":"Turn ignition OFF when engine is not running; continuously ON headlamp discharges battery. Do not misapply this caution to prohibit documented starting setup.","unresolved":"Keep unsuccessful attempt separate; clarify fuel only if unknown; no inferred switch/battery health or repeat. Starter attempt uses independently reviewed compact checklist/limits and post-start MIL branch."},
"a_refuel": {"safety":"Engine OFF, ventilated area, no smoking/flames/sparks, mobile/handheld devices OFF. No live phone/chat use at open tank. Cap operation, slow opening, anti-splash limit, expansion, EVAP/overfill damage, spill cleanup and locking need full procedure review.","fuel_indicator_discrepancy":"Preserve adequate-fuel report plus continuously blinking bar. Establish side stand retracted and ignition ON for page63 post-refuel gauge refresh, and whether blinking persisted after refuelling. Track unresolved fuel-level/indicator discrepancy separately; no gauge/sensor diagnosis, no repeat refuel to clear it. Continue only independently eligible no-start checks; retain discrepancy even if engine later starts.","correction":"Append a superseding observation rather than erase earlier feedback."},
"a_reconnect": {"source_gap":"Service referral only. Scope absence to the supporting guidance/audited access evidence; do not overstate exhaustive absence. No rider reconnection procedure.","unresolved":"Previously attempted reconnection remains unresolved and refers service. Normal-looking connection does not prove ignition health.","fuse_precedence":"Failed fuse replacement stops at service and cannot continue into this path."},
"a_raise_stand": {"entry":"Compact pair: Side Stand indicator observation and actual stand position; do not assume they agree.","mismatch":"Physically up but indicator showing is a separately open discrepancy; service without switch/sensor diagnosis or bypass.","unclear":"Use matching reviewed cluster schematic58/59 and stand location25 inline only after scoped permission/figure review; no guessed display variant.","unresolved":"No automatic repeat or road test. Explain supporting owner guidance lacks another applicable remedy and refer service."},
"a_cool_engine": {"unclear":"No numerical threshold, cooling duration, room-temperature/overnight endpoint, touch test or restart clearance. Display examples37/38 do not establish hot/not-hot eligibility; uncertainty refers service.","unresolved":"Record unresolved cooling action, no normal-engine inference or repeat cooling loop. Service for persistent/recurrent concern; do not infer contaminated fuel or coolant/fan repair.","fuel_concern":"A reported separate fuel concern stays separate; failure to improve does not establish adulteration."}}

WARNINGS = {
"lookup_oil_grade": ["Using the wrong oil grade reduces the life of moving parts and seriously affects performance."],
"lookup_tyre_pressure": ["Underinflated tyres can overheat, suffer damage and cause rider injury.", "If replacing tyres, use Royal Enfield's specified tyres; failure to do so can cause tyre damage and rider injury."],
"lookup_fan_fuse": [],
"lookup_starter_duration": ["Do not keep holding the starter for long periods: this can drain the battery below 10 V. An unresolved no-start condition requires authorised-service inspection."],
"lookup_usb_charging": ["Keep the port cap closed and locked when not in use. The manual warns that warranty will not be provided if the cap is damaged and the port is not properly sealed."],
"a_fuse": ["After any fuse failure, have the electrical system thoroughly checked and faults corrected immediately at authorised service, even if replacement restores operation.","Never bridge a defective fuse or substitute conductive material; this risks short-circuit and fire. Wrong-rating or low-grade fuses can damage the electrical system.","Replenish a used spare fuse in its holder at the earliest opportunity."],
"a_switches_on": ["When finishing checks with the engine not running, turn ignition OFF; the continuously ON headlamp can discharge the battery."],
"a_refuel": ["Gasoline vapour is highly explosive; no smoking, flames or sparks while refuelling or while the cap is open.","Overfilling can send gasoline into the EVAP canister and damage the emission system.","Avoid fuel spills on painted surfaces and wipe any immediately to prevent permanent stains."],
"a_reconnect": [], "a_raise_stand": [], "a_cool_engine": []}
PREREQUISITES = {
"lookup_starter_duration":["Before an actual starting attempt, establish neutral and neutral lamp glowing, ignition ON, right-hand kill switch RUN, adequate fuel/no continuously blinking final bar, clutch pulled in and held, and side stand fully retracted."],
"a_switches_on":["Setting a switch does not authorize starting. Establish the compact starting checklist before any starter action; retained confirmations are not re-asked."],
"a_fuse":["Keep ignition OFF for fuse work. Circuit, rating and defective condition must be established; uncertainty in condition goes directly to service."],
"a_refuel":["Refuel only with engine OFF in a well-ventilated area, no smoking/flames/sparks and mobile/handheld devices OFF. Read beforehand and return to chat after completion."],
"a_raise_stand":["Confirm the actual stand position and reported indicator condition; a discrepancy is not a sensor diagnosis."],
"a_cool_engine":["Apply this high-level branch only when its documented condition is established; no unsupported temperature threshold may establish eligibility."]}

def write(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")

def reconcile(index, output):
    existing_ledger=output/'review_decisions.json'
    if existing_ledger.exists() and json.loads(existing_ledger.read_text()).get('decisions'):
        raise ValueError('Do not overwrite an independently reviewed draft; use a new output version')
    original = EvidenceRegistry.load("registry",index,"source_manifest.json")
    c=deepcopy(original.candidate)
    c['version']='accepted-eleven-reconciliation-draft-v1'
    c['authored_by']='accepted-example-reconciliation-author'
    history={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
             ('human_review/record_id_verification.md','human_review/subagent_feedback.md')}
    c['reconciliation_provenance']={'base_registry_digest':content_hash(original.candidate),
        'review_context_sha256':history,'status':'CONVERSATION_ACCEPTED_SOURCE_REVIEW_PENDING',
        'excluded_pending_additions':['Page75:15â€“20seconds after three successive cranks','Page75:scoped post-start idle/acceleration cautions'],
        'excluded_unsupported_additions':['Room-temperature/overnight cooling endpoint','Starter-sound diagnosis','Colour-only fuse identification','Tube/tubeless-specific tyre model mapping']}
    examples=[]
    for sid,step in c['steps'].items():
        old=original.candidate['steps'][sid];dep=c['dependencies'][sid]
        page_ids={eid for eid,e in original.evidence.items() if any(p.get('page_no',p.get('pdf_page')) in PAGES[sid] for p in e['provenance'])}
        # These additions are candidate associations, deliberately not reviewed edges.
        new_ids=sorted(page_ids-set(old['required_evidence_ids']))
        required=sorted(set(old['required_evidence_ids'])|page_ids)
        step['required_evidence_ids']=required;dep['required_evidence_ids']=required
        dep['categories']['accepted_additional_context']=new_ids
        figures=[eid for eid in required if original.evidence[eid]['type']=='picture']
        if figures:dep['categories']['figures']=figures
        step['draft_pdf_pages']=PAGES[sid]
        claims=[]
        def claim(name,text,role,ids):
            claims.append({'claim_id':sid+':accepted-draft:'+name,'text':text,'response_role':role,
                           'evidence_ids':sorted(set(ids)), 'presentation_mode':'DRAFT_PARAPHRASE',
                           'source_mapping_status':'CANDIDATE_PAGE_SCOPE_NEEDS_ORIGINAL_SPAN_REVIEW'})
        main_ids=old['claims'][0]['evidence_ids']
        claim('main',BASE_TEXT[sid], 'ACTION' if step['kind']=='ACTION' else 'FACT',main_ids)
        for i,text in enumerate(WARNINGS[sid]):
            claim('warning'+str(i),text,'WARNING',dep['categories'].get('warnings',[]) or main_ids)
        for i,text in enumerate(PREREQUISITES.get(sid,[])):
            claim('setup'+str(i),text,'PREREQUISITE',dep['categories'].get('prerequisites',[]) or main_ids)
        step['claims']=claims
        step['review_status']='DRAFT';dep['review_status']='DRAFT';dep['scope_review_complete']=False
        step['conversation_acceptance']='ACCEPTED_SCOPED_CONVERSATION_ONLY'
        step['authoring_blockers']=['INDEPENDENT_CONTENT_BOUND_REVIEW_REQUIRED','CLAIM_SPANS_AND_BRANCH_DEPENDENCY_SCOPE_REQUIRED','DRAFT_PARAPHRASES_REQUIRE_DISPLAY_REVIEW']
        step['branch_drafts']={**COMMON,**BRANCHES[sid]}
        step['branch_draft_citations']=[{'evidence_id':eid,'pdf_page':p.get('page_no',p.get('pdf_page'))} for eid in required for p in original.evidence[eid]['provenance']]
        if figures:step['authoring_blockers']+=['PRECISE_FIGURE_LEGEND_ASSOCIATION_REQUIRED','SCOPED_DISPLAY_POLICY_RECONCILIATION_REQUIRED','FIGURE_VERIFIER_NOT_IMPLEMENTED']
        if sid in ('lookup_starter_duration','a_switches_on'):
            step['authoring_blockers']+=['STARTING_PAGE75_ADDITIONS_PENDING_SEPARATE_SCOPE_REVIEW']
        if sid=='a_reconnect':
            step['kind']='LOOKUP';step['parent_procedure_id']=None
            step['claims'][0]['response_role']='FACT'
            step['runtime_disposition']='SERVICE_REFERRAL_ONLY_NO_OWNER_RECONNECTION'
            step['authoring_blockers']+=['SOURCE_ABSENCE_SCOPE_AUDIT_REQUIRED']
        if sid=='a_cool_engine':step['authoring_blockers']+=['SOURCE_ABSENCE_SCOPE_AND_ELIGIBILITY_REVIEW_REQUIRED']
        if sid=='a_fuse':step['unresolved_route']='ESCALATE'
        examples.append({'record_id':sid,'accepted_source_pages':PAGES[sid],'draft_claim_ids':[a['claim_id'] for a in claims],
            'draft_branches':step['branch_drafts'],'expected_runtime_before_review':'UNSUPPORTED',
            'approval_status':'DRAFT','authoring_blockers':step['authoring_blockers'],
            'evaluation_partition':'REGRESSION_TUNING_NOT_HELD_OUT'})
    for procedure in c['procedures'].values():
        procedure['review_status']='DRAFT';procedure['boundaries_checked']=False
    for rule in c['rules'].values():rule['review_status']='DRAFT'
    # Approval cannot be copied across new content/version. This is an empty draft ledger.
    reviews={'schema_version':'review-ledger-v1','decisions':[]}
    drafted=EvidenceRegistry(c,reviews,original.evidence,original.source)
    write(output/'candidate_registry.json',c);write(output/'review_decisions.json',reviews)
    write(output/'accepted_examples.json',{'schema_version':'accepted-eleven-draft-v1','manual_checksum':original.checksum,
        'index_id':original.index_id,'registry_version':c['version'],'context_sha256':history,'examples':examples,
        'note':'Derived solely from scoped feedback on the original eleven; no new generated expansion cases or release approval.'})
    report={'schema_version':'accepted-reconciliation-report-v1','manual_checksum':original.checksum,
        'index_id':original.index_id,'candidate_digest':content_hash(c),'examples':len(examples),'source_ready':drafted.source_ready(),
        'ready_steps':[sid for sid in c['steps'] if drafted.step_ready(sid)],'formal_decisions':0,
        'existing_registry_changed':False,'human_review_files_changed':False,'embedding_rebuilt':False}
    write(output/'reconciliation_report.json',report)
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--index',required=True,type=Path);p.add_argument('--output',type=Path,default=Path('registry/reconciled-accepted-eleven'))
    args=p.parse_args();print(json.dumps(reconcile(args.index,args.output)))
if __name__=='__main__':main()
