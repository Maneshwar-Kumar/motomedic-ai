"""Top-5 hybrid retrieval over the section index.

Dense (BGE-M3 query vector, top 20 from hosted read-only Qdrant, or exact local cosine for
tests and evaluation) and BM25 score the query. Reciprocal rank fusion (k=60) merges them and
only the top 5 chunks are kept. When the ordered top-3 distinct sections of the dense and BM25
rankings differ, the pinned cross-encoder orders those 5; it never brings in another chunk.

The cross-encoder also scores the 5 when the rankings agree, but only to check relevance. If its
best score is below RELEVANCE_FLOOR, the turn is treated as nothing retrieved: the fixed message
and support route, with no model call. The floor is set so that no answerable development question
fell below it (lowest -7.95), and it can only refuse, never authorize, an answer.
No request parses or embeds the manual.
"""
import json
import math
from pathlib import Path
import re
import urllib.request

VERSION = 'section-top5-hybrid-v2'
TOP_K = 5
RRF_K = 60
DENSE_LIMIT = 20
FUSE_DEPTH = 50
DISAGREEMENT_TOP = 3
MAX_QUERY_TOKENS = 128
RELEVANCE_FLOOR = -9.0
TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.'/-][a-z0-9]+)*")


class RetrievalError(RuntimeError):
    pass


def tokens(text):
    return TOKEN_RE.findall(text.lower())


def _topic_boundary(question):
    """Conversational topic markers apply to arbitrary subjects, never source IDs."""
    return bool(re.match(r'^\s*(?:(?:a\s+)?(?:different|new|another|separate|unrelated)\s+'
        r'(?:question|topic|issue)\b|(?:back|return(?:ing)?|switch(?:ing)?|moving)\s+'
        r'(?:back\s+)?to\s+\S|on\s+another\s+note\b)', question, re.IGNORECASE))


def _needs_topic_context(question):
    if _topic_boundary(question):
        return False
    words = re.findall(r"[\w'-]+", question.lower())
    if any(word in {'it', 'its', 'them', 'their', 'that', 'same'} for word in words):
        return True
    placeholders = {'one', 'ones', 'part', 'parts', 'component', 'components',
        'thing', 'things', 'item', 'items', 'issue', 'problem', 'step', 'procedure',
        'condition', 'setting', 'value', 'of', 'is', 'was', 'are', 'were'}
    for at, word in enumerate(words):
        if word in {'this', 'these', 'those'} and (at + 1 == len(words) or words[at + 1] in placeholders):
            return True
    return bool(re.fullmatch(r'\s*(?:(?:and|also|then)\s+)?(?:'
        r'what\s+(?:should|can|do)\s+i\s+(?:do|check|avoid|try)|what\s+(?:next|else)|'
        r'(?:how|why|when)|how\s+(?:long|much|often)|anything\s+else|'
        r'(?:and|also)\s+(?:the\s+)?(?:value|grade|interval|condition|precautions|next\s+step))'
        r'\s*[?!.]*\s*', question, re.IGNORECASE))


def retrieval_query(question, history=()):
    """Keep the prior rider topic for short or deictic follow-ups, without adding facts."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError('Query is empty')
    if not _needs_topic_context(question):
        return question
    prior = [row.get('question', row.get('text', row.get('content', ''))) for row in history
             if isinstance(row, dict) and (row.get('role') in ('user', 'rider') or 'question' in row)]
    prior = [text for text in prior if isinstance(text, str) and text.strip() and text.strip() != question.strip()]
    if not prior:
        return question
    selected = [prior[-1]]
    for earlier in reversed(prior[:-1]):
        if not _needs_topic_context(selected[0]):
            break
        selected.insert(0, earlier)
    return 'Previous rider questions (topic context):\n' + '\n'.join(selected) + '\nCurrent rider question:\n' + question


def _distinct(sections, n):
    out = []
    for section in sections:
        if section not in out:
            out.append(section)
    return out[:n]


class ExactDense:
    """Exact cosine over the index's own stored vectors (tests and local evaluation)."""
    def __init__(self, vectors):
        self.vectors = vectors

    def top(self, vector, limit):
        scores = self.vectors @ vector
        order = sorted(range(len(scores)), key=lambda i: -float(scores[i]))[:limit]
        return [(i, float(scores[i])) for i in order]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RetrievalError('QDRANT_REDIRECT_REJECTED')


class QdrantDense:
    """Hosted read-only Qdrant over the same immutable vectors, bound to index and source."""
    def __init__(self, url, index_id, source_sha256, chunk_ids, *, send=None, token=None):
        if not isinstance(url, str) or not url.startswith('https://') or url.endswith('/'):
            raise RetrievalError('QDRANT_AUTHENTICATED_HTTPS_REQUIRED')
        self.url, self.index_id, self.source_sha256 = url, index_id, source_sha256
        self.positions = {cid: at for at, cid in enumerate(chunk_ids)}
        self.send, self.token = send or self._send, token or self._token

    def _token(self):
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token
        return id_token.fetch_id_token(Request(), self.url)

    def _send(self, path, payload, headers):
        request = urllib.request.Request(self.url + path, data=json.dumps(payload, allow_nan=False).encode('utf-8'),
                                         headers=headers, method='POST')
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=30) as response:
            if response.status != 200:
                raise RetrievalError('QDRANT_RPC_STATUS')
            return json.loads(response.read(262145))

    def top(self, vector, limit):
        vector = [float(v) for v in vector]
        if not vector or not all(math.isfinite(v) for v in vector) or not 1 <= limit <= DENSE_LIMIT:
            raise RetrievalError('QDRANT_INVALID_QUERY')
        token = self.token()
        if not isinstance(token, str) or not token or '\r' in token or '\n' in token:
            raise RetrievalError('QDRANT_IDENTITY_UNAVAILABLE')
        response = self.send('/query', {'vector': vector, 'limit': limit, 'source_sha256': self.source_sha256,
                                        'index_id': self.index_id},
                             {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
        if (type(response) is not dict or response.get('index_id') != self.index_id
                or response.get('candidate_evidence_only') is not True):
            raise RetrievalError('QDRANT_RESPONSE_IDENTITY')
        points = (response.get('result') or {}).get('points') if type(response.get('result')) is dict else None
        if type(points) is not list or len(points) > limit:
            raise RetrievalError('QDRANT_MALFORMED_RESPONSE')
        out, seen = [], set()
        for point in points:
            payload, score = (point.get('payload'), point.get('score')) if type(point) is dict else (None, None)
            cid = payload.get('chunk_id') if type(payload) is dict else None
            if (cid not in self.positions or cid in seen or payload.get('source_sha256') != self.source_sha256
                    or type(score) not in (int, float) or not math.isfinite(score)):
                raise RetrievalError('QDRANT_UNKNOWN_OR_WRONG_SOURCE_POINT')
            seen.add(cid)
            out.append((self.positions[cid], float(score)))
        return sorted(out, key=lambda row: -row[1])


class SectionRetriever:
    def __init__(self, index_dir, embedding_model, cross_encoder, dense=None):
        import numpy as np
        root = Path(index_dir)
        self.manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        with (root / 'chunks.jsonl').open(encoding='utf-8') as handle:
            self.chunks = [json.loads(line) for line in handle]
        self.bm25 = json.loads((root / 'bm25.json').read_text(encoding='utf-8'))
        if self.bm25['chunk_ids'] != [c['id'] for c in self.chunks]:
            raise RetrievalError('SECTION_INDEX_FILES_MISMATCH')
        self.model, self.cross_encoder = embedding_model, cross_encoder
        self.dense = dense or ExactDense(np.load(root / 'embeddings.npy'))

    def dense_ranking(self, query):
        import numpy as np
        vector = self.model.encode(query, normalize_embeddings=True)
        if np.shape(vector) != (self.manifest['embedding']['dimensions'],) or not np.isfinite(vector).all():
            raise RetrievalError('INVALID_QUERY_EMBEDDING')
        return self.dense.top(vector, DENSE_LIMIT)

    def sparse_ranking(self, query):
        bm, scores = self.bm25, [0.0] * len(self.chunks)
        for term in set(tokens(query)):
            for idx, tf in bm['postings'].get(term, []):
                denom = tf + bm['k1'] * (1 - bm['b'] + bm['b'] * bm['lengths'][idx] / max(bm['avgdl'], 1))
                scores[idx] += bm['idf'][term] * tf * (bm['k1'] + 1) / denom
        order = sorted((i for i, s in enumerate(scores) if s > 0), key=lambda i: (-scores[i], self.chunks[i]['id']))
        return [(i, scores[i]) for i in order]

    def _rerank(self, query, top):
        tokenizer = getattr(self.cross_encoder, 'tokenizer', None)
        if tokenizer is not None and len(tokenizer.encode(query, add_special_tokens=False)) > MAX_QUERY_TOKENS:
            return {}, 'QUERY_EXCEEDS_RERANK_LIMIT'
        scores = self.cross_encoder.predict([(query, self.chunks[i]['index_text']) for i in top])
        if len(scores) != len(top) or not all(math.isfinite(float(s)) for s in scores):
            raise RetrievalError('INVALID_CROSS_ENCODER_SCORES')
        return {i: float(s) for i, s in zip(top, scores)}, None

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
        # Scores are always taken for the relevance floor; they reorder only on disagreement.
        scores, skip = self._rerank(query, top) if top else ({}, None)
        reranked = bool(scores) and disagree and len(top) > 1
        if reranked:
            top = sorted(top, key=lambda i: (-scores[i], self.chunks[i]['id']))
        best = max(scores.values()) if scores else None
        return {'version': VERSION, 'index_id': self.manifest['index_id'],
                'chunk_ids': [self.chunks[i]['id'] for i in top],
                'dense_top': [self.chunks[i]['id'] for i, _ in dense[:TOP_K]],
                'bm25_top': [self.chunks[i]['id'] for i, _ in sparse[:TOP_K]],
                'sections_disagree': disagree, 'reranked': reranked, 'rerank_skip_reason': skip,
                'max_cross_score': best, 'below_relevance_floor': best is not None and best < RELEVANCE_FLOOR}
