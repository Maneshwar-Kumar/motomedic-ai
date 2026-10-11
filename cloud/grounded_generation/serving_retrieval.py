"""Authenticated hosted dense/BM25 serving orchestration over the unchanged index.

The private Qdrant service applies its immutable collection/source filter and
checks the index identity. No document parsing, embedding or local vector
similarity occurs in this request path. Transport/model injection supports
provider-free synthetic tests; it does not claim hosted acceptance.
"""
from collections import defaultdict
from contextvars import ContextVar
from copy import deepcopy
import json
import math
from pathlib import Path
import time
import urllib.request
from online_ingest import stable_id, digest
from online_retrieve import Retriever as FrozenRetriever, RetrievalSystemError
from retrieval_policy import RetrievalPolicy, ranking_signals

VERSION = 'authenticated-open-hybrid-rank-disagreement-v3'
RERANK_GATE_VERSION = 'ordered-distinct-parent-rank-disagreement-v1'
QUERY_CONTEXT = ContextVar('motomedic_retrieval_history', default=())


def conditional_rank_signals(dense_sections, sparse_sections, fused_sections, policy):
    """Only observed differences between backend parent ranks trigger reranking.

    Several sibling search chunks represent one section. Missing backend hits
    and an unmatched trailing rank supply no contradictory ordering. RRF margin
    is diagnostic: adjacent reciprocal ranks are intrinsically close even when
    both backends agree, so margin alone cannot start cross-encoder inference.
    """
    signals = ranking_signals(dense_sections, sparse_sections, fused_sections, policy)
    dense = list(dict.fromkeys(dense_sections))[:policy.disagreement_top_k]
    sparse = list(dict.fromkeys(sparse_sections))[:policy.disagreement_top_k]
    comparable = bool(dense and sparse)
    differences = [rank for rank, (left, right) in enumerate(zip(dense, sparse), 1)
                   if left != right] if comparable else []
    signals.update(rerank_gate_version=RERANK_GATE_VERSION,
        dense_top_distinct_parent_ids=dense, sparse_top_distinct_parent_ids=sparse,
        rank_comparison_available=comparable,
        compared_rank_positions=min(len(dense), len(sparse)) if comparable else 0,
        disagreeing_rank_positions=differences,
        dense_sparse_section_overlap=(len(set(dense) & set(sparse)) /
            min(len(dense), len(sparse))) if comparable else None,
        uncertainty_reasons=['DENSE_SPARSE_DISTINCT_PARENT_RANK_DISAGREEMENT'] if differences else [],
        ranking_uncertain=bool(differences), rrf_margin_is_diagnostic_only=True)
    return signals


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RetrievalSystemError('QDRANT_REDIRECT_REJECTED')


def retrieval_query(question, history=()):
    """Preserve prior rider topic for short/deictic follow-ups without new facts."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError('Query is empty')
    words = question.split()
    references = {'it', 'its', 'that', 'this', 'those', 'them', 'there', 'same'}
    if len(words) > 16 and not references.intersection(w.lower().strip('.,?!') for w in words):
        return question
    prior = []
    for row in history:
        if not isinstance(row, dict):
            continue
        if row.get('role') in ('user', 'rider') or 'question' in row:
            text = row.get('question', row.get('text', row.get('content', '')))
            if isinstance(text, str) and text.strip() and text.strip() != question.strip():
                prior.append(text)
    if not prior:
        return question
    # Full selected prior rider turn is retained; overlong query is an explicit
    # token-bound failure, never silent cropping or an invented observation.
    selected = [prior[-1]]
    # Follow the explicit reference chain to its original rider question.
    for earlier in reversed(prior[:-1]):
        if not references.intersection(w.lower().strip('.,?!') for w in selected[0].split()):
            break
        selected.insert(0, earlier)
    return 'Previous rider questions (topic context):\n' + '\n'.join(selected) + '\nCurrent rider question:\n' + question


class QdrantTransport:
    def __init__(self, url, index_id, source_sha256, *, send=None, token=None):
        if not isinstance(url, str) or not url.startswith('https://') or url.endswith('/'):
            raise RetrievalSystemError('QDRANT_AUTHENTICATED_HTTPS_REQUIRED')
        self.url, self.index_id, self.source_sha256 = url, index_id, source_sha256
        self.send, self.token = send or self._send, token or self._token

    def _token(self):
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token
        return id_token.fetch_id_token(Request(), self.url)

    def _send(self, path, payload, headers):
        request = urllib.request.Request(self.url + path,
            data=json.dumps(payload, allow_nan=False).encode('utf-8'), headers=headers,
            method='POST')
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=30) as response:
            if response.status != 200:
                raise RetrievalSystemError('QDRANT_RPC_STATUS')
            return json.loads(response.read(262145))

    def query(self, vector, limit=20):
        if (type(vector) is not list or not vector or any(type(v) not in (float, int)
                or not math.isfinite(v) for v in vector) or type(limit) is not int or not 1 <= limit <= 20):
            raise RetrievalSystemError('QDRANT_INVALID_QUERY')
        token = self.token()
        if not isinstance(token, str) or not token or '\r' in token or '\n' in token:
            raise RetrievalSystemError('QDRANT_IDENTITY_UNAVAILABLE')
        response = self.send('/query', {'vector': vector, 'limit': limit,
            'source_sha256': self.source_sha256, 'index_id': self.index_id},
            {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
        if (type(response) is not dict or response.get('index_id') != self.index_id
                or response.get('candidate_evidence_only') is not True):
            raise RetrievalSystemError('QDRANT_RESPONSE_IDENTITY')
        result = response.get('result')
        points = result.get('points') if type(result) is dict else None
        if type(points) is not list or len(points) > limit:
            raise RetrievalSystemError('QDRANT_MALFORMED_RESPONSE')
        return points


class Retriever(FrozenRetriever):
    def __init__(self, index_dir, rerank=False, embedding_model=None, cross_encoder=None,
                 qdrant_transport=None, source_authority=None):
        from cloud.grounded_generation.serving_baseline import validate_index
        self.baseline_receipt = validate_index(index_dir)
        if embedding_model is None and not (Path(index_dir) / 'embedding_model').is_dir():
            raise RetrievalSystemError('PINNED_QUERY_MODEL_UNAVAILABLE_NO_RUNTIME_DOWNLOAD')
        super().__init__(index_dir, rerank, embedding_model, cross_encoder)
        self.source_authority = source_authority
        self._chunk_positions = {chunk['id']: at for at, chunk in enumerate(self.chunks)}
        if qdrant_transport is None:
            deployment = json.loads((Path(__file__).resolve().parents[2] / 'cloud/deployment_status.json').read_text())
            if deployment.get('authenticated') is not True or deployment.get('selected_index_id') != self.manifest['index_id']:
                raise RetrievalSystemError('QDRANT_DEPLOYMENT_BINDING')
            qdrant_transport = QdrantTransport(deployment['url'], self.manifest['index_id'], self.manifest['source_sha256'])
        self.qdrant_transport = qdrant_transport

    def _load_reranker(self):
        if self.reranker is None and not (self.root / 'reranker_model').is_dir():
            raise RetrievalSystemError('PINNED_RERANKER_UNAVAILABLE_NO_RUNTIME_DOWNLOAD')
        return super()._load_reranker()

    def _dense_scores(self, query):
        import numpy as np
        started = time.perf_counter()
        vector = self.model.encode(query, normalize_embeddings=True)
        dimensions = self.manifest['embedding']['dimensions']
        if np.shape(vector) != (dimensions,) or not np.isfinite(vector).all():
            raise RetrievalSystemError('INVALID_QUERY_EMBEDDING')
        points = self.qdrant_transport.query(vector.tolist(), 20)
        dense = np.full(len(self.chunks), -np.inf)
        seen = set()
        for point in points:
            if type(point) is not dict:
                raise RetrievalSystemError('QDRANT_MALFORMED_POINT')
            payload, score = point.get('payload'), point.get('score')
            if type(payload) is not dict or type(score) not in (float, int) or not math.isfinite(score):
                raise RetrievalSystemError('QDRANT_MALFORMED_POINT')
            cid = payload.get('chunk_id')
            if cid not in self._chunk_positions or cid in seen or payload.get('source_sha256') != self.manifest['source_sha256']:
                raise RetrievalSystemError('QDRANT_UNKNOWN_OR_WRONG_SOURCE_POINT')
            indexed = self.chunks[self._chunk_positions[cid]]
            # Remote payload is immutable source/index membership, not content
            # that can replace or extend the loaded search snapshot.
            if any(payload.get(key) != value for key, value in indexed.get('scope', {}).items()):
                raise RetrievalSystemError('QDRANT_CHANGED_CHUNK_MEMBERSHIP')
            seen.add(cid)
            dense[self._chunk_positions[cid]] = float(score)
        self.last_dense_trace = {'backend': 'AUTHENTICATED_QDRANT_RPC',
            'index_id': self.manifest['index_id'], 'source_sha256': self.manifest['source_sha256'],
            'collection': 'owner_manual', 'remote_candidate_limit': 20, 'returned_points': len(points),
            'query_embedding_only': True, 'document_embedding_calls': 0}
        return dense, time.perf_counter() - started

    def _rank(self, dense, sparse, candidate_limit, policy, allowed_indices=None):
        fused, rankings = defaultdict(float), []
        for at, scores in enumerate((dense, sparse)):
            ranking = sorted((i for i in range(len(scores)) if
                (allowed_indices is None or i in allowed_indices) and math.isfinite(float(scores[i]))
                and (at == 0 or scores[i] > 0)), key=lambda i: (-float(scores[i]), self.chunks[i]['id']))
            rankings.append(ranking)
            for rank, idx in enumerate(ranking[:max(candidate_limit * 2, 50)], 1):
                fused[idx] += 1 / (60 + rank)
        candidates = sorted(fused, key=lambda i: (-fused[i], self.chunks[i]['id']))[:candidate_limit]
        sections = {}
        for i in candidates:
            section = self.chunks[i]['parent_section_id']
            sections[section] = max(sections.get(section, 0), fused[i])
        signals = conditional_rank_signals(*([self.chunks[i]['parent_section_id'] for i in rank] for rank in rankings),
            sorted(sections.items(), key=lambda x: (-x[1], x[0])), policy)
        return candidates, fused, signals

    def _assemble_open(self, query, candidates, limit, dense, sparse, fused, rerank_scores=None,
                       retained_ids=()):
        hits = [{**deepcopy(self.chunks[i]), 'dense_score': float(dense[i]) if math.isfinite(float(dense[i])) else None,
                 'bm25_score': float(sparse[i]), 'rrf_score': fused[i],
                 'cross_encoder_score': (rerank_scores or {}).get(i)} for i in candidates[:limit]]
        bundle = {'index_id': self.manifest['index_id'], 'manual_checksum': self.manifest['source_sha256'],
            'source_sha256': self.manifest['source_sha256'], 'hits': hits, 'query': query,
            'conflicts': [], 'applicability_status': 'CONFIRMED', 'parents': [], 'linked_chunks': [], 'links': [],
            'retained_approved_evidence_ids': sorted(retained_ids), 'may_generate_procedural_advice': False}
        context = self.source_authority.scheduling_context(bundle)
        required = set(context['required_evidence_ids'])
        attached = {e for hit in hits for e in hit['evidence_ids']} | set(retained_ids)
        bundle.update({k: deepcopy(v) for k, v in context.items() if k != 'payload'})
        bundle.update(required_evidence_ids=sorted(required), attached_evidence_ids=sorted(attached),
                      missing_evidence_ids=sorted(required-attached),
                      evidence_ids=sorted(attached & self.evidence.keys()))
        return bundle

    def search(self, query, limit=5, candidate_limit=None, scope=None, rerank=None, *, policy=None,
               dependency_manifest=None, step_id=None, applicability_status='UNCONFIRMED',
               gate_status=None, gate_evidence_ids=()):
        # Legacy authored-action consumers retain their scoped scheduler, while
        # ordinary Q&A uses reviewed object context without a step identifier.
        if dependency_manifest is not None or self.source_authority is None:
            return super().search(query, limit, candidate_limit, scope, rerank, policy=policy,
                dependency_manifest=dependency_manifest, step_id=step_id, applicability_status=applicability_status,
                gate_status=gate_status, gate_evidence_ids=gate_evidence_ids)
        started = time.perf_counter()
        policy = policy or RetrievalPolicy()
        candidate_limit = candidate_limit or policy.candidate_limit
        if not 1 <= limit <= candidate_limit <= policy.expanded_candidate_limit:
            raise ValueError('Invalid retrieval bounds')
        limit = min(limit, 5)  # Current open-Q&A configured assembly maximum.
        if applicability_status != 'CONFIRMED':
            raise RetrievalSystemError('SELECTED_SOURCE_SCOPE_NOT_CONFIRMED')
        if rerank is not None and type(rerank) is not bool:
            raise ValueError('Invalid rerank override')
        allowed = set()
        reviewed = getattr(self, 'reviewed_scope', self.source_authority.base.source)
        for key, expected in (scope or {}).items():
            actual = self.manifest['source_sha256'] if key == 'source_sha256' else reviewed.get(key)
            if actual != expected:
                raise RetrievalSystemError('SELECTED_SOURCE_SCOPE_MISMATCH')
        for i, chunk in enumerate(self.chunks):
            if chunk['source_sha256'] == self.manifest['source_sha256'] and all(
                (chunk['source_sha256'] if key == 'source_sha256' else
                 chunk.get('scope', {}).get(key) or reviewed.get(key)) == expected
                for key, expected in (scope or {}).items()):
                allowed.add(i)
        query = retrieval_query(query, QUERY_CONTEXT.get())
        telemetry = {'version': VERSION, 'policy': policy.to_dict(), 'recovery_attempts': 0,
            'rerank_attempts': 0, 'rerank_pair_count': 0, 'stages_seconds': {},
            'first_stage_execution': 'CONCURRENT_AUTHENTICATED_QDRANT_AND_BM25',
            'decisions': [], 'rerank_skip_reason': None, 'assembled_hit_limit': limit,
            'rerank_gate_version': RERANK_GATE_VERSION,
            'rerank_mode': ('CONDITIONAL_RANK_DISAGREEMENT' if rerank is None else
                            'ALWAYS_DIAGNOSTIC' if rerank else 'OFF_DIAGNOSTIC')}
        try:
            if not allowed:
                raise RetrievalSystemError('SELECTED_SCOPE_HAS_NO_INDEXED_CHUNKS')
            dense, sparse, dt, st = self._first_stage(query)
            telemetry['stages_seconds'].update(dense_query_embedding_and_qdrant_rpc=dt, bm25_scoring=st)
            candidates, fused, signals = self._rank(dense, sparse, candidate_limit, policy, allowed)
            assembly_started = time.perf_counter()
            bundle = self._assemble_open(query, candidates, limit, dense, sparse, fused)
            telemetry['stages_seconds']['initial_assembly'] = time.perf_counter()-assembly_started
            retained = set()
            if bundle['missing_evidence_ids']:
                recovery_started = time.perf_counter()
                telemetry['recovery_attempts'] = 1
                missing = list(bundle['missing_evidence_ids'])
                # Exact reviewed dependencies are recovered from the already
                # hash-validated object snapshot, not another semantic guess.
                retained.update(bundle['required_evidence_ids'])
                candidates, fused, signals = self._rank(dense, sparse, policy.expanded_candidate_limit, policy, allowed)
                bundle = self._assemble_open(query, candidates, limit, dense, sparse, fused, retained_ids=retained)
                telemetry['recovery'] = {'requested_evidence_ids': missing,
                    'fetched_evidence_ids': sorted(set(missing)&retained),
                    'remaining_missing_evidence_ids': bundle['missing_evidence_ids'],
                    'candidate_limit': policy.expanded_candidate_limit, 'dense_candidate_limit': 20}
                telemetry['decisions'].append('RECOVER_REVIEWED_DEPENDENCIES')
                telemetry['stages_seconds']['dependency_recovery'] = time.perf_counter()-recovery_started
            if bundle['source_gaps']:
                action = 'CONTINUE_WITH_SOURCE_GAPS' if bundle['coverage_established'] else 'SOURCE_REVIEW_REQUIRED'
                telemetry['rerank_skip_reason'] = 'SOURCE_REVIEW_REQUIRED'
            elif not bundle['coverage_established']:
                action = 'SOURCE_REVIEW_REQUIRED'
                telemetry['rerank_skip_reason'] = action
            elif (rerank is True or (rerank is None and signals['ranking_uncertain'])):
                telemetry['rerank_attempts'] = 1
                pool = candidates[:candidate_limit]
                rerank_started = time.perf_counter()
                scores, pairs, skip = self._rerank(query, pool, policy)
                telemetry['stages_seconds']['reranking'] = time.perf_counter()-rerank_started
                telemetry.update(rerank_pair_count=pairs, rerank_skip_reason=skip)
                if scores is not None:
                    retained.update(bundle['required_evidence_ids'])
                    pool.sort(key=lambda i: (-scores[i], self.chunks[i]['id']))
                    bundle = self._assemble_open(query, pool, limit, dense, sparse, fused, scores, retained)
                # Optional rerank bounds do not turn complete evidence into a
                # missing-source claim; full query and dependencies are retained.
                action = 'CONTINUE_GATES'
            else:
                action = 'CONTINUE_GATES'
                telemetry['rerank_skip_reason'] = ('RERANK_DISABLED' if rerank is False else
                    'DENSE_SPARSE_DISTINCT_PARENT_RANKS_AGREE' if signals['rank_comparison_available'] else
                    'NO_COMPARABLE_DENSE_SPARSE_RANKS')
            telemetry.update(final_action=action, initial_ranking_signals=signals,
                             dense_rpc=deepcopy(getattr(self, 'last_dense_trace', None)))
            telemetry['decisions'].append(action)
            bundle.update(retrieval_action=action, retrieval_policy=telemetry,
                assembly_version=stable_id('assembly', self.manifest['source_sha256'],
                    [VERSION, self.source_authority.lock, digest(Path(__file__))]),
                elapsed_seconds=time.perf_counter()-started,
                reranked=bool(telemetry['rerank_attempts'] and not telemetry['rerank_skip_reason']))
            bundle['query_id'] = stable_id('query', self.manifest['source_sha256'], [query, bundle['assembly_version']])
            return bundle
        except Exception as exc:
            error = RetrievalSystemError('SYSTEM_ERROR: retrieval or source assembly failed')
            error.telemetry = {**telemetry, 'final_action': 'SYSTEM_ERROR', 'error_class': type(exc).__name__}
            raise error from exc


class GuardedRetriever(Retriever):
    def install_controls(self, budget):
        self.token_budget = budget
        self.last_cache_trace = None
        self._control_binding = stable_id('retrieval-controls', self.manifest['source_sha256'],
            [self.manifest, budget.model_name, budget.model_revision, budget.input_limit, VERSION])

    def _first_stage(self, query):
        if not hasattr(self, 'token_budget'):
            raise RetrievalSystemError('VERIFIED_QUERY_TOKEN_BUDGET_UNAVAILABLE')
        count = self.token_budget.query(query)
        binding = stable_id('retrieval-controls', self.manifest['source_sha256'],
            [self.manifest, self.token_budget.model_name, self.token_budget.model_revision, self.token_budget.input_limit, VERSION])
        if binding != self._control_binding:
            raise RetrievalSystemError('IMMUTABLE_RETRIEVAL_CONTROLS_CHANGED')
        result = super()._first_stage(query)
        self.last_cache_trace = {'cache': 'BYPASS', 'input_tokens': count,
            'first_stage': 'CONCURRENT_AUTHENTICATED_QDRANT_AND_BM25',
            'provider_calls': 0, 'raw_query_retained': False}
        return result
