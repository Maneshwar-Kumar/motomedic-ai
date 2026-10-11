"""Exact source-context authority boundaries; never source semantic approval."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from approved_registry import ApprovedEvidenceRegistry
from constrained_generator import ValidationFailure
from cloud.grounded_generation import source_context as contexts

ROOT=Path(__file__).resolve().parents[2]
INDEX=Path(os.environ.get('MOTOMEDIC_TEST_INDEX',str(ROOT/'build/index-bge-final')))
class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=ApprovedEvidenceRegistry.load(ROOT,INDEX)
        raw=(ROOT/contexts.BINDING_PATH).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==contexts.BINDING_SHA256
        cls.manifest=json.loads(raw)
        cls.eid=next(eid for eid,row in cls.manifest['bindings'].items() if row['review_status']=='APPROVED_CONTEXT_LABELS')
    def proxy(self):
        r=self.registry
        return SimpleNamespace(checksum=r.checksum,index_id=r.index_id,source=deepcopy(r.source),reviews=deepcopy(r.reviews),
            evidence=dict(r.evidence),approved_sources=dict(r.approved_sources),source_ready=r.source_ready,evidence_ready=r.evidence_ready)
    def test_all184_approved_and334_held_contexts_exactly(self):
        approved=held=0
        for eid,row in self.manifest['bindings'].items():
            with self.subTest(evidence=eid):
                if row['review_status']=='APPROVED_CONTEXT_LABELS':
                    result=contexts.context_for(self.registry,eid);approved+=1
                    self.assertEqual(result['section_path'],row['section_path'])
                    self.assertEqual(result['parent_section_ids'],row['parent_section_ids'])
                    self.assertEqual(result['immutable_chunk_ids'],row['immutable_chunk_ids'])
                    self.assertEqual(result['original_object_sha256'],row['raw_object_sha256'])
                else:
                    with self.assertRaisesRegex(ValidationFailure,'SOURCE_CONTEXT_REVIEW_REQUIRED'):
                        contexts.context_for(self.registry,eid)
                    held+=1
        self.assertEqual((approved,held),(184,334))
    def test_no_parent_or_source_text_is_returned(self):
        expected={'context_kind','context_authority','evidence_id','section_path','parent_section_ids',
            'immutable_chunk_ids','parent_membership','source_context_review_sha256','original_object_sha256'}
        for eid,row in self.manifest['bindings'].items():
            if row['review_status']!='APPROVED_CONTEXT_LABELS':continue
            result=contexts.context_for(self.registry,eid);self.assertEqual(set(result),expected)
            self.assertTrue(all(set(p)=={'parent_section_id','parent_object_sha256'} for p in result['parent_membership']))
    def test_cached_decode_cannot_mask_changed_review_bytes(self):
        contexts.context_for(self.registry,self.eid)
        with patch.object(Path,'read_bytes',return_value=b'changed context approval'):
            with self.assertRaisesRegex(ValidationFailure,'SOURCE_CONTEXT_BINDING_CHANGED'):
                contexts.context_for(self.registry,self.eid)
    def test_missing_package_fails_integrity(self):
        with patch.object(Path,'read_bytes',side_effect=FileNotFoundError()):
            with self.assertRaisesRegex(ValidationFailure,'SOURCE_CONTEXT_BINDING_UNAVAILABLE'):
                contexts.context_for(self.registry,self.eid)
    def test_manual_index_and_release_mismatches_fail(self):
        for field,value,code in [('checksum','wrong','MANUAL_MISMATCH'),('index_id','wrong','INDEX_MISMATCH')]:
            r=self.proxy();setattr(r,field,value)
            with self.assertRaisesRegex(ValidationFailure,code):contexts.context_for(r,self.eid)
        r=self.proxy();r.reviews['release_manifest_sha256']='wrong'
        with self.assertRaisesRegex(ValidationFailure,'RELEASE_MISMATCH'):contexts.context_for(r,self.eid)
        r=self.proxy();r.source['sha256']='wrong'
        with self.assertRaisesRegex(ValidationFailure,'MANUAL_MISMATCH'):contexts.context_for(r,self.eid)
    def test_raw_provenance_and_source_object_tampering_fail(self):
        for field,code in [('raw_object','RAW_OBJECT_MISMATCH'),('provenance','PROVENANCE_MISMATCH')]:
            r=self.proxy();r.evidence[self.eid]=deepcopy(r.evidence[self.eid])
            r.evidence[self.eid][field]={'changed':'unapproved value'}
            with self.assertRaisesRegex(ValidationFailure,code):contexts.context_for(r,self.eid)
        r=self.proxy();r.approved_sources[self.eid]=deepcopy(r.approved_sources[self.eid])
        r.approved_sources[self.eid]['exact_text']='changed source facts'
        with self.assertRaisesRegex(ValidationFailure,'SOURCE_OBJECT_MISMATCH'):contexts.context_for(r,self.eid)
    def test_absent_binding_and_evidence_fail_closed(self):
        r=self.proxy();r.evidence['unknown']=deepcopy(r.evidence[self.eid]);r.approved_sources['unknown']=deepcopy(r.approved_sources[self.eid])
        with self.assertRaisesRegex(ValidationFailure,'SOURCE_CONTEXT_REVIEW_REQUIRED'):contexts.context_for(r,'unknown')
        with self.assertRaisesRegex(ValidationFailure,'SOURCE_CONTEXT_REVIEW_REQUIRED'):contexts.context_for(r,'absent')
    def test_source_or_evidence_review_never_lifted_by_context(self):
        r=self.proxy();r.source_ready=lambda:False
        with self.assertRaisesRegex(ValidationFailure,'SOURCE_CONTEXT_REVIEW_REQUIRED'):contexts.context_for(r,self.eid)
        r=self.proxy();r.evidence_ready=lambda eid:False
        with self.assertRaisesRegex(ValidationFailure,'SOURCE_CONTEXT_REVIEW_REQUIRED'):contexts.context_for(r,self.eid)
    def test_policy_requires_existing_ready_authority_and_is_explicit_non_oem(self):
        r=self.proxy();r.evidence['policy']={'raw_object':{'text':'Policy-only test object'}}
        r.approved_sources['policy']={'authority':'PRODUCT_POLICY'};r.evidence_ready=lambda eid:eid=='policy'
        result=contexts.context_for(r,'policy')
        self.assertEqual(result['context_kind'],'PRODUCT_POLICY');self.assertIn('NOT_OEM_MANUAL',result['context_authority'])
        self.assertEqual(result['section_path'],[]);self.assertEqual(result['parent_membership'],[])
        self.assertNotIn('Policy-only test object',str(result))
        r.evidence_ready=lambda eid:False
        with self.assertRaisesRegex(ValidationFailure,'SOURCE_CONTEXT_REVIEW_REQUIRED'):contexts.context_for(r,'policy')
    def test_returned_values_do_not_mutate_cached_manifest(self):
        result=contexts.context_for(self.registry,self.eid)
        expected=list(result['section_path']);result['section_path'].append('injected subject')
        result['parent_membership'].clear()
        fresh=contexts.context_for(self.registry,self.eid)
        self.assertEqual(fresh['section_path'],expected);self.assertTrue(fresh['parent_membership'])

if __name__=='__main__':unittest.main()