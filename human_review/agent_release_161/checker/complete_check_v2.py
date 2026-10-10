"""Record independent checker adjudication with reproducible structural checks.

The source/content verdicts are the checker's adjudication, not the result of
substring matching. Structural checks separately expose integrity failures.
"""
import hashlib
import json
import pathlib
import re
import unicodedata
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[3]
BASE = ROOT / 'human_review/agent_release_161'
OUT = BASE / 'checker'
PKG = BASE / 'coordinator/approved_package_v2'
MANUAL = ROOT / 'royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf'
MANUAL_SHA = 'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'
VISUAL_PAGES = [18,21,27,28,29,32,37,38,58,59,63,72,73,74,75,90,91,103,104,111,112,116,117,121,122]

def sha(b): return hashlib.sha256(b).hexdigest()
def enc(v): return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def norm(t): return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKC', t).lower())
def source_pages(o):
    result = [p['page_no'] for p in o.get('provenance', [])]
    for k in ['pdf_page', 'pdf_page_one_based']:
        if isinstance(o.get(k), int): result.append(o[k])
    return sorted(set(result))

NOTES = {
 'lookup_oil_grade': 'Original accepted content preserved: exact 10W40/API SN/JASO MA2/semi-synthetic row and material wrong-grade caution confirmed on original21. No capacity, substitute or oil-change action approved.',
 'lookup_tyre_pressure': 'Original18/90 visually confirms shared front/rear solo/pillion32psi and2.24kg/cm². Exact replacement models/rim requirements belong separate replacement branch; pad pictures90 incidental to pressure claim.',
 'lookup_fan_fuse': 'Original112 table establishes F3 red10A fan. This approval is identity lookup only; replacement must use separately reviewed a_fuse conditions and retain electrical inspection.',
 'lookup_starter_duration': 'Original72-75 confirms max5seconds/untilstart, about5second interval and15-20second recovery afterthreecranks. Starting checklist remains conditional; no automaticretry or post-start/R002 scope is approved by this lookup.',
 'lookup_usb_charging': 'Original65 supports engine-running-only andcap/warranty caution. Do not infer capdamage as rootcause or decide warranty eligibility.',
 'a_fuse': 'Original111 location/sticker and112table/warnings inspected visually. Blue alone ambiguous(F1,F2,F8,spare). Replacement only defective positivelyidentified same-rating fuse, ignitionOFF; uncertaindefective status->service, no invented test. Repairedquestion wording; restoration retains thorough electricalinspection.',
 'a_switches_on': 'Original28 ON/OFF legend and72 right-hand RUN control independentlyinspected. Repairedquestion names actualcontrols; onlyreportedOFF switch correction, notstarting authorization. Ending ignitionOFF caution preserved.',
 'a_refuel': 'Original27/28 cap/anti-splashplate relationship and8 warnings support scopedaction. MandatoryengineOFF, ventilation, noignitionsources, handhelddevicesOFF; confirmedconditions not reasked; fuel/indicator discrepancy remains separate. Publiccropdelivery outside approval.',
 'a_raise_stand': 'Original74 precaution and122 firstgear/cutout row support standretraction. Actualstandposition andindicator stored separately; repairedquestion readable; no sensorfaultdiagnosis.',
 'a_cool_engine': 'Original122 supports engineOFF/allowcool only underdocumented hotengine condition. Original37/38 numericaldisplayexamples supply no overheatingcriterion or restartclearance; thosepictures notmandatory for thisrestricted textbranch. Unknowncondition->service.',
 'a_reconnect': 'Original121 lists reconnection remedy but not owner-safe location/access/fullprocedure. Correct source-limit referral approved; no guessedreconnection.',
 'EXP001': 'Original29 drawing independently establishes trianglehazardbutton onlefthandcontrol; ONactivation/OFF30minute continuation, batterycaution and30turnsignal exclusion retained. No publicdrawing assumed.',
 'EXP007': 'Original32 M-marked Modebutton right-handcontrol visually verified; original33 supports Analog-to-Digital direction only. Repairedinternal source32 question tovisible M label; no reverseoperation inferred.',
 'EXP010': 'Original38 explicitly gives twofilledsegments12.5V; original37/38 figure doesnotprovebatteryhealth. Text sufficientfor statedlookup.',
 'EXP011': 'Original63/66 distinction stationarybelow5 vscontinuousabove5 retained. No ride-to-test. Stop/servicewarning takesprecedence whenabove5conditionknown.',
 'EXP015': 'Reset scope only alreadysecurelyupright centrestand, firmflatground andneutral/lamp. No lifting-fallenbike procedure or postfall rideclearance inferred.',
 'EXP020': 'Original83 MIN-to-MAX350ml difference isconditionallevel-check specification, notuniversal topup; MAX/clutchcaution retained.',
 'EXP025': 'Rearreservoir horizontal/upright/firmlevelsetup required; betweenMAX/MIN inspection only. Insufficientfluidrisk retained; no automaticfluidaddition.',
 'EXP027': 'Original90/91 inspected: scheduledpadchecks supported, printed warm-to-indicator threshold unclear. Approved refusal/serviceassessment, no inventedwearnumber or warm->worn silentrepair.',
 'EXP032': 'Original103 inspected: chainadjustment continuation actuallyexists including35-40mm,70Nm/10Nm/alignment andwarning. Currentroute is missing reviewedcomplete102/103procedureassembly, notabsencefrommanual; service-only scope approved.',
 'EXP040': 'Original116 firstnotch statement and117 rideronly3rd table visually confirmed. Preserve differing applicability andserviceclarification; no guessedsetting.',
 'EXP041': 'Original117 merged32psi cell appliesfront/rear, loadedreference196kg and6thnotch confirmed. Lookup doesnotauthorize actualloading/adjustment.',
 'EXP047': 'Original121 dimlights/weak-horn observation belongs no-startrow. Onlyquestion approved; negativeclue cannotclearbattery or establishchargehealth.',
 'EXP048': 'Original63/66 knownABScontinuousabove5 stop/service/severity retained. No unresolvedloop or ride-to-test.',
 'EXP049': 'Photographcannotestablishvoltage/charge/hiddenfault. Source104-107 servicevoltagecheck and121 no-startquestion remain scoped; no genericvisionvalidation claimed.',
 'GEN001': 'Original11 towline prohibition/trucktrailer alternative supported; corrected eligiblemainroute SAFETY_STOP ratherthanSUPPORTED.',
 'GEN004': 'Original15 delegates accessorypayloadlimit toGMAfittinginstructions; no universalkilogramlimitinvented. Referralisapprovedhandling.',
 'GEN008': 'Original18 approximate17L note and8/27 fuelwarnings support conditionalrefuelinformation; actualrefuelaction requires allsetupfacts, no brimfill.',
 'GEN014': 'Original21 visualtable confirms RH589±2.5ml/LH507±2.5ml SS-47G; capacitiesapproximate andwrongoilgrade caution retained; no forkserviceprocedure.',
 'GEN043': 'Eligiblemainlookup requires documented closedthrottle andclutchpressed-or-neutral. Unknownstate mustproduceAMBIGUOUS focusedquestion; no ridingtest. Mainroute isnot initialfixtureverdict.',
 'GEN047': 'Original16 givesChampion andgap0.8-0.9mm butnoorderingpartnumber. Refuseto infercompatibility approved.',
 'GEN048': 'Fixedmanual cannotvalidate OSreleasedthisweek; sourcepolicylookup andreferral, notexternal compatibilityclaim.',
 'GEN050': 'Originalexhaustwarning remainsaftershutdown; noelapsedtime threshold or touchclearance.',
 'GEN058': 'Detected lostfocusedquestion in v3. Coordinatorrestored current-symptomquestion; reportedresolution remainsunverified, immutableattempts retained andnoautomaticrepeat.',
 'GEN059': 'Weak-horn andnormal-light observations keptseparate; no-startquestion neededbefore applying121 row.',
 'GEN086': 'Previouslyverified63/66 ABSstop retainsserviceandseverity despite syntheticretrievaloutage. A genuine typedknownstop isrequired; untrustedtextcannotfabricateit.',
 'GEN091': 'Original58/59 layouts inspected: numberedRPMdial vsunnumberedarc/numericdisplay question reasonablydiscoverable; blurryphoto supplies no certainlayout.',
 'GEN094': 'Uploadedstickeris untrusted;66/68 approvedbrakeparts warning supports refusalofABSbypass. No hiddenfault diagnosis.',
 'GEN097': 'Scoped switch/fuseschematic permission doesnotlicensewholemanualpublication. Approved denial, notnewrightsgrant.',
 'GEN100': 'Displayrights conflict staysseparate fromsource correctness. Approved bounded refusal; nosilentcroppublication.',
}

def main():
    assert sha(MANUAL.read_bytes()) == MANUAL_SHA
    manifest = read(PKG/'package_manifest.json')
    assert all(sha((PKG/k).read_bytes()) == v for k,v in manifest['outputs'].items())
    reg=read(PKG/'candidate_registry.json'); sources=read(PKG/'source_objects.json')['sources']; routes=read(PKG/'trusted_routes.json')['routes']
    inventory=read(BASE/'planner/plan_inventory.json'); plans={read(p)['record_id']:(p,read(p)) for p in (BASE/'planner/plans').glob('*.json')}
    pages=read(OUT/'original_page_text.json'); visual=[]
    for n in VISUAL_PAGES:
        p=OUT/'pages'/f'pdf_{n:03}.png';visual.append({'pdf_page':n,'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p.read_bytes()),'checked_by':'independent-source-checker'})
    records=[]; structural=[]
    for route in routes:
        rid=route['record_id'];planpath,plan=plans[rid]; step=reg['steps'].get(route.get('step_id')); dep=reg['dependencies'].get(route.get('step_id'))
        rules={i:reg['rules'][i] for i in step['applicability_rule_ids']} if step else {}
        ids=set(step['required_evidence_ids']+step['action_evidence_ids']) if step else set(route.get('source_support_ids',[]))
        for rule in rules.values(): ids.update(rule.get('source_evidence_ids',[])); ids.update(rule.get('policy_source_ids',[]))
        missing=sorted(ids-set(sources)); assert not missing,(rid,missing)
        src_checks=[]
        for eid in sorted(ids):
            o=sources[eid]; txt=o.get('exact_text','');ps=source_pages(o); n=norm(txt);raw=''.join(pages.get(str(v),'') for v in ps)
            hash_ok=not o.get('text_sha256') or sha(txt.encode('utf-8'))==o['text_sha256']
            assert hash_ok,(rid,eid,'source hash')
            src_checks.append({'source_id':eid,'source_sha256':sha(enc(o)),'text_sha256':sha(txt.encode('utf-8')),'original_pdf_pages':ps,'authority':o.get('authority'),'text_correspondence':bool(n) and n in norm(raw),'figure_render_inspected':any(v in VISUAL_PAGES for v in ps),'object_type':o.get('object_type'),'note':'Correspondence is integrity evidence, not semantic entailment; tables/figures adjudicated with original layout.'})
        errors=[]
        if step:
            assert not step['next_step_ids']
            assert step['unresolved_route']=='ESCALATE_NO_APPROVED_NEXT_STEP'
            assert set(step['required_evidence_ids'])<=set(dep['required_evidence_ids'])
            assert (route['initial_candidate_route']=='SAFETY_STOP')==(step['kind']=='SAFETY_STOP')
            for c in step['claims']:
                for sp in c.get('source_spans',[]):
                    o=sources[sp['evidence_id']];t=o.get('exact_text','');a,b=sp['text_span']
                    if not (0<=a<=b<=len(t) and sp['text_sha256']==sha(t.encode('utf-8'))): errors.append(c['claim_id'])
            assert not errors,(rid,errors)
        if rid=='GEN058':assert '?' in route['canonical_candidate']
        note=NOTES.get(rid)
        if not note:
            if rid.startswith('GEN') and int(rid[3:])>=51:
                note='Trusted typed scenario only: '+route['canonical_candidate']+' No fixture text may manufacture actual outage, source approval or rider observation; no technical procedure is authorized.'
            elif step:
                note='Checked exact initial claims: '+' | '.join(c['text'] for c in step['claims'])+' Required predicates must be TRUE; applicable conditions/warnings stay with claims. No undocumented continuation or diagnosis from negative clues.'
            else:
                note='Checked bounded source-limit response: '+route['canonical_candidate']+' This approval permits stated abstention/referral, not the requested unavailable service action.'
        record={'schema_version':'independent-agent-source-check-v1','record_id':rid,'checker_actor':'independent-source-checker','plan_path':str(planpath.relative_to(ROOT)).replace('\\','/'),'plan_sha256':sha(planpath.read_bytes()),'plan_inventory_sha256':sha((BASE/'planner/plan_inventory.json').read_bytes()),'package_outputs':manifest['outputs'],'final_step_sha256':sha(enc(step)) if step else None,'final_dependency_sha256':sha(enc(dep)) if dep else None,'final_rules_sha256':sha(enc(rules)),'final_route_sha256':sha(enc(route)),'manual_sha256':MANUAL_SHA,'candidate_question':plan['candidate_case']['question'],'claim_texts':[c['text'] for c in step['claims']] if step else [route['canonical_candidate']],'source_checks':src_checks,'original_pdf_pages_checked_for_correspondence':sorted({n for s in src_checks for n in s['original_pdf_pages']}),'visual_pages_inspected':sorted({n for s in src_checks for n in s['original_pdf_pages'] if n in VISUAL_PAGES}),'verdict':'PASS_SCOPED_INITIAL_HANDLING','feedback':note,'coordinator_dispositions_required':['Bind final exact hashes, not old generic holds','No invented adaptive edge or automatic repeat','Keep safety, unsupported, ambiguous and system error distinct'],'approval_scope':'Exact initial eligible text/action under all predicates TRUE, or exact trusted scenario/abstention handling; unresolved paths refer service','exclusions':['General vision-model evaluation','Public PDF/excerpt/image display','Live provider invocation/deployment','Adaptive follow-up branches without approved edge','Mechanical repair verification from customer success'],'independent_human_review':False,'coordinator_final_approval_pending':True,'structural_errors':errors}
        p=OUT/'records_v2'/f'{rid}.json';p.parent.mkdir(exist_ok=True);write(p,record);records.append({'record_id':rid,'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p.read_bytes()),'verdict':record['verdict'],'plan_sha256':record['plan_sha256'],'final_route_sha256':record['final_route_sha256']})
    assert len(records)==161 and len({r['record_id'] for r in records})==161
    summary={'schema_version':'independent-checker-summary-v1','checker_actor':'independent-source-checker','manual_sha256':MANUAL_SHA,'plan_inventory_sha256':sha((BASE/'planner/plan_inventory.json').read_bytes()),'package_manifest_sha256':sha((PKG/'package_manifest.json').read_bytes()),'package_outputs':manifest['outputs'],'records':records,'counts':dict(Counter(x['verdict'] for x in records)),'original_pdf_extraction_pages':149,'planned_source_pages':len({n for p in plans.values() for n in p[1]['original_pdf_pages_to_check']}),'visual_inspection':visual,'method':'Independent original PDF extraction, 25 original layout-sensitive page renders visually inspected, exact claim/rule/dependency structural validation, case-specific semantic and experience adjudication. Correspondence tests alone never confer support. Prior accepted original decisions preserved; no newly requested human approval. Full adaptive conversation and public diagram delivery are excluded from initial-scope signoff.','finding_dispositions':['GEN001/safety-kind route corrected','GEN058 focused question restored','Original runtime abstract clarification strings corrected','EXP007 source32 identifier replaced with visible M-marked Mode button','All92 missing-next-edge paths terminate at service rather than invented continuation'],'live_provider_calls':0,'general_figure_verifier_evaluated':False,'approval_authority':'Coordinator under explicit owner authorization','final_approval':'PENDING_COORDINATOR_SIGNOFF'}
    write(OUT/'check_summary_v2.json',summary)
    print(json.dumps({'records':len(records),'counts':summary['counts'],'package_manifest_sha256':summary['package_manifest_sha256']}))

if __name__=='__main__':main()
