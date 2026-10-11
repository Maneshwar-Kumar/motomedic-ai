"""Exact candidate drafts and real tokenizer budgets; no provider calls."""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
import json
import time
from constrained_generator import ValidationFailure
from evidence_registry import content_hash
from rider_ui.safeguards import diagnostic_projection

VERSION = 'arm-a-exact-candidate-controls-v1'

class ExactCandidates:
    def __init__(self, capacity=128, ttl=900, clock=time.monotonic):
        if not 1 <= capacity <= 256 or not 1 <= ttl <= 900:
            raise ValueError('Invalid cache bounds')
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self.entries, self.mutex = OrderedDict(), RLock()

    @staticmethod
    def key(registry, session, step_id, allowed, runtime_lock, policy_hash):
        return content_hash({'version':VERSION, 'source':registry.checksum,
            'index':registry.index_id, 'registry':registry.lock,
            'variant':session.bike_variant, 'edition':session.edition,
            'session_source_lock':session.version_lock,
            'generation_lock':session.generation_lock, 'runtime':runtime_lock,
            'role_policy':policy_hash, 'step':step_id,
            'typed_state':diagnostic_projection(session), 'allowed_envelope':allowed})

    def get(self, key):
        with self.mutex:
            now = self.clock()
            for expired in [k for k,v in self.entries.items() if v[0] <= now]:
                del self.entries[expired]
            row = self.entries.get(key)
            if not row or row[1] != 'EXACT_SCOPE_VALIDATED':
                return None
            self.entries.move_to_end(key)
            return deepcopy(row[2])

    def put_validated(self, key, draft):
        # Only after both fresh exact envelope checks; cached output is a draft.
        with self.mutex:
            self.entries[key] = (self.clock()+self.ttl, 'EXACT_SCOPE_VALIDATED', deepcopy(draft))
            self.entries.move_to_end(key)
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)

class TokenBudget:
    """BGE is A's only serving model; use its pinned, loaded tokenizer.

    Context/presentation counts are an explicitly named deterministic policy
    budget, not a generative provider countTokens claim. Never truncate.
    """
    def __init__(self, model, embedding_config, policy, policy_hash):
        self.tokenizer = getattr(model, 'tokenizer', None)
        model_limit = getattr(model, 'max_seq_length', None)
        tokenizer_limit = getattr(self.tokenizer, 'model_max_length', None)
        if (not callable(getattr(self.tokenizer, 'encode', None)) or
                type(model_limit) is not int or model_limit < 1 or
                type(tokenizer_limit) is not int or tokenizer_limit < 1):
            raise RuntimeError('Verified serving tokenizer is unavailable')
        self.input_limit = min(8192, model_limit, tokenizer_limit)
        self.model_name = embedding_config['model']
        self.model_revision = embedding_config['revision']
        self.policy, self.policy_hash = policy, policy_hash

    def count(self, text):
        try:
            ids = self.tokenizer.encode(text, add_special_tokens=True, truncation=False)
            if not isinstance(ids, list) or any(type(i) is not int for i in ids):
                raise ValueError()
            return len(ids)
        except Exception:
            raise ValidationFailure('TOKEN_COUNT_UNAVAILABLE') from None

    def query(self, text):
        count = self.count(text)
        if count > self.input_limit:
            raise ValidationFailure('EMBEDDING_INPUT_TOKEN_BOUND')
        return count

    def context(self, allowed, session):
        payload = {'role_policy':self.policy, 'allowed_envelope':allowed,
                   'diagnostic_state':diagnostic_projection(session)}
        wire = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        if len(wire.encode('utf-8')) > 24000:
            raise ValidationFailure('CONTEXT_BOUND_NO_TRUNCATION')
        count = self.count(wire)
        if count > 8192:
            raise ValidationFailure('CONTEXT_TOKEN_BOUND_NO_TRUNCATION')
        return {'budget_tokenizer':self.model_name,
                'budget_tokenizer_revision':self.model_revision,
                'context_tokens':count, 'context_bytes':len(wire.encode('utf-8')),
                'provider_input_tokens':None, 'provider_request':False,
                'all_active_outcomes_preserved':True}

    def output(self, text):
        count = self.count(text)
        if count > 1800:
            raise ValidationFailure('OUTPUT_TOKEN_BOUND_NO_TRUNCATION')
        return count


CANDIDATES = ExactCandidates()

def cache_requested():
    from flask import has_request_context, request
    return has_request_context() and request.environ.get('arm_a_cache_enabled') is True


from online_retrieve import Retriever, RetrievalSystemError

class GuardedRetriever(Retriever):
    """Reuse exact dense/sparse scores only; ranking/assembly always rerun."""
    def install_controls(self, budget):
        self.token_budget = budget
        self.score_cache = ExactCandidates(capacity=128, ttl=900)
        self.score_binding = content_hash({
            'index_manifest':self.manifest, 'runtime_controls':VERSION,
            'input_limit':budget.input_limit,
            'tokenizer_model':budget.model_name,
            'tokenizer_revision':budget.model_revision})
        self.last_cache_trace = None

    def _first_stage(self, query):
        if not hasattr(self, 'token_budget'):
            raise RetrievalSystemError('Verified token budget unavailable')
        count = self.token_budget.query(query)  # Count before every hit or encode.
        key = content_hash({'binding':self.score_binding, 'exact_query':query})
        current_binding = content_hash({
            'index_manifest':self.manifest, 'runtime_controls':VERSION,
            'input_limit':self.token_budget.input_limit,
            'tokenizer_model':self.token_budget.model_name,
            'tokenizer_revision':self.token_budget.model_revision})
        if current_binding != self.score_binding:
            raise RetrievalSystemError('Immutable cache binding changed')
        hit = self.score_cache.get(key) if cache_requested() else None
        if hit is None:
            dense, sparse, dt, st = super()._first_stage(query)
            # Parent validates finite dense vectors; sparse scores derive from
            # the integrity-checked immutable BM25. Copy before retaining.
            import numpy as np
            if not np.isfinite(dense).all() or not np.isfinite(sparse).all():
                raise RetrievalSystemError('Invalid first-stage scores')
            if cache_requested():
                self.score_cache.put_validated(key, (dense, sparse))
            status = 'MISS' if cache_requested() else 'BYPASS'
        else:
            dense, sparse = hit
            dt, st, status = 0.0, 0.0, 'HIT_EXACT_SCORES'
        self.last_cache_trace = {'cache':status, 'input_tokens':count,
            'input_token_limit':self.token_budget.input_limit,
            'source_assembly_and_gates_rerun':True,
            'provider_calls':0, 'raw_query_retained':False}
        return dense, sparse, dt, st
