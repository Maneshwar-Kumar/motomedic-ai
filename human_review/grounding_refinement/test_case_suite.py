"""Tests on actual case-specific fixture identities, not semantic-verifier scoring."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from human_review.grounding_refinement import case_suite as mod
from evidence_registry import EvidenceRegistry
from generation_providers import gemma_runtime_config
from online_retrieve import Retriever
from reviewed_controller import ReviewedController
from verify_controller import NoInferenceEncoder

class SuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite=json.loads((mod.OUT/'suite.json').read_text(encoding='utf-8'))

    def test_complete_case_specific_entries_and_corrections(self):
        rows=self.suite['records'];self.assertEqual(len(rows),161)
        self.assertEqual({r['record_id'] for r in rows if r['candidate_revision']=='corrected-alternative-v1'},
                         {'GEN057','GEN058','EXP024','EXP027'})
        self.assertTrue(all(r['question'] and r['claims'] and r['branch_context'] for r in rows))

    def test_actual_canonical_contracts_preserve_every_claim(self):
        for r in self.suite['records']:
            with self.subTest(record=r['record_id']):
                self.assertTrue(mod.validate_candidate(r,mod.canonical(r)))
                self.assertTrue(mod.validate_sources(r,self.suite['sources']))

    def test_forged_citation_and_omitted_warning_are_rejected(self):
        r=next(r for r in self.suite['records'] if r['record_id']=='lookup_tyre_pressure')
        output=mod.canonical(r);output['citations'][0]['evidence_id']='fake'
        with self.assertRaises(ValueError):mod.validate_candidate(r,output)
        warning=next(c for c in r['claims'] if c.get('response_role')=='WARNING')
        output=mod.canonical(r);output['answer']=output['answer'].replace(warning['exact_claim_text'],'')
        with self.assertRaises(ValueError):mod.validate_candidate(r,output)

    def test_changed_units_policy_oem_authority_and_missing_dependency_rejected(self):
        r=next(r for r in self.suite['records'] if r['record_id']=='GEN007')
        eid=r['required_candidate_source_ids'][0]
        for key,value in [('exact_text','Invented specification'),('authority','COUNTERFEIT')]:
            sources=dict(self.suite['sources']);sources[eid]={**sources[eid],key:value}
            with self.assertRaises(ValueError):mod.validate_sources(r,sources)
        sources=dict(self.suite['sources']);sources.pop(eid)
        with self.assertRaises(ValueError):mod.validate_sources(r,sources)

    def test_original_r001_conditional_and_r002_pending(self):
        for rid in ('a_switches_on','lookup_starter_duration'):
            r=next(r for r in self.suite['records'] if r['record_id']==rid)
            branch=r['branch_context']['branches']['starter_recovery_R001']
            self.assertIn('already',branch['condition'])
            self.assertIn('15–20',branch['claims'][0]['exact_claim_text'])
            self.assertEqual(r['branch_context']['R002'],'PENDING_POST_START_SCOPE')
        switch=next(r for r in self.suite['records'] if r['record_id']=='a_switches_on')
        self.assertNotIn('15–20',switch['canonical_answer'])

    def test_corrected_gen058_retains_known_symptom_without_reasking(self):
        r=next(r for r in self.suite['records'] if r['record_id']=='GEN058')
        self.assertNotIn('?',r['canonical_answer'])
        self.assertIn('customer-reported',r['canonical_answer'])

    def test_changed_candidate_cannot_redefine_its_expected_answer(self):
        r=deepcopy(self.suite['records'][0]);r['canonical_answer']='Invented new repair.'
        with self.assertRaises(ValueError):mod.validate_candidate(r,mod.canonical(r))

    def test_forged_fixture_approval_cannot_pass_actual_registry(self):
        index=mod.ROOT/'build/index-bge-final'
        registry=EvidenceRegistry.load(mod.ROOT/'registry/reconciled-accepted-eleven',index,mod.ROOT/'source_manifest.json')
        c=ReviewedController(registry,Retriever(index,embedding_model=NoInferenceEncoder()))
        record=deepcopy(next(r for r in self.suite['records'] if r['record_id']=='lookup_oil_grade'))
        record['formal_source_approved']=True
        blockers,_=mod.preflight(record,registry,c,gemma_runtime_config())
        self.assertIn('FORMAL_SOURCE_METADATA_APPROVAL_REQUIRED',blockers)

    def test_live_request_with_all_holds_reads_no_key_and_constructs_no_provider(self):
        with patch.object(mod,'build_generator',side_effect=AssertionError('Provider constructed before source gate')) as provider:
            with patch('generation_providers.os.environ.get',side_effect=AssertionError('Key access before source gate')):
                report=mod.evaluate(self.suite,live=True)
        provider.assert_not_called()
        self.assertEqual(report['live_provider_calls'],0)
        self.assertEqual(report['source_approved_eligible_cases'],0)
        self.assertTrue(all(r['live_status']=='BLOCKED_BEFORE_KEY_ACCESS' for r in report['records']))

if __name__=='__main__':unittest.main()
