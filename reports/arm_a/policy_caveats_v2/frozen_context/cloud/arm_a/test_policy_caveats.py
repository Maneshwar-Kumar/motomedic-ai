"""Exact policy caveats and unchanged technical gates; no provider/inference calls."""
from dataclasses import replace
from copy import deepcopy
import unittest
from approved_registry import ApprovedEvidenceRegistry
from cloud.arm_a import test_composer as composer_tests
from cloud.arm_a.rider_contract import saved_view
from constrained_generator import envelope, ValidationFailure
from controller_contracts import ResponseType
from test_approved_integration import ROOT, INDEX

class PolicyCaveatTests(unittest.TestCase):
    controller=composer_tests.ComposerTests.controller
    session=composer_tests.ComposerTests.session
    def setUp(self):
        self.registry=ApprovedEvidenceRegistry.load(ROOT, INDEX)

    def test_exact_policy_caveat_with_manual_fact(self):
        c=self.controller();s=self.session(c,'GEN012');sid='GEN012:candidate-v3'
        response=c.response_generator.compose(c,s,sid)
        self.assertEqual(response.type,ResponseType.SUPPORTED)
        self.assertEqual(response.natural_language,' '.join(x['text'] for x in self.registry.step(sid).claims))
        policy=[x for x in response.claim_evidence_map if not x['evidence_ids']]
        self.assertEqual(len(policy),1)
        self.assertTrue(policy[0]['policy_support_ids'])
        self.assertFalse(any(x['evidence_id'].startswith('policy_') for x in response.cited_pages))
        view,_=saved_view(self.registry,s,response)
        self.assertTrue(view['response']['release_gate_passed'])
        with self.assertRaises(ValidationFailure):envelope(c,s,sid)

    def test_changed_or_wrong_scope_policy_claim_rejected(self):
        claim=deepcopy(self.registry.step('GEN012:candidate-v3').claims[-1])
        self.assertFalse(self.registry.approved_policy_caveat('GEN015:candidate-v3',claim))
        claim['text']='Adjust the plug to an invented setting.'
        self.assertFalse(self.registry.approved_policy_caveat('GEN012:candidate-v3',claim))

    def test_policy_source_mutation_rejected(self):
        sid='GEN012:candidate-v3';claim=self.registry.step(sid).claims[-1]
        ref=claim['policy_support_ids'][0]
        self.registry.approved_sources[ref]['exact_text']='untrusted replacement'
        self.assertFalse(self.registry.approved_policy_caveat(sid,claim))
        c=self.controller();response=c.response_generator.compose(c,self.session(c,'GEN012'),sid)
        self.assertNotEqual(response.type,ResponseType.SUPPORTED)

    def test_missing_technical_citation_cannot_become_policy(self):
        sid='GEN012:candidate-v3';claim=deepcopy(self.registry.step(sid).claims[0])
        claim['evidence_ids']=[]
        claim['policy_support_ids']=self.registry.step(sid).claims[-1]['policy_support_ids']
        self.assertFalse(self.registry.approved_policy_caveat(sid,claim))

    def test_missing_retrieved_technical_evidence_still_withheld(self):
        c=self.controller(missing=True)
        _,response,_=c.next(self.session(c,'GEN012'),'What spark-plug gap is specified?')
        self.assertNotEqual(response.type,ResponseType.SUPPORTED)

    def test_policy_reference_tampering_at_display_rejected(self):
        c=self.controller();s=self.session(c,'GEN012')
        response=c.response_generator.compose(c,s,'GEN012:candidate-v3')
        claims=[dict(x) for x in response.claim_evidence_map]
        claims[-1]['policy_support_ids']=['policy_fake']
        with self.assertRaises(ValueError):saved_view(self.registry,s,replace(response,claim_evidence_map=tuple(claims)))

    def test_safety_warning_keeps_manual_and_policy_support_separate(self):
        c=self.controller();s=self.session(c,'GEN042')
        response=c.render(s,'GEN042:candidate-v3',safety=True)
        self.assertEqual(response.type,ResponseType.SAFETY_STOP)
        view,_=saved_view(self.registry,s,response)
        self.assertTrue(view['response']['release_gate_passed'])
        self.assertFalse(any(x['evidence_id'].startswith('policy_') for x in response.cited_pages))

if __name__=='__main__':unittest.main()
