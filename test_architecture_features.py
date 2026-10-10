"""Offline safety/overlap checks; no provider requests or latency claims."""
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import numpy as np

from online_retrieve import Retriever
from semantic_candidate_cache import SemanticCandidateCache
from verified_delivery_stream import VerifiedDeliveryStream
import test_architecture_benchmark as existing
from architecture_benchmark import run_sample, Allocation, MODEL
from approved_text_journeys import SimulatedRetrieval
from generation_providers import ProviderResult, gemma_runtime_config
from session_store import SQLiteSessionStore
from test_approved_integration import INDEX


class ConcurrentSearch(unittest.TestCase):
    def test_ranking_matches_sequential_scores(self):
        from test_conditional_retrieval import fixture
        from retrieval_policy import RetrievalPolicy
        r,_=fixture()
        r.bm25.update(postings={'check':[(0,1)]},idf={'check':1.})
        d,_=r._dense_scores('check')
        s,_=r._sparse_scores('check')
        expected=r._rank(d,s,2,RetrievalPolicy())
        cd,cs,_,_=r._first_stage('check')
        self.assertEqual(expected,r._rank(cd,cs,2,RetrievalPolicy()))

    def test_both_branches_start_before_either_can_complete(self):
        retriever = object.__new__(Retriever)
        barrier = threading.Barrier(2)
        def dense(query):
            barrier.wait(timeout=3)
            return np.array([1.,2.]), .1
        def sparse(query):
            barrier.wait(timeout=3)
            return np.array([3.,4.]), .2
        retriever._dense_scores, retriever._sparse_scores = dense, sparse
        d,s,dt,st = retriever._first_stage('q')
        np.testing.assert_equal(d,[1,2])
        np.testing.assert_equal(s,[3,4])
        self.assertEqual((dt,st),(.1,.2))

    def test_either_branch_failure_prevents_partial_result(self):
        retriever = object.__new__(Retriever)
        def broken(query): raise RuntimeError('failure')
        for branch in ('dense','sparse'):
            retriever._dense_scores = broken if branch == 'dense' else lambda q: ([1],0)
            retriever._sparse_scores = broken if branch == 'sparse' else lambda q: ([2],0)
            with self.assertRaises(RuntimeError): retriever._first_stage('q')


class CacheContracts(unittest.TestCase):
    def setUp(self):
        self.allowed = {'claims':[{'wording':['approved']} ]}
        self.now = 0
        self.cache = SemanticCandidateCache(embedding_revision='pinned',clock=lambda:self.now,ttl_seconds=1,max_entries=1)

    def test_similarity_without_exact_authority_cannot_hit(self):
        self.cache.put([1,0],'exact',self.allowed,['approved'])
        self.assertEqual(self.cache.lookup([1,0],'changed',self.allowed)[1],'MISS')
        self.assertEqual(self.cache.lookup([0,1],'exact',self.allowed)[1],'MISS')
        self.assertEqual(self.cache.lookup([1,.01],'exact',self.allowed)[0],['approved'])

    def test_unreviewed_paraphrase_and_tampered_content_rejected(self):
        self.assertEqual(self.cache.put([1,0],'exact',self.allowed,['invented']),'UNREVIEWED_PARAPHRASE_NOT_CACHED')
        self.cache.put([1,0],'exact',self.allowed,['approved'])
        next(iter(self.cache.entries.values()))['texts'][0]='invented'
        self.assertEqual(self.cache.lookup([1,0],'exact',self.allowed)[1],'MISS')

    def test_expiry_capacity_copy_and_bypass(self):
        self.cache.put([1,0],'exact',self.allowed,['approved'])
        result,_=self.cache.lookup([1,0],'exact',self.allowed)
        result[0]='mutated'
        self.assertEqual(self.cache.lookup([1,0],'exact',self.allowed)[0],['approved'])
        self.assertEqual(self.cache.lookup(None,'exact',{},bypass=True),(None,'BYPASS'))
        self.now=2
        self.assertEqual(self.cache.lookup([1,0],'exact',self.allowed)[1],'MISS')
        self.cache.put([1,0],'one',self.allowed,['approved'])
        self.cache.put([1,0],'two',self.allowed,['approved'])
        self.assertEqual(len(self.cache.entries),1)
        self.assertEqual(self.cache.lookup([1,0],'one',self.allowed)[1],'MISS')

    def test_invalid_vectors_fail_closed(self):
        for vector in ([0,0],[np.nan,1],[[1,2]]):
            with self.assertRaises(ValueError): self.cache.lookup(vector,'a',self.allowed)


class RuntimeFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        existing.BenchmarkContracts.setUpClass()
        cls.registry=existing.BenchmarkContracts.registry

    def execute(self, architecture, cache, *, reject=False, bypass=False, rid='GEN003'):
        calls=[]
        stream=VerifiedDeliveryStream()
        class Provider:
            def __init__(self,*args,**kwargs): pass
            def complete(self,policy,payload,schema):
                props=schema['properties']
                calls.append(tuple(props))
                if 'choices' in props:
                    return ProviderResult({'choices':[0]*len(payload['claims'])})
                if 'texts' in props:
                    return ProviderResult({'texts':[c['meaning'] for c in payload['claims']]})
                if 'supported' in props:
                    n=len(payload['claims'])
                    return ProviderResult({'supported':[not reject]*n,'complete':[True]*n,'unsupported_additions':False})
                raise AssertionError('Unexpected generator request')
        with tempfile.TemporaryDirectory() as temp:
            store=SQLiteSessionStore(Path(temp)/'state.sqlite')
            store.db.execute('CREATE TABLE benchmark_deliveries (session_id TEXT, block INTEGER, session_version INTEGER, content_sha256 TEXT, evidence_ids TEXT)')
            original_deliver=stream.deliver
            def committed_delivery(packet):
                self.assertEqual(store.db.execute('SELECT count(*) FROM benchmark_deliveries').fetchone()[0],packet['block']+1)
                self.assertEqual(store.load(packet['session_id']).version,packet['session_version'])
                original_deliver(packet)
            stream.deliver=committed_delivery
            try:
                with patch('architecture_benchmark.BoundedProvider',Provider):
                    row=run_sample(self.registry,SimulatedRetrieval(INDEX),gemma_runtime_config(MODEL),
                        Allocation(),store,rid,'semantic equivalent',architecture,
                        semantic_cache=cache,cache_encoder=lambda q:np.array([1.,0.]),
                        cache_bypass=bypass,delivery_stream=stream)
                return row,calls,list(stream.iter_events())
            finally: store.close()

    def test_a_cache_hit_skips_generation_and_streams_after_commit(self):
        cache=SemanticCandidateCache(embedding_revision='test-pinned')
        first,calls,events=self.execute('A_COMPONENT_SELECTION',cache)
        self.assertEqual(first['route'],'SUPPORTED')
        self.assertEqual(len(calls),1)
        second,calls,events=self.execute('A_COMPONENT_SELECTION',cache)
        self.assertEqual(second['route'],'SUPPORTED')
        self.assertEqual(calls,[])
        self.assertEqual(second['semantic_cache'],'EXACT_AUTHORITY_VALIDATED_CANDIDATE_HIT')
        self.assertEqual([e['event'] for e in events],['verified_block','complete'])
        self.assertTrue(events[0]['data']['citations'])
        bypass,calls,_=self.execute('A_COMPONENT_SELECTION',cache,bypass=True)
        self.assertEqual(len(calls),1)
        self.assertEqual(bypass['semantic_cache'],'BYPASS')

    def test_b_cache_hit_still_verifies_and_rejection_emits_only_error(self):
        cache=SemanticCandidateCache(embedding_revision='test-pinned')
        first,calls,_=self.execute('B_SHORT_GENERATION',cache)
        self.assertEqual(first['route'],'SUPPORTED')
        second,calls,events=self.execute('B_SHORT_GENERATION',cache)
        self.assertEqual(second['route'],'SUPPORTED')
        self.assertEqual(len(calls),1)
        self.assertIn('supported',calls[0])
        rejected,calls,events=self.execute('B_SHORT_GENERATION',cache,reject=True)
        self.assertEqual(rejected['route'],'SYSTEM_ERROR')
        self.assertEqual([e['event'] for e in events],['error'])

    def test_c_cached_candidate_still_verifies(self):
        # Prime C's exact scoped authority using the same reviewed wording, then
        # assert fresh per-block verification without a generator request.
        from semantic_candidate_cache import binding
        cache=SemanticCandidateCache(embedding_revision='test-pinned')
        def seeded(controller,session,allowed,architecture,config,revision,prompt):
            authority=binding(controller,session,allowed,architecture,config,revision,prompt)
            cache.put([1.,0.],authority,allowed,[c['wording'][0] for c in allowed['claims']])
            return authority
        with patch('architecture_benchmark.cache_binding',seeded):
            row,calls,events=self.execute('C_VERIFIED_STREAM_BLOCKS',cache)
        self.assertEqual(row['route'],'SUPPORTED')
        self.assertEqual(len(calls),1)
        self.assertIn('supported',calls[0])
        self.assertFalse(row['terminal_provider_integrity_checked_after_early_blocks'])
        self.assertEqual([e['event'] for e in events],['verified_block','complete'])

    def test_authority_changes_for_state_manual_versions_and_outcomes(self):
        from semantic_candidate_cache import binding
        from dataclasses import replace
        from controller_contracts import Outcome
        checked=[]
        def inspected(controller,session,allowed,architecture,config,revision,prompt):
            original=binding(controller,session,allowed,architecture,config,revision,prompt)
            for key in ('manual_checksum','bike_variant','edition','version_lock','generation_lock',
                        'symptom_revision','pending_step_id','scope_reconfirmation_required',
                        'excluded_branches','clarification_counts'):
                value=getattr(session,key)
                changed=(not value if type(value) is bool else value+1 if type(value) is int
                         else ('changed',) if type(value) is tuple else 'changed')
                self.assertNotEqual(original,binding(controller,replace(session,**{key:changed}),
                    allowed,architecture,config,revision,prompt),key)
            for args in ((architecture,revision+'new',prompt),(architecture,revision,prompt+'new'),
                         ('changed',revision,prompt)):
                self.assertNotEqual(original,binding(controller,session,allowed,args[0],config,args[1],args[2]))
            changed_allowed=deepcopy(allowed)
            changed_allowed['step_id']='changed'
            self.assertNotEqual(original,binding(controller,session,changed_allowed,architecture,config,revision,prompt))
            if session.active_attempts():
                attempt=session.active_attempts()[0]
                changed=replace(attempt,outcome_enum=Outcome.ACTION_COMPLETED_UNRESOLVED)
                altered=replace(session,attempted_steps=(changed,))
                self.assertNotEqual(original,binding(controller,altered,allowed,architecture,config,revision,prompt))
            checked.append(True)
            return original
        with patch('architecture_benchmark.cache_binding',inspected):
            row,_,_=self.execute('A_COMPONENT_SELECTION',SemanticCandidateCache(embedding_revision='test'),rid='EXP003')
        self.assertEqual(row['route'],'SUPPORTED')
        self.assertEqual(checked,[True])

    def test_c_success_and_partial_failure_stream_distinct_terminal_events(self):
        helper=existing.StreamReleaseContracts()
        helper.registry=self.registry
        for failure in (False,True):
            stream=VerifiedDeliveryStream()
            row,count=helper.run_stream(terminal_failure=failure,delivery_stream=stream)
            events=list(stream.iter_events())
            self.assertEqual(len(events),count+1)
            self.assertEqual(events[-1]['event'],'error' if failure else 'complete')
            self.assertEqual(events[-1]['data']['partial_verified_delivery'],failure)

    def test_sse_serializes_untrusted_newlines_inside_json(self):
        stream=VerifiedDeliveryStream()
        packet={'session_id':'s','session_version':1,'block':0,'texts':['x\nevent: injected'],
                'citations':[{'id':'e'}],'content_sha256':'h','architecture':'A'}
        stream.deliver(packet)
        with self.assertRaises(ValueError): stream.deliver(packet)
        stream.finish({'route':'SUPPORTED'})
        frames=list(stream.iter_sse())
        self.assertNotIn(b'\nevent: injected',frames[0])
        self.assertIn(b'\\nevent: injected',frames[0])


if __name__ == '__main__': unittest.main()
