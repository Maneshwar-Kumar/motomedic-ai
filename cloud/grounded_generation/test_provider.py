"""Software-only failure/budget/cache tests; never a semantic score."""
import json
import unittest
from copy import deepcopy
from cloud.grounded_generation.provider import GemmaProvider, MODEL,INPUT_TOKENS, ProviderFailure
from cloud.grounded_generation.policy import SCHEMA

class Transport:
    def __init__(self): self.calls=[];self.count=100;self.fail=[];self.output_tokens=20
    def __call__(self,method,path,body,key):
        self.calls.append((path,deepcopy(body)))
        if path.endswith(':countTokens'): return {'totalTokens':self.count}
        if path=='cachedContents': return {'name':'cachedContents/test'}
        if self.fail: raise ProviderFailure(self.fail.pop(0))
        output={'route':'UNSUPPORTED','scope_ids':[],'step_id':'','clarification_id':'','claims':[]}
        return {'modelVersion':MODEL,'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(output)}]}}],
            'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':self.output_tokens,'totalTokenCount':120,
                'cachedContentTokenCount':80 if 'cachedContent' in body else 0}}

class Tests(unittest.TestCase):
    def setUp(self):
        self.transport=Transport();self.reservations=[]
        self.provider=GemmaProvider(lambda n,k:self.reservations.append((n,k)),transport=self.transport,key='test-only')
    def call(self): return self.provider.complete('stable policy',{'version':'v1','evidence':{}},{'question':'unseen'},SCHEMA)
    def test_actual_counter_and_no_semantic_call(self):
        result=self.call();self.assertEqual(result.telemetry['generation_calls'],1)
        body=self.transport.calls[-1][1]
        self.assertEqual(body['generationConfig']['responseMimeType'],'application/json')
        self.assertEqual(body['generationConfig']['responseJsonSchema'],SCHEMA)
        self.assertEqual(result.telemetry['verifier_calls'],0);self.assertEqual(self.reservations,[(1900,'generation')])
    def test_overflow_no_generation_no_truncation(self):
        self.transport.count=INPUT_TOKENS+1
        with self.assertRaisesRegex(ProviderFailure,'NO_TRUNCATION'): self.call()
        self.assertFalse(self.reservations)

    def test_preflight_overflow_after_success_has_current_zero_generation_trace(self):
        previous=self.call();previous_trace=deepcopy(previous.telemetry)
        before=list(self.reservations)
        self.transport.count=INPUT_TOKENS+1
        with self.assertRaisesRegex(ProviderFailure,'TOKEN_BOUND_NO_TRUNCATION'):
            self.provider.context('policy',{'fixture':True},{'question':'private current question'},SCHEMA)
        trace=self.provider.last_trace
        self.assertEqual(trace['generation_calls'],0)
        self.assertEqual(trace['input_tokens_counted'],INPUT_TOKENS+1)
        self.assertEqual(trace['failure_code'],'COMPLETE_CONTEXT_TOKEN_BOUND_NO_TRUNCATION')
        self.assertGreater(trace['request_bytes'],0)
        self.assertNotIn('input_tokens',trace)
        self.assertNotIn('private current question',str(trace))
        self.assertEqual(previous.telemetry,previous_trace)
        self.assertEqual(self.reservations,before)
        self.assertEqual(sum(c[0].endswith(':generateContent') for c in self.transport.calls),1)

    def test_large_source_preflight_counts_full_context_without_artificial_byte_cap(self):
        self.call();before_calls=len(self.transport.calls);before=list(self.reservations)
        self.provider.context('policy',{'mandatory':'x'*65536},{},SCHEMA)
        trace=self.provider.last_trace
        self.assertEqual(trace['generation_calls'],0)
        self.assertGreater(trace['request_bytes'],65536)
        self.assertEqual(trace['input_tokens_counted'],100)
        self.assertNotIn('input_tokens',trace)
        self.assertNotIn('failure_code',trace)
        self.assertEqual(len(self.transport.calls),before_calls+1)
        self.assertEqual(self.reservations,before)

    def test_completion_trace_stays_attached_after_failed_preflight(self):
        self.call();self.transport.count=INPUT_TOKENS+1
        with self.assertRaisesRegex(ProviderFailure,'TOKEN_BOUND_NO_TRUNCATION'):self.call()
        self.assertEqual(self.provider.last_trace['generation_calls'],0)
        self.assertEqual(self.provider.last_trace['input_tokens_counted'],INPUT_TOKENS+1)
        self.assertEqual(len(self.reservations),1)
        self.transport.count=100
        result=self.call()
        self.assertEqual(self.provider.last_trace,result.telemetry)
        self.assertEqual(result.telemetry['generation_calls'],1)
        self.assertEqual(result.telemetry['input_tokens_counted'],100)
        self.assertGreater(result.telemetry['request_bytes'],0)
        self.assertNotIn('failure_code',result.telemetry)
        self.assertEqual(len(self.reservations),2)
    def test_large_bundle_is_preserved_and_size8193_is_not_rejected(self):
        self.transport.count=8193
        body,count=self.provider.context('policy',{'mandatory':'x'*65536},{},SCHEMA)
        self.assertEqual(count,8193)
        self.assertEqual(json.loads(body['contents'][0]['parts'][0]['text'])['mandatory'],'x'*65536)
        self.assertFalse(self.reservations)
    def test_single_retry_only_explicit_rejection(self):
        self.transport.fail=['PROVIDER_HTTP_429'];result=self.call()
        self.assertEqual(result.telemetry['retry_count'],1);self.assertEqual(len(self.reservations),2)
    def test_uncertain_timeout_never_retried(self):
        self.transport.fail=['PROVIDER_TRANSPORT_OR_SCHEMA_FAILURE']
        with self.assertRaises(ProviderFailure): self.call()
        self.assertEqual(len(self.reservations),1)
    def test_retry_exhaustion(self):
        self.transport.fail=['PROVIDER_HTTP_503']*2
        with self.assertRaises(ProviderFailure): self.call()
        self.assertEqual(len(self.reservations),2)
    def test_output_bound(self):
        self.transport.output_tokens=1801
        with self.assertRaisesRegex(ProviderFailure,'TOKEN_BOUND'): self.call()
    def test_concurrency_rejected(self):
        self.provider.lock.acquire()
        try:
            with self.assertRaisesRegex(ProviderFailure,'CONCURRENCY'): self.call()
        finally:self.provider.lock.release()
    def test_supported_cache_prefix_versioning(self):
        self.provider.cache_capability='explicit'
        a=self.call();b=self.call()
        self.assertEqual(a.telemetry['cached_tokens'],80)
        self.assertEqual(len([c for c in self.transport.calls if c[0]=='cachedContents']),1)
        self.provider.complete('changed policy',{'version':'v1','evidence':{}},{},SCHEMA)
        self.assertEqual(len([c for c in self.transport.calls if c[0]=='cachedContents']),2)
    def test_unsupported_cache_has_no_creation_or_claimed_savings(self):
        self.call();self.call()
        self.assertFalse(any(c[0]=='cachedContents' for c in self.transport.calls))
        self.assertEqual(self.provider.last_trace['cached_tokens'],0)
    def test_store_failure_blocks_provider(self):
        def failed(n,k):raise ProviderFailure('PROVIDER_ADMISSION_STORE_UNAVAILABLE')
        self.provider.reserve=failed
        with self.assertRaises(ProviderFailure):self.call()
        self.assertFalse(any(c[0].endswith(':generateContent') for c in self.transport.calls))
    def test_exact_empty_thought_marker_only(self):
        transport=self.transport
        class Marker:
            def __call__(self,method,path,body,key):
                value=transport(method,path,body,key)
                if path.endswith(':generateContent'):
                    value['candidates'][0]['content']['parts'].insert(0,{'text':'','thought':True})
                return value
        self.provider.transport=Marker()
        self.assertEqual(self.call().telemetry['empty_thought_markers'],1)
    def test_real_thought_content_fails(self):
        transport=self.transport
        class Thought:
            def __call__(self,method,path,body,key):
                value=transport(method,path,body,key)
                if path.endswith(':generateContent'):
                    value['candidates'][0]['content']['parts'].insert(0,{'text':'reasoning','thought':True})
                return value
        self.provider.transport=Thought()
        with self.assertRaisesRegex(ProviderFailure,'INVALID_PARTS'):self.call()

if __name__=='__main__':unittest.main()
