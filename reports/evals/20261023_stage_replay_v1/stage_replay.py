"""Provider-free, local stage-by-stage replay of MotoMedic v10.14 retrieval and source admission.

LOCAL DIAGNOSTIC ONLY. No provider (Haiku) call, no hosted call, no spend.
The frozen v10.14 backend code is imported unchanged; a subclass only records
what each stage returned. The hosted Qdrant RPC (down: billing disabled) is
replaced by exact cosine over the index's own stored embeddings.npy, which are
the vectors the hosted Qdrant collection was exported from.

Usage: python stage_replay.py <backend_dir> <index_dir> <bge_m3_dir> <cases.json> <out.json> [v5]
The optional "v5" argument swaps in the candidate scoped-structure authority
(reports/grounded_generation/structural_review_v2/candidate/serving_source_authority_v5.py),
imported from the working tree; retrieval code stays the frozen v10.14 backend.
"""
import json
import math
import os
import sys
import time
from pathlib import Path

BACKEND, INDEX, BGE, CASES, OUT = (Path(p).resolve() for p in sys.argv[1:6])
AUTHORITY = sys.argv[6] if len(sys.argv) > 6 else 'v4'
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer

from approved_registry import ApprovedEvidenceRegistry
from cloud.arm_a.runtime_controls import TokenBudget
from cloud.grounded_generation import serving_retrieval as sr
from cloud.grounded_generation.fuse_refusal import detect_refusal
from cloud.grounded_generation.serving_source_authority import SourceAuthority
from cloud.grounded_generation.verified_qa import DRAFT_POLICY, DRAFT_POLICY_SHA256

STAGE_K = 20


class LocalExactQdrant:
    """Same contract as QdrantTransport.query: top-`limit` cosine points with payload."""

    def __init__(self, index_dir, chunks):
        self.vectors = np.load(index_dir / 'embeddings.npy')
        if self.vectors.shape != (len(chunks), 1024):
            raise SystemExit('embeddings.npy does not align with chunks.jsonl')
        self.chunks = chunks

    def query(self, vector, limit=20):
        scores = self.vectors @ np.asarray(vector, dtype=self.vectors.dtype)
        order = sorted(range(len(scores)), key=lambda i: -float(scores[i]))[:limit]
        return [{'score': float(scores[i]), 'payload': {'chunk_id': self.chunks[i]['id'],
                 'source_sha256': self.chunks[i]['source_sha256'], **self.chunks[i].get('scope', {})}}
                for i in order]


class RecordingRetriever(sr.GuardedRetriever):
    """Records stage outputs; every decision is made by the frozen parent code."""

    def _first_stage(self, query):
        dense, sparse, dt, st = super()._first_stage(query)
        self.rec['dense'], self.rec['sparse'] = dense.copy(), sparse.copy()
        return dense, sparse, dt, st

    def _rank(self, dense, sparse, candidate_limit, policy, allowed_indices=None):
        candidates, fused, signals = super()._rank(dense, sparse, candidate_limit, policy, allowed_indices)
        self.rec['rrf_candidates'], self.rec['fused'] = list(candidates), dict(fused)
        return candidates, fused, signals

    def _rerank(self, query, candidates, policy):
        scores, pairs, skip = super()._rerank(query, candidates, policy)
        self.rec['rerank_scores'] = dict(scores) if scores is not None else None
        self.rec['rerank_order'] = (sorted(candidates, key=lambda i: (-scores[i], self.chunks[i]['id']))
                                    if scores is not None else None)
        return scores, pairs, skip

    def _assemble_open(self, query, candidates, limit, *args, **kwargs):
        bundle = super()._assemble_open(query, candidates, limit, *args, **kwargs)
        self.rec.setdefault('assemblies', []).append({'chunk_idx': list(candidates[:limit]),
            'admitted': list(bundle.get('required_evidence_ids', [])),
            'coverage_established': bundle.get('coverage_established')})
        return bundle


def main():
    t0 = time.time()
    registry = ApprovedEvidenceRegistry.load(BACKEND, INDEX)
    chunks = [json.loads(l) for l in (INDEX / 'chunks.jsonl').open(encoding='utf-8')]
    embedding = SentenceTransformer(str(BGE), device='cpu', local_files_only=True)
    reranker = CrossEncoder(str(INDEX / 'reranker_model'), device='cpu', local_files_only=True)
    retriever = RecordingRetriever(INDEX, rerank=True, embedding_model=embedding, cross_encoder=reranker,
                                   qdrant_transport=LocalExactQdrant(INDEX, chunks))
    retriever.install_controls(TokenBudget(retriever.model, retriever.manifest['embedding'],
                                           DRAFT_POLICY, DRAFT_POLICY_SHA256))
    if AUTHORITY == 'v5':
        # Candidate loader lives in the working tree; it subclasses the frozen v4
        # already imported from BACKEND, and its packages resolve from the project root.
        import importlib.util
        spec = importlib.util.spec_from_file_location('serving_source_authority_v5',
            INDEX.parents[1] / 'reports/grounded_generation/structural_review_v2/candidate/serving_source_authority_v5.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.PROPOSAL_PATH = str(INDEX.parents[1] / mod.PROPOSAL_PATH)
        mod.REVIEW_PATH = str(INDEX.parents[1] / mod.REVIEW_PATH)
        authority = mod.SourceAuthority(registry, retriever.root)
    else:
        authority = SourceAuthority(registry, retriever.root)
    retriever.source_authority = authority
    scope = {'source_sha256': registry.checksum, 'manual_id': registry.source['manual_id'],
             'variant': registry.source['variant'], 'edition': registry.source['edition'],
             'language': registry.source['language'], 'motorcycle': registry.source['motorcycle']}
    reviewed_ids = set(authority.complete_context_ids)
    pages_of = {}
    for line in (INDEX / 'evidence.jsonl').open(encoding='utf-8'):
        e = json.loads(line)
        pages_of[e['id']] = sorted({p['page_no'] for p in e['provenance']})

    def chunk_row(i, extra=None):
        c = chunks[i]
        return {'chunk_id': c['id'], 'pages': [x['pdf_page'] for x in c['citations']],
                'section': ' > '.join(c['section_path'])[:120], 'evidence_ids': c['evidence_ids'],
                'reviewed_evidence_ids': [e for e in c['evidence_ids'] if e in reviewed_ids],
                **(extra or {})}

    cases = json.loads(CASES.read_text(encoding='utf-8'))['cases']
    results = []
    for case in cases:
        retriever.rec = {}
        q = case['question']
        error = None
        try:
            bundle = retriever.search(q, limit=6, scope=scope, applicability_status='CONFIRMED')
            refusal = detect_refusal(registry, q)
            if refusal:  # same safety attachment as open_questions.Questions.answer
                existing = {h['id'] for h in bundle['hits']}
                need = {e for claim in refusal['claims'] for e in claim['evidence_ids']}
                for ch in authority.chunks.values():
                    if need & set(ch['evidence_ids']) and ch['id'] not in existing:
                        bundle['hits'].append({'id': ch['id'], 'evidence_ids': list(ch['evidence_ids']),
                                               'parent_section_id': ch['parent_section_id']})
            admitted = authority.assemble(bundle)
        except Exception as exc:  # retained as a SYSTEM_ERROR stage outcome
            error = f'{type(exc).__name__}: {exc}'
            bundle, admitted = {'hits': [], 'retrieval_policy': getattr(exc, 'telemetry', {})}, None
        rec = retriever.rec
        dense, sparse = rec.get('dense'), rec.get('sparse')
        idx_of = retriever._chunk_positions
        dense_rank = sorted((i for i in range(len(chunks)) if math.isfinite(float(dense[i]))),
                            key=lambda i: -float(dense[i]))[:STAGE_K] if dense is not None else []
        sparse_rank = sorted((i for i in range(len(chunks)) if sparse[i] > 0),
                             key=lambda i: (-float(sparse[i]), chunks[i]['id']))[:STAGE_K] if sparse is not None else []
        rp = bundle.get('retrieval_policy', {})
        final_idx = [idx_of[h['id']] for h in bundle.get('hits', [])]
        results.append({
            'case_id': case['case_id'], 'group': case['group'], 'question': q, 'error': error,
            'gold_evidence_ids': case['gold_evidence_ids'], 'gold_pages': case['gold_pages'],
            'gold_evidence_reviewed': {e: e in reviewed_ids for e in case['gold_evidence_ids']},
            'gold_evidence_pages': {e: pages_of.get(e) for e in case['gold_evidence_ids']},
            'dense_top20': [chunk_row(i, {'dense': round(float(dense[i]), 4)}) for i in dense_rank],
            'bm25_top20': [chunk_row(i, {'bm25': round(float(sparse[i]), 3)}) for i in sparse_rank],
            'rrf_top20': [chunk_row(i, {'rrf': round(rec['fused'][i], 5)}) for i in rec.get('rrf_candidates', [])],
            'initial_primary_top5': [chunk_row(i) for i in rec.get('rrf_candidates', [])[:5]],
            'initial_admitted_evidence_ids': (rec.get('assemblies') or [{}])[0].get('admitted'),
            'rerank_fired': bool(rp.get('rerank_attempts')),
            'rerank_skip_reason': rp.get('rerank_skip_reason'),
            'rank_signals': {k: rp.get('initial_ranking_signals', {}).get(k) for k in
                             ('dense_top_distinct_parent_ids', 'sparse_top_distinct_parent_ids',
                              'disagreeing_rank_positions', 'ranking_uncertain')},
            'rerank_order_top10': ([chunk_row(i, {'ce': round(float(rec['rerank_scores'][i]), 3)})
                                    for i in rec['rerank_order'][:10]] if rec.get('rerank_order') else None),
            'preserved_anchor_chunk_ids': rp.get('preserved_initial_anchor_chunk_ids', []),
            'final_hits': [chunk_row(i) for i in final_idx],
            'final_action': rp.get('final_action'),
            'admitted_evidence_ids': admitted['required_evidence_ids'] if admitted else None,
            'admitted_anchor_ids': admitted.get('anchor_evidence_ids') if admitted else None,
            'admitted_pages': sorted({p for e in (admitted['required_evidence_ids'] if admitted else [])
                                      for p in pages_of.get(e, [])}),
            'gaps': [{'chunk_id': g['chunk_id'], 'evidence_ids': g['evidence_ids'], 'type': g['type']}
                     for g in (admitted['gaps'] if admitted else [])],
            'refusal_attached': bool(error is None and detect_refusal(registry, q)),
        })
        print(case['case_id'], 'rerank' if results[-1]['rerank_fired'] else 'no-rerank',
              'admitted', len(results[-1]['admitted_evidence_ids'] or []), error or '', flush=True)
    OUT.write_text(json.dumps({'schema': 'motomedic-local-stage-replay-v1',
        'label': 'LOCAL_PROVIDER_FREE_DIAGNOSTIC_NOT_HOSTED_ACCEPTANCE',
        'backend_code': str(BACKEND), 'index_id': retriever.manifest['index_id'],
        'retrieval_version': sr.VERSION, 'rerank_gate_version': sr.RERANK_GATE_VERSION,
        'source_authority': AUTHORITY, 'source_authority_lock': authority.lock, 'reviewed_complete_context_ids': len(reviewed_ids),
        'dense_backend': 'LOCAL_EXACT_COSINE_OVER_INDEX_EMBEDDINGS (hosted Qdrant unavailable)',
        'provider_calls': 0, 'elapsed_seconds': round(time.time() - t0, 1), 'results': results},
        indent=1, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
