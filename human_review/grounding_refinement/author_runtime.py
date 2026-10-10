"""Concrete isolated runtime candidates. No reviews, installation or inference.

Rules are explicit typed author proposals, never extracted expressions or inferred
diagnostic order. Engineering policy/scenario routes are separate from OEM steps.
"""
from copy import deepcopy
from pathlib import Path
import json
import re

from human_review.grounding_refinement.case_suite import ROOT,load,textsha,content_hash,sha

OUT=Path(__file__).parent/'candidate_runtime_v3'
VERSION='isolated-runtime-candidates-v3'

# Explicit author decisions after reading the complete case-specific answers.
ACTION={'EXP003','EXP005','EXP006','EXP008','EXP012','EXP015','EXP017','EXP025',
        'a_fuse','a_switches_on','a_refuel','a_raise_stand','a_cool_engine'}
STOP={'GEN001','GEN002','GEN005','GEN016','GEN021','GEN042','GEN049','GEN050',
      'EXP016','EXP023','EXP048'}
QUESTIONS={'GEN043':'dynamic_conditions_met','EXP001':'hazard_button_identified',
           'EXP002':'hazards_on','EXP007':'mode_button_identified','EXP011':'abs_continuous_above_5',
           'EXP028':'noise_only','EXP030':'rpm_disproportionate','EXP047':'dim_lights_or_weak_horn',
           'EXP049':'dim_lights_or_weak_horn'}
WITHHOLD={'GEN004','GEN037','GEN041','GEN046','GEN047','GEN048','EXP014','EXP027','EXP031',
          'EXP032','EXP034','EXP036','EXP037','EXP038','EXP040','EXP044','EXP046','a_reconnect'}

# fact_key, source-backed expected boolean, origin. No temperature thresholds.
SETUPS={
 'EXP003':[('turn_switch_centred',True,'MANUAL')],
 'EXP005':[('home_button_identified',True,'PRODUCT_POLICY')],
 'EXP006':[('safely_stopped',True,'PRODUCT_POLICY'),('controls_identified',True,'PRODUCT_POLICY')],
 'EXP008':[('safely_stopped',True,'PRODUCT_POLICY'),('trip1_reset_intended',True,'PRODUCT_POLICY')],
 'EXP012':[('hard_emergency_braking_pulsations',True,'MANUAL')],
 'EXP015':[('already_securely_upright_on_centre_stand',True,'MANUAL'),('firm_flat_ground',True,'MANUAL'),('neutral_and_lamp',True,'MANUAL')],
 'EXP017':[('firm_flat_ground',True,'MANUAL')],
 'EXP025':[('bike_upright',True,'MANUAL'),('firm_level_surface',True,'MANUAL'),('rear_reservoir_horizontal',True,'MANUAL')],
 'a_fuse':[('ignition_off',True,'MANUAL'),('fuse_defective_confirmed',True,'MANUAL'),('fuse_identity_and_same_rating_confirmed',True,'PRODUCT_POLICY')],
 'a_switches_on':[('reported_switch_off',True,'MANUAL'),('switch_identified',True,'PRODUCT_POLICY')],
 'a_refuel':[('low_fuel_condition',True,'MANUAL'),('engine_off',True,'MANUAL'),('ventilated_area',True,'MANUAL'),('no_flames_smoking_sparks',True,'MANUAL'),('handheld_devices_off',True,'MANUAL')],
 'a_raise_stand':[('stand_down',True,'MANUAL'),('stand_indicator_shows',True,'MANUAL')],
 'a_cool_engine':[('documented_overheat_condition_confirmed',True,'MANUAL')],
}

def write(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def author():
    suite=load(Path(__file__).parent/'case_specific_v2/suite.json')
    records=deepcopy(suite['records']);sources=deepcopy(suite['sources'])
    evidence={obj['id']:obj for obj in map(json.loads,(ROOT/'build/index-bge-final/evidence.jsonl').read_text(encoding='utf-8').splitlines())}
    repair_log=[]
    # Preserve actual table headers, cell text and units instead of empty text fields.
    for eid,source in sources.items():
        raw=evidence.get(eid,{}).get('raw_object',{})
        if not source['exact_text'] and source.get('object_type')=='table':
            cells=raw.get('data',{}).get('table_cells',[])
            require_cells=bool(cells)
            if require_cells:
                source['table_cells']=cells
                source['exact_text']=json.dumps(cells,ensure_ascii=False,sort_keys=True)
                source['text_sha256']=textsha(source['exact_text']);source['text_span']=[0,len(source['exact_text'])]
                source['table_representation']='Exact structured cells with row/column spans and header flags; not invented row interpretation'
                repair_log.append({'source_id':eid,'repair':'Preserve structured table rather than empty candidate text'})
    policy_ids=[eid for eid,obj in sources.items() if obj['authority']=='PRODUCT_POLICY']
    def policy(needle):
        return [eid for eid in policy_ids if needle.casefold() in sources[eid]['exact_text'].casefold()]
    repeat_policy=policy('Do not repeat')
    selection_policy=next(r['branch_context']['producer'].get('source_limits',[]) for r in records if r['record_id']=='GEN051')
    general_policy=policy('UNKNOWN')
    assert repeat_policy and general_policy
    def mapped(claim,ids,policy_refs=()):
        claim['support_evidence_ids']=list(ids)
        claim['policy_support_ids']=list(policy_refs)
        claim['source_spans']=[{'evidence_id':eid,'text_sha256':sources[eid]['text_sha256'],
                              'text_span':sources[eid]['text_span'],'exact_text':sources[eid]['exact_text'],
                              'provenance':sources[eid].get('provenance',[])} for eid in ids]
        claim['support_review_status']='AGENT_AUTHORED_EXACT_OBJECT_SCOPE; NOT_INDEPENDENT_SIGNOFF'
        return claim
    # Fix original mappings by exact OEM object scope, not broad nearby pages.
    original_maps={
      'a_switches_on:accepted-draft:warning0':['evidence_e141910747861df746685a2e'],
      'a_refuel:accepted-draft:main':['evidence_ff04ce4096a0444b874929b5','evidence_59184c3d66b4b2a53143442e','evidence_5034a983959e52887c0072bf'],
      'a_refuel:accepted-draft:warning0':['evidence_b02f383c70aefc628503f3ce','evidence_fd5a9183e18775af14291d97','evidence_430d1ff1fa68dbcabfbbb0cf'],
      'a_refuel:accepted-draft:warning1':['evidence_a66e862d634c23573bb30c90'],
      'a_refuel:accepted-draft:warning2':['evidence_3b85a6b930363f5bd9ce3f4e'],
      'a_refuel:accepted-draft:setup0':['evidence_b57860aec348c8aefa09d0e3','evidence_2a4402c7fa3a280cff8e7923','evidence_fd5a9183e18775af14291d97'],
      'a_fuse:accepted-draft:warning0':['evidence_4e1a61e411e2b752c1a8716b'],
      'a_fuse:accepted-draft:warning1':['evidence_8b5ef092d20493cd2b9b58b8','evidence_00497a5a6998712d564a2df2'],
      'a_fuse:accepted-draft:warning2':['evidence_0c58e6021490c80a7a7f8d99'],
      'lookup_starter_duration:accepted-draft:setup0':['evidence_f4dbcfa8fd37b20ab295e5a1','evidence_001335e5b633008075189f76','evidence_272bd86a27fe5489e66a4af6','evidence_017a78d6fdfd30389967f3c9','evidence_a7a5ea8352d16679e89780fb'],
    }
    for record in records:
        rid=record['record_id']
        if record['case_kind']=='ORIGINAL_ELEVEN_DRAFT_REFERENCE':
            for claim in record['claims']:
                ids=original_maps.get(claim['claim_id'],claim['support_evidence_ids'])
                mapped(claim,ids)
                if claim['claim_id'] in original_maps:repair_log.append({'record_id':rid,'claim_id':claim['claim_id'],'exact_source_ids':ids})
            if rid=='a_refuel':
                record['claims'].append(mapped({'claim_id':rid+':cap-lock','exact_claim_text':'Press the cap to lock with the key in position, then remove the key and close the flap.','response_role':'ACTION'},
                                              ['evidence_99063aa16735b277a9cb4fb3','evidence_a509149b220b562583a4cf2d']))
                repair_log.append({'record_id':rid,'repair':'Preserve documented cap locking/removal/flap closure in the draft parent procedure'})
            # Turn every original conditional branch into a concrete source-scope record.
            record['canonical_answer']=' '.join(c['exact_claim_text'] for c in record['claims'])
    registry={'schema_version':'isolated-draft-step-registry-v3','version':VERSION,
              'manual_checksum':suite['manual_sha256'],'index_id':suite['index_id'],
              'authored_by':'grounding-refinement-agent','steps':{},'rules':{},'dependencies':{},'procedures':{},
              'review_decisions':[],'runtime_authorized':False}
    routes=[];sessions=[];branches=[];gaps=[]
    def rule(rid,key,expected,origin,ids,question=None,rider=True):
        identifier=rid+':rule:'+key
        registry['rules'][identifier]={'rule_id':identifier,'predicate_type':'BOOLEAN','fact_key':key,'operator':'EQ',
          'expected_value':expected,'unit':None,'origin':origin,'source_evidence_ids':ids if origin=='MANUAL' else [],
          'policy_source_ids':ids if origin=='PRODUCT_POLICY' else [],'policy_version':VERSION if origin=='PRODUCT_POLICY' else None,
          'clarification_evidence_ids':ids if origin=='MANUAL' and rider else [],'review_status':'DRAFT','rule_version':VERSION,
          'clarification_question':question,'rider_resolvable':bool(question and rider),
          'human_signoff':False,'authoring_scope':'Explicit typed proposition; no mechanical health or diagnostic order inferred'}
        return identifier
    for record in records:
        rid=record['record_id'];claims=record['claims']
        manual_ids=sorted({eid for c in claims for eid in c['support_evidence_ids'] if sources[eid]['authority'].startswith('OEM')})
        if record['case_kind']=='ENGINEERING_POLICY_SCENARIO' or rid=='EXP050':
            routes.append({'record_id':rid,'route_kind':'TRUSTED_POLICY_OR_FAILURE_SCENARIO','expected_route':record['candidate_expected_route'] or 'SYSTEM_ERROR',
                           'canonical_candidate':record['canonical_answer'],'step_id':None,'source_support_ids':record['required_candidate_source_ids'],
                           'required_signal':'Trusted typed scenario event; user/model text cannot fabricate outage, approval, safety stop or source verdict',
                           'runtime_authorized':False})
            sessions.append({'record_id':rid,'scope':'POLICY_SCENARIO_NOT_OEM_ACTION','initial_facts':{},'events':[],
                             'expected_route':record['candidate_expected_route'] or 'SYSTEM_ERROR','actual_runtime_measured':False})
            continue
        if rid in WITHHOLD:
            routes.append({'record_id':rid,'route_kind':'SOURCE_LIMIT_OR_AUTHORIZED_SERVICE','expected_route':'UNSUPPORTED',
                           'canonical_candidate':record['canonical_answer'],'step_id':None,'source_support_ids':manual_ids,
                           'support_scope':'Scoped source-limit/referral candidate, not a new owner repair step','runtime_authorized':False})
            sessions.append({'record_id':rid,'scope':'WITHHOLDING_NOT_OEM_PROCEDURE','initial_facts':{},'events':[],
                             'expected_route':'UNSUPPORTED','actual_runtime_measured':False})
            if rid in ('EXP027','EXP032','EXP040','a_reconnect'):
                gaps.append({'record_id':rid,'gap':record['canonical_answer'],'smallest_decision':'Preserve this scoped abstention; do not invent a threshold, fitting procedure or source reconciliation','source_ids':manual_ids})
            continue
        kind='SAFETY_STOP' if rid in STOP else 'ACTION' if rid in ACTION else 'LOOKUP'
        sid=rid+':candidate-v3';pid=sid+':procedure' if kind=='ACTION' else None
        # Role grouping is an author proposal. Complete text remains immutable.
        runtime_claims=[]
        for i,c in enumerate(claims):
            role=c.get('response_role','FACT')
            if kind=='ACTION':role='ACTION' if i==0 else ('WARNING' if re.search(r'warning|risk|injur|failure|damage|burn',c['exact_claim_text'],re.I) else 'FACT')
            elif kind=='SAFETY_STOP':role='WARNING'
            else:role='FACT' if role=='ACTION' else role
            runtime_claims.append({'claim_id':c['claim_id'],'text':c['exact_claim_text'],'evidence_ids':[eid for eid in c['support_evidence_ids'] if sources[eid]['authority'].startswith('OEM')],
                                   'policy_support_ids':[eid for eid in c['support_evidence_ids'] if not sources[eid]['authority'].startswith('OEM')],
                                   'response_role':role,'presentation_mode':'DRAFT_PARAPHRASE','source_spans':c.get('source_spans',[])})
        applicability=[rule(rid,'bike_scope_confirmed',True,'PRODUCT_POLICY',general_policy)]
        if kind=='ACTION':applicability.append(rule(rid,'attempted:'+sid,False,'PRODUCT_POLICY',repeat_policy))
        setup=[]
        for fact,expected,origin in SETUPS.get(rid,[]):
            supporting=manual_ids if origin=='MANUAL' else general_policy
            rider=fact!='documented_overheat_condition_confirmed'
            q=None if not rider else 'Can you confirm '+fact.replace('_',' ')+'?'
            identifier=rule(rid,fact,expected,origin,supporting,q,rider)
            applicability.append(identifier);setup.append({'fact_key':fact,'expected':expected,'rule_id':identifier})
        if rid in QUESTIONS:
            key=QUESTIONS[rid]
            question=next((c['exact_claim_text'] for c in claims if '?' in c['exact_claim_text']),record['question'])
            identifier=rule(rid,key,True,'MANUAL',manual_ids,question)
            applicability.append(identifier)
        required=set(manual_ids)
        if record['case_kind']=='ORIGINAL_ELEVEN_DRAFT_REFERENCE':
            required|={eid for eid in record['required_candidate_source_ids'] if sources[eid]['authority'].startswith('OEM')}
        categories={key:[] for key in ('actions','warnings','prerequisites','tables','figures','conditions')}
        categories['actions']=sorted({eid for c in runtime_claims if c['response_role'] in ('ACTION','FACT') for eid in c['evidence_ids']}) or manual_ids
        categories['warnings']=sorted({eid for c in runtime_claims if c['response_role']=='WARNING' for eid in c['evidence_ids']})
        categories['prerequisites']=sorted({eid for c in runtime_claims if c['response_role']=='PREREQUISITE' for eid in c['evidence_ids']})
        for eid in required:
            obj=sources[eid]
            if obj.get('object_type')=='table':categories['tables'].append(eid)
            if obj.get('requires_visual_verification') or obj.get('object_type') in ('picture','figure','image'):categories['figures'].append(eid)
        registry['steps'][sid]={'step_id':sid,'manual_checksum':suite['manual_sha256'],'action_evidence_ids':categories['actions'],
          'parent_procedure_id':pid,'symptom_tags':[rid],'applicability_rule_ids':applicability,'required_evidence_ids':sorted(required),
          'dependency_manifest_version':VERSION,'review_status':'DRAFT','rule_version':VERSION,'kind':kind,
          'safety_rule_ids':[],'next_step_ids':[],'next_step_evidence_ids':[],'repeat_rule_ids':[],
          'claims':runtime_claims,'unresolved_route':'ESCALATE' if rid=='a_fuse' else 'CONTINUE_DOCUMENTED',
          'unresolved_evidence_ids':['evidence_15e1ce067b76cc524a0448d2'] if rid=='a_fuse' else [],
          'authoring_blockers':['INDEPENDENT_SOURCE_RULE_DEPENDENCY_SIGNOFF_REQUIRED','BRANCH_SCOPES_AND_ROLE_GROUPS_NOT_RUNTIME_APPROVED'],
          'canonical_record_id':rid,'runtime_authorized':False}
        registry['dependencies'][sid]={'step_id':sid,'version':VERSION,'manual_checksum':suite['manual_sha256'],
          'index_id':suite['index_id'],'action_evidence_ids':categories['actions'],'required_evidence_ids':sorted(required),
          'review_status':'DRAFT','scope_review_complete':False,'categories':categories,
          'branch_scope':'Main response and explicit conditional children are separate; not relevance-based closure'}
        if pid:registry['procedures'][pid]={'procedure_id':pid,'manual_checksum':suite['manual_sha256'],'evidence_ids':sorted(required),
          'boundaries_checked':False,'review_status':'DRAFT','sequence_kind':'SOURCE_PROCEDURE_CANDIDATE_NO_DIAGNOSTIC_NEXT_STEP_ORDER',
          'source_text':record['canonical_answer'],'runtime_authorized':False}
        context=record['branch_context']
        branch_records=context.get('branches',{}) if 'branches' in context else {str(i):b for i,b in enumerate(context.get('reviewed_conditional_spans',[]))}
        for key,branch in branch_records.items():
            branches.append({'branch_id':rid+':branch:'+key,'parent_step_id':sid,'branch_context':branch,
                             'source_ids':record['required_candidate_source_ids'],'review_status':'DRAFT',
                             'selection':'Explicit reviewed typed predicate required; narrative never executes as code','runtime_authorized':False})
        if rid in ('lookup_starter_duration','a_switches_on'):
            branches.append({'branch_id':rid+':R001-recovery','parent_step_id':sid,'condition':{'fact_key':'successive_cranking_attempts','operator':'GE','expected_value':3,'value_type':'NUMBER','unit':'attempts'},
              'claim_text':'If you have already made three successive cranking attempts, wait 15–20 seconds for the battery to recover.',
              'source_ids':['evidence_634643c9be7de4d37ee7b5a2'],'owner_scope':'R001_ACCEPTED; R002_PENDING','repeat_authorized':False,'runtime_authorized':False})
        initial={'bike_scope_confirmed':True}
        initial.update({x['fact_key']:None for x in setup})
        if rid in QUESTIONS:initial[QUESTIONS[rid]]=None
        sessions.append({'record_id':rid,'step_id':sid,'symptoms':[rid],'manual_checksum':suite['manual_sha256'],
          'initial_facts':initial,'events':[{'outcome':'ACTION_COMPLETED_UNRESOLVED','expected_new_health_fact':False,'expected_repeat':False},
            {'outcome':'OBSERVED_NORMAL','requires_rule_id_and_typed_fact':True,'must_not_prove_system_health':True},
            {'outcome':'UNCLEAR','expected_one_focused_question':True},
            {'outcome':'RESOLVED','scope':'Selected issue only; other issues remain open'},
            {'outcome':'CORRECTION','supersedes_immutable_attempt':True}],
          'review_status':'DRAFT','actual_runtime_measured':False})
        routes.append({'record_id':rid,'route_kind':'SOURCE_DRAFT_STEP','step_id':sid,
                       'initial_candidate_route':'AMBIGUOUS' if setup or rid in QUESTIONS else 'SUPPORTED',
                       'requires_actual_formal_approval':True,'runtime_authorized':False})
        if rid=='a_cool_engine':
            gaps.append({'record_id':rid,'gap':'Source supplies switch-OFF/allow-cool but no numerical overheating criterion or restart clearance. The observed condition cannot be inferred from display value or photo.',
                         'smallest_decision':'Keep unknown condition on service-only path; no threshold needs to be invented or approved','source_ids':manual_ids})
        if rid=='EXP015':
            gaps.append({'record_id':rid,'gap':'Reset presupposes safely upright, securely supported motorcycle; supporting reset evidence does not teach lifting a fallen bike.',
                         'smallest_decision':'Only the already-supported branch is a candidate; otherwise service referral','source_ids':manual_ids})
    OUT.mkdir(exist_ok=True)
    write('candidate_registry.json',registry);write('source_objects.json',{'sources':sources,'formal_approvals':0})
    write('trusted_routes.json',{'routes':routes,'runtime_authorized':False});write('session_fixtures.json',{'records':sessions,'runtime_authorized':False})
    write('branch_dependencies.json',{'branches':branches,'runtime_authorized':False});write('original_span_repairs.json',{'repairs':repair_log,'producer_modified':False})
    write('source_gaps.json',{'gaps':gaps,'formal_approval_requested':False})
    write('manifest.json',{'version':VERSION,'suite_sha256':sha(Path(__file__).parent/'case_specific_v2/suite.json'),
                         'author_code_sha256':sha(Path(__file__)),'outputs':{p.name:sha(p) for p in OUT.glob('*.json') if p.name!='manifest.json'},
                         'record_count':len(routes),'step_count':len(registry['steps']),'rule_count':len(registry['rules']),
                         'formal_approvals':0,'live_provider_calls':0,'shared_runtime_installed':False})
    print(json.dumps({'records':len(routes),'draft_steps':len(registry['steps']),'draft_rules':len(registry['rules']),
                      'branch_records':len(branches),'session_fixtures':len(sessions),'formal_approvals':0}))

if __name__=='__main__':author()
