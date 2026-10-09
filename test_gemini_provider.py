"""Offline Gemma contract tests. Scripted answers do not establish OEM grounding."""
from copy import deepcopy
from dataclasses import replace
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from constrained_generator import build_generator
from generation_contracts import object_schema
from generation_providers import GeminiJSONProvider, ProviderFailure, gemma_runtime_config
from gemini_transport import TransportFailure, stream_request
from test_constrained_generator import fixture
from controller_contracts import ResponseType, Outcome


def events(output, **options):
    return [{"modelVersion": options.get('model','gemma-4-31b-it'),
             "candidates":[{"index":0,"content":{"parts":[{"text":json.dumps(output)}]},
                            "finishReason":options.get('finish','STOP')}],
             "usageMetadata":options.get('usage',{'promptTokenCount':12,'candidatesTokenCount':9,'totalTokenCount':21,'serviceTier':'standard'})}]

class GemmaProviderTests(unittest.TestCase):
    def setUp(self):
        self.key_patch=patch.dict(os.environ,{'MOTOMEDIC_GEMINI_API_KEY':'SECRET_SENTINEL'});self.key_patch.start()
        self.config=gemma_runtime_config();self.calls=[]
    def tearDown(self):self.key_patch.stop()
    def provider(self,output=None,**options):
        def transport(model,key,payload,timeout):
            self.calls.append((model,key,payload,timeout))
            return events(output or {'ok':True},**options),{'first_byte_seconds':.2,'first_visible_token_seconds':.3,'completion_seconds':.4,'http_status':200}
        return GeminiJSONProvider('gemma-4-31b-it',self.config,enabled=True,authorized_calls=1,transport=transport)
    def test_disabled_and_unconfigured_do_not_send(self):
        p=self.provider();p.enabled=False
        with self.assertRaisesRegex(ProviderFailure,'LIVE_CALL_NOT_AUTHORIZED'):p.complete('policy',{}, {})
        self.assertEqual(self.calls,[])
        p.enabled=True
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ProviderFailure,'PROVIDER_UNCONFIGURED'):p.complete('policy',{}, {})
        self.assertEqual(self.calls,[])
    def test_selected_model_no_silent_substitution(self):
        for name in ('gemma-4-26b-a4b-it','gemini-2.5-flash','../models/injected'):
            with self.assertRaises(ValueError):GeminiJSONProvider(name,self.config)
    def test_payload_and_separate_policy_no_credentials_in_telemetry(self):
        p=self.provider();result=p.complete('POLICY_SENTINEL',{'observation':'untrusted data'},object_schema({'ok':{'type':'boolean'}}))
        model,key,body,timeout=self.calls[0]
        self.assertEqual((model,timeout),('gemma-4-31b-it',30))
        self.assertIn('POLICY_SENTINEL',body['systemInstruction']['parts'][0]['text'])
        self.assertEqual(body['generationConfig']['thinkingConfig'],{'thinkingLevel':'minimal'})
        self.assertNotIn('tools',body)
        self.assertNotIn('SECRET_SENTINEL',json.dumps(result.telemetry))
        self.assertEqual(p.remaining_calls,0)
        with self.assertRaisesRegex(ProviderFailure,'LIVE_CALL_NOT_AUTHORIZED'):p.complete('policy',{}, {})
    def test_context_bound_prevents_request_without_truncating(self):
        p=self.provider()
        with self.assertRaisesRegex(ProviderFailure,'PROVIDER_CONTEXT_BOUND'):p.complete('policy',{'text':'x'*48001},{})
        self.assertEqual(self.calls,[]);self.assertEqual(p.remaining_calls,1)
    def test_outage_reserved_once_no_retry(self):
        def failure(*args):
            self.calls.append(1);raise TransportFailure('PROVIDER_SERVICE_ERROR',{'http_status':500,'retry_count':0})
        p=GeminiJSONProvider('gemma-4-31b-it',self.config,enabled=True,authorized_calls=1,transport=failure)
        with self.assertRaisesRegex(ProviderFailure,'PROVIDER_SERVICE_ERROR'):p.complete('policy',{}, {})
        self.assertEqual(len(self.calls),1);self.assertEqual(p.remaining_calls,0)
    def test_wrong_model_truncation_and_invalid_usage_fail_closed(self):
        for options in ({'model':'WRONG_MODEL_RAW_CONTENT'},{'finish':'MAX_TOKENS'},
                        {'usage':{'promptTokenCount':True,'candidatesTokenCount':9,'totalTokenCount':10}},
                        {'usage':{'promptTokenCount':10,'candidatesTokenCount':9,'totalTokenCount':0}},
                        {'usage':{'promptTokenCount':1,'candidatesTokenCount':1801,'totalTokenCount':1802}},
                        {'usage':{'promptTokenCount':1,'candidatesTokenCount':3,'totalTokenCount':4,'thoughtsTokenCount':10}}):
            with self.subTest(options=options):
                p=self.provider(**options)
                with self.assertRaises(ProviderFailure):p.complete('policy',{}, {})
                self.assertNotIn('WRONG_MODEL_RAW_CONTENT',json.dumps(p.last_telemetry))
    def test_malformed_duplicate_and_markdown_json_are_rejected(self):
        for raw in ('```json\n{}\n```','{"ok":true,"ok":false}','{"x":NaN}','[]'):
            def transport(*args):
                e=events({});e[0]['candidates'][0]['content']['parts'][0]['text']=raw;return e,{}
            p=GeminiJSONProvider('gemma-4-31b-it',self.config,enabled=True,authorized_calls=1,transport=transport)
            with self.assertRaisesRegex(ProviderFailure,'PROVIDER_REFUSAL_OR_MALFORMED'):p.complete('policy',{}, {})

class GemmaControllerTests(unittest.TestCase):
    def pipeline(self, mutation=None, judge_reject=False, outage=False):
        c,s,_,_=fixture();config=gemma_runtime_config();pipeline=build_generator(config,live_enabled=True,authorized_calls_per_adapter=1)
        self.composer_calls=0;self.verifier_calls=0
        def composer(model,key,body,timeout):
            self.composer_calls+=1
            if outage:raise TransportFailure('PROVIDER_SERVICE_ERROR',{'http_status':500})
            allowed=json.loads(body['contents'][0]['parts'][0]['text'])
            d={k:allowed[k] for k in ('schema_version','route','step_id','kind','citations')}
            d['claims']=[{'claim_id':r['claim_id'],'text':r['wording'][0],'evidence_ids':r['evidence_ids']} for r in allowed['claims']]
            if mutation:mutation(d)
            return events(d),{'http_status':200,'first_visible_token_seconds':.01}
        def verifier(model,key,body,timeout):
            self.verifier_calls+=1;payload=json.loads(body['contents'][0]['parts'][0]['text'])
            d={'claims':[{'claim_id':r['claim_id'],'supported':not judge_reject} for r in payload['claims']], 'unsupported_additions':judge_reject}
            return events(d),{'http_status':200,'first_visible_token_seconds':.02}
        pipeline.provider.transport=composer;pipeline.verifier.provider.transport=verifier
        c.response_generator=pipeline;s=replace(s,generation_lock=config.lock)
        return c,s
    @patch.dict(os.environ,{'MOTOMEDIC_GEMINI_API_KEY':'SECRET_SENTINEL'})
    def test_controller_uses_independent_composer_verifier_instances(self):
        c,s=self.pipeline();_,r,_=c.next(s,'raw rider media/text sentinel')
        self.assertEqual(r.type,ResponseType.SUPPORTED)
        self.assertEqual((self.composer_calls,self.verifier_calls),(1,1))
        trace=c.response_generator.last_trace
        self.assertEqual(trace['generation_transport']['first_visible_token_seconds'],.01)
        self.assertEqual(trace['verifier_transport']['first_visible_token_seconds'],.02)
        self.assertNotIn('SECRET_SENTINEL',json.dumps(trace))
        self.assertNotIn('raw rider media/text sentinel',json.dumps(trace))
    @patch.dict(os.environ,{'MOTOMEDIC_GEMINI_API_KEY':'SECRET_SENTINEL'})
    def test_altered_claim_is_rejected_before_semantic_call(self):
        c,s=self.pipeline(mutation=lambda d:d['claims'][0].update(text='Invented bypass at 999 volts.'))
        _,r,_=c.next(s,'synthetic')
        self.assertEqual(r.type,ResponseType.SYSTEM_ERROR)
        self.assertIn('UNREVIEWED_WORDING_OR_SPECIFICATION',r.reason_codes)
        self.assertEqual((self.composer_calls,self.verifier_calls),(1,0))
    @patch.dict(os.environ,{'MOTOMEDIC_GEMINI_API_KEY':'SECRET_SENTINEL'})
    def test_provider_error_distinct_from_support_rejection(self):
        c,s=self.pipeline(outage=True);_,r,_=c.next(s,'synthetic')
        self.assertIn('PROVIDER_SERVICE_ERROR',r.reason_codes)
        c,s=self.pipeline(judge_reject=True);_,r,_=c.next(s,'synthetic')
        self.assertIn('SEMANTIC_SUPPORT_REJECTED',r.reason_codes)
        self.assertEqual(r.type,ResponseType.SYSTEM_ERROR)
    def test_authoring_hold_cannot_be_bypassed_by_synthetic_approval(self):
        from test_constrained_generator import approve
        c,s=self.pipeline()
        c.registry.candidate['steps']['selected']['authoring_blockers']=['SOURCE_SCOPE_PENDING']
        approve(c.registry)  # Fictional-only approval, never an OEM source decision.
        self.assertFalse(c.registry.step_ready('selected'))
        _,r,_=c.next(s,'synthetic')
        self.assertEqual(r.type,ResponseType.UNSUPPORTED)
        self.assertEqual((self.composer_calls,self.verifier_calls),(0,0))

    @patch.dict(os.environ,{'MOTOMEDIC_GEMINI_API_KEY':'SECRET_SENTINEL'})
    def test_unresolved_action_neither_normal_nor_repeated(self):
        c,s=self.pipeline();s,r,_=c.next(s,'synthetic')
        s=c.feedback(s,'ACTION_COMPLETED_UNRESOLVED','tried-unresolved')
        self.assertEqual(s.active_attempts()[-1].outcome_enum,Outcome.ACTION_COMPLETED_UNRESOLVED)
        _,r,_=c.next(s,'still unresolved')
        self.assertNotEqual(r.suggested_step_id,'selected')
        self.assertEqual((self.composer_calls,self.verifier_calls),(1,1))

class TransportTests(unittest.TestCase):
    def fake(self,status=200,exit_code=0):
        e=events({'ok':True});metrics={'http_code':status,'time_starttransfer':.1,'time_total':.2,'num_redirects':0}
        payload=json.dumps(e[0])
        script="import sys,json;sys.stdin.read();m="+repr(metrics)+";m['certs']='SECRET_METADATA'*3000;sys.stderr.write('MM_METRICS '+json.dumps(m)+'\\n');sys.stderr.flush();sys.stdout.write('data: '+"+repr(payload)+"+'\\n\\n');sys.stdout.flush();sys.exit("+str(exit_code)+")"
        real=subprocess.Popen
        return lambda command,**kw:real([sys.executable,'-c',script],**kw)
    def test_large_metadata_pipe_drained_without_leaking(self):
        with patch('gemini_transport.shutil.which',return_value='fake-curl'),patch('gemini_transport.subprocess.Popen',side_effect=self.fake()):
            chunks,trace=stream_request('gemma-4-31b-it','SECRET_KEY',{},2)
        self.assertTrue(chunks);self.assertNotIn('SECRET_METADATA',json.dumps(trace));self.assertNotIn('SECRET_KEY',json.dumps(trace))
    def test_status_and_timeout_categories(self):
        for status,code,expected in ((500,0,'PROVIDER_SERVICE_ERROR'),(429,0,'PROVIDER_QUOTA_EXHAUSTED'),(403,0,'PROVIDER_ACCESS_ERROR'),(400,0,'PROVIDER_REQUEST_REJECTED'),(0,28,'PROVIDER_TIMEOUT')):
            with self.subTest(status=status),patch('gemini_transport.shutil.which',return_value='fake-curl'),patch('gemini_transport.subprocess.Popen',side_effect=self.fake(status,code)):
                with self.assertRaisesRegex(TransportFailure,expected):stream_request('gemma-4-31b-it','SECRET_KEY',{},2)

if __name__=='__main__':unittest.main()
