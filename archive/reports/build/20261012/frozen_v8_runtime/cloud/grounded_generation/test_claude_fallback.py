import json, unittest, types, threading
from unittest.mock import patch
from generation_providers import ProviderFailure, ProviderResult
from cloud.grounded_generation.claude_provider import ClaudeProvider, MODEL, MAX_CALL_USD
from cloud.grounded_generation.fallback_provider import FallbackProvider
from cloud.grounded_generation.claude_budget import nanodollars, ClaudeBudget, ALLOCATION
from cloud.grounded_generation.test_admission import Client as TokenClient, atomic

SCHEMA={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}

class Transport:
    def __init__(self):
        self.calls=[];self.tokens=100
        self.response={'model':MODEL,'stop_reason':'end_turn','content':[{'type':'text','text':'{"ok":true}'}],
            'usage':{'input_tokens':100,'output_tokens':20}}
    def __call__(self,method,path,body,key):
        self.calls.append((path,body))
        if path.endswith('count_tokens'):return {'input_tokens':self.tokens}
        if isinstance(self.response,Exception):raise self.response
        return self.response

class Primary:
    def __init__(self,failure=None):self.failure=failure;self.last_trace={};self.calls=0
    def count(self,body):
        if self.failure:raise ProviderFailure(self.failure)
        return 100
    def complete(self,*args):
        self.calls+=1;self.last_trace={'generation_calls':1,'model':'gemma-4-26b-a4b-it'}
        if self.failure:raise ProviderFailure(self.failure)
        return ProviderResult({'ok':True},telemetry=self.last_trace)

class Tests(unittest.TestCase):
    def make(self):
        transport=Transport();tokens=[];money=[]
        provider=ClaudeProvider(lambda n,k:tokens.append((n,k)),reserve_cost=lambda n,m:money.append((n,m)),transport=transport,key='fixture')
        return provider,transport,tokens,money
    def test_full_request_schema_counted_and_reserved_before_generation(self):
        p,t,tokens,money=self.make();value=p.complete('policy',{'source':'all original text'},{'question':'q'},SCHEMA)
        self.assertEqual(value.output,{'ok':True});self.assertEqual(tokens,[(1900,'generation')])
        self.assertEqual(money,[(MAX_CALL_USD,MODEL)])
        count=t.calls[0][1];generation=t.calls[1][1]
        self.assertEqual(count,{k:v for k,v in generation.items() if k!='max_tokens'})
        self.assertEqual(count['output_config']['format']['schema'],SCHEMA)
        self.assertEqual(generation['thinking'],{'type':'disabled'})
        self.assertNotIn('temperature',generation)
    def test_context_overflow_has_no_paid_call_or_fallback(self):
        p,t,tokens,money=self.make();t.tokens=8193
        with self.assertRaisesRegex(ProviderFailure,'TOKEN_BOUND'):p.complete('p',{}, {},SCHEMA)
        self.assertFalse(tokens);self.assertFalse(money);self.assertEqual(len(t.calls),1)
    def test_no_secret_no_transport(self):
        p,t,_,_=self.make();p.key=None
        with self.assertRaisesRegex(ProviderFailure,'UNCONFIGURED'):p.complete('p',{}, {},SCHEMA)
        self.assertFalse(t.calls)
    def test_required_cost_guard_fail_closed(self):
        p,t,_,_=self.make();p.reserve_cost=None
        with self.assertRaisesRegex(ProviderFailure,'SPEND_GUARD'):p.complete('p',{}, {},SCHEMA)
        self.assertFalse(t.calls)
    def test_quota_or_cost_rejection_does_not_transmit(self):
        for kind in ('reserve','reserve_cost'):
            p,t,_,_=self.make()
            def rejected(*args):raise ProviderFailure('CLAUDE_SPEND_LIMIT')
            setattr(p,kind,rejected)
            with self.assertRaisesRegex(ProviderFailure,'SPEND_LIMIT'):p.complete('p',{}, {},SCHEMA)
            self.assertEqual([c[0]for c in t.calls],['messages/count_tokens'])
    def test_provider_errors_model_finish_thinking_and_json_fail_closed(self):
        for patch,reason in [({'model':'other'},'MODEL_MISMATCH'),({'stop_reason':'max_tokens'},'INCOMPLETE'),
            ({'content':[{'type':'thinking','thinking':'private'}]},'INVALID_PARTS'),
            ({'content':[{'type':'text','text':'{"ok":true,"ok":false}'}]},'INVALID_JSON'),
            ({'usage':{'input_tokens':8193,'output_tokens':20}},'TOKEN_BOUND')]:
            with self.subTest(reason=reason):
                p,t,_,_=self.make();t.response.update(patch)
                with self.assertRaisesRegex(ProviderFailure,reason):p.complete('p',{}, {},SCHEMA)
                self.assertEqual(len(t.calls),2)
    def test_no_claude_retry_after_500(self):
        p,t,_,_=self.make();t.response=ProviderFailure('CLAUDE_HTTP_500')
        with self.assertRaisesRegex(ProviderFailure,'CLAUDE_HTTP_500'):p.complete('p',{}, {},SCHEMA)
        self.assertEqual(len(t.calls),2)
    def test_availability_fallback_keeps_both_attempts(self):
        p,t,tokens,money=self.make();chain=FallbackProvider(Primary('PROVIDER_HTTP_500'),p)
        value=chain.complete('p',{}, {},SCHEMA)
        self.assertEqual(value.output,{'ok':True});self.assertEqual(value.telemetry['generation_calls'],2)
        self.assertTrue(value.telemetry['fallback_used']);self.assertEqual(len(value.telemetry['attempts']),2)
    def test_successful_primary_never_calls_claude(self):
        p,t,_,_=self.make();chain=FallbackProvider(Primary(),p)
        self.assertEqual(chain.complete('p',{}, {},SCHEMA).output,{'ok':True});self.assertFalse(t.calls)
    def test_schema_integrity_quota_and_context_never_select_fallback(self):
        for failure in ('PROVIDER_INVALID_JSON','PROVIDER_MODEL_MISMATCH','PROVIDER_HTTP_429',
            'PROVIDER_DAILY_OR_RATE_LIMIT','COMPLETE_CONTEXT_TOKEN_BOUND_NO_TRUNCATION',
            'PROVIDER_TRANSPORT_OR_SCHEMA_FAILURE','PROVIDER_INCOMPLETE_OR_REFUSED'):
            with self.subTest(failure=failure):
                p,t,_,_=self.make();chain=FallbackProvider(Primary(failure),p)
                with self.assertRaisesRegex(ProviderFailure,failure):chain.complete('p',{}, {},SCHEMA)
                self.assertFalse(t.calls)
    def test_failed_fallback_retains_primary_attempt_count(self):
        p,t,_,_=self.make();t.response=ProviderFailure('CLAUDE_HTTP_500');chain=FallbackProvider(Primary('PROVIDER_HTTP_500'),p)
        with self.assertRaisesRegex(ProviderFailure,'CLAUDE_HTTP_500'):chain.complete('p',{}, {},SCHEMA)
        self.assertEqual(chain.last_trace['generation_calls'],2)
    def test_cost_rounds_up_and_rejects_invalid(self):
        self.assertEqual(nanodollars(MAX_CALL_USD),1719200)
        self.assertEqual(nanodollars('0.0000000001'),1)
        for value in (0,-1,'NaN','Infinity'):
            with self.assertRaises(ProviderFailure):nanodollars(value)

    def test_atomic_nonrecurring_cost_cap_survives_recreation_and_concurrency(self):
        class Client(TokenClient):
            def document(self,name):
                self_name=name
                if self_name!=ALLOCATION:raise AssertionError(name)
                return self
        client=Client();cloud=types.ModuleType('google.cloud')
        cloud.firestore=types.SimpleNamespace(transactional=atomic)
        google=types.ModuleType('google');google.cloud=cloud
        results=[]
        with patch.dict('sys.modules',{'google':google,'google.cloud':cloud}):
            def call():
                try:ClaudeBudget(client)(.25,MODEL);results.append('accepted')
                except ProviderFailure:results.append('limited')
            workers=[threading.Thread(target=call)for _ in range(12)]
            for worker in workers:worker.start()
            for worker in workers:worker.join()
            self.assertEqual(results.count('accepted'),4)
            self.assertEqual(client.body['reserved_nanodollars'],1_000_000_000)
            self.assertNotIn('expires_at',client.body)
            with self.assertRaisesRegex(ProviderFailure,'SPEND_LIMIT'):ClaudeBudget(client)(.0001,MODEL)
            client.fail=True
            with self.assertRaisesRegex(ProviderFailure,'STORE_UNAVAILABLE'):ClaudeBudget(client)(.25,MODEL)

if __name__=='__main__':unittest.main()
