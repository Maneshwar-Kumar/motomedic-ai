"""Real-manual source gates for accepted examples, with opt-in two-call evaluation."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import subprocess
from constrained_generator import build_generator, envelope, ValidationFailure
from evidence_registry import EvidenceRegistry, content_hash, read_json
from generation_providers import gemma_runtime_config
from online_retrieve import Retriever
from reviewed_controller import start_session
from verify_controller import NoInferenceEncoder

QUERIES = {'lookup_oil_grade':'What engine oil grade is specified?',
'lookup_tyre_pressure':'What tyre pressure should I use?', 'lookup_fan_fuse':'Which fuse protects the fan?',
'lookup_starter_duration':'How long can I hold the starter?', 'lookup_usb_charging':'Why does USB not charge with engine off?',
'a_fuse':'The engine will not start.', 'a_switches_on':'The engine will not start.',
'a_refuel':'The engine will not start.', 'a_reconnect':'The engine will not start.',
'a_raise_stand':'Engine stops when first gear is engaged.', 'a_cool_engine':'Engine misfires or stops.'}

def evaluate(index, registry_path, output, *, live=False, case_id=None):
    registry=EvidenceRegistry.load(registry_path,index,'source_manifest.json')
    config=gemma_runtime_config()
    controller=Retriever(index,embedding_model=NoInferenceEncoder()).reviewed_controller(registry)
    controller.audience='engineering'
    pipeline=build_generator(config,live_enabled=False,authorized_calls_per_adapter=0)
    controller.response_generator=pipeline
    rows=[]
    for sid in sorted(QUERIES):
        step=registry.step(sid)
        session=replace(start_session(registry,list(step.symptom_tags),registry.source['variant']),generation_lock=config.lock)
        updated,response,decisions=controller.next(session,QUERIES[sid])
        expected_block=not registry.source_ready() or not registry.step_ready(sid)
        branch_feedback_rejected=True
        if updated.pending_step_id is None:
            try:controller.feedback(updated,'ACTION_COMPLETED_UNRESOLVED','unissued-accepted-example-feedback')
            except ValueError:pass
            else:branch_feedback_rejected=False
        trace=pipeline.last_trace or {}
        passed=(response.type.value=='UNSUPPORTED' and not response.suggested_step_id and not response.claim_evidence_map
                and not updated.pending_step_id and not trace.get('generation_calls') and not trace.get('verifier_calls')
                and branch_feedback_rejected) if expected_block else None
        rows.append({'record_id':sid,'route':response.type.value,'reason_codes':response.reason_codes,
                     'source_ready':registry.source_ready(),'step_ready':registry.step_ready(sid),
                     'draft_gate_passed':passed,'unissued_unresolved_feedback_rejected':branch_feedback_rejected,
                     'generation_calls':trace.get('generation_calls',0),'verifier_calls':trace.get('verifier_calls',0),
                     'split':'REGRESSION_TUNING_NOT_HELD_OUT'})
    report={'schema_version':'gemma-grounding-gates-v1','checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'manual_checksum':registry.checksum,'index_id':registry.index_id,'registry_path':str(registry_path),
            'registry_version':registry.version,'registry_lock':registry.lock,
            'registry_digest':content_hash(registry.candidate),'runtime_lock':config.lock,'runtime_versions':config.versions(),
            'cases':rows,'formal_review_decisions':len(registry.reviews.get('decisions',[])),
            'generation_calls':0,'verifier_calls':0,'live_provider_calls':0,
            'unsupported_and_altered_claim_calibration':'SOURCE_REVIEW_BLOCKED; synthetic contract tests only',
            'semantic_accuracy':'NOT_EVALUATED','held_out_cases':0,'release_gate_passed':False,
            'index_rebuilt':False,'billing_or_deployment_changed':False}
    report['runtime_code_sha256']={name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in
        ('generation_contracts.py','generation_providers.py','gemini_transport.py','constrained_generator.py','reviewed_controller.py','evidence_registry.py','verify_gemma_grounding.py')}
    if not os.environ.get('GITHUB_ACTIONS'):
        report['base_commit']=report.pop('commit')
        report['execution_environment']='LOCAL_WORKTREE; exact runtime_code_sha256 captured'
    else:
        report['execution_environment']='GITHUB_ACTIONS_COMMIT'
    if live:
        if case_id not in QUERIES:raise ValueError('One original accepted record ID is required')
        blockers=[];step=registry.step(case_id)
        if not registry.source_ready():blockers.append('SOURCE_REVIEW_REQUIRED')
        if not registry.step_ready(case_id):blockers.append('STEP_REVIEW_REQUIRED')
        if step.kind!='LOOKUP':blockers.append('LIVE_ACTION_REQUIRES_REVIEWED_TYPED_SESSION_FIXTURE')
        if registry.candidate['dependencies'][case_id]['categories'].get('figures'):blockers.append('FIGURE_VERIFIER_NOT_IMPLEMENTED')
        if any(c.get('response_role') not in ('ACTION','FACT','WARNING','PREREQUISITE') for c in step.claims):blockers.append('CLAIM_ROLE_REVIEW_REQUIRED')
        report['requested_live_case_id']=case_id
        report['live_blockers']=blockers
        if blockers:
            report['live_status']='BLOCKED_BEFORE_PROVIDER'
        else:
            # Owner-authorized candidate account; finite one composer + one verifier call.
            pipeline=build_generator(config,live_enabled=True,authorized_calls_per_adapter=1)
            controller.response_generator=pipeline
            session=replace(start_session(registry,list(step.symptom_tags),registry.source['variant']),generation_lock=config.lock)
            controller.audience='engineering'
            try:envelope(controller,session,case_id)
            except ValidationFailure as exc:
                report['live_status']='BLOCKED_BEFORE_PROVIDER';report['live_blockers']=[str(exc)]
            else:
                updated,response,_=controller.next(session,QUERIES[case_id])
                trace=pipeline.last_trace or {}
                report['live_status']='EVALUATED_CANDIDATE_NOT_RELEASE'
                report['live_route']=response.type.value;report['live_reason_codes']=response.reason_codes
                report['provider_trace']=trace
                report['generation_calls']=trace.get('generation_calls',0)
                report['verifier_calls']=trace.get('verifier_calls',0)
                report['live_provider_calls']=report['generation_calls']+report['verifier_calls']
                report['semantic_accuracy']='LIVE_VERDICT_ONLY; independent adjudication still required'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'records':len(rows),'draft_gate_passes':sum(r['draft_gate_passed'] is True for r in rows),
        'live_provider_calls':report['live_provider_calls'],'live_status':report.get('live_status','NOT_REQUESTED')}))
    if any(r['draft_gate_passed'] is False for r in rows):raise SystemExit(1)
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--index',type=Path,required=True)
    p.add_argument('--registry',type=Path,default=Path('registry/reconciled-accepted-eleven'))
    p.add_argument('--output',type=Path,default=Path('build/gemma-grounding-gates.json'))
    p.add_argument('--live',action='store_true');p.add_argument('--case-id',choices=tuple(QUERIES))
    a=p.parse_args();evaluate(a.index,a.registry,a.output,live=a.live,case_id=a.case_id)
if __name__=='__main__':main()
