"""Synthetic provider-free serving RPC/scheduling regressions; no model loading."""
from copy import deepcopy
from pathlib import Path
import threading
import unittest
import numpy as np
from online_retrieve import RetrievalSystemError
from cloud.grounded_generation.serving_retrieval import (
    Retriever, QdrantTransport, QUERY_CONTEXT, retrieval_query)
from test_conditional_retrieval import fixture, Encoder, Reranker


class Authority:
    lock = 'exact-synthetic-source-lock'
    base = type('Base', (), {'source': {}})()
    def __init__(self, gap=False):
        self.gap = gap
    def scheduling_context(self, bundle):
        anchors = {e for hit in bundle['hits'] for e in hit['evidence_ids']}
        required = anchors | ({'warning'} if 'action' in anchors else set())
        required.update(bundle.get('retained_approved_evidence_ids', ()))
        return {'payload': {}, 'required_evidence_ids': sorted(required),
            'reviewed_anchor_ids': sorted(anchors),
            'source_gaps': [{'type': 'SOURCE_CONTEXT_REVIEW_REQUIRED', 'rider_resolvable': False}] if self.gap else [],
            'dependency_review_status': 'APPROVED', 'coverage_established': True,
            'source_review_required': self.gap}


def serving(gap=False):
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

    def test_open_question_recovers_once_and_reranks_without_step_manifest(self):
        r = serving()
        b = r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(b['retrieval_policy']['recovery_attempts'], 1)
        self.assertEqual(b['retrieval_policy']['rerank_attempts'], 1)
        self.assertIn('warning', b['attached_evidence_ids'])
        self.assertEqual(b['retrieval_action'], 'CONTINUE_GATES')
        self.assertEqual(r.reranker.calls, 1)

    def test_source_review_gap_skips_rerank_and_keeps_partial_anchors(self):
        r = serving(gap=True)
        b = r.search('check', limit=1, applicability_status='CONFIRMED')
        self.assertEqual(b['retrieval_action'], 'CONTINUE_WITH_SOURCE_GAPS')
        self.assertEqual(r.reranker.calls, 0)
        self.assertFalse(b['source_gaps'][0]['rider_resolvable'])

    def test_rerank_query_bound_preserves_complete_full_query(self):
        r = serving()
        query = 'check ' * 150
        b = r.search(query, limit=1, applicability_status='CONFIRMED')
        self.assertEqual(b['query'], query)
        self.assertEqual(b['retrieval_policy']['rerank_skip_reason'], 'QUERY_EXCEEDS_RERANK_LIMIT')
        self.assertEqual(b['retrieval_action'], 'CONTINUE_GATES')
        self.assertIn('warning', b['attached_evidence_ids'])

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


if __name__ == '__main__': unittest.main()
