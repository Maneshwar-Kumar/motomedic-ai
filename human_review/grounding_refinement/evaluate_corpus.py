"""Versioned 161-record gate baseline. No provider calls or approvals are possible."""
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from constrained_generator import build_generator
from evidence_registry import EvidenceRegistry
from generation_providers import gemma_runtime_config
from online_retrieve import Retriever
from reviewed_controller import ReviewedController, start_session
from verify_controller import NoInferenceEncoder
from verify_gemma_grounding import QUERIES
from human_review.grounding_refinement.verify_batch import verify, sha, load
from human_review.grounding_refinement.controller_candidate import ControllerCandidate

OUT=Path(__file__).parent

def corpus():
    rows=[]
    registry=load(ROOT/'registry/reconciled-accepted-eleven/candidate_registry.json')
    history=ROOT/'human_review/record_id_verification.md'
    for rid,q in QUERIES.items():
        rows.append({'record_id':rid,'input_path':str(history.relative_to(ROOT)),
                     'sha256':sha(history),'query':q,'candidate':registry['steps'][rid],
                     'case_type':'original_conversational_acceptance_not_source_approval',
                     'expected_content_route':None,'source_approval':'PENDING'})
    for r in load(ROOT/'human_review/record_workflow/inventory.json')['records']:
        text=(ROOT/r['draft_path']).read_text(encoding='utf-8-sig')
        match=re.search(r'Rider:\s*["\u201c](.+?)["\u201d]',text)
        rows.append({'record_id':r['record_id'],'input_path':r['draft_path'],
                     'sha256':r['draft_sha256'],'query':match.group(1) if match else text,
                     'candidate':text,'case_type':'legacy_candidate','review_state':r['state'],
                     'blockers':[str(p.relative_to(ROOT)) for p in (ROOT/'human_review/blockers').glob(r['record_id']+'_*')],
                     'expected_content_route':None,'source_approval':'PENDING'})
    for r in load(ROOT/'human_review/record_workflow/batch_100_completion.json')['records']:
        d=load(ROOT/r['draft_path'])
        rows.append({'record_id':r['record_id'],'input_path':r['draft_path'],
                     'sha256':r['draft_sha256'],'query':d['question'],'candidate':d,
                     'case_type':d.get('case_type','manual_scope_candidate'),
                     'blockers':r['blocker_card_paths'],'expected_content_route':d['expected_route'],
                     'source_approval':'PENDING'})
    assert len(rows)==161 and len({r['record_id'] for r in rows})==161
    return rows

def run():
    gate=verify()
    records=corpus()
    index=ROOT/'build/index-bge-final'
    registry=EvidenceRegistry.load(ROOT/'registry/reconciled-accepted-eleven', index, ROOT/'source_manifest.json')
    assert not registry.source_ready(), 'Reviewed sources require a different authorized evaluation path'
    config=gemma_runtime_config()
    all_symptoms=sorted({s for step in registry.candidate['steps'].values() for s in step['symptom_tags']})
    arms={}
    for name,cls,use_model in [('deterministic',ReviewedController,False),
                               ('current_gemma_gated',ReviewedController,True),
                               ('revised_candidate_gemma_gated',ControllerCandidate,True)]:
        c=cls(registry,Retriever(index,embedding_model=NoInferenceEncoder()))
        pipeline=build_generator(config,live_enabled=False,authorized_calls_per_adapter=0)
        if use_model:c.response_generator=pipeline
        arm=[]
        for record in records:
            session=replace(start_session(registry,all_symptoms,registry.source['variant']),generation_lock=config.lock)
            updated,response,decisions=c.next(session,record['query'])
            trace=pipeline.last_trace or {}
            passed=(response.type.value=='UNSUPPORTED' and not response.claim_evidence_map
                    and not response.suggested_step_id and not updated.pending_step_id
                    and trace.get('generation_calls',0)==trace.get('verifier_calls',0)==0)
            arm.append({'record_id':record['record_id'],'route':response.type.value,
                        'reason_codes':response.reason_codes,'gate_passed':passed,
                        'controller_candidates':len(decisions),'generation_calls':trace.get('generation_calls',0),
                        'verifier_calls':trace.get('verifier_calls',0)})
        assert all(r['gate_passed'] for r in arm)
        arms[name]=arm
    inputs=[]
    for record in records:
        candidate=record['candidate']
        refs=candidate.get('source_refs',[]) if isinstance(candidate,dict) else []
        text=json.dumps(candidate,ensure_ascii=False) if isinstance(candidate,dict) else candidate
        inputs.append({k:v for k,v in record.items() if k not in ('candidate','query')} | {
            'required_candidate_pages':sorted({r['pdf_page'] for r in refs}),
            'candidate_source_refs_have_evidence_ids':bool(refs) and all(r.get('evidence_ids') for r in refs),
            'runtime_expected_route':'UNSUPPORTED_SOURCE_REVIEW_HOLD',
            'comparison_scope':'SOURCE_GATES_ONLY; not intent, branch, technical correctness or model accuracy',
            'units_to_review':sorted(set(re.findall(r'\b(?:psi|kg/cm|mm|mA|rpm|km/h|cc|kPa|Nm|V|A|L)\b',text))),
            'condition_count':len(candidate.get('conditions',[])) if isinstance(candidate,dict) else None,
            'warning_count':len(candidate.get('warnings',[])) if isinstance(candidate,dict) else None})
    code_names=['reviewed_controller.py','controller_contracts.py','evidence_registry.py','reviewed_cache.py',
                'generation_contracts.py','generation_providers.py','gemini_transport.py','constrained_generator.py']
    report={'schema_version':'expanded-refinement-gates-v1','checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'gate':gate,'registry_lock':registry.lock,'registry_version':registry.version,
            'index_id':registry.index_id,'manual_checksum':registry.checksum,'runtime_versions':config.versions(),
            'runtime_code_sha256':{p:sha(ROOT/p) for p in code_names},
            'candidate_code_sha256':{p.name:sha(p) for p in OUT.glob('*.py')},
            'split':'TUNING_REGRESSION_NOT_HELD_OUT','held_out_cases':0,
            'source_approved_technical_cases':0,'live_provider_calls':0,'source_gate_rows_per_arm':161,
            'arms':arms,'inputs':inputs,'semantic_accuracy':'NOT_EVALUATED_SOURCE_REVIEW_BLOCKED',
            'branch_correctness':'Only separately reported fictional protocol tests; corpus branches not measured',
            'release_gate_passed':False,'deployment_or_billing_changed':False,'index_rebuilt':False}
    (OUT/'corpus_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (OUT/'verified_gate.json').write_text(json.dumps(gate,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'gate_verified':True,'records':161,'source_gate_passes':{k:sum(x['gate_passed'] for x in v) for k,v in arms.items()},'live_provider_calls':0}))

if __name__=='__main__':run()
