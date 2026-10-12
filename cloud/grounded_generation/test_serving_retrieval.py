"""Synthetic provider-free serving RPC/scheduling regressions; no model loading."""
from copy import deepcopy
from pathlib import Path
import threading
import unittest
import numpy as np
from online_retrieve import RetrievalSystemError
from cloud.grounded_generation.serving_retrieval import (
    Retriever, QdrantTransport, QUERY_CONTEXT, retrieval_query, conditional_rank_signals)
from test_conditional_retrieval import fixture, Encoder, Reranker


class Authority:
    lock = 'exact-synthetic-source-lock'
    base = type('Base', (), {'source': {}})()
    def __init__(self, gap=False):
        self.gap = gap
    def scheduling_context(self, bundle):
        anchors = {e for hit in bundle['hits'] for e in hit['evidence_ids']}
        required = anchors | ({'warning'} if 'action' in anchors else set())
        gaps = [{'type': 'SOURCE_CONTEXT_REVIEW_REQUIRED', 'chunk_id': hit['id'],
                 'rider_resolvable': False} for hit in bundle['hits']] if self.gap else []
        for hit in bundle.get('retained_gap_hits', ()):
            gap = {'type': 'SOURCE_CONTEXT_REVIEW_REQUIRED', 'chunk_id': hit['id'],
                   'rider_resolvable': False}
            if gap not in gaps:
                gaps.append(gap)
        return {'payload': {'evidence': {eid: {} for eid in required}}, 'required_evidence_ids': sorted(required),
            'reviewed_anchor_ids': sorted(anchors),
            'source_gaps': gaps,
            'dependency_review_status': 'APPROVED', 'coverage_established': True,
            'source_review_required': self.gap}


def serving(gap=False, disagreement=False):
    old, _ = fixture()
    r = Retriever.__new__(Retriever)
    r.__dict__.update(old.__dict__)
    r.manifest['embedding'] = {'dimensions': 2}
    for chunk in r.chunks:
        chunk.update(source_sha256='sha', scope={})
    r._chunk_positions = {chunk['id']: i for i, chunk in enumerate(r.chunks)}
    r.source_authority = Authority(gap)
    r.qdrant_transport = type('Remote', (), {'query': lambda _, vec, limit: [
        {'score': .99, 'payload': {'chunk_id': c['id'], 'source_sha256': 'sha'}} for c in r.chunks]})()
    if disagreement:
        r._sparse_scores = lambda query: (np.array([1., 2.]), 0.)
    return r


class Tests(unittest.TestCase):
    def test_rpc_uses_iam_token_and_exact_source_index_body(self):
        calls = []
        def send(path, payload, headers):
            calls.append((path, payload, headers))
            return {'index_id': 'idx', 'candidate_evidence_only': True, 'result': {'points': []}}
        rpc = QdrantTransport('https://private.example', 'idx', 'sha', send=send, token=lambda: 'synthetic-identity')
        self.assertEqual(rpc.query([1., 0.]), [])
        path, body, headers = calls[0]
        self.assertEqual(path, '/query')
        self.assertEqual(body['source_sha256'], 'sha')
        self.assertEqual(body['index_id'], 'idx')
        self.assertEqual(headers['Authorization'], 'Bearer synthetic-identity')

    def test_rpc_rejects_identity_malformed_and_missing_token(self):
        for response in ({'index_id': 'wrong'}, {'index_id': 'idx', 'candidate_evidence_only': True,
                          'result': {'points': 'wrong'}}):
            rpc = QdrantTransport('https://private.example', 'idx', 'sha',
                send=lambda *_, result=response: result, token=lambda: 'synthetic')
            with self.assertRaises(RetrievalSystemError): rpc.query([1., 0.])
        rpc = QdrantTransport('https://private.example', 'idx', 'sha', token=lambda: '')
        with self.assertRaises(RetrievalSystemError): rpc.query([1., 0.])

    def test_no_local_dense_similarity_and_unknown_remote_ids_rejected(self):
        r = serving()
        # Poison document vectors: successful RPC proves no local dot product.
        r.vectors = None
        scores, _ = r._dense_scores('check')
        self.assertEqual(list(scores), [.99, .99])
        r.qdrant_transport.query = lambda *_: [{'score': .9, 'payload': {'chunk_id': 'wrong', 'source_sha256': 'sha'}}]
        with self.assertRaisesRegex(RetrievalSystemError, 'UNKNOWN_OR_WRONG_SOURCE'):
            r._dense_scores('check')

    def test_missing_remote_points_do_not_become_arbitrary_dense_ranks(self):
        r = serving()
        r.qdrant_transport.query = lambda *_: []
        dense, _ = r._dense_scores('no match')
        from retrieval_policy import RetrievalPolicy
        candidates, _, _ = r._rank(dense, np.zeros(2), 20, RetrievalPolicy())
        self.assertEqual(candidates, [])

    def test_dense_rpc_and_bm25_are_concurrent(self):
        r = serving()
        barrier = threading.Barrier(2)
        def dense(_): barrier.wait(timeout=2); return np.array([.9, .8]), 0.
        def sparse(_): barrier.wait(timeout=2); return np.array([1., 0.]), 0.
        r._dense_scores, r._sparse_scores = dense, sparse
        dense, sparse, _, _ = r._first_stage('query')
        self.assertEqual(list(dense), [.9, .8]); self.assertEqual(list(sparse), [1., 0.])

    def test_open_question_uses_loaded_dependencies_and_final_reranked_anchors(self):
        r = serving(disagreement=True)
        b = r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(b['retrieval_policy']['recovery_attempts'], 0)
        self.assertEqual(b['retrieval_policy']['rerank_attempts'], 1)
        self.assertEqual(b['required_evidence_ids'], ['other'])
        self.assertNotIn('warning', b['attached_evidence_ids'])
        self.assertEqual(b['retrieval_action'], 'CONTINUE_GATES')
        self.assertEqual(r.reranker.calls, 1)

    def test_selected_anchor_keeps_complete_warning_closure_without_false_recovery(self):
        r = serving()
        b = r.search('check', limit=1, applicability_status='CONFIRMED', rerank=False)
        self.assertEqual(set(b['attached_evidence_ids']), {'action', 'warning'})
        self.assertEqual(b['missing_evidence_ids'], [])
        self.assertEqual(b['retrieval_policy']['recovery_attempts'], 0)
        self.assertNotIn('recovery', b['retrieval_policy'])
        self.assertEqual(r.reranker.calls, 0)

    def test_reranked_new_anchor_loads_its_own_complete_warning_closure(self):
        r = serving(disagreement=True)
        r.evidence['other-warning'] = {'id': 'other-warning'}
        original = r.source_authority.scheduling_context
        def context(bundle):
            value = original(bundle)
            if 'other' in value['reviewed_anchor_ids']:
                value['required_evidence_ids'].append('other-warning')
                value['payload']['evidence']['other-warning'] = {}
            return value
        r.source_authority.scheduling_context = context
        b = r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(set(b['required_evidence_ids']), {'other', 'other-warning'})
        self.assertEqual(set(b['attached_evidence_ids']), {'other', 'other-warning'})
        self.assertEqual(b['missing_evidence_ids'], [])
        self.assertEqual(b['retrieval_policy']['recovery_attempts'], 0)
        self.assertNotIn('action', b['required_evidence_ids'])
        self.assertNotIn('warning', b['required_evidence_ids'])
        self.assertEqual(r.reranker.calls, 1)

    def test_incomplete_reported_payload_is_integrity_failure_not_false_recovery(self):
        r = serving()
        original = r.source_authority.scheduling_context
        def corrupted(bundle):
            context = original(bundle)
            context['payload']['evidence'].pop('warning', None)
            return context
        r.source_authority.scheduling_context = corrupted
        with self.assertRaises(RetrievalSystemError) as raised:
            r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(raised.exception.telemetry['final_action'], 'SYSTEM_ERROR')
        self.assertEqual(raised.exception.telemetry['recovery_attempts'], 0)
        self.assertEqual(r.reranker.calls, 0)

    def test_source_review_gap_preserves_observed_rerank_and_partial_anchors(self):
        r = serving(gap=True, disagreement=True)
        b = r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(b['retrieval_action'], 'CONTINUE_WITH_SOURCE_GAPS')
        self.assertEqual(r.reranker.calls, 1)
        self.assertEqual(b['retrieval_policy']['rerank_attempts'], 1)
        self.assertEqual(b['attached_evidence_ids'], ['other'])
        self.assertFalse(b['source_gaps'][0]['rider_resolvable'])

    def test_source_gaps_do_not_trigger_rerank_when_backend_ranks_agree(self):
        r = serving(gap=True)
        r._sparse_scores = lambda query: (np.array([2., 1.]), 0.)
        b = r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(b['retrieval_action'], 'CONTINUE_WITH_SOURCE_GAPS')
        self.assertEqual(r.reranker.calls, 0)
        self.assertEqual(b['retrieval_policy']['rerank_skip_reason'], 'DENSE_SPARSE_DISTINCT_PARENT_RANKS_AGREE')

    def test_source_gaps_do_not_trigger_rerank_without_comparable_backend_ranks(self):
        r = serving(gap=True)
        b = r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(b['retrieval_action'], 'CONTINUE_WITH_SOURCE_GAPS')
        self.assertEqual(r.reranker.calls, 0)
        self.assertEqual(b['retrieval_policy']['rerank_skip_reason'], 'NO_COMPARABLE_DENSE_SPARSE_RANKS')

    def test_no_reviewed_anchors_skip_observed_disagreement_even_with_diagnostic_override(self):
        r = serving(gap=True, disagreement=True)
        context = r.source_authority.scheduling_context
        def missing(bundle):
            value = context(bundle)
            value.update(coverage_established=False, required_evidence_ids=[], reviewed_anchor_ids=[],
                payload={'evidence': {}})
            return value
        r.source_authority.scheduling_context = missing
        for override in (None, True):
            with self.subTest(override=override):
                b = r.search('check', limit=1, applicability_status='CONFIRMED', rerank=override)
                self.assertEqual(b['retrieval_action'], 'SOURCE_REVIEW_REQUIRED')
                self.assertTrue(b['retrieval_policy']['initial_ranking_signals']['ranking_uncertain'])
                self.assertEqual(r.reranker.calls, 0)

    def test_rerank_dropped_unreviewed_sibling_remains_in_immutable_gap_retention(self):
        from cloud.grounded_generation.serving_source_authority import SourceAuthority
        from evidence_registry import content_hash
        r = serving(disagreement=True)
        r.chunks[0]['evidence_ids'].append('unreviewed-sibling')
        authority = SourceAuthority.__new__(SourceAuthority)
        authority.lock = 'synthetic-gap-authority'; authority.base = r.source_authority.base
        authority.index_id = 'synthetic'; authority.checksum = 'sha'
        authority.chunks = {c['id']: deepcopy(c) for c in r.chunks}
        authority._chunk_hashes = {cid: content_hash(c) for cid, c in authority.chunks.items()}
        authority.complete_context_ids = {'action', 'warning', 'other'}
        authority.check = lambda: None
        authority.evidence_ready = lambda eid: eid in authority.complete_context_ids
        authority._closure = lambda ids: set(ids) | ({'warning'} if 'action' in ids else set())
        authority._payload = lambda ids, anchors, gaps: {
            'required_evidence_ids': sorted(ids), 'anchor_evidence_ids': sorted(anchors),
            'evidence': {eid: {} for eid in ids}, 'gaps': gaps}
        r.source_authority = authority
        b = r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(r.reranker.calls, 1)
        self.assertEqual([hit['id'] for hit in b['hits']], ['c2'])
        self.assertEqual(b['retained_gap_hits'], [{'id':'c1',
            'evidence_ids':['action', 'unreviewed-sibling'], 'parent_section_id':'p1'}])
        self.assertEqual(b['retrieval_action'], 'CONTINUE_WITH_SOURCE_GAPS')
        self.assertTrue(b['source_review_required'])
        self.assertEqual(b['source_gaps'][0]['evidence_ids'], ['unreviewed-sibling'])
        self.assertEqual(b['required_evidence_ids'], ['other'])
        self.assertEqual(b['reviewed_anchor_ids'], ['other'])
        admitted = authority.assemble(b)
        self.assertTrue(admitted['gaps'])
        self.assertNotIn('unreviewed-sibling', admitted['evidence'])
        self.assertNotIn('action', admitted['evidence'])
        self.assertNotIn('warning', admitted['evidence'])

    def test_rerank_query_bound_preserves_complete_full_query(self):
        r = serving(disagreement=True)
        query = 'check ' * 150
        b = r.search(query, limit=1, applicability_status='CONFIRMED')
        self.assertEqual(b['query'], query)
        self.assertEqual(b['retrieval_policy']['rerank_skip_reason'], 'QUERY_EXCEEDS_RERANK_LIMIT')
        self.assertEqual(b['retrieval_action'], 'CONTINUE_GATES')
        self.assertIn('warning', b['attached_evidence_ids'])

    def test_long_history_reference_query_is_never_cropped_for_reranking(self):
        prior = 'battery ' + 'condition ' * 100
        history = [{'question': prior, 'response': {'type': 'SYSTEM_ERROR'}}]
        current = 'What should I avoid with it?'
        expanded = retrieval_query(current, history)
        self.assertIn(prior, expanded)
        self.assertTrue(expanded.endswith(current))
        r = serving(disagreement=True)
        token = QUERY_CONTEXT.set(history)
        try:
            b = r.search(current, limit=1, applicability_status='CONFIRMED')
        finally:
            QUERY_CONTEXT.reset(token)
        self.assertEqual(b['query'], expanded)
        # Force the entire combined query above the existing128-token limit.
        r = serving(disagreement=True)
        history[0]['question'] += ' condition' * 50
        token = QUERY_CONTEXT.set(history)
        try:
            b = r.search(current, limit=1, applicability_status='CONFIRMED')
        finally:
            QUERY_CONTEXT.reset(token)
        self.assertEqual(b['query'], retrieval_query(current, history))
        self.assertEqual(b['retrieval_policy']['rerank_skip_reason'], 'QUERY_EXCEEDS_RERANK_LIMIT')
        self.assertEqual(r.reranker.calls, 0)
        self.assertEqual(set(b['required_evidence_ids']), {'action', 'warning'})

    def test_named_short_question_and_explicit_topic_shift_do_not_inherit_history(self):
        history = [{'question': 'Where is the charging socket?'},
            {'question': 'What should I avoid with it?'}]
        for question in ('What is the battery capacity?',
                'What grade of brake fluid is required?', 'Where is this bike battery?',
                'Different question: how much fuel is left when the warning flashes?',
                'Back to the suspension: how do I adjust it?',
                'Switching to the brake: where is it?',
                'A new topic: where is the horn?'):
            with self.subTest(question=question):
                self.assertEqual(retrieval_query(question, history), question)
        self.assertEqual(len(history), 2)

    def test_deictic_and_elliptic_followup_keeps_only_actual_rider_reference_chain(self):
        history = [{'question': 'Where is the brake-fluid reservoir?'},
            {'question': 'How do I check its level?'},
            {'role': 'assistant', 'text': 'INVENTED UNSAFE EXPECTED ANSWER'}]
        for question in ('What should I avoid with it?', 'What next?', 'and the grade?'):
            with self.subTest(question=question):
                expanded = retrieval_query(question, history)
                self.assertIn('Where is the brake-fluid reservoir?', expanded)
                self.assertIn('How do I check its level?', expanded)
                self.assertTrue(expanded.endswith(question))
                self.assertNotIn('INVENTED', expanded)

    def test_reference_chain_stops_at_explicit_topic_boundary(self):
        history = [{'question': 'Where is the charging socket?'},
            {'question': 'What should I avoid with it?'},
            {'question': 'Different topic: where is the rear brake?'},
            {'question': 'How do I check it?'}]
        expanded = retrieval_query('What precautions apply to it?', history)
        self.assertIn('rear brake', expanded)
        self.assertIn('How do I check it?', expanded)
        self.assertNotIn('charging socket', expanded)

    def test_outage_is_system_error(self):
        r = serving()
        def fail(*_): raise TimeoutError('synthetic')
        r.qdrant_transport.query = fail
        with self.assertRaises(RetrievalSystemError) as raised:
            r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(raised.exception.status, 'SYSTEM_ERROR')

    def test_followup_retrieval_retains_rider_topic_and_does_not_invent_outcome(self):
        history = [{'role': 'user', 'text': 'Where is the rear brake pedal?'},
                   {'role': 'assistant', 'text': 'Unknown unverified content'}]
        query = retrieval_query('For that brake, what fluid grade?', history)
        self.assertIn('rear brake pedal', query)
        self.assertNotIn('Unknown unverified', query)
        r = serving(gap=True)
        token = QUERY_CONTEXT.set(history)
        try: result = r.search('For that brake, what fluid grade?', limit=1, applicability_status='CONFIRMED')
        finally: QUERY_CONTEXT.reset(token)
        self.assertEqual(result['query'], query)
        self.assertEqual(QUERY_CONTEXT.get(), ())

    def test_wrong_source_selection_rejected_before_rpc(self):
        r = serving()
        with self.assertRaisesRegex(RetrievalSystemError, 'SCOPE_MISMATCH'):
            r.search('check', scope={'source_sha256': 'other'}, applicability_status='CONFIRMED')

    def test_actual_saved_history_schema_and_reference_chain(self):
        history = [{'question': 'Where is the USB socket?', 'response': 'Unverified answer'},
                   {'question': 'Can I use that in rain?', 'response': 'Another answer'}]
        query = retrieval_query('And its current rating?', history)
        self.assertIn('Where is the USB socket?', query)
        self.assertIn('Can I use that in rain?', query)
        self.assertNotIn('Unverified answer', query)

    def test_unrelated_substantive_question_keeps_own_retrieval_query(self):
        question = 'Please explain the details of the recommended motorcycle cleaning procedure including preparation conditions and warnings for riding afterwards.'
        self.assertEqual(retrieval_query(question, [{'question': 'Where is the USB socket?'}]), question)

    def test_identical_backend_ranks_skip_despite_close_rrf_margin(self):
        r = serving()
        r._sparse_scores = lambda query: (np.array([2., 1.]), 0.)
        bundle = r.search('check', limit=1, applicability_status='CONFIRMED')
        trace = bundle['retrieval_policy']
        signals = trace['initial_ranking_signals']
        self.assertLess(signals['relative_rrf_section_margin'], .05)
        self.assertFalse(signals['ranking_uncertain'])
        self.assertEqual(trace['rerank_attempts'], 0)
        self.assertEqual(r.reranker.calls, 0)
        self.assertEqual(trace['rerank_skip_reason'], 'DENSE_SPARSE_DISTINCT_PARENT_RANKS_AGREE')
        self.assertIn('warning', bundle['attached_evidence_ids'])

    def test_missing_backend_rank_is_not_disagreement(self):
        from retrieval_policy import RetrievalPolicy
        for dense, sparse in ((['a', 'b'], []), ([], ['a', 'b'])):
            signals = conditional_rank_signals(dense, sparse, [('a', 1.), ('b', .999)], RetrievalPolicy())
            self.assertFalse(signals['rank_comparison_available'])
            self.assertFalse(signals['ranking_uncertain'])
            self.assertIsNone(signals['dense_sparse_section_overlap'])
        r = serving()  # Its synthetic BM25 has no postings.
        bundle = r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(bundle['retrieval_policy']['rerank_attempts'], 0)
        self.assertEqual(bundle['retrieval_policy']['rerank_skip_reason'], 'NO_COMPARABLE_DENSE_SPARSE_RANKS')
        self.assertEqual(r.reranker.calls, 0)
        r = serving()
        r.qdrant_transport.query = lambda *_: []
        r._sparse_scores = lambda query: (np.array([2., 1.]), 0.)
        bundle = r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(bundle['retrieval_policy']['rerank_attempts'], 0)
        self.assertEqual(bundle['retrieval_policy']['rerank_skip_reason'], 'NO_COMPARABLE_DENSE_SPARSE_RANKS')
        self.assertEqual(r.reranker.calls, 0)

    def test_siblings_and_unmatched_trailing_depth_do_not_create_disagreement(self):
        from retrieval_policy import RetrievalPolicy
        signals = conditional_rank_signals(['a', 'a', 'b', 'c'], ['a', 'b'],
            [('a', 1.), ('b', .999)], RetrievalPolicy())
        self.assertEqual(signals['dense_top_distinct_parent_ids'], ['a', 'b', 'c'])
        self.assertEqual(signals['compared_rank_positions'], 2)
        self.assertFalse(signals['ranking_uncertain'])

    def test_order_disagreement_reranks_once_even_when_parent_sets_overlap(self):
        from retrieval_policy import RetrievalPolicy
        signals = conditional_rank_signals(['a', 'b', 'c'], ['b', 'a', 'c'],
            [('a', 1.), ('b', .999)], RetrievalPolicy())
        self.assertEqual(signals['dense_sparse_section_overlap'], 1.)
        self.assertEqual(signals['disagreeing_rank_positions'], [1, 2])
        self.assertTrue(signals['ranking_uncertain'])
        r = serving(disagreement=True)
        bundle = r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(bundle['retrieval_policy']['rerank_attempts'], 1)
        self.assertEqual(r.reranker.calls, 1)
        self.assertEqual(bundle['attached_evidence_ids'], ['other'])

    def test_conditional_reranker_failure_is_system_error_without_retry(self):
        r = serving(disagreement=True)
        r.reranker = Reranker(fail=True)
        with self.assertRaises(RetrievalSystemError) as caught:
            r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(caught.exception.status, 'SYSTEM_ERROR')
        self.assertEqual(caught.exception.telemetry['rerank_attempts'], 1)
        self.assertEqual(r.reranker.calls, 1)

    def test_explicit_rerank_override_is_marked_diagnostic(self):
        r = serving()
        bundle = r.search('check', limit=1, applicability_status='CONFIRMED', rerank=True)
        self.assertEqual(bundle['retrieval_policy']['rerank_mode'], 'ALWAYS_DIAGNOSTIC')
        self.assertEqual(r.reranker.calls, 1)


if __name__ == '__main__': unittest.main()
