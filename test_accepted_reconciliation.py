"""Actual accepted-example draft gates; never creates source approvals."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from evidence_registry import EvidenceRegistry, content_hash
from reconcile_accepted_examples import BASE_TEXT, PAGES, reconcile
from verify_gemma_grounding import evaluate

INDEX = Path(os.environ.get('MOTOMEDIC_TEST_INDEX','build/index-bge-final'))

@unittest.skipUnless((INDEX/'manifest.json').exists(),'Immutable hosted index required')
class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.original=EvidenceRegistry.load('registry',INDEX,'source_manifest.json')
        self.draft=EvidenceRegistry.load('registry/reconciled-accepted-eleven',INDEX,'source_manifest.json')
    def test_all_eleven_acceptances_are_draft_not_formal_approval(self):
        self.assertEqual(set(self.draft.candidate['steps']),set(BASE_TEXT))
        self.assertEqual(self.draft.reviews['decisions'],[])
        self.assertFalse(self.draft.source_ready())
        self.assertFalse(any(self.draft.step_ready(sid) for sid in BASE_TEXT))
        for sid,step in self.draft.candidate['steps'].items():
            self.assertTrue(step['authoring_blockers'])
            self.assertFalse(self.draft.candidate['dependencies'][sid]['scope_review_complete'])
            self.assertTrue(all(c['response_role'] in ('FACT','ACTION','WARNING','PREREQUISITE') for c in step['claims']))
            self.assertTrue(all(c['presentation_mode']=='DRAFT_PARAPHRASE' for c in step['claims']))
    def test_immutable_citations_and_source_additions(self):
        for sid,pages in PAGES.items():
            step=self.draft.candidate['steps'][sid]
            self.assertEqual(set(pages),set(step['draft_pdf_pages']))
            for citation in step['branch_draft_citations']:
                self.assertIn(citation['evidence_id'],self.original.evidence)
                self.assertIn(citation['pdf_page'],[p.get('page_no',p.get('pdf_page')) for p in self.original.evidence[citation['evidence_id']]['provenance']])
        self.assertIn('evidence_b6d98c3420a27b81214d7e15',self.draft.candidate['steps']['a_refuel']['required_evidence_ids'])
    def test_accepted_exclusions_and_service_precedence(self):
        c=self.draft.candidate
        self.assertEqual(c['steps']['a_fuse']['unresolved_route'],'ESCALATE')
        self.assertEqual(c['steps']['a_reconnect']['runtime_disposition'],'SERVICE_REFERRAL_ONLY_NO_OWNER_RECONNECTION')
        self.assertEqual(c['steps']['a_reconnect']['kind'],'LOOKUP')
        self.assertIn('page75',json.dumps(c['reconciliation_provenance']['excluded_pending_additions']).lower())
        self.assertNotIn('overnight',c['steps']['a_cool_engine']['claims'][0]['text'].lower())
        self.assertNotIn('data transfer',c['steps']['lookup_usb_charging']['claims'][0]['text'].lower())
        self.assertIn('fuel_indicator_discrepancy',c['steps']['a_refuel']['branch_drafts'])
        self.assertIn('uncertain_condition',c['steps']['a_fuse']['branch_drafts'])
    def test_requested_live_eval_stops_before_transport_or_key_access(self):
        before=content_hash(self.original.candidate)
        with tempfile.TemporaryDirectory() as directory,patch('gemini_transport.stream_request',side_effect=AssertionError('No real source calls allowed')):
            report=evaluate(INDEX,Path('registry/reconciled-accepted-eleven'),Path(directory)/'report.json',live=True,case_id='lookup_oil_grade')
        self.assertEqual(report['live_provider_calls'],0)
        self.assertEqual(report['live_status'],'BLOCKED_BEFORE_PROVIDER')
        self.assertEqual(sum(c['draft_gate_passed'] is True for c in report['cases']),11)
        self.assertEqual(before,content_hash(EvidenceRegistry.load('registry',INDEX,'source_manifest.json').candidate))
    def test_reauthor_cannot_overwrite_nonempty_review_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'review_decisions.json').write_text(json.dumps({'decisions':[{'decision':'REJECTED'}]}))
            with self.assertRaisesRegex(ValueError,'Do not overwrite'):reconcile(INDEX,root)

if __name__=='__main__':unittest.main()
