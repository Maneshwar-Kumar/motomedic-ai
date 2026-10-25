"""Top-5 hybrid retrieval over the section index (no review layer).

Dense (BGE-M3 cosine, top 20; hosted serving runs the same vectors in Qdrant) and BM25 score the
query. Reciprocal rank fusion (k=60) merges them and only the top 5 chunks are kept. When the
ordered top-3 distinct sections of the dense and BM25 rankings differ, the pinned cross-encoder
orders those 5; it never brings in another chunk.
"""
import json
import math
from pathlib import Path
import re

VERSION = 'section-top5-hybrid-v1'
TOP_K = 5
RRF_K = 60
DENSE_LIMIT = 20
FUSE_DEPTH = 50
DISAGREEMENT_TOP = 3
TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.'/-][a-z0-9]+)*")


def tokens(text):
    return TOKEN_RE.findall(text.lower())


def _distinct(sections, n):
    out = []
    for section in sections:
        if section not in out:
            out.append(section)
    return out[:n]


class SectionRetriever:
    def __init__(self, index_dir, embedding_model, cross_encoder):
        import numpy as np
        root = Path(index_dir)
        self.manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        with (root / 'chunks.jsonl').open(encoding='utf-8') as handle:
            self.chunks = [json.loads(line) for line in handle]
        self.bm25 = json.loads((root / 'bm25.json').read_text(encoding='utf-8'))
        self.vectors = np.load(root / 'embeddings.npy')
        if self.bm25['chunk_ids'] != [c['id'] for c in self.chunks] or len(self.vectors) != len(self.chunks):
            raise ValueError('Section index files do not belong together')
        self.model, self.cross_encoder = embedding_model, cross_encoder

    def dense_ranking(self, query):
        vector = self.model.encode(query, normalize_embeddings=True)
        scores = self.vectors @ vector
        order = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), self.chunks[i]['id']))[:DENSE_LIMIT]
        return [(i, float(scores[i])) for i in order]

    def sparse_ranking(self, query):
        bm, scores = self.bm25, [0.0] * len(self.chunks)
        for term in set(tokens(query)):
            for idx, tf in bm['postings'].get(term, []):
                denom = tf + bm['k1'] * (1 - bm['b'] + bm['b'] * bm['lengths'][idx] / max(bm['avgdl'], 1))
                scores[idx] += bm['idf'][term] * tf * (bm['k1'] + 1) / denom
        order = sorted((i for i, s in enumerate(scores) if s > 0), key=lambda i: (-scores[i], self.chunks[i]['id']))
        return [(i, scores[i]) for i in order]

    def search(self, query):
        if not isinstance(query, str) or not query.strip():
            raise ValueError('Query is empty')
        dense, sparse = self.dense_ranking(query), self.sparse_ranking(query)
        fused = {}
        for ranking in (dense, sparse):
            for rank, (idx, _score) in enumerate(ranking[:FUSE_DEPTH], 1):
                fused[idx] = fused.get(idx, 0.0) + 1 / (RRF_K + rank)
        top = sorted(fused, key=lambda i: (-fused[i], self.chunks[i]['id']))[:TOP_K]
        dense_sections = _distinct([self.chunks[i]['section_id'] for i, _ in dense], DISAGREEMENT_TOP)
        sparse_sections = _distinct([self.chunks[i]['section_id'] for i, _ in sparse], DISAGREEMENT_TOP)
        depth = min(len(dense_sections), len(sparse_sections))
        disagree = bool(depth) and dense_sections[:depth] != sparse_sections[:depth]
        rerank = {}
        if disagree and len(top) > 1:
            scores = self.cross_encoder.predict([(query, self.chunks[i]['index_text']) for i in top])
            if len(scores) != len(top) or not all(math.isfinite(float(s)) for s in scores):
                raise RuntimeError('Invalid cross-encoder scores')
            rerank = {i: float(s) for i, s in zip(top, scores)}
            top = sorted(top, key=lambda i: (-rerank[i], self.chunks[i]['id']))
        return {'version': VERSION, 'index_id': self.manifest['index_id'], 'query': query,
                'chunk_ids': [self.chunks[i]['id'] for i in top],
                'dense_top': [self.chunks[i]['id'] for i, _ in dense[:TOP_K]],
                'bm25_top': [self.chunks[i]['id'] for i, _ in sparse[:TOP_K]],
                'fused_scores': {self.chunks[i]['id']: round(fused[i], 6) for i in top},
                'rerank_scores': {self.chunks[i]['id']: round(s, 4) for i, s in rerank.items()},
                'sections_disagree': disagree, 'reranked': bool(rerank)}
