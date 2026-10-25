"""One Haiku call fills the answer template; nothing else calls a model.

The system prompt is cached for five minutes; the rider question and manual sections are sent
uncached. Effort is high with thinking disabled: on the 30-question run, default (medium) effort
released 24/30 and high effort 30/30 with no unfaithful cited statement
(evals/20261025_answer_release_v3). There is no verifier, correction round, retry or
fallback model. Before the call, the whole-turn ledger reserves one slot holding the counted
input, a small counter headroom and the full output bound; the slot stays charged even when the
call fails.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import os
import threading
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cloud.common import ProviderFailure
from cloud.grounded_generation.template_answer import SYSTEM_PROMPT, answer_schema

MODEL = 'claude-haiku-5-5'
VERSION = 'haiku-template-answer-v1'
EFFORT = 'high'
OUTPUT_TOKENS = 1800
OUTPUT_JSON_BYTES = 16384
CONTEXT_TOKENS = 1000000
INPUT_TOKENS = CONTEXT_TOKENS - OUTPUT_TOKENS
COUNTER_HEADROOM_TOKENS = 512
LONG_CONTEXT_TOKENS = 100000
CONTRACT = {'provider': 'anthropic', 'model': MODEL, 'version': VERSION, 'role': 'generation',
    'effort': EFFORT, 'thinking': 'disabled', 'output_tokens': OUTPUT_TOKENS,
    'output_json_bytes': OUTPUT_JSON_BYTES, 'context_window_tokens': CONTEXT_TOKENS,
    'counter_headroom_tokens': COUNTER_HEADROOM_TOKENS, 'native_json_schema': True,
    'prompt_cache': 'SYSTEM_PROMPT_5M', 'answer_cache': 'DISABLED', 'automatic_retries': 0,
    'verifier': 'NONE', 'fallback_model': None,
    'system_prompt_sha256': hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
    'pricing_checked_date': '2026-10-12',
    'pricing_source': 'https://platform.claude.com/docs/en/models/haiku-5-5/overview',
    'pricing': {'long_context_above_input_tokens': LONG_CONTEXT_TOKENS,
        'base_usd_per_million': {'input': .10, 'output': .50, 'cache_write': .125, 'cache_read': .01},
        'long_usd_per_million': {'input': .50, 'output': 2.50, 'cache_write': .625, 'cache_read': .05}}}


def maximum_nanodollars(input_tokens, output_tokens=OUTPUT_TOKENS):
    """Worst case: every input token written to the cache, plus the full output bound."""
    if (type(input_tokens) is not int or type(output_tokens) is not int or
            not 0 < input_tokens <= INPUT_TOKENS or not 0 < output_tokens <= OUTPUT_TOKENS):
        raise ValueError('HAIKU_COST_INPUT_INVALID')
    write, out = (Decimal('.625'), Decimal('2.50')) if input_tokens > LONG_CONTEXT_TOKENS else (Decimal('.125'), Decimal('.50'))
    return int(((Decimal(input_tokens) * write + Decimal(output_tokens) * out) * 1000).to_integral_value(rounding=ROUND_CEILING))


def actual_cost(new, created, read, output):
    total = new + created + read
    rates = (.50, .625, .05, 2.50) if total > LONG_CONTEXT_TOKENS else (.10, .125, .01, .50)
    return (new * rates[0] + created * rates[1] + read * rates[2] + output * rates[3]) / 1000000


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def _strict_json(raw):
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ProviderFailure('PROVIDER_REDIRECT_REJECTED')


class HTTP:
    def __call__(self, method, path, body, key):
        raw = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
        request = Request('https://api.anthropic.com/v1/' + path, data=raw, method=method,
            headers={'Content-Type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01'})
        try:
            with build_opener(_NoRedirect).open(request, timeout=60) as response:
                data = response.read(131073)
                if len(data) > 131072:
                    raise ProviderFailure('PROVIDER_OUTPUT_BYTE_BOUND')
                return _strict_json(data)
        except HTTPError as exc:
            raise ProviderFailure('CLAUDE_HTTP_' + str(exc.code)) from None
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure('CLAUDE_TRANSPORT_OR_SCHEMA_FAILURE') from None


def request_body(assembled, user_text):
    return {'model': MODEL, 'max_tokens': OUTPUT_TOKENS,
            'system': [{'type': 'text', 'text': SYSTEM_PROMPT, 'cache_control': {'type': 'ephemeral', 'ttl': '5m'}}],
            'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': user_text}]}],
            'thinking': {'type': 'disabled'},
            'output_config': {'effort': EFFORT, 'format': {'type': 'json_schema', 'schema': answer_schema(assembled)}}}


class HaikuAnswer:
    contract = CONTRACT

    def __init__(self, admission, *, transport=None, key=None):
        self.admission = admission
        self.transport = transport or HTTP()
        self.key = key or os.environ.get('ANTHROPIC_API_KEY')
        self.lock = threading.Lock()
        self.last_trace = None

    def _count(self, body):
        counted = {k: deepcopy(v) for k, v in body.items() if k != 'max_tokens'}
        value = self.transport('POST', 'messages/count_tokens', counted, self.key).get('input_tokens')
        if type(value) is not int or value < 1:
            raise ProviderFailure('EXACT_TOKEN_COUNT_UNAVAILABLE')
        return value

    def __call__(self, assembled, user_text, operation_id):
        """Return (draft dict, trace). Raises ProviderFailure; the caller fails closed."""
        trace = {'model': MODEL, 'version': VERSION, 'role': 'generation', 'effort': EFFORT,
                 'generation_calls': 0, 'retry_count': 0, 'raw_content_logged': False,
                 'token_counter': 'ANTHROPIC_COUNT_TOKENS'}
        self.last_trace = trace
        if not self.key:
            raise ProviderFailure('CLAUDE_UNCONFIGURED')
        if self.admission is None:
            raise ProviderFailure('CLAUDE_SPEND_GUARD_UNCONFIGURED')
        if not self.lock.acquire(blocking=False):
            raise ProviderFailure('PROVIDER_CONCURRENCY_LIMIT')
        began = False
        try:
            body = request_body(assembled, user_text)
            wire = json.dumps(body, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            trace['request_bytes'] = len(wire.encode())
            trace['request_sha256'] = hashlib.sha256(wire.encode()).hexdigest()
            count = self._count(body)
            trace['input_tokens_counted'] = count
            reserved_input = count + COUNTER_HEADROOM_TOKENS
            if reserved_input > INPUT_TOKENS:
                raise ProviderFailure('COMPLETE_CONTEXT_TOKEN_BOUND_NO_TRUNCATION')
            maximum = maximum_nanodollars(reserved_input)
            slot = {'model': MODEL, 'stage': 'generate', 'input_tokens': reserved_input,
                    'output_tokens': OUTPUT_TOKENS, 'attempt': 1, 'maximum_nanodollars': maximum}
            trace['admission'] = self.admission.begin_turn(operation_id, plan={
                'slots': [slot], 'request_sha256': trace['request_sha256']})
            began = True
            permit = self.admission.for_model(MODEL, role='generation')(reserved_input + OUTPUT_TOKENS, 'generation')
            if (type(permit) is not dict or permit.get('model') != MODEL or permit.get('stage') != 'generate' or
                    permit.get('attempt') != 1 or permit.get('input_tokens') != reserved_input or
                    permit.get('output_tokens') != OUTPUT_TOKENS or permit.get('maximum_nanodollars') != maximum):
                raise ProviderFailure('MODEL_RESERVATION_BINDING_REQUIRED')
            trace['reserved_maximum_cost_usd'] = maximum / 1e9
            started = time.monotonic()
            trace['generation_calls'] = 1
            result = self.transport('POST', 'messages', body, self.key)
            trace['provider_seconds'] = time.monotonic() - started
            if type(result) is not dict or result.get('model') != MODEL:
                raise ProviderFailure('PROVIDER_MODEL_MISMATCH')
            if result.get('stop_reason') != 'end_turn':
                raise ProviderFailure('PROVIDER_INCOMPLETE_OR_REFUSED')
            blocks = result.get('content')
            if (type(blocks) is not list or len(blocks) != 1 or type(blocks[0]) is not dict or
                    blocks[0].get('type') != 'text' or type(blocks[0].get('text')) is not str or
                    set(blocks[0]) - {'type', 'text', 'citations'} or blocks[0].get('citations') not in (None, [])):
                raise ProviderFailure('PROVIDER_INVALID_PARTS')
            usage = result.get('usage')
            fields = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')
            if type(usage) is not dict or any(type(usage.get(k)) is not int or usage[k] < 0 for k in fields):
                raise ProviderFailure('PROVIDER_USAGE_MISSING')
            new, output, created, read = (usage[k] for k in fields)
            total = new + created + read
            if total < 1 or total > reserved_input or output > OUTPUT_TOKENS:
                raise ProviderFailure('PROVIDER_TOKEN_BOUND')
            if 'cache_creation' in usage:
                details = usage['cache_creation']
                if (type(details) is not dict or
                        set(details) != {'ephemeral_5m_input_tokens', 'ephemeral_1h_input_tokens'} or
                        any(type(v) is not int or v < 0 for v in details.values()) or
                        details['ephemeral_1h_input_tokens'] != 0 or details['ephemeral_5m_input_tokens'] != created):
                    raise ProviderFailure('PROVIDER_CACHE_USAGE_BINDING')
            cost = actual_cost(new, created, read, output)
            if cost > maximum / 1e9:
                raise ProviderFailure('PROVIDER_COST_BOUND')
            if len(blocks[0]['text'].encode()) > OUTPUT_JSON_BYTES:
                raise ProviderFailure('GENERATED_JSON_BYTE_BOUND')
            draft = _strict_json(blocks[0]['text'])
            if type(draft) is not dict:
                raise ProviderFailure('PROVIDER_INVALID_JSON')
            trace.update(input_tokens=total, uncached_input_tokens=new, cache_creation_input_tokens=created,
                         cache_read_input_tokens=read, cache_hit_observed=read > 0, output_tokens=output,
                         estimated_cost_usd=cost)
            return draft, trace
        except ProviderFailure as exc:
            trace['failure_code'] = str(exc)
            raise
        except Exception:
            trace['failure_code'] = 'PROVIDER_INVALID_JSON'
            raise ProviderFailure('PROVIDER_INVALID_JSON') from None
        finally:
            if began:
                trace['admission'] = self.admission.end_turn() or trace.get('admission')
            self.lock.release()
