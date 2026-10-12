"""Explicit evidence-only Haiku verifier with bounded prompt-prefix caching.

This provider is a selected verification role, never an availability fallback.
It caches policy/source prefixes, never rider questions, history or answer buffers.
"""
from copy import deepcopy
import hashlib
import json
import os
import threading
import time

from generation_providers import ProviderFailure, ProviderResult
from evidence_registry import content_hash
from cloud.grounded_generation.claude_provider import HTTP
from cloud.grounded_generation.provider import OUTPUT_TOKENS, unique
from cloud.grounded_generation.role_contracts import (HAIKU_DRAFT,HAIKU_VERIFIER,
    HAIKU_CONTEXT_TOKENS,OUTPUT_JSON_BYTES,haiku_maximum_nanodollars,haiku_actual_cost)

MODEL = 'claude-haiku-5-5'
INPUT_TOKENS=HAIKU_CONTEXT_TOKENS-OUTPUT_TOKENS
DRAFT_CONTRACT=HAIKU_DRAFT
CONTRACT=HAIKU_VERIFIER
# Retained isolated two-call fixture admission; production uses an atomic
# counted role plan, not this historical default forecast.
MAX_CALL_USD=haiku_maximum_nanodollars(8192)/1000000000
MAX_TURN_CALLS = 2  # Initial verifier plus the sole correction's verifier.
STABLE_FIELDS = frozenset((
    'runtime_contract', 'full_evidence_payload_sha256', 'source_projection',
    'manual_checksum', 'index_id', 'source_authority_lock', 'evidence',
    'required_source_display', 'source_gaps', 'verified_oem_support',
))


def wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(',', ':'))


def native_role_schema(template,evidence,role):
    """Bind native citation choices to exact literal admitted source objects.

    This enum restricts citation spelling/membership, never semantic support.
    A wrong admitted object must still fail exact-object verification.
    """
    source=evidence.get('evidence')
    if type(source)is not dict or any(type(key)is not str or not key for key in source):
        raise ProviderFailure('CLAUDE_LITERAL_EVIDENCE_MAP_REQUIRED')
    ids=sorted(source)
    schema=deepcopy(template)
    if role=='private_draft':
        target=schema['properties']['claims']['items']['properties']['evidence_ids']
    elif role=='semantic_verifier':
        target=schema['properties']['per_claim_support']['items']['properties']['supported_evidence_ids']
    else:raise ProviderFailure('CLAUDE_VERIFIER_ROLE_MISMATCH')
    if ids:target['items']={'type':'string','enum':ids}
    else:target['description']='No admitted source objects: this array must be empty. The server rejects every citation.'
    return schema,ids


class CachedVerifier:
    cache_capability = 'explicit'
    contract = CONTRACT

    def __init__(self, reserve, *, reserve_cost=None, transport=None, key=None,pre_reserved=False):
        self.contract=deepcopy(type(self).contract)
        self.reserve = reserve
        self.reserve_cost = reserve_cost
        self.transport = transport or HTTP()
        self.key = key or os.environ.get('ANTHROPIC_API_KEY')
        self.lock = threading.Lock()
        self.turn = threading.local()
        self.last_trace = None
        self.central_admission=pre_reserved

    def expect_initial_context(self,expected):
        self.turn.expected_context=expected

    def begin_turn(self):
        if not callable(self.reserve_cost):
            raise ProviderFailure('CLAUDE_VERIFIER_SPEND_GUARD_UNCONFIGURED')
        if getattr(self.turn, 'remaining', None) is not None:
            raise ProviderFailure('CLAUDE_VERIFIER_TURN_ALREADY_RESERVED')
        self.reserve_cost(MAX_TURN_CALLS * MAX_CALL_USD, MODEL)
        self.turn.remaining = MAX_TURN_CALLS
        return {'version': CONTRACT['version'], 'reserved_attempts': MAX_TURN_CALLS,
                'reserved_maximum_cost_usd': MAX_TURN_CALLS * MAX_CALL_USD}

    def end_turn(self):
        self.turn.remaining = None

    def _count(self, body):
        if not self.key:
            raise ProviderFailure('CLAUDE_UNCONFIGURED')
        counted = {k: deepcopy(v) for k, v in body.items()
                   if k not in ('max_tokens', 'stream')}
        result = self.transport('POST', 'messages/count_tokens', counted, self.key)
        value = result.get('input_tokens')
        if type(value) is not int or value < 1:
            raise ProviderFailure('EXACT_TOKEN_COUNT_UNAVAILABLE')
        return value

    def count(self, body):
        messages = [{'role': 'user', 'content': [
            {'type': 'text', 'text': p['text']}
            for c in body.get('contents', []) for p in c.get('parts', [])]}]
        return self._count({'model': MODEL, 'messages': messages,
                            'thinking': {'type': 'disabled'}})

    @classmethod
    def _new_trace(cls):
        return {'model': MODEL, 'provider': 'anthropic', 'role': 'semantic_verifier',
                 'generation_calls': 0, 'retry_count': 0, 'cached_tokens': 0,
                 'provider_cache': CONTRACT['prompt_cache'], 'cache_hit_observed': False,
                 'raw_content_logged': False, 'token_counter': 'ANTHROPIC_COUNT_TOKENS',
                 'token_counter_is_estimate': True}

    def context(self, policy, evidence, dynamic, schema, *, _trace=None):
        trace = self._new_trace() if _trace is None else _trace
        if _trace is None:
            self.last_trace = trace
        try:
            from cloud.grounded_generation.verified_qa import VERIFY_POLICY, VERIFY_SCHEMA,DRAFT_POLICY,DRAFT_SCHEMA
            expected=(DRAFT_POLICY,DRAFT_SCHEMA) if self.contract['role']=='private_draft' else (VERIFY_POLICY,VERIFY_SCHEMA)
            if policy != expected[0] or schema != expected[1]:
                raise ProviderFailure('CLAUDE_VERIFIER_ROLE_MISMATCH')
            if type(evidence) is not dict or set(evidence) != STABLE_FIELDS:
                raise ProviderFailure('CLAUDE_VERIFIER_STABLE_PREFIX_FIELDS')
            if type(evidence['source_projection'])is not str or (type(dynamic)is dict and dynamic.get('encoding')=='lossless-shared-json-v2'):
                raise ProviderFailure('CLAUDE_PLAIN_COMPLETE_CONTEXT_REQUIRED')
            native_schema,citable_ids=native_role_schema(schema,evidence,self.contract['role'])
            cache = {'type': 'ephemeral', 'ttl': '5m'}
            body = {
                'model': MODEL, 'max_tokens': OUTPUT_TOKENS,
                'system': [{'type': 'text', 'text': policy, 'cache_control': deepcopy(cache)}],
                'messages': [{'role': 'user', 'content': [
                    {'type': 'text', 'text': wire({'assembled_evidence': evidence}),
                     'cache_control': deepcopy(cache)},
                    {'type': 'text', 'text': wire({'request': dynamic})},
                ]}],
                'thinking': {'type': 'disabled'},
                'output_config': {'effort': 'medium',
                                  'format': {'type': 'json_schema', 'schema': native_schema}},
            }
            trace.update(role_schema_template_sha256=content_hash(schema),
                         native_role_schema_sha256=content_hash(native_schema),
                         citable_evidence_ids_sha256=content_hash(citable_ids),
                         citable_evidence_id_count=len(citable_ids))
            trace['request_bytes'] = len(wire(body).encode())
            count = self._count(body)
            trace['input_tokens_counted'] = count
            if count > INPUT_TOKENS:
                raise ProviderFailure('COMPLETE_CONTEXT_TOKEN_BOUND_NO_TRUNCATION')
            return body, count
        except ProviderFailure as exc:
            trace['failure_code'] = str(exc)
            raise

    def complete(self, policy, evidence, dynamic, schema):
        trace = self._new_trace()
        self.last_trace = trace
        if not self.key:
            raise ProviderFailure('CLAUDE_UNCONFIGURED')
        if not self.central_admission and not callable(self.reserve_cost):
            raise ProviderFailure('CLAUDE_VERIFIER_SPEND_GUARD_UNCONFIGURED')
        if not self.lock.acquire(blocking=False):
            raise ProviderFailure('PROVIDER_CONCURRENCY_LIMIT')
        try:
            body, count = self.context(policy, evidence, dynamic, schema, _trace=trace)
            expected=getattr(self.turn,'expected_context',None)
            if expected is not None:
                if content_hash(body)!=expected:raise ProviderFailure('ROUTER_INITIAL_REQUEST_BINDING_CHANGED')
                self.turn.expected_context=None
            trace.update(input_tokens_counted=count,
                         cached_prefix_sha256=hashlib.sha256(wire({
                             'contract': self.contract, 'system': body['system'],
                             'evidence': body['messages'][0]['content'][0],
                             'schema': body['output_config']['format']['schema']}).encode()).hexdigest())
            remaining = getattr(self.turn, 'remaining', None)
            maximum_cost=haiku_maximum_nanodollars(count)/1000000000
            if self.central_admission:
                pass  # Atomic turn admission owns both token and USD1 ledgers.
            elif remaining is None:
                self.reserve_cost(maximum_cost, MODEL)
            elif remaining <= 0:
                raise ProviderFailure('CLAUDE_VERIFIER_UNRESERVED_ATTEMPT')
            else:
                if count>8192:raise ProviderFailure('CLAUDE_LEGACY_TURN_COST_FORECAST_EXCEEDED')
                self.turn.remaining = remaining - 1
            # Anthropic writes the cache in the same generation request. Keep
            # admission's existing generation-only slots and full token bound.
            permit=self.reserve(count + OUTPUT_TOKENS, 'generation')
            input_ceiling=INPUT_TOKENS
            if self.central_admission:
                stages=('draft','correction') if self.contract['role']=='private_draft' else ('verify','reverify')
                if (type(permit)is not dict or permit.get('model')!=MODEL or
                    permit.get('stage') not in stages or permit.get('attempt')!=1 or
                    type(permit.get('input_tokens'))is not int or permit['input_tokens']<count or
                    permit.get('output_tokens')!=OUTPUT_TOKENS or
                    type(permit.get('maximum_nanodollars'))is not int or
                    permit['maximum_nanodollars']!=haiku_maximum_nanodollars(permit['input_tokens'])):
                    raise ProviderFailure('MODEL_ROLE_RESERVATION_BINDING_REQUIRED')
                input_ceiling=permit['input_tokens'];maximum_cost=permit['maximum_nanodollars']/1000000000
            trace['reserved_maximum_cost_usd'] = maximum_cost
            trace['reserved_input_token_ceiling']=input_ceiling
            started = time.monotonic()
            trace['generation_calls'] = 1
            result = self.transport('POST', 'messages', body, self.key)
            trace['provider_seconds'] = time.monotonic() - started
            if result.get('model') != MODEL:
                raise ProviderFailure('PROVIDER_MODEL_MISMATCH')
            if result.get('stop_reason') != 'end_turn':
                raise ProviderFailure('PROVIDER_INCOMPLETE_OR_REFUSED')
            blocks = result.get('content')
            if (type(blocks) is not list or len(blocks) != 1 or
                    type(blocks[0]) is not dict or blocks[0].get('type') != 'text' or
                    type(blocks[0].get('text')) is not str or
                    set(blocks[0]) - {'type', 'text', 'citations'} or
                    blocks[0].get('citations') not in (None, [])):
                raise ProviderFailure('PROVIDER_INVALID_PARTS')
            usage = result.get('usage', {})
            fields = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens',
                      'cache_read_input_tokens')
            if type(usage) is not dict or any(type(usage.get(k)) is not int or usage[k] < 0 for k in fields):
                raise ProviderFailure('PROVIDER_USAGE_MISSING')
            new, output, created, read = (usage[k] for k in fields)
            total = new + created + read
            if total < 1 or total > min(INPUT_TOKENS,input_ceiling) or output > OUTPUT_TOKENS:
                raise ProviderFailure('PROVIDER_TOKEN_BOUND')
            if 'cache_creation' in usage:
                details = usage['cache_creation']
                if (type(details) is not dict or
                        set(details) != {'ephemeral_5m_input_tokens', 'ephemeral_1h_input_tokens'} or
                        any(type(v) is not int or v < 0 for v in details.values()) or
                        details['ephemeral_1h_input_tokens'] != 0 or
                        details['ephemeral_5m_input_tokens'] != created):
                    raise ProviderFailure('PROVIDER_CACHE_USAGE_BINDING')
            cost = haiku_actual_cost(new,created,read,output)
            if cost > maximum_cost:
                raise ProviderFailure('PROVIDER_COST_BOUND')
            if len(blocks[0]['text'].encode())>OUTPUT_JSON_BYTES:raise ProviderFailure('PRIVATE_GENERATED_JSON_BYTE_BOUND')
            parsed = json.loads(blocks[0]['text'], object_pairs_hook=unique,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if type(parsed) is not dict:
                raise ProviderFailure('PROVIDER_INVALID_JSON')
            trace.update(input_tokens=total, uncached_input_tokens=new,
                         cache_creation_input_tokens=created, cached_tokens=read,
                         cache_read_input_tokens=read, cache_hit_observed=read > 0,
                         output_tokens=output, estimated_cost_usd=cost)
            return ProviderResult(parsed, total, output, cost, deepcopy(trace))
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure('PROVIDER_INVALID_JSON') from None
        finally:
            self.lock.release()


class CachedDraft(CachedVerifier):
    """Same native cache/transport, explicitly selected private drafting role."""
    contract=HAIKU_DRAFT

    @classmethod
    def _new_trace(cls):
        trace=super()._new_trace();trace['role']='private_draft';return trace
