"""Admission wording boundary tests; synthetic authority never grants real approval."""
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import os
import unittest
from cloud.grounded_generation.runtime import scope_payload
from constrained_generator import ValidationFailure
from controller_contracts import Truth
from approved_registry import ApprovedEvidenceRegistry

class SyntheticScope:
    """Isolate predicates after a scripted source/step approval boundary."""
    def __init__(self,kind='LOOKUP'):
        fact={'claim_id':'unused','text':'An unused authored question?',
            'reviewed_wording_variants':['Another unused question?'],
            'response_role':'ACTION' if kind=='ACTION' else 'FACT','evidence_ids':['e'],
            'presentation_mode':'unused authored metadata'}
        warning={'claim_id':'warning','text':'Required warning remains unchanged.',
            'response_role':'WARNING','evidence_ids':['w'],'presentation_mode':'REVIEWED_PARAPHRASE'}
        self.item=SimpleNamespace(kind=kind,claims=[fact,warning],required_evidence_ids=['e','w'],action_evidence_ids=['e'])
        self.source={'pdf_pages':149};self.candidate={'dependencies':{'s':{'categories':{'warnings':['w'],'prerequisites':[]}}}}
        self.evidence={e:{'type':'text','provenance':[{'page_no':1}]} for e in ('e','w')}
        self.ready=True
    def source_ready(self):return self.ready
    def step_ready(self,sid):return self.ready
    def step(self,sid):return self.item
    def approved_policy_caveat(self,*args):return False

class Tests(unittest.TestCase):
    def setUp(self):
        self.registry=SyntheticScope();self.truth=Truth.TRUE
        self.controller=SimpleNamespace(registry=self.registry,eligible=lambda *args:SimpleNamespace(eligibility_status=self.truth))
    def call(self):return scope_payload(self.controller,None,'s')
    def test_unused_fact_question_and_variants_do_not_gate_admission(self):
        result=self.call()
        self.assertEqual(result['required_display'],[self.registry.item.claims[1]])
        self.assertNotIn('An unused authored question?',str(result))
        self.assertNotIn('Another unused question?',str(result))
    def test_unused_action_wording_does_not_gate_admission(self):
        self.registry=SyntheticScope('ACTION');self.controller.registry=self.registry
        result=self.call();self.assertEqual(result['permitted_action_evidence_ids'],['e'])
        self.assertNotIn('An unused authored question?',str(result))
    def test_mandatory_display_question_is_rejected(self):
        self.registry.item.claims[1]['text']='Is this a warning?'
        with self.assertRaisesRegex(ValidationFailure,'MANDATORY_DISPLAY'):self.call()
    def test_unreviewed_or_verbatim_mandatory_display_is_rejected(self):
        self.registry.item.claims[1]['presentation_mode']='GENERATED_PARAPHRASE'
        with self.assertRaisesRegex(ValidationFailure,'MANDATORY_DISPLAY'):self.call()
        self.registry.item.claims[1]['presentation_mode']='REVIEWED_PARAPHRASE'
        self.registry.item.claims[1]['verbatim_warning']=True
        with self.assertRaisesRegex(ValidationFailure,'MANDATORY_DISPLAY'):self.call()
    def test_mandatory_warning_coverage_still_required(self):
        self.registry.item.claims[1]['response_role']='FACT'
        with self.assertRaisesRegex(ValidationFailure,'MANDATORY_WARNING_OR_CONDITION_OMITTED'):self.call()
    def test_source_and_typed_eligibility_still_fail_closed(self):
        self.registry.ready=False
        with self.assertRaisesRegex(ValidationFailure,'SOURCE_REVIEW_REQUIRED'):self.call()
        self.registry.ready=True;self.truth=Truth.UNKNOWN
        with self.assertRaisesRegex(ValidationFailure,'STEP_NOT_ELIGIBLE'):self.call()
    def test_figures_and_unbound_evidence_still_rejected(self):
        self.registry.evidence['e']['type']='picture'
        with self.assertRaisesRegex(ValidationFailure,'FIGURE'):self.call()
        self.registry.evidence['e']['type']='text';self.registry.item.claims[0]['evidence_ids']=['invented']
        with self.assertRaisesRegex(ValidationFailure,'INVALID_CLAIM_CITATION'):self.call()
    def test_actual_approved_registry_claim_mutation_does_not_acquire_approval(self):
        root=Path(__file__).resolve().parents[2]
        registry=ApprovedEvidenceRegistry.load(root,Path(os.environ.get('MOTOMEDIC_TEST_INDEX',str(root/'build/index-bge-final'))))
        sid='GEN007:candidate-v3';self.assertTrue(registry.step_ready(sid))
        registry.candidate['steps'][sid]['claims'][0]['text']='Changed source approval content'
        self.assertFalse(registry.step_ready(sid))
        controller=SimpleNamespace(registry=registry,eligible=lambda *args:SimpleNamespace(eligibility_status=Truth.TRUE))
        with self.assertRaisesRegex(ValidationFailure,'SOURCE_REVIEW_REQUIRED'):scope_payload(controller,None,sid)

if __name__=='__main__':unittest.main()