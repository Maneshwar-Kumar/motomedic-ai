"""Synthetic receipt-join controls; no acceptance file, provider or cloud writes."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('functional_receipt_builder',HERE/'build_functional_acceptance_v1.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class FunctionalReceiptJoinTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=builder.ROOT/'tmp');self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name)
        self.waiver=self.out/'owner_waiver.json';self.waiver.write_bytes(builder.WAIVER.read_bytes())
        self.images=json.loads((builder.OUT/'hosted_image_binding_v10_13.json').read_bytes())
        self.manifest=builder.OUT/'serving_manifest_v10_13.json'
        self.write(self.out/'hosted_image_binding_v10_13.json',self.images)
        self.job='12345678-1234-1234-1234-123456789012';self.folder=self.out/'hosted_runs'/self.job
        self.folder.mkdir(parents=True)
        self.receipt_path=self.folder/'receipt.json';self.audit_path=self.out/'functional_audit.json'
        self.source_path=self.out/'evaluator_client_source_v11.json';self.submission_path=self.out/'evaluator_client_submission_v9.json'
        self.lock=json.loads(self.waiver.read_bytes())['frozen_candidate']['runtime_lock']
        self.source={'object':'synthetic-exact-source11','generation':'123','serving_manifest_sha256':self.images['serving_manifest_sha256'],'runtime_lock':self.lock}
        self.submission={'operation':{'metadata':{'build':{'id':self.job}}},'config':{'source':{'storageSource':{
            'bucket':'motomedic-ai-20261009-indices','object':self.source['object'],'generation':self.source['generation']}}}}
        self.write(self.source_path,self.source);self.write(self.submission_path,self.submission)
        cases={}
        for case in builder.CASE_IDS:
            row={'case_id':case,'expected_route_matched':True,'saved_view':{'runtime_controls':{'source_admission':{'retrieval_policy':{
                'first_stage_execution':'CONCURRENT_AUTHENTICATED_QDRANT_AND_BM25',
                'dense_rpc':{'backend':'AUTHENTICATED_QDRANT_RPC','index_id':'synthetic-index','document_embedding_calls':0},
                'rerank_mode':'CONDITIONAL_RANK_DISAGREEMENT','initial_ranking_signals':{'ranking_uncertain':True},
                'rerank_attempts':1,'rerank_skip_reason':None}}}}}
            path=self.folder/(case+'.json');self.write(path,row);cases[case]=self.sha(path)
        self.receipt={'cloud_build_id':self.job,'runtime_lock':self.lock,'index_id':'synthetic-index','case_files':cases,
            'engineering_transport_and_route_passed':True,'engineering_completed_cases':6,'attempted_case_count':6}
        self.write(self.receipt_path,self.receipt)
        inventory={'cloud_build_id':self.job,'files':{'receipt.json':{'sha256':self.sha(self.receipt_path)},
            **{case+'.json':{'sha256':value} for case,value in cases.items()}}}
        self.write(self.folder/'download_inventory.json',inventory)
        self.proof={'passed':True,'current_role_cache_usage_proofs':{role:{'current_role_creation_then_read_usage_proven':True}
            for role in ('private_draft','semantic_verifier')},'role_cache_proofs':{role:{'exact_role_prefix_creation_then_read_proven':False}
            for role in ('private_draft','semantic_verifier')},'limits':['SYNTHETIC MOCK FOR RECEIPT-JOIN TEST ONLY']}
        self.write(self.audit_path,self.proof)

    def write(self,path,value):path.write_text(json.dumps(value,sort_keys=True),encoding='utf-8')
    def sha(self,path):return hashlib.sha256(path.read_bytes()).hexdigest()

    def build(self,proof=None):
        with patch.object(builder,'OUT',self.out),patch.object(builder,'WAIVER',self.waiver),patch.object(builder.audit,'run',return_value=proof or self.proof):
            return builder.build(self.manifest,self.receipt_path,self.audit_path,self.source_path,self.submission_path)

    def test_fresh_source11_submission9_and_actual_receipt_refs_are_emitted(self):
        value=self.build()
        self.assertEqual(value['evaluator_source'],{
            'path':self.source_path.relative_to(builder.ROOT).as_posix(),'sha256':self.sha(self.source_path)})
        self.assertEqual(value['evaluator_submission']['sha256'],self.sha(self.submission_path))
        self.assertEqual(value['hosted_receipt']['path'],self.receipt_path.relative_to(builder.ROOT).as_posix())
        self.assertNotIn('hosted_client_source',value);self.assertNotIn('hosted_client_submission',value)
        self.assertFalse(value['independent_factual_quality_acceptance']);self.assertFalse(value['public_browser_acceptance'])
        self.assertFalse(any(value['exact_full_evidence_prefix_cache_reuse_observed'].values()))
        self.assertFalse(builder.TARGET.exists())

    def test_failed_actual_audit_cannot_create_functional_acceptance(self):
        failed=deepcopy(self.proof);failed['passed']=False
        with self.assertRaisesRegex(ValueError,'ACTUAL_FUNCTIONAL_DELIVERY_CACHE_AUDIT_NOT_PASSED'):self.build(failed)

    def test_recorded_audit_cannot_replace_recomputed_actual_proof(self):
        recorded=deepcopy(self.proof);recorded['limits']=[];self.write(self.audit_path,recorded)
        with self.assertRaisesRegex(ValueError,'RECORDED_AUDIT_DIFFERS'):self.build()

    def test_different_submission_source_generation_is_rejected(self):
        self.submission['config']['source']['storageSource']['generation']='changed';self.write(self.submission_path,self.submission)
        with self.assertRaisesRegex(ValueError,'EXACT_HOSTED_SUBMISSION_AND_SOURCE_CHANGED'):self.build()

    def test_changed_downloaded_case_is_rejected(self):
        path=self.folder/(builder.CASE_IDS[0]+'.json');path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'EXACT_FUNCTIONAL_CASE_DOWNLOAD_HASH_CHANGED'):self.build()

    def test_owner_waiver_drift_cannot_authorize_functional_acceptance(self):
        self.waiver.write_bytes(self.waiver.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'EXACT_OWNER_FUNCTIONAL_WAIVER_CHANGED'):self.build()


if __name__=='__main__':unittest.main()
