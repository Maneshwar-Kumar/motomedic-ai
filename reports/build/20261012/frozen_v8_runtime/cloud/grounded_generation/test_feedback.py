"""Source-bound clarification capability tests; no source/semantic approval."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
import os
from unittest.mock import patch
from approved_registry import ApprovedEvidenceRegistry
from controller_contracts import ResponseType
from reviewed_controller import start_session
from cloud.grounded_generation import feedback

ROOT=Path(__file__).resolve().parents[2]
INDEX=Path(os.environ.get('MOTOMEDIC_TEST_INDEX',str(ROOT/'build/index-bge-final')))

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=ApprovedEvidenceRegistry.load(ROOT,INDEX)
        raw=(ROOT/feedback.PATH).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==feedback.SHA
        cls.manifest=json.loads(raw)
        cls.ready=[]
        for row in cls.manifest['bindings']:
            owners=[sid for sid,step in cls.r.candidate['steps'].items()
                if step['canonical_record_id'] in row['owners'] and cls.r.step_ready(sid)]
            if owners: cls.ready.append((row,owners[0]))
        assert cls.ready
    def session(self,row,sid):
        return replace(start_session(self.r,(),self.r.source['variant'],self.r.source['edition']),
            pending_step_id=sid,pending_rule_id=row['rule_id'],version=4)
    def response(self,row):
        from types import SimpleNamespace
        return SimpleNamespace(type=ResponseType.AMBIGUOUS,natural_language=row['clarification_question'])
    def test_all_ready_source_bindings_issue_correct_boolean_capabilities(self):
        for row,sid in self.ready:
            with self.subTest(rule=row['rule_id']):
                session=self.session(row,sid)
                public,private=feedback.issue_choices(self.r,session,self.response(row))
                self.assertEqual(len(public),3)
                for choice in public:
                    binding=private[choice['id']]
                    outcome,fact=feedback.consume_choice(self.r,session,private,choice['id'],4)
                    value=row['answer_values'][binding['answer']]
                    self.assertEqual(fact.value if fact else None,value)
                    self.assertEqual(outcome.value,binding['outcome'])
    def test_canonical_owner_is_not_runtime_step_id(self):
        row,sid=self.ready[0]
        self.assertNotIn(sid,row['owners'])
        self.assertIn(self.r.candidate['steps'][sid]['canonical_record_id'],row['owners'])
        self.assertIsNotNone(feedback.binding_for(self.r,self.session(row,sid)))
    def test_stale_version_and_cross_session_capabilities_fail(self):
        row,sid=self.ready[0];s=self.session(row,sid)
        public,private=feedback.issue_choices(self.r,s,self.response(row))
        with self.assertRaises(ValueError):
            feedback.consume_choice(self.r,s,private,public[0]['id'],3)
        with self.assertRaises(ValueError):
            feedback.consume_choice(self.r,replace(s,session_id='different-session'),private,public[0]['id'],4)
    def test_saved_fact_and_answer_tampering_fail(self):
        row,sid=self.ready[0];s=self.session(row,sid)
        public,private=feedback.issue_choices(self.r,s,self.response(row))
        key=public[0]['id'];changed=deepcopy(private)
        changed[key]['fact']['value']=not changed[key]['fact']['value']
        with self.assertRaises(ValueError):
            feedback.consume_choice(self.r,s,changed,key,4)
        changed=deepcopy(private);changed[key]['answer']='invented'
        with self.assertRaises(ValueError):
            feedback.consume_choice(self.r,s,changed,key,4)
    def test_unsure_never_creates_fact(self):
        row,sid=self.ready[0];s=self.session(row,sid)
        public,private=feedback.issue_choices(self.r,s,self.response(row))
        key=next(c['id'] for c in public if private[c['id']]['answer']=='unsure')
        outcome,fact=feedback.consume_choice(self.r,s,private,key,4)
        self.assertEqual(outcome.value,'UNCLEAR');self.assertIsNone(fact)
    def test_changed_source_review_bytes_fail_closed(self):
        row,sid=self.ready[0]
        with patch.object(Path,'read_bytes',return_value=b'changed approval'):
            with self.assertRaisesRegex(ValueError,'CLARIFICATION_REVIEW_CHANGED'):
                feedback.binding_for(self.r,self.session(row,sid))
    def test_wrong_pending_owner_misses(self):
        row,sid=self.ready[0]
        other=next(k for k,v in self.r.candidate['steps'].items() if v['canonical_record_id'] not in row['owners'])
        self.assertIsNone(feedback.binding_for(self.r,self.session(row,other)))
    def test_unissued_question_has_no_boolean_capabilities(self):
        row,sid=self.ready[0];s=self.session(row,sid)
        response=self.response(row);response.natural_language='An unrelated question?'
        public,_=feedback.issue_choices(self.r,s,response)
        self.assertEqual(public,[])

    def test_exp003_changed_display_question_cannot_issue_fact(self):
        row,sid=next(pair for pair in self.ready if pair[0]['rule_id']=='EXP003:rule:turn_switch_centred')
        s=self.session(row,sid);response=self.response(row)
        response.natural_language='Have you completed an unrelated action?'
        public,private=feedback.issue_choices(self.r,s,response)
        self.assertEqual(public,[]);self.assertEqual(private,{})

class ThoughtBoundaryTests(unittest.TestCase):
    def run_parts(self,parts,thoughts=0):
        from cloud.grounded_generation.provider import GemmaProvider
        from cloud.grounded_generation.test_provider import Transport
        from cloud.grounded_generation.policy import SCHEMA
        transport=Transport()
        def wrapped(method,path,body,key):
            result=transport(method,path,body,key)
            if path.endswith(':generateContent'):
                original=result['candidates'][0]['content']['parts']
                result['candidates'][0]['content']['parts']=parts+original
                result['usageMetadata']['thoughtsTokenCount']=thoughts
            return result
        provider=GemmaProvider(lambda n,k:None,transport=wrapped,key='software-test')
        return provider.complete('policy',{}, {}, SCHEMA)
    def test_exact_empty_true_marker_is_harmless_and_counted(self):
        result=self.run_parts([{'text':'','thought':True}])
        self.assertEqual(result.telemetry['empty_thought_markers'],1)
    def test_nonempty_thought_content_is_rejected(self):
        from cloud.grounded_generation.provider import ProviderFailure
        with self.assertRaises(ProviderFailure):self.run_parts([{'text':'hidden reasoning','thought':True}])
    def test_marker_extra_keys_are_rejected(self):
        from cloud.grounded_generation.provider import ProviderFailure
        with self.assertRaises(ProviderFailure):self.run_parts([{'text':'','thought':True,'extra':'x'}])
    def test_numeric_thought_flag_is_rejected(self):
        from cloud.grounded_generation.provider import ProviderFailure
        with self.assertRaises(ProviderFailure):self.run_parts([{'text':'','thought':1}])
    def test_paid_thought_tokens_are_rejected_despite_empty_marker(self):
        from cloud.grounded_generation.provider import ProviderFailure
        with self.assertRaises(ProviderFailure):self.run_parts([{'text':'','thought':True}],thoughts=1)

if __name__=='__main__': unittest.main()
