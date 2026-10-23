"""Synthetic integration over unchanged approved source objects, no model calls.

These checks establish bindings and delivery behavior, never factual model
accuracy, live Cloud Tasks/Firestore/Qdrant, latency or release acceptance.
"""
from copy import deepcopy
import hashlib
import unittest
from cloud.grounded_generation import test_generic_runtime as source_fixtures
from cloud.grounded_generation.test_verified_qa import Provider, draft
from cloud.grounded_generation.serving_source_authority import SourceAuthority
from cloud.grounded_generation.serving_questions import Questions
from cloud.grounded_generation.verified_qa import Composer
from cloud.grounded_generation.delivery import bind_view, accepted_events, response_hash

BORE,LOCATION=source_fixtures.BORE,source_fixtures.LOCATION


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_fixtures.Tests.setUpClass()
        cls.original=source_fixtures.Tests.original
        cls.original_authority=SourceAuthority(cls.original, source_fixtures.Tests.original_authority.index)

    def setUp(self):
        self.registry=deepcopy(self.original)
        self.authority=deepcopy(self.original_authority)
        self.authority.base=self.registry;self.authority.evidence=self.registry.evidence

    def make(self, provider=None, evidence_id=BORE):
        provider=provider or Provider()
        chunk=next(c for c in self.authority.chunks.values() if evidence_id in c['evidence_ids'])
        retriever=source_fixtures.ScriptedRetriever(self.authority,[chunk])
        composer=Composer(provider,self.authority)
        questions=Questions(self.registry,retriever,composer,self.authority)
        return questions,provider,composer

    def test_arbitrary_question_verifies_then_replays_exact_accepted_buffer(self):
        self.registry.candidate['steps']={}
        questions,provider,composer=self.make()
        session=questions.new_session();stages=[]
        _,view,_=questions.answer(session,'Tell me the cylinder bore specification.',
            progress=stages.append,operation_id='synthetic-operation')
        self.assertEqual(view['response']['type'],'SUPPORTED')
        self.assertEqual(stages,['retrieving','drafting','verifying'])
        self.assertEqual(len(provider.calls),2)
        projected=provider.calls[0][1]['evidence'][BORE]['source_object']['content']
        self.assertIn('84 mm',str(projected))
        self.assertNotIn('bbox',projected)
        frozen=bind_view(view,'synthetic-operation',composer.config.lock)
        recovered=deepcopy(frozen)
        events=list(accepted_events(recovered,'synthetic-operation'))
        text=''.join(body['text'] for kind,body in events if kind=='answer_chunk')
        self.assertEqual(text,provider.calls[-1][2]['complete_proposed_response']['text'])
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),frozen['verified_delivery']['text_sha256'])
        self.assertEqual(response_hash(recovered),frozen['delivery']['response_sha256'])
        self.assertTrue(all(body.get('sequence')==i+1 for i,(_,body) in enumerate(events)))

    def test_partial_answer_states_limit_before_separate_verification(self):
        candidate=draft(coverage='PARTIAL')
        candidate['unanswered_parts']=['the service procedure']
        candidate['claims'].append({'text':'The retrieved owner manual evidence does not establish the service procedure.',
            'role':'LIMITATION','evidence_ids':[]})
        questions,provider,composer=self.make(Provider([candidate]))
        _,view,_=questions.answer(questions.new_session(),'Give the bore and its service procedure.',operation_id='partial')
        self.assertEqual(view['response']['type'],'SUPPORTED')
        self.assertIn('does not establish',provider.calls[-1][2]['complete_proposed_response']['text'])
        self.assertEqual(composer.last_admitted['verdict']['decision'],'RELEASE_PARTIAL')

    def test_source_warning_and_units_survive_compaction_and_finalization(self):
        questions,provider,_=self.make(Provider([draft(LOCATION,'The charging port is at the handlebar centre.')]),LOCATION)
        _,view,_=questions.answer(questions.new_session(),'Where is the charging port?',operation_id='warnings')
        self.assertEqual(view['response']['type'],'SUPPORTED')
        final=provider.calls[-1][2]['complete_proposed_response']
        self.assertIn('rain',final['text']);self.assertIn('engine is running',final['text'])
        self.assertTrue(any(row['pdf_page']==64 for row in final['citations']))

    def test_semantic_rejection_exposes_only_fixed_fallback(self):
        def reject(value,*_):
            value.update(decision='SHOW_FALLBACK',release_eligible=False,correction_possible=False,
                question_coverage='IRRELEVANT')
            return value
        questions,_,composer=self.make(Provider(verifier=reject))
        _,view,_=questions.answer(questions.new_session(),'Actual question',operation_id='rejected')
        self.assertEqual(view['response']['type'],'UNSUPPORTED')
        self.assertIsNone(composer.last_admitted)
        bound=bind_view(view,'rejected',composer.config.lock)
        events=list(accepted_events(bound,'rejected'))
        self.assertEqual([kind for kind,_ in events],['complete'])
        self.assertNotIn('84 mm',str(events))


if __name__=='__main__':unittest.main()
