"""Synthetic provider transport checks; no model calls or factual scoring."""
from copy import deepcopy
import json
import unittest

from generation_providers import ProviderFailure
from cloud.grounded_generation.cached_verifier import CachedVerifier, CONTRACT, MODEL, MAX_CALL_USD,INPUT_TOKENS, STABLE_FIELDS
from cloud.grounded_generation.role_contracts import haiku_maximum_nanodollars
from cloud.grounded_generation.verified_qa import VERIFY_POLICY, VERIFY_SCHEMA, DRAFT_POLICY


def stable():
    value = {k: {} for k in STABLE_FIELDS}
    value.update(manual_checksum='synthetic-manual', index_id='synthetic-index',
                 full_evidence_payload_sha256='synthetic-evidence',
                 source_authority_lock='synthetic-source-lock',
                 evidence={'synthetic-id': {'text': 'Engineering fixture only.'}})
    return value


class Transport:
    def __init__(self):
        self.calls = []
        self.count = 1000
        self.failure = None
        self.response = {'model': MODEL, 'stop_reason': 'end_turn',
                         'content': [{'type': 'text', 'text': '{"engineering_fixture":true}'}],
                         'usage': {'input_tokens': 100, 'output_tokens': 50,
                                   'cache_creation_input_tokens': 900, 'cache_read_input_tokens': 0}}

    def __call__(self, method, path, body, key):
        self.calls.append((method, path, deepcopy(body)))
        if path == 'messages/count_tokens':
            return {'input_tokens': self.count}
        if self.failure:
            raise ProviderFailure(self.failure)
        return deepcopy(self.response)


class Tests(unittest.TestCase):
    def setUp(self):
        self.transport = Transport()
        self.tokens, self.costs = [], []
        self.provider = CachedVerifier(lambda n, k: self.tokens.append((n, k)),
            reserve_cost=lambda n, m: self.costs.append((n, m)),
            transport=self.transport, key='engineering-only')

    def call(self, evidence=None, dynamic=None):
        return self.provider.complete(VERIFY_POLICY, stable() if evidence is None else evidence,
            {'question': 'synthetic question', 'history': ['private rider history'],
             'complete_proposed_response': {'text': 'exact finalized fixture'}} if dynamic is None else dynamic,
            VERIFY_SCHEMA)

    def test_policy_and_evidence_cached_but_question_history_and_final_response_outside_prefix(self):
        self.call()
        body = self.transport.calls[-1][2]
        self.assertEqual(body['system'][0]['cache_control'], {'type': 'ephemeral', 'ttl': '5m'})
        prefix, dynamic = body['messages'][0]['content']
        self.assertEqual(prefix['cache_control'], {'type': 'ephemeral', 'ttl': '5m'})
        self.assertNotIn('cache_control', dynamic)
        self.assertNotIn('private rider history', prefix['text'])
        self.assertNotIn('exact finalized fixture', prefix['text'])
        self.assertEqual(json.loads(dynamic['text'])['request']['question'], 'synthetic question')
        self.assertEqual(body['thinking'], {'type': 'disabled'})
        self.assertEqual(body['output_config']['effort'], 'medium')
        self.assertEqual(body['output_config']['format']['schema'], VERIFY_SCHEMA)
        counted = self.transport.calls[0][2]
        self.assertNotIn('max_tokens', counted)
        self.assertEqual(counted['messages'], body['messages'])
        self.assertEqual(self.tokens, [(2800, 'generation')])

    def test_cache_write_then_read_truthful_usage_and_cost(self):
        write = self.call()
        self.assertEqual(write.input_tokens, 1000)
        self.assertEqual(write.telemetry['cached_tokens'], 0)
        self.assertFalse(write.telemetry['cache_hit_observed'])
        self.assertAlmostEqual(write.cost_usd, (100*.10 + 900*.125 + 50*.50)/1e6)
        self.transport.response['usage'].update(cache_creation_input_tokens=0, cache_read_input_tokens=900)
        read = self.call()
        self.assertTrue(read.telemetry['cache_hit_observed'])
        self.assertEqual(read.telemetry['cached_tokens'], 900)
        self.assertEqual(read.telemetry['cached_prefix_sha256'], write.telemetry['cached_prefix_sha256'])
        self.assertAlmostEqual(read.cost_usd, (100*.10 + 900*.01 + 50*.50)/1e6)
        self.assertLess(read.cost_usd, write.cost_usd)

    def test_prefix_identity_excludes_dynamic_but_binds_evidence(self):
        first = self.call()
        other_question = self.call(dynamic={'question': 'a different question'})
        self.assertEqual(first.telemetry['cached_prefix_sha256'], other_question.telemetry['cached_prefix_sha256'])
        changed = stable()
        changed['full_evidence_payload_sha256'] = 'different-source-binding'
        self.assertNotEqual(first.telemetry['cached_prefix_sha256'], self.call(evidence=changed).telemetry['cached_prefix_sha256'])

    def test_actual_cache_miss_remains_a_miss_without_padding(self):
        self.transport.count = 400
        self.transport.response['usage'].update(input_tokens=400, cache_creation_input_tokens=0, cache_read_input_tokens=0)
        result = self.call()
        self.assertFalse(result.telemetry['cache_hit_observed'])
        self.assertEqual(result.telemetry['cached_tokens'], 0)
        self.assertEqual(json.loads(self.transport.calls[-1][2]['messages'][0]['content'][0]['text'])['assembled_evidence'], stable())

    def test_full_cache_write_maximum_reserved_before_transport(self):
        self.call()
        self.assertEqual(self.costs, [(haiku_maximum_nanodollars(1000)/1e9, MODEL)])
        self.assertAlmostEqual(MAX_CALL_USD, .001924)

    def test_turn_reserves_two_verifier_calls_with_no_reset_or_retry(self):
        reservation = self.provider.begin_turn()
        self.assertEqual(reservation['reserved_attempts'], 2)
        self.assertEqual(self.costs, [(2*MAX_CALL_USD, MODEL)])
        self.call(); self.call()
        with self.assertRaisesRegex(ProviderFailure, 'UNRESERVED_ATTEMPT'):
            self.call()
        self.assertEqual(len(self.tokens), 2)
        self.assertEqual(len(self.costs), 1)
        with self.assertRaisesRegex(ProviderFailure, 'ALREADY_RESERVED'):
            self.provider.begin_turn()
        self.provider.end_turn()
        self.assertIsNone(self.provider.turn.remaining)

    def test_uncertain_timeout_reservation_retained_no_retry(self):
        self.provider.begin_turn()
        self.transport.failure = 'CLAUDE_TRANSPORT_OR_SCHEMA_FAILURE'
        with self.assertRaisesRegex(ProviderFailure, 'TRANSPORT'):
            self.call()
        self.assertEqual(self.provider.turn.remaining, 1)
        self.assertEqual(len([c for c in self.transport.calls if c[1] == 'messages']), 1)
        self.assertEqual(self.provider.last_trace['generation_calls'], 1)
        self.assertEqual(self.costs, [(2*MAX_CALL_USD, MODEL)])

    def test_role_or_schema_change_rejected_before_transport(self):
        for policy, schema in ((DRAFT_POLICY, VERIFY_SCHEMA), (VERIFY_POLICY, {'type':'object'})):
            with self.assertRaisesRegex(ProviderFailure, 'ROLE_MISMATCH'):
                self.provider.complete(policy, stable(), {}, schema)
        self.assertFalse(self.transport.calls)
        self.assertFalse(self.costs)

    def test_rider_data_added_to_stable_prefix_rejected(self):
        evidence = stable(); evidence['history'] = 'private'
        with self.assertRaisesRegex(ProviderFailure, 'STABLE_PREFIX'):
            self.call(evidence=evidence)
        self.assertFalse(self.transport.calls)

    def test_full_input_bounds_without_truncation(self):
        self.transport.count = INPUT_TOKENS+1
        with self.assertRaisesRegex(ProviderFailure, 'TOKEN_BOUND_NO_TRUNCATION'):
            self.call()
        self.assertFalse(self.tokens); self.assertFalse(self.costs)
        self.transport.count = 1000
        evidence = stable(); evidence['evidence'] = {'fixture': 'x'*65536}
        body,n=self.provider.context(VERIFY_POLICY,evidence,{},VERIFY_SCHEMA)
        self.assertEqual(n,1000)
        self.assertEqual(json.loads(body['messages'][0]['content'][0]['text'])['assembled_evidence'],evidence)

    def test_preflight_overflow_after_success_has_current_zero_generation_trace(self):
        previous = self.call(); previous_trace = deepcopy(previous.telemetry)
        before_tokens, before_costs = list(self.tokens), list(self.costs)
        self.transport.count = INPUT_TOKENS+1
        with self.assertRaisesRegex(ProviderFailure, 'TOKEN_BOUND_NO_TRUNCATION'):
            self.provider.context(VERIFY_POLICY, stable(), {'question':'private current question'}, VERIFY_SCHEMA)
        trace = self.provider.last_trace
        self.assertEqual(trace['generation_calls'], 0)
        self.assertEqual(trace['input_tokens_counted'], INPUT_TOKENS+1)
        self.assertEqual(trace['failure_code'], 'COMPLETE_CONTEXT_TOKEN_BOUND_NO_TRUNCATION')
        self.assertGreater(trace['request_bytes'], 0)
        self.assertNotIn('input_tokens', trace)
        self.assertNotIn('cached_prefix_sha256', trace)
        self.assertNotIn('private current question', str(trace))
        self.assertEqual(previous.telemetry, previous_trace)
        self.assertEqual((self.tokens, self.costs), (before_tokens, before_costs))
        self.assertEqual(sum(c[1] == 'messages' for c in self.transport.calls), 1)

    def test_large_source_preflight_counts_full_payload_and_keeps_current_trace(self):
        self.call(); before_calls = len(self.transport.calls)
        before_tokens, before_costs = list(self.tokens), list(self.costs)
        evidence = stable(); evidence['evidence'] = {'fixture':'x'*65536}
        self.provider.context(VERIFY_POLICY, evidence, {}, VERIFY_SCHEMA)
        trace = self.provider.last_trace
        self.assertEqual(trace['generation_calls'], 0)
        self.assertGreater(trace['request_bytes'], 65536)
        self.assertEqual(trace['input_tokens_counted'],1000)
        self.assertNotIn('input_tokens', trace)
        self.assertNotIn('failure_code', trace)
        self.assertEqual(len(self.transport.calls), before_calls+1)
        self.assertEqual((self.tokens, self.costs), (before_tokens, before_costs))

    def test_completion_trace_stays_attached_after_failed_preflight(self):
        self.call(); self.transport.count = INPUT_TOKENS+1
        with self.assertRaisesRegex(ProviderFailure, 'TOKEN_BOUND_NO_TRUNCATION'):
            self.call()
        self.assertEqual(self.provider.last_trace['generation_calls'], 0)
        self.assertEqual(self.provider.last_trace['input_tokens_counted'], INPUT_TOKENS+1)
        self.assertEqual((len(self.tokens), len(self.costs)), (1, 1))
        self.transport.count = 1000
        result = self.call()
        self.assertEqual(self.provider.last_trace, result.telemetry)
        self.assertEqual(result.telemetry['generation_calls'], 1)
        self.assertEqual(result.telemetry['input_tokens_counted'], 1000)
        self.assertGreater(result.telemetry['request_bytes'], 0)
        self.assertNotIn('failure_code', result.telemetry)
        self.assertEqual((len(self.tokens), len(self.costs)), (2, 2))

    def test_cached_and_created_tokens_count_toward_full_input_bound(self):
        for values in ((1,INPUT_TOKENS,0), (1,0,INPUT_TOKENS), (100,4000,INPUT_TOKENS-4099)):
            with self.subTest(values=values):
                self.transport.response['usage'].update(input_tokens=values[0],
                    cache_creation_input_tokens=values[1], cache_read_input_tokens=values[2])
                with self.assertRaisesRegex(ProviderFailure, 'TOKEN_BOUND'):
                    self.call()

    def test_invalid_missing_boolean_or_negative_usage_fails(self):
        for field in ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'):
            for invalid in (None, True, -1, 1.5):
                original = deepcopy(self.transport.response)
                self.transport.response['usage'][field] = invalid
                with self.subTest(field=field, invalid=invalid), self.assertRaisesRegex(ProviderFailure, 'USAGE_MISSING'):
                    self.call()
                self.transport.response = original

    def test_cache_duration_usage_must_match_five_minute_write(self):
        self.transport.response['usage']['cache_creation'] = {
            'ephemeral_5m_input_tokens':900, 'ephemeral_1h_input_tokens':0}
        self.call()
        for details in ({'ephemeral_5m_input_tokens':899, 'ephemeral_1h_input_tokens':0},
                        {'ephemeral_5m_input_tokens':0, 'ephemeral_1h_input_tokens':900},
                        {'ephemeral_5m_input_tokens':900, 'ephemeral_1h_input_tokens':False}):
            self.transport.response['usage']['cache_creation'] = details
            with self.assertRaisesRegex(ProviderFailure, 'CACHE_USAGE_BINDING'):
                self.call()

    def test_provider_identity_stop_output_and_private_parts_fail_closed(self):
        for key, value in (('model','other-model'), ('stop_reason','max_tokens'),
                           ('content',[{'type':'thinking','thinking':'private'}]),
                           ('content',[{'type':'text','text':'{}','citations':[{'private':'x'}]}])):
            original = deepcopy(self.transport.response); self.transport.response[key] = value
            with self.subTest(key=key), self.assertRaises(ProviderFailure):
                self.call()
            self.transport.response = original
        self.transport.response['usage']['output_tokens'] = 1801
        with self.assertRaisesRegex(ProviderFailure, 'TOKEN_BOUND'):
            self.call()

    def test_duplicate_nonfinite_or_nonobject_json_fails(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '[]'):
            self.transport.response['content'][0]['text'] = text
            with self.assertRaisesRegex(ProviderFailure, 'INVALID_JSON'):
                self.call()

    def test_failed_spend_guard_or_capacity_never_sends_generation(self):
        def failure(*args): raise ProviderFailure('SYNTHETIC_GUARD_FAILURE')
        for field in ('reserve_cost', 'reserve'):
            original = getattr(self.provider, field); setattr(self.provider, field, failure)
            with self.subTest(field=field), self.assertRaisesRegex(ProviderFailure, 'GUARD_FAILURE'):
                self.call()
            setattr(self.provider, field, original)
        self.assertFalse(any(c[1] == 'messages' for c in self.transport.calls))

    def test_concurrent_verifier_rejected(self):
        self.provider.lock.acquire()
        try:
            with self.assertRaisesRegex(ProviderFailure, 'CONCURRENCY'):
                self.call()
        finally:
            self.provider.lock.release()


if __name__ == '__main__': unittest.main()
