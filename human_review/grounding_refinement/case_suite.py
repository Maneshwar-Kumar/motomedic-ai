"""Case-specific candidate contracts and source-gated live entry point.

Deterministic membership tests are not semantic entailment judgments. Source maps
and editorial verdicts remain engineering data, never runtime approval records.
"""
from copy import deepcopy
from dataclasses import replace
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from constrained_generator import build_generator,envelope,ValidationFailure
from controller_contracts import Fact,Truth
from evidence_registry import EvidenceRegistry,content_hash
from generation_providers import gemma_runtime_config, GeminiJSONProvider
from online_retrieve import Retriever
from reviewed_controller import ReviewedController,start_session
from verify_controller import NoInferenceEncoder
from verify_gemma_grounding import QUERIES

BASE=ROOT/'grounding_bindings/expanded-v1'
OUT=Path(__file__).parent/'case_specific_v2'
FILES=('candidate_grounding_fixtures.json','support_review.json','reviewed_sources.json',
       'corrected_candidates.json','support_validation.json','legacy_attestation_remediation.json')

def textsha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def require(value,reason):
    if not value:raise ValueError(reason)

def verified_inputs():
    from human_review.grounding_refinement.verify_batch import verify
    gate=verify()
    status=load(BASE/'status.json')
    for name,digest in status['support_output_sha256'].items():
        require(sha(BASE/name)==digest,'Changed generator artifact: '+name)
    require(sha(BASE/'support_review.json')=='baff1055936a46242a816a8ae095c350d093a0308be2776225c4453dc5e78547','Review handoff changed')
    require(sha(BASE/'candidate_grounding_fixtures.json')=='3e76e5ecdadd334efb0cb0c20e6dfc0ed7305fc009e49d6720bfdae2ea5478d9','Fixture handoff changed')
    review,sources,corrections=(load(BASE/name) for name in ('support_review.json','reviewed_sources.json','corrected_candidates.json'))
    # Independent stdlib audit; do not import author code that needs PDF extraction.
    require(review['feedback_sha256']==sha(ROOT/'human_review/subagent_feedback.md'),'Feedback changed')
    require(review['first50_inventory_sha256']==sha(ROOT/'human_review/record_workflow/inventory.json'),'Inventory changed')
    require(review['batch100_completion_sha256']==gate['manifest_sha256'],'Batch changed')
    require(review['input_binding_sha256']==sha(BASE/'claim_bindings.json'),'Claim bindings changed')
    require(review['review_code_sha256']==sha(BASE/'review_support.py'),'Review code changed')
    require(review['independent_human_approval'] is False and review['runtime_authorized'] is False,'Agent review promoted')
    count=0
    for row in review['records']:
        require(sha(ROOT/row['draft_path'])==row['draft_sha256'],'Frozen producer changed')
        require(textsha(row['answer'])==row['answer_sha256'],'Answer changed')
        require(not row['source_approval'] and not row['cache_authorized'] and not row['runtime_authorized'],'Record promoted')
        draft=(ROOT/row['draft_path']).read_bytes().decode('utf-8-sig')
        for branch in row['branch_scope_review']:
            require(draft[slice(*branch['draft_span'])]==branch['exact_text'],'Branch span changed')
        for c in row['claims']:
            count+=1
            require(row['answer'][slice(*c['answer_span'])]==c['exact_claim_text'],'Claim span changed')
            require(len(c['support_evidence_ids'])==len(c['source_spans']),'Source locator omitted')
            for eid,span in zip(c['support_evidence_ids'],c['source_spans']):
                obj=sources['sources'][eid]
                require(span['evidence_id']==eid and span['text_sha256']==obj['text_sha256'] and span['text_span']==obj['text_span'],'Source locator changed')
            require(all(sources['sources'][eid]['authority'].startswith('OEM') for eid in c['manual_evidence_ids']),'Policy mislabelled OEM')
            require(all(not sources['sources'][eid]['authority'].startswith('OEM') for eid in c['policy_evidence_ids']),'OEM mislabelled policy')
    require(count==371,'Original claim count changed')
    for obj in sources['sources'].values():
        require(textsha(obj['exact_text'])==obj['text_sha256'],'Source text changed')
        if obj.get('source_path'):require(sha(ROOT/obj['source_path'])==obj['source_sha256'],'Policy source changed')
    require({r['record_id'] for r in corrections['records']}=={'GEN057','GEN058','EXP027','EXP024'},'Corrections missing')
    validation={'records':150,'original_claims':count,'source_objects':len(sources['sources']),
                'scope':'Independent artifact-integrity audit only, no semantic verdict or approval'}
    fixture=load(BASE/'candidate_grounding_fixtures.json')
    require(fixture['support_review_sha256']==sha(BASE/'support_review.json'),'Stale candidate review')
    require(fixture['corrected_candidates_sha256']==sha(BASE/'corrected_candidates.json'),'Stale corrections')
    original={r['record_id']:r for r in review['records']}
    require(len(fixture['records'])==150,'Missing expanded fixtures')
    for row in fixture['records']:
        require(row['producer_draft_sha256']==original[row['record_id']]['draft_sha256'],'Producer binding mismatch')
        require(textsha(row['answer'])==row['answer_sha256'],'Candidate text changed')
        require(row['runtime_authorized'] is False and row['formal_source_approved'] is False,'Candidate promoted')
    return gate,fixture,review,sources['sources'],corrections,validation

def build_suite():
    gate,fixture,review,sources,corrections,validation=verified_inputs()
    index=ROOT/'build/index-bge-final'
    registry=EvidenceRegistry.load(ROOT/'registry/reconciled-accepted-eleven',index,ROOT/'source_manifest.json')
    # Original objects are retained as engineering references only, stripped of media.
    for eid,obj in registry.evidence.items():
        if eid not in sources:
            text=obj.get('raw_object',{}).get('text','')
            sources[eid]={'evidence_id':eid,'authority':'OEM_MANUAL','exact_text':text,
                          'text_sha256':textsha(text),'text_span':[0,len(text)],
                          'index_id':registry.index_id,'manual_sha256':registry.checksum,
                          'object_type':obj.get('type'),'provenance':obj.get('provenance',[]),
                          'requires_visual_verification':obj.get('type') in ('picture','figure','image'),
                          'formal_approval':False}
    records=[]
    review_by_id={r['record_id']:r for r in review['records']}
    corrected_ids={r['record_id'] for r in corrections['records']}
    for row in fixture['records']:
        context=row['producer_context'];original=review_by_id[row['record_id']]
        question=context.get('question')
        if question is None:
            match=re.search(r'Rider:\s*["\u201c](.+?)["\u201d]',context['full_record_text'])
            require(match is not None,'Missing EXP entry question')
            question=match.group(1)
        claims=[]
        for i,c in enumerate(row['claims']):
            ids=c['support_evidence_ids']
            require(all(eid in sources for eid in ids),'Missing selected source')
            require(row['answer'][slice(*c['answer_span'])]==c['exact_claim_text'],'Changed candidate span')
            claims.append({**c,'claim_id':c.get('claim_id',row['record_id']+':correction:'+str(i)),
                           'source_spans':c.get('source_spans',[{'evidence_id':eid,'text_sha256':sources[eid]['text_sha256'],
                                                            'text_span':sources[eid]['text_span']} for eid in ids])})
        all_ids=sorted({eid for c in claims for eid in c['support_evidence_ids']}|
                       {eid for dep in row['branch_dependencies'] for eid in dep['evidence_ids']})
        require(all(eid in sources for eid in all_ids),'Branch context source missing')
        records.append({'record_id':row['record_id'],'case_kind':'ENGINEERING_POLICY_SCENARIO' if row['record_id'].startswith('GEN') and int(row['record_id'][3:])>50 else 'OEM_SCOPE_CANDIDATE',
                        'question':question,'canonical_answer':row['answer'],'claims':claims,
                        'producer_draft_sha256':row['producer_draft_sha256'],'producer_version':row['producer_version'],
                        'candidate_revision':'corrected-alternative-v1' if row['record_id'] in corrected_ids else 'original-answer-v1',
                        'candidate_expected_route':context.get('expected_route'),
                        'branch_context':{'producer':context,'dependencies':row['branch_dependencies'],
                                          'reviewed_conditional_spans':original['branch_scope_review']},
                        'required_candidate_source_ids':all_ids,'prior_holds':row['prior_blocks'],
                        'agent_support_work':'COMPLETE_SAME_CHAT_EDITORIAL','formal_source_approved':False,
                        'runtime_binding':None})
    original_corrections=[]
    for rid,question in QUERIES.items():
        step=registry.candidate['steps'][rid];claims=[]
        for c in step['claims']:
            text=c['text'].replace('kg/cm\u00c2\u00b2','kg/cm\u00b2')
            claims.append({'claim_id':c['claim_id'],'exact_claim_text':text,'support_evidence_ids':c['evidence_ids'],
                           'response_role':c['response_role'],'source_spans':[{'evidence_id':eid,'text_sha256':sources[eid]['text_sha256'],
                                                                       'text_span':sources[eid]['text_span']} for eid in c['evidence_ids']],
                           'support_review_status':'PRECISE_SPAN_AND_ENTAILMENT_AGENT_WORK_PENDING'})
            if text!=c['text']:original_corrections.append({'record_id':rid,'fix':'Repair tyre unit encoding only','producer_modified':False})
        branches=deepcopy(step['branch_drafts'])
        required=set(step['required_evidence_ids'])
        if rid in ('lookup_starter_duration','a_switches_on'):
            eid='evidence_634643c9be7de4d37ee7b5a2'
            require(eid in sources and '15 to 20' in sources[eid]['exact_text'],'R001 recovery evidence changed')
            claim={'claim_id':rid+':R001:recovery','exact_claim_text':'If you have already made three successive cranking attempts, wait 15–20 seconds for the battery to recover.',
                   'support_evidence_ids':[eid],'response_role':'WARNING','source_spans':[{'evidence_id':eid,'text_sha256':sources[eid]['text_sha256'],'text_span':sources[eid]['text_span']}],
                   'support_review_status':'ACCEPTED_R001_WORDING_SOURCE_OBJECT_APPROVAL_PENDING'}
            # Timing belongs to a conditional starter branch, never switch-only output.
            branches['starter_recovery_R001']={'condition':'Three successive cranking attempts already reported; not a request to make three attempts',
                                               'claims':[claim],'owner_status':'CONVERSATIONALLY_ACCEPTED',
                                               'formal_source_approved':False}
            if rid=='lookup_starter_duration':claims.append(claim)
            required.add(eid)
            original_corrections.append({'record_id':rid,'fix':'Carry accepted R001 as conditional recovery; keep R002 pending','producer_modified':False})
        answer=' '.join(c['exact_claim_text'] for c in claims)
        records.append({'record_id':rid,'case_kind':'ORIGINAL_ELEVEN_DRAFT_REFERENCE','question':question,
                        'canonical_answer':answer,'claims':claims,'producer_draft_sha256':sha(ROOT/'registry/reconciled-accepted-eleven/candidate_registry.json'),
                        'producer_version':registry.version,'candidate_revision':'original-eleven-suite-v2',
                        'candidate_expected_route':'UNSUPPORTED' if rid=='a_reconnect' else 'SUPPORTED',
                        'branch_context':{'branches':branches,'citations':step['branch_draft_citations'],
                                          'rules':{x:registry.candidate['rules'][x] for x in step['applicability_rule_ids']+step['safety_rule_ids']},
                                          'dependency_manifest':registry.candidate['dependencies'][rid],
                                          'R001':'ACCEPTED_CONVERSATIONALLY','R002':'PENDING_POST_START_SCOPE'},
                        'required_candidate_source_ids':sorted(required),'prior_holds':step['authoring_blockers'],
                        'agent_support_work':'ORIGINAL_PRECISE_SPAN_AND_BRANCH_AUTHORING_PENDING',
                        'formal_source_approved':False,'runtime_binding':{'step_id':rid,'symptoms':step['symptom_tags'],'facts':{}}})
    require(len(records)==161 and len({r['record_id'] for r in records})==161,'Incomplete suite')
    for record in records:
        record['required_source_locks']={eid:{'text_sha256':sources[eid]['text_sha256'],'authority':sources[eid]['authority']}
                                        for eid in record['required_candidate_source_ids']}
        record['case_digest']=content_hash(record)
        record['canonical_citations']=[{'claim_id':c['claim_id'],'evidence_id':eid,
                                       'source_text_sha256':sources[eid]['text_sha256']} for c in record['claims'] for eid in c['support_evidence_ids']]
        record['coverage_plan']={
            'claim_support':'Agent maps retained; live semantic verdict NOT_MEASURED',
            'branch_execution':'Branch-specific context retained; no invented executable predicates',
            'adversaries':['added instruction','changed number','changed unit','omitted claim/warning','forged citation','wrong variant','missing dependency','draft/stale cache','provider outage'],
            'source_policy':'Policy references never presented as OEM facts',
            'typed_outcomes':['OBSERVED_NORMAL','OBSERVED_ABNORMAL','ACTION_COMPLETED_UNRESOLVED','NOT_APPLICABLE','UNCLEAR','RESOLVED'],
            'question_review':'Accessible observations, no internal enum, no redundant recurrence question; automatic flags require adjudication',
            'modality':'Visible observation only; referenced figures require reviewed image-capable verifier'}
    return {'schema_version':'case-specific-grounding-suite-v2','gate':gate,'manual_sha256':registry.checksum,
            'index_id':registry.index_id,'registry_lock':registry.lock,'runtime_versions':gemma_runtime_config().versions(),
            'input_sha256':{name:sha(BASE/name) for name in FILES},'original_registry_sha256':sha(ROOT/'registry/reconciled-accepted-eleven/candidate_registry.json'),
            'accepted_feedback_sha256':sha(ROOT/'human_review/subagent_feedback.md'),'records':records,'sources':sources,
            'original_corrections':original_corrections,'support_integrity':validation,
            'split':'TUNING_REGRESSION_NOT_HELD_OUT','release_authorized':False}

def canonical(record):
    return {'case_digest':record['case_digest'],'answer':record['canonical_answer'],
            'citations':deepcopy(record['canonical_citations'])}

def validate_candidate(record,output):
    """Exact candidate contract only; a pass says nothing about source truth."""
    payload={k:v for k,v in record.items() if k not in ('case_digest','canonical_citations','coverage_plan')}
    require(content_hash(payload)==record['case_digest'],'CASE_CONTENT_DIGEST_CHANGED')
    require(set(output)=={'case_digest','answer','citations'},'OUTPUT_SCHEMA')
    require(output['case_digest']==record['case_digest'],'CASE_VERSION_MISMATCH')
    require(output['answer']==record['canonical_answer'],'UNREVIEWED_CONTENT_NUMBER_UNIT_OR_OMISSION')
    require(output['citations']==record['canonical_citations'],'CITATION_MAPPING_CHANGED')
    return True

def validate_sources(record,sources):
    for eid,lock in record['required_source_locks'].items():
        require(eid in sources,'MISSING_CANDIDATE_DEPENDENCY')
        require(sources[eid]['authority']==lock['authority'],'OEM_POLICY_ROLE_CHANGED')
        require(textsha(sources[eid]['exact_text'])==lock['text_sha256'],'SOURCE_TEXT_OR_UNITS_CHANGED')
    return True

def preflight(record,registry,controller,config):
    """Actual formal gates, not artifact flags. No key read or provider construction."""
    blockers=[];binding=record['runtime_binding']
    if not registry.source_ready():blockers.append('FORMAL_SOURCE_METADATA_APPROVAL_REQUIRED')
    if binding is None:
        blockers.append('CASE_SPECIFIC_RUNTIME_STEP_RULE_DEPENDENCY_BINDING_NOT_IMPLEMENTED')
        return blockers,None
    sid=binding['step_id']
    if sid not in registry.candidate['steps']:
        blockers.append('RUNTIME_STEP_NOT_FOUND');return blockers,None
    step=registry.step(sid)
    if ([c['text'] for c in step.claims]!=[c['exact_claim_text'] for c in record['claims']] or
            [c['evidence_ids'] for c in step.claims]!=[c['support_evidence_ids'] for c in record['claims']]):
        blockers.append('FINAL_RUNTIME_CLAIMS_NOT_RECONCILED_TO_CASE_CANDIDATE')
    if registry.candidate['steps'][sid].get('authoring_blockers'):blockers.append('ORIGINAL_RUNTIME_AUTHORING_HOLDS_REMAIN')
    if not registry.step_ready(sid):blockers.append('CONTENT_BOUND_STEP_EVIDENCE_RULE_PROCEDURE_DEPENDENCY_APPROVAL_REQUIRED')
    session=replace(start_session(registry,binding['symptoms'],registry.source['variant']),generation_lock=config.lock)
    if binding.get('facts'):blockers.append('REVIEWED_TYPED_SESSION_SEED_NOT_IMPLEMENTED')
    decision=controller.eligible(session,sid)
    if decision.eligibility_status!=Truth.TRUE:blockers.append('ACTUAL_STEP_NOT_TRUE_ELIGIBLE')
    categories=registry.candidate['dependencies'][sid]['categories']
    if categories.get('figures') or any(registry.evidence[eid].get('type') in ('picture','figure','image') for eid in step.required_evidence_ids):
        blockers.append('EVALUATED_FIGURE_VERIFIER_NOT_IMPLEMENTED')
    if record['case_kind']=='ENGINEERING_POLICY_SCENARIO':blockers.append('POLICY_SCENARIO_IS_NOT_LIVE_OEM_ANSWER')
    if record['candidate_expected_route']!='SUPPORTED':blockers.append('WITHHOLDING_OR_POLICY_ROUTE_NOT_TECHNICAL_GENERATION')
    if not blockers:
        try:envelope(controller,session,sid)
        except ValidationFailure as exc:blockers.append(str(exc))
    return blockers,session

def evaluate(suite,live=False,limit=1):
    require(type(limit) is int and 1<=limit<=1,'At most one eligible composer/verifier pair per invocation')
    config=gemma_runtime_config();index=ROOT/'build/index-bge-final'
    registry=EvidenceRegistry.load(ROOT/'registry/reconciled-accepted-eleven',index,ROOT/'source_manifest.json')
    controller=ReviewedController(registry,Retriever(index,embedding_model=NoInferenceEncoder()))
    rows=[];live_used=0
    for record in suite['records']:
        output=canonical(record);validate_candidate(record,output);validate_sources(record,suite['sources'])
        mutants={}
        added=deepcopy(output);added['answer']+=' Perform an undocumented adjustment.';mutants['unsupported_addition']=added
        changed=deepcopy(output);changed['answer']=re.sub(r'\d+',lambda m:str(int(m.group())+1),changed['answer'],count=1)
        if changed['answer']!=output['answer']:mutants['changed_number']=changed
        unit=deepcopy(output);unit['answer']=re.sub(r'\b(?:psi|mm|rpm|kg|V|A|L)\b','INVALID_UNIT',unit['answer'],count=1)
        if unit['answer']!=output['answer']:mutants['changed_unit']=unit
        for index,claim in enumerate(record['claims']):
            omitted=deepcopy(output);omitted['answer']=omitted['answer'].replace(claim['exact_claim_text'],'',1)
            mutants['omitted_claim_'+str(index)]=omitted
        citation=deepcopy(output);citation['citations'].append({'claim_id':'forged','evidence_id':'invented','source_text_sha256':'bad'});mutants['forged_citation']=citation
        stale=deepcopy(output);stale['case_digest']='stale';mutants['stale_case']=stale
        checks={}
        for name,mutant in mutants.items():
            try:validate_candidate(record,mutant)
            except ValueError as exc:checks[name]={'rejected':True,'reason':str(exc)}
            else:checks[name]={'rejected':False}
        if record['required_candidate_source_ids']:
            eid=record['required_candidate_source_ids'][0]
            missing=dict(suite['sources']);missing.pop(eid)
            try:validate_sources(record,missing)
            except ValueError as exc:checks['missing_dependency']={'rejected':True,'reason':str(exc)}
            else:checks['missing_dependency']={'rejected':False}
            changed_sources=dict(suite['sources']);changed_sources[eid]={**changed_sources[eid],'exact_text':changed_sources[eid]['exact_text']+' altered units'}
            try:validate_sources(record,changed_sources)
            except ValueError as exc:checks['source_text_units_changed']={'rejected':True,'reason':str(exc)}
            else:checks['source_text_units_changed']={'rejected':False}
        require(all(c['rejected'] for c in checks.values()),'Candidate validator let a mutation through')
        warnings=record['branch_context']['producer'].get('warnings',[]) if 'producer' in record['branch_context'] else []
        findings=[]
        if any(re.search(r'\b(?:NOT_APPLICABLE|OBSERVED_NORMAL|ACTION_COMPLETED_UNRESOLVED|UNCLEAR|RESOLVED)\b',c['exact_claim_text']) for c in record['claims']):
            findings.append('INTERNAL_OUTCOME_ENUM_IN_RIDER_TEXT_REVIEW')
        if record['canonical_answer'].count('?')>1:findings.append('MULTIPLE_QUESTION_MARKS_REQUIRE_SCOPE_REVIEW')
        blockers,session=preflight(record,registry,controller,config)
        row={'record_id':record['record_id'],'case_kind':record['case_kind'],'case_digest':record['case_digest'],
             'candidate_revision':record['candidate_revision'],'candidate_expected_route':record['candidate_expected_route'],
             'candidate_contract_pass':True,'mutation_results':checks,'practical_question_flags':findings,
             'retained_warning_count':len(warnings),'retained_branch_context':bool(record['branch_context']),
             'formal_preflight_blockers':blockers,'live_status':'BLOCKED_BEFORE_KEY_ACCESS' if blockers else 'ELIGIBLE_NOT_REQUESTED',
             'generation_calls':0,'verifier_calls':0,'claim_semantic_accuracy':'NOT_MEASURED',
             'dialogue_execution':'NOT_RUN_CASE_RUNTIME_BINDINGS_REQUIRED'}
        if live and not blockers and live_used<limit:
            # Only the actual approved controller envelope can cross this boundary.
            pipeline=build_generator(config,live_enabled=True,authorized_calls_per_adapter=1)
            controller.response_generator=pipeline
            sid=record['runtime_binding']['step_id']
            # Use controller retrieval and assembly; cannot render a technical draft
            # without the actual complete, applicable bundle. NoInferenceEncoder
            # deliberately prevents accidental query model use in this local harness.
            # An eligible production runner must inject its authorized retriever.
            try:
                bundle=controller.retriever.search(record['question'],dependency_manifest=registry.retrieval_manifest(sid),
                    step_id=sid,applicability_status='CONFIRMED',scope={'source_sha256':registry.checksum,
                    'manual_id':session.manual_id,'variant':session.bike_variant,'edition':session.edition,
                    'language':registry.source['language'],'motorcycle':registry.source['motorcycle']})
            except Exception:
                row.update(live_status='RETRIEVAL_SYSTEM_ERROR_BEFORE_KEY_ACCESS',actual_route='SYSTEM_ERROR',reason_codes=['RETRIEVAL_FAILURE'])
                rows.append(row);continue
            response=controller.render(session,sid,bundle)
            trace=pipeline.last_trace or {};live_used+=1
            row.update(live_status='EVALUATED',actual_route=response.type.value,reason_codes=response.reason_codes,
                       provider_trace=trace,generation_calls=trace.get('generation_calls',0),verifier_calls=trace.get('verifier_calls',0))
        rows.append(row)
    return {'schema_version':'case-specific-evaluation-v2','input_sha256':suite['input_sha256'],
            'suite_digest':content_hash(suite),'runtime_versions':config.versions(),'records':rows,
            'source_approved_eligible_cases':sum(not r['formal_preflight_blockers'] for r in rows),
            'live_provider_calls':sum(r['generation_calls']+r['verifier_calls'] for r in rows),
            'live_requested':live,'claim_accuracy':'NOT_MEASURED_WITHOUT_ELIGIBLE_LIVE_CASES',
            'contract_test_scope':'Exact fixture membership and citation identity only; not entailment or live Gemma quality',
            'split':suite['split'],'held_out_cases':0,'release_gate_passed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true')
    parser.add_argument('--approved',action='store_true',help='Use exact coordinator v3 authority in the shared runner')
    parser.add_argument('--model',choices=GeminiJSONProvider.ALLOWED_MODELS,default=GeminiJSONProvider.MODEL,help='Explicit approved-run model comparison; no automatic fallback')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/approved_text_journeys_v1.json')
    args=parser.parse_args()
    if args.approved:
        from approved_text_journeys import evaluate as evaluate_approved
        import os
        report = evaluate_approved(Path(os.environ.get('MOTOMEDIC_TEST_INDEX',ROOT/'build/index-bge-final')),args.output,live=args.live,model=args.model)
        raise SystemExit(0 if report['passed'] else 1)
    if args.model != GeminiJSONProvider.MODEL:
        parser.error('--model comparison requires --approved')
    suite=build_suite();report=evaluate(suite,live=args.live);OUT.mkdir(exist_ok=True)
    (OUT/'suite.json').write_text(json.dumps(suite,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'cases':len(report['records']),'eligible':report['source_approved_eligible_cases'],
                      'live_calls':report['live_provider_calls'],'mutations_rejected':sum(len(r['mutation_results']) for r in report['records'])}))
