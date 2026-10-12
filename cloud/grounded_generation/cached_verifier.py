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
from cloud.grounded_generation.claude_provider import HTTP
from cloud.grounded_generation.provider import INPUT_TOKENS, OUTPUT_TOKENS, REQUEST_BYTES, unique

MODEL = 'claude-haiku-5-5'
DRAFT_CONTRACT = {'provider': 'google-generative-language',
                  'model': 'gemma-4-26b-a4b-it', 'role': 'private_draft',
                  'input_tokens': INPUT_TOKENS, 'output_tokens': OUTPUT_TOKENS,
                  'request_bytes': REQUEST_BYTES, 'maximum_attempts_per_call': 2,
                  'retry_rejections': [429, 503], 'prompt_cache': 'UNSUPPORTED',
                  'answer_cache': 'DISABLED'}
CONTRACT = {
    'provider': 'anthropic', 'model': MODEL, 'role': 'semantic_verifier',
    'version': 'haiku-evidence-prefix-verifier-v1',
    'input_tokens': INPUT_TOKENS, 'output_tokens': OUTPUT_TOKENS,
    'request_bytes': REQUEST_BYTES, 'native_json_schema': True,
    'thinking': 'disabled', 'effort': 'medium', 'automatic_retries': 0,
    'prompt_cache': 'EXPLICIT_POLICY_AND_EVIDENCE_PREFIX',
    'cache_ttl': '5m', 'minimum_cache_tokens': 512,
    'input_usd_per_million': 0.10, 'output_usd_per_million': 0.50,
    'cache_write_usd_per_million': 0.125, 'cache_read_usd_per_million': 0.01,
    'pricing_checked_date': '2026-10-12',
    'pricing_source': 'https://platform.claude.com/docs/en/build-with-claude/prompt-caching',
    'answer_cache': 'DISABLED', 'fallback_role': False,
}
MAX_CALL_USD = (INPUT_TOKENS * 0.125 + OUTPUT_TOKENS * 0.50) / 1_000_000
MAX_TURN_CALLS = 2  # Initial verifier plus the sole correction's verifier.
STABLE_FIELDS = frozenset((
    'runtime_contract', 'full_evidence_payload_sha256', 'source_projection',
    'manual_checksum', 'index_id', 'source_authority_lock', 'evidence',
    'required_source_display', 'source_gaps', 'verified_oem_support',
))


def wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(',', ':'))


class CachedVerifier:
    cache_capability = 'explicit'
    contract = CONTRACT

    def __init__(self, reserve, *, reserve_cost, transport=None, key=None):
        self.reserve = reserve
        self.reserve_cost = reserve_cost
        self.transport = transport or HTTP()
        self.key = key or os.environ.get('ANTHROPIC_API_KEY')
        self.lock = threading.Lock()
        self.turn = threading.local()
        self.last_trace = None

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

    @staticmethod
    def _new_trace():
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
            from cloud.grounded_generation.verified_qa import VERIFY_POLICY, VERIFY_SCHEMA
            if policy != VERIFY_POLICY or schema != VERIFY_SCHEMA:
                raise ProviderFailure('CLAUDE_VERIFIER_ROLE_MISMATCH')
            if type(evidence) is not dict or set(evidence) != STABLE_FIELDS:
                raise ProviderFailure('CLAUDE_VERIFIER_STABLE_PREFIX_FIELDS')
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
                                  'format': {'type': 'json_schema', 'schema': deepcopy(schema)}},
            }
            trace['request_bytes'] = len(wire(body).encode())
            if trace['request_bytes'] > REQUEST_BYTES:
                raise ProviderFailure('COMPLETE_CONTEXT_BYTE_BOUND_NO_TRUNCATION')
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
        if not callable(self.reserve_cost):
            raise ProviderFailure('CLAUDE_VERIFIER_SPEND_GUARD_UNCONFIGURED')
        if not self.lock.acquire(blocking=False):
            raise ProviderFailure('PROVIDER_CONCURRENCY_LIMIT')
        try:
            body, count = self.context(policy, evidence, dynamic, schema, _trace=trace)
            trace.update(input_tokens_counted=count,
                         cached_prefix_sha256=hashlib.sha256(wire({
                             'contract': self.contract, 'system': body['system'],
                             'evidence': body['messages'][0]['content'][0],
                             'schema': schema}).encode()).hexdigest())
            remaining = getattr(self.turn, 'remaining', None)
            if remaining is None:
                self.reserve_cost(MAX_CALL_USD, MODEL)
            elif remaining <= 0:
                raise ProviderFailure('CLAUDE_VERIFIER_UNRESERVED_ATTEMPT')
            else:
                self.turn.remaining = remaining - 1
            # Anthropic writes the cache in the same generation request. Keep
            # admission's existing generation-only slots and full token bound.
            self.reserve(count + OUTPUT_TOKENS, 'generation')
            trace['reserved_maximum_cost_usd'] = MAX_CALL_USD
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
            if total < 1 or total > INPUT_TOKENS or output > OUTPUT_TOKENS:
                raise ProviderFailure('PROVIDER_TOKEN_BOUND')
            if 'cache_creation' in usage:
                details = usage['cache_creation']
                if (type(details) is not dict or
                        set(details) != {'ephemeral_5m_input_tokens', 'ephemeral_1h_input_tokens'} or
                        any(type(v) is not int or v < 0 for v in details.values()) or
                        details['ephemeral_1h_input_tokens'] != 0 or
                        details['ephemeral_5m_input_tokens'] != created):
                    raise ProviderFailure('PROVIDER_CACHE_USAGE_BINDING')
            cost = (new * .10 + created * .125 + read * .01 + output * .50) / 1_000_000
            if cost > MAX_CALL_USD:
                raise ProviderFailure('PROVIDER_COST_BOUND')
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
