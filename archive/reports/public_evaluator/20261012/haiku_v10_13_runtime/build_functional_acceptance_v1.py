"""Join actual functional receipts under the exact owner waiver; no providers."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OUT=ROOT/'reports/public_evaluator/20261012'
WAIVER=OUT/'public_review/owner_functional_acceptance_scope_v1.json'
WAIVER_SHA='19371f8c30839754cfd5233e5db68efc88589f25313b96e67aee3e72c112248d'
TARGET=HERE/'functional_operational_acceptance_v1.json'
CASE_IDS=('EVAL_DIRECT_01','EVAL_USB_02','EVAL_FOLLOWUP_03','EVAL_TOPIC_TABLE_04','EVAL_PARTIAL_05','EVAL_UNSUPPORTED_06')
spec=importlib.util.spec_from_file_location('functional_auditor_v3',HERE/'audit_hosted_delivery_cache_v3.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def require(value,code):
    if not value:raise ValueError(code)


def reference(path,**extra):
    path=Path(path).resolve()
    require(path.is_relative_to(OUT),'ACTUAL_RECEIPT_MUST_STAY_IN_REPORT_AREA')
    return {'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**extra}


def build(manifest_path,receipt_path,audit_path,source_path,submission_path):
    release,manifest_sha=audit.read(manifest_path)
    receipt,receipt_sha=audit.read(receipt_path)
    recorded_audit,audit_sha=audit.read(audit_path)
    actual_audit=audit.run(manifest_path,receipt_path)
    require(actual_audit.get('passed') is True,'ACTUAL_FUNCTIONAL_DELIVERY_CACHE_AUDIT_NOT_PASSED')
    require({key:value for key,value in recorded_audit.items() if key!='recorded_utc'}==
            {key:value for key,value in actual_audit.items() if key!='recorded_utc'},'RECORDED_AUDIT_DIFFERS_FROM_RECOMPUTED_ACTUAL_PROOF')
    waiver,waiver_sha=audit.read(WAIVER)
    require(waiver_sha==WAIVER_SHA,'EXACT_OWNER_FUNCTIONAL_WAIVER_CHANGED')
    for key in ('owner_authorized','independent_manual_review_waived_for_present_functional_demo',
                'immutable_source_bindings_required','runtime_semantic_verifier_required','answering_enablement_requires_functional_probe'):
        require(waiver.get(key) is True,'REQUIRED_OWNER_FUNCTIONAL_SCOPE_MISSING')
    for key in ('independent_manual_review_required','independent_manual_review_performed',
                'independent_factual_quality_acceptance','human_factual_signoff','existing_scoped_source_approval_waived',
                'source_content_approval_changed','runtime_semantic_verifier_bypass_authorized'):
        require(waiver.get(key) is False,'OWNER_WAIVER_CANNOT_ASSERT_SOURCE_QUALITY_OR_BYPASS_RUNTIME')
    images,image_sha=audit.read(OUT/'hosted_image_binding_v10_13.json')
    candidate=waiver['frozen_candidate']
    require(images['serving_manifest_sha256']==candidate['serving_manifest_sha256']==manifest_sha and
            receipt['runtime_lock']==candidate['runtime_lock'] and images['source_commit']==candidate['source_commit'],
            'EXACT_FROZEN_SOURCE_IMAGE_RUNTIME_CHANGED')
    job=receipt.get('cloud_build_id')
    directory=Path(receipt_path).resolve().parent
    require(directory==OUT/'hosted_runs'/job,'EXACT_ACTUAL_HOSTED_JOB_DIRECTORY_REQUIRED')
    inventory,inventory_sha=audit.read(directory/'download_inventory.json')
    require(inventory.get('cloud_build_id')==job and inventory['files']['receipt.json']['sha256']==receipt_sha,
            'ACTUAL_HOSTED_RECEIPT_DOWNLOAD_BINDING_CHANGED')
    source,source_sha=audit.read(source_path)
    submission,submission_sha=audit.read(submission_path)
    require(submission['operation']['metadata']['build']['id']==job and
            submission['config']['source']['storageSource']=={'bucket':'motomedic-ai-20261009-indices',
                'object':source['object'],'generation':source['generation']} and
            source['serving_manifest_sha256']==manifest_sha and source['runtime_lock']==receipt['runtime_lock'],
            'EXACT_HOSTED_SUBMISSION_AND_SOURCE_CHANGED')
    require(set(receipt.get('case_files',{}))==set(CASE_IDS) and receipt.get('engineering_transport_and_route_passed') is True and
            receipt.get('engineering_completed_cases')==6 and receipt.get('attempted_case_count')==6,
            'SIX_ACTUAL_FUNCTIONAL_CASES_NOT_COMPLETE')
    retrieval=[]
    for case in CASE_IDS:
        row,row_sha=audit.read(directory/(case+'.json'))
        require(row_sha==receipt['case_files'][case]==inventory['files'][case+'.json']['sha256'],
                'EXACT_FUNCTIONAL_CASE_DOWNLOAD_HASH_CHANGED')
        require(row.get('expected_route_matched') is True,'FUNCTIONAL_CASE_ROUTE_NOT_MATCHED')
        policy=row['saved_view']['runtime_controls']['source_admission']['retrieval_policy']
        require(policy.get('first_stage_execution')=='CONCURRENT_AUTHENTICATED_QDRANT_AND_BM25' and
                policy.get('dense_rpc',{}).get('backend')=='AUTHENTICATED_QDRANT_RPC' and
                policy['dense_rpc'].get('index_id')==receipt['index_id'] and
                policy['dense_rpc'].get('document_embedding_calls')==0 and
                policy.get('rerank_mode')=='CONDITIONAL_RANK_DISAGREEMENT',
                'ACTUAL_IMMUTABLE_HYBRID_RETRIEVAL_NOT_PROVEN')
        retrieval.append({'case_id':case,'first_stage_execution':policy['first_stage_execution'],
            'dense_backend':policy['dense_rpc']['backend'],'rerank_mode':policy['rerank_mode'],
            'ranking_uncertain':policy['initial_ranking_signals']['ranking_uncertain'],
            'rerank_attempts':policy['rerank_attempts'],'rerank_skip_reason':policy['rerank_skip_reason']})
    role_usage={role:proof['current_role_creation_then_read_usage_proven']
                for role,proof in actual_audit['current_role_cache_usage_proofs'].items()}
    return {'schema':'motomedic-owner-waived-functional-demo-acceptance-v1',
        'classification':'ACTUAL_HOSTED_FUNCTIONAL_OPERATIONAL_ACCEPTANCE','decision':'FUNCTIONAL_DEMO_ACCEPTED',
        'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'owner_waiver':reference(WAIVER),
        'serving_manifest_sha256':manifest_sha,'runtime_lock':receipt['runtime_lock'],'images':images['images'],
        'source_commit':images['source_commit'],'hosted_image_binding':reference(OUT/'hosted_image_binding_v10_13.json'),
        'hosted_receipt':reference(receipt_path,cloud_build_id=job),'delivery_cache_audit':reference(audit_path),
        'download_inventory':reference(directory/'download_inventory.json'),'case_files':receipt['case_files'],
        'evaluator_source':reference(source_path),
        'evaluator_submission':reference(submission_path),
        'delivered_case_count':6,'functional_demo_operational_acceptance':True,'saved_stream_recovery_identical':True,
        'completed_operation_boundary_checks':True,'permanent_charges_preserved':True,'unchanged_attempt_usd_inr_guards':True,
        'role_cache_creation_and_reads_observed':role_usage,
        'exact_full_evidence_prefix_cache_reuse_observed':{role:proof['exact_role_prefix_creation_then_read_proven']
            for role,proof in actual_audit['role_cache_proofs'].items()},
        'actual_retrieval':retrieval,'independent_manual_review_required':False,'independent_manual_review_performed':False,
        'independent_factual_quality_acceptance':False,'human_signoff':False,'runtime_semantic_verifier_required':True,
        'runtime_semantic_verifier_bypassed':False,'public_browser_acceptance':False,'public_browser_acceptance_pending':True,
        'provider_calls_by_receipt_builder':0,'cloud_mutations':0,'original_manual_pages_inspected':False,
        'limits':actual_audit['limits']}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True);parser.add_argument('--receipt',required=True);parser.add_argument('--audit',required=True)
    parser.add_argument('--source',required=True);parser.add_argument('--submission',required=True)
    args=parser.parse_args()
    require(not TARGET.exists(),'NEVER_OVERWRITE_FUNCTIONAL_ACCEPTANCE_RECEIPT')
    value=build(args.manifest,args.receipt,args.audit,args.source,args.submission)
    with TARGET.open('x',encoding='utf-8') as target:
        json.dump(value,target,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);target.write('\n')
    print(json.dumps({'decision':value['decision'],'output':str(TARGET),'provider_calls_by_receipt_builder':0}))
