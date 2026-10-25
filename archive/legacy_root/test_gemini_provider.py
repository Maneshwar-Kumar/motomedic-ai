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
    def test_explicit_26b_config_and_returned_model_are_exact(self):
        selected='gemma-4-26b-a4b-it';config=gemma_runtime_config(selected)
        self.assertEqual((config.generator_model,config.verifier_model),(selected,selected))
        self.assertNotEqual(config.lock,self.config.lock)
        requested=[]
        def transport(model,key,body,timeout):
            requested.append(model)
            return events({'ok':True},model=selected),{}
        p=GeminiJSONProvider(selected,config,enabled=True,authorized_calls=1,transport=transport)
        self.assertEqual(p.complete('policy',{},{}).output,{'ok':True})
        self.assertEqual(requested,[selected])
        self.assertEqual(p.last_telemetry['returned_model_versions'],[selected])
        wrong=GeminiJSONProvider(selected,config,enabled=True,authorized_calls=1,
            transport=lambda *args:(events({'ok':True},model=GeminiJSONProvider.MODEL),{}))
        with self.assertRaisesRegex(ProviderFailure,'PROVIDER_INCOMPLETE_OR_MODEL_MISMATCH'):
            wrong.complete('policy',{}, {})

    def test_unknown_and_mixed_model_configs_are_rejected_before_transport(self):
        selected='gemma-4-26b-a4b-it';config=gemma_runtime_config(selected)
        for unknown in ('gemini-2.5-flash','gemma-4-26b','../models/injected'):
            with self.assertRaises(ValueError):gemma_runtime_config(unknown)
            with self.assertRaises(ValueError):GeminiJSONProvider(unknown,config)
        for mixed in (replace(config,generator_model=GeminiJSONProvider.MODEL),
                      replace(config,verifier_model=GeminiJSONProvider.MODEL)):
            for model in GeminiJSONProvider.ALLOWED_MODELS:
                with self.assertRaises(ValueError):GeminiJSONProvider(model,mixed)
            with self.assertRaises(ValueError):build_generator(mixed)
        self.assertEqual(gemma_runtime_config().generator_model,GeminiJSONProvider.MODEL)

    def test_live_26b_preflight_requires_separate_exact_owner_authorization(self):
        from approved_text_journeys import require_live_preflight
        from datetime import datetime,timezone
        from pathlib import Path
        import tempfile
        selected='gemma-4-26b-a4b-it'
        proof={'project_id':'motomedic-ai-20261009','live_calls_authorized':True,
               'main_billing_enabled':True,'inference_billing_enabled':False,
               'billing_stop_guard_ready':True,'checked_at_utc':datetime.now(timezone.utc).isoformat()}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'simulated-preflight.json'
            path.write_text(json.dumps(proof),encoding='utf-8')
            with patch.dict(os.environ,{'MOTOMEDIC_GROUNDED_LIVE_AUTHORIZED':'1',
                                        'MOTOMEDIC_BUDGET_PREFLIGHT_FILE':str(path)}):
                self.assertEqual(require_live_preflight()['calls_per_adapter'],2)
                with self.assertRaisesRegex(ValueError,'Explicit owner authorization'):
                    require_live_preflight(selected)
                proof.update(selected_comparison_model=selected,owner_authorized_model_comparison=True)
                path.write_text(json.dumps(proof),encoding='utf-8')
                approved=require_live_preflight(selected)
                self.assertEqual(approved['selected_comparison_model'],selected)
                self.assertTrue(approved['owner_authorized_model_comparison'])
                proof['selected_comparison_model']=GeminiJSONProvider.MODEL
                path.write_text(json.dumps(proof),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'Explicit owner authorization'):
                    require_live_preflight(selected)

    def test_approved_factory_wires_explicit_26b_without_changing_default(self):
        from approved_runner import build_approved_runner
        c,_,_,_=fixture();config=gemma_runtime_config('gemma-4-26b-a4b-it')
        with patch('approved_runner.ApprovedEvidenceRegistry.load',return_value=c.registry):
            selected=build_approved_runner('unused-index',retriever=c.retriever,runtime_config=config)
            default=build_approved_runner('unused-index',retriever=c.retriever)
        self.assertEqual(selected.response_generator.config,config)
        self.assertEqual(selected.response_generator.provider.model,'gemma-4-26b-a4b-it')
        self.assertEqual(default.response_generator.provider.model,GeminiJSONProvider.MODEL)
        with patch('approved_runner.ApprovedEvidenceRegistry.load',return_value=c.registry):
            with self.assertRaisesRegex(ValueError,'configuration differ'):
                build_approved_runner('unused-index',retriever=c.retriever,
                                      generator=default.response_generator,runtime_config=config)

    def test_explicit_26b_outage_never_falls_back_to_31b(self):
        selected='gemma-4-26b-a4b-it';requested=[]
        def failure(model,*args):
            requested.append(model)
            raise TransportFailure('PROVIDER_SERVICE_ERROR',{'http_status':500,'retry_count':0})
        p=GeminiJSONProvider(selected,gemma_runtime_config(selected),enabled=True,
                             authorized_calls=1,transport=failure)
        with self.assertRaisesRegex(ProviderFailure,'PROVIDER_SERVICE_ERROR'):p.complete('policy',{}, {})
        with self.assertRaisesRegex(ProviderFailure,'LIVE_CALL_NOT_AUTHORIZED'):p.complete('policy',{}, {})
        self.assertEqual(requested,[selected])
        self.assertEqual(p.remaining_calls,0)

    def test_payload_and_separate_policy_no_credentials_in_telemetry(self):
        p=self.provider();result=p.complete('POLICY_SENTINEL',{'observation':'untrusted data'},object_schema({'ok':{'type':'boolean'}}))
        model,key,body,timeout=self.calls[0]
        self.assertEqual((model,timeout),('gemma-4-31b-it',30))
        self.assertIn('POLICY_SENTINEL',body['systemInstruction']['parts'][0]['text'])
        self.assertEqual(body['systemInstruction']['role'],'user')
        self.assertEqual(body['contents'][0]['role'],'user')
        self.assertEqual(self.config.provider_revision,'gemini-sse-json-models-utf8-empty-thought-v5')
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

    def test_confirmed_exact_empty_thought_marker_accepts_both_models(self):
        for model in GeminiJSONProvider.ALLOWED_MODELS:
            for reported in (None,0):
                with self.subTest(model=model,reported=reported):
                    chunks=events({'ok':True},model=model)
                    chunks[0]['candidates'][0]['content']['parts'].insert(0,{'text':'','thought':True})
                    if reported is not None:chunks[0]['usageMetadata']['thoughtsTokenCount']=reported
                    p=GeminiJSONProvider(model,gemma_runtime_config(model),enabled=True,authorized_calls=1,
                        transport=lambda *args:(chunks,{}))
                    result=p.complete('policy',{}, {})
                    self.assertEqual(result.output,{'ok':True})
                    self.assertTrue(result.telemetry['usage_reported'])
                    structure=result.telemetry['response_structure']
                    self.assertEqual(structure['empty_thought_part_count'],1)
                    self.assertEqual(structure['nonempty_thought_part_count'],0)
                    self.assertEqual(structure['reported_thoughts_token_count'],reported if reported is not None else 'UNKNOWN')

    def test_empty_thought_normalization_rejects_all_other_shapes_and_usage(self):
        markers=[{'text':'PRIVATE_THOUGHT_SENTINEL','thought':True},
                 {'text':' ','thought':True},
                 {'text':'','thought':True,'thoughtSignature':'PRIVATE_SIGNATURE_SENTINEL'},
                 {'text':'','thought':True,'PRIVATE_FIELD_KEY_SENTINEL':None},
                 {'text':'','thought':1},{'text':'','thought':0},
                 {'text':'','thought':'false'},{'text':'','thought':None},
                 {'thought':True},{'text':None,'thought':True}]
        for marker in markers:
            chunks=events({'ok':True});chunks[0]['candidates'][0]['content']['parts'].insert(0,marker)
            p=GeminiJSONProvider(GeminiJSONProvider.MODEL,self.config,enabled=True,authorized_calls=1,
                transport=lambda *args:(chunks,{}))
            with self.subTest(marker=marker),self.assertRaisesRegex(ProviderFailure,'PROVIDER_REFUSAL_OR_MALFORMED'):
                p.complete('policy',{}, {})
            trace=json.dumps(p.last_telemetry)
            for secret in ('PRIVATE_THOUGHT_SENTINEL','PRIVATE_SIGNATURE_SENTINEL','PRIVATE_FIELD_KEY_SENTINEL'):
                self.assertNotIn(secret,trace)
        for value in (1,True,-1,'0',None):
            chunks=events({'ok':True});chunks[0]['candidates'][0]['content']['parts'].insert(0,{'text':'','thought':True})
            chunks[0]['usageMetadata']['thoughtsTokenCount']=value
            p=GeminiJSONProvider(GeminiJSONProvider.MODEL,self.config,enabled=True,authorized_calls=1,
                transport=lambda *args:(chunks,{}))
            with self.subTest(usage=value),self.assertRaisesRegex(ProviderFailure,'PROVIDER_REFUSAL_OR_MALFORMED'):
                p.complete('policy',{}, {})

    def test_empty_thought_marker_does_not_bypass_json_model_stop_or_usage_gates(self):
        for options in ({'model':'WRONG_MODEL'},{'finish':'MAX_TOKENS'},
                        {'usage':{'promptTokenCount':1,'candidatesTokenCount':2,'totalTokenCount':0}}):
            chunks=events({'ok':True},**options);chunks[0]['candidates'][0]['content']['parts'].insert(0,{'text':'','thought':True})
            p=GeminiJSONProvider(GeminiJSONProvider.MODEL,self.config,enabled=True,authorized_calls=1,
                transport=lambda *args:(chunks,{}))
            with self.subTest(options=options),self.assertRaises(ProviderFailure):p.complete('policy',{}, {})
        chunks=events({});chunks[0]['candidates'][0]['content']['parts']=[{'text':'','thought':True}]
        p=GeminiJSONProvider(GeminiJSONProvider.MODEL,self.config,enabled=True,authorized_calls=1,
            transport=lambda *args:(chunks,{}))
        with self.assertRaisesRegex(ProviderFailure,'PROVIDER_REFUSAL_OR_MALFORMED'):p.complete('policy',{}, {})

    def test_response_structure_counts_rejected_parts_without_content(self):
        cases = [
            ([{"text":"PRIVATE_THOUGHT_SENTINEL", "thought":True}],
             {"thought_part_count":1, "empty_thought_part_count":0, "nonempty_thought_part_count":1}),
            ([{"text":"REJECTED_TEXT_SENTINEL", "thoughtSignature":"PRIVATE_SIGNATURE_SENTINEL"}],
             {"thought_signature_present":True, "thought_signature_part_count":1}),
            ([{"text":"REJECTED_TEXT_SENTINEL", "PRIVATE_FIELD_KEY_SENTINEL":"PRIVATE_VALUE_SENTINEL"}],
             {"other_part_field_count":1}),
            ([{"functionCall":{"name":"PRIVATE_FUNCTION_SENTINEL"}}],
             {"nontext_part_count":1, "known_nontext_field_count":1})]
        for parts, expected in cases:
            with self.subTest(expected=expected):
                chunks=events({});chunks[0]['candidates'][0]['content']['parts']=parts
                chunks[0]['usageMetadata']['thoughtsTokenCount']=0
                p=GeminiJSONProvider(GeminiJSONProvider.MODEL,self.config,enabled=True,authorized_calls=1,
                    transport=lambda *args:(chunks,{}))
                with self.assertRaisesRegex(ProviderFailure,'PROVIDER_REFUSAL_OR_MALFORMED') as caught:
                    p.complete('policy',{}, {})
                structure=caught.exception.telemetry['response_structure']
                for key,value in expected.items():self.assertEqual(structure[key],value)
                self.assertEqual(structure['reported_thoughts_token_count'],0)
                self.assertTrue(structure['usage_metadata_present'])
                self.assertNotIn('usage_reported',p.last_telemetry)
                trace=json.dumps(p.last_telemetry)
                for sentinel in ('REJECTED_TEXT_SENTINEL','PRIVATE_THOUGHT_SENTINEL','PRIVATE_SIGNATURE_SENTINEL',
                                 'PRIVATE_FIELD_KEY_SENTINEL','PRIVATE_VALUE_SENTINEL','PRIVATE_FUNCTION_SENTINEL'):
                    self.assertNotIn(sentinel,trace)

    def test_response_structure_candidate_and_block_diagnostics_are_redacted(self):
        for mutation,expected in (
            (lambda c:c['candidates'].append(deepcopy(c['candidates'][0])),{'candidate_count':2,'maximum_candidates_per_chunk':2}),
            (lambda c:c['candidates'][0].update(index=7),{'candidate_index_valid':False}),
            (lambda c:c.update(promptFeedback={'blockReason':'SAFETY'}),{'prompt_block_reasons':['SAFETY']}),
            (lambda c:c.update(promptFeedback={'blockReason':'PRIVATE_BLOCK_SENTINEL'}),{'prompt_block_reasons':['UNRECOGNIZED']})):
            chunks=events({});mutation(chunks[0])
            p=GeminiJSONProvider(GeminiJSONProvider.MODEL,self.config,enabled=True,authorized_calls=1,
                transport=lambda *args:(chunks,{}))
            with self.assertRaisesRegex(ProviderFailure,'PROVIDER_REFUSAL_OR_MALFORMED'):p.complete('policy',{}, {})
            for key,value in expected.items():self.assertEqual(p.last_telemetry['response_structure'][key],value)
            self.assertNotIn('PRIVATE_BLOCK_SENTINEL',json.dumps(p.last_telemetry))

    def test_reported_thought_tokens_are_strict_and_available_before_rejection(self):
        for value,expected in ((0,0),(3,3),(True,'UNKNOWN'),(-1,'UNKNOWN'),('PRIVATE_TOKEN_SENTINEL','UNKNOWN'),(None,'UNKNOWN')):
            chunks=events({});chunks[0]['candidates'][0]['content']['parts']=[{'text':'','thought':True,'extra':None}]
            if value is not None:chunks[0]['usageMetadata']['thoughtsTokenCount']=value
            p=GeminiJSONProvider(GeminiJSONProvider.MODEL,self.config,enabled=True,authorized_calls=1,
                transport=lambda *args:(chunks,{}))
            with self.assertRaises(ProviderFailure):p.complete('policy',{}, {})
            self.assertEqual(p.last_telemetry['response_structure']['reported_thoughts_token_count'],expected)
            self.assertNotIn('PRIVATE_TOKEN_SENTINEL',json.dumps(p.last_telemetry))

    def test_new_denied_call_resets_previous_response_telemetry(self):
        for failure in ('exhausted','disabled','unconfigured','context'):
            with self.subTest(failure=failure):
                p=self.provider();p.complete('policy',{}, {})
                self.assertIsNotNone(p.last_telemetry)
                p.remaining_calls=1
                payload={}
                if failure=='exhausted':p.remaining_calls=0
                if failure=='disabled':p.enabled=False
                if failure=='context':payload={'text':'x'*48001}
                env={} if failure=='unconfigured' else {'MOTOMEDIC_GEMINI_API_KEY':'SECRET_SENTINEL'}
                with patch.dict(os.environ,env,clear=True):
                    with self.assertRaises(ProviderFailure) as caught:p.complete('policy',payload,{})
                self.assertIsNone(p.last_telemetry)
                self.assertIsNone(caught.exception.telemetry)
                self.assertEqual(len(self.calls),1)
                self.calls.clear()

class GemmaControllerTests(unittest.TestCase):
    def pipeline(self, mutation=None, judge_reject=False, outage=False, model=GeminiJSONProvider.MODEL):
        c,s,_,_=fixture();config=gemma_runtime_config(model);pipeline=build_generator(config,live_enabled=True,authorized_calls_per_adapter=1)
        self.composer_calls=0;self.verifier_calls=0;self.requested_models=[]
        def composer(model,key,body,timeout):
            self.composer_calls+=1;self.requested_models.append(model)
            if outage:raise TransportFailure('PROVIDER_SERVICE_ERROR',{'http_status':500})
            allowed=json.loads(body['contents'][0]['parts'][0]['text'])
            d={k:allowed[k] for k in ('schema_version','route','step_id','kind','citations')}
            d['claims']=[{'claim_id':r['claim_id'],'text':r['wording'][0],'evidence_ids':r['evidence_ids']} for r in allowed['claims']]
            if mutation:mutation(d)
            return events(d,model=model),{'http_status':200,'first_visible_token_seconds':.01}
        def verifier(model,key,body,timeout):
            self.verifier_calls+=1;self.requested_models.append(model);payload=json.loads(body['contents'][0]['parts'][0]['text'])
            d={'claims':[{'claim_id':r['claim_id'],'supported':not judge_reject} for r in payload['claims']], 'unsupported_additions':judge_reject}
            return events(d,model=model),{'http_status':200,'first_visible_token_seconds':.02}
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
    def test_explicit_26b_has_independent_exact_composer_and_verifier(self):
        selected='gemma-4-26b-a4b-it'
        c,s=self.pipeline(model=selected);_,r,_=c.next(s,'scripted rider')
        self.assertEqual(r.type,ResponseType.SUPPORTED)
        self.assertEqual((self.composer_calls,self.verifier_calls),(1,1))
        self.assertEqual(self.requested_models,[selected,selected])
        pipeline=c.response_generator
        self.assertIsNot(pipeline.provider,pipeline.verifier.provider)
        self.assertEqual((pipeline.provider.model,pipeline.verifier.provider.model),(selected,selected))
        self.assertEqual((pipeline.provider.remaining_calls,pipeline.verifier.provider.remaining_calls),(0,0))

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
    @patch.dict(os.environ,{'MOTOMEDIC_GEMINI_API_KEY':'SECRET_SENTINEL'})
    def test_failed_new_composition_does_not_inherit_previous_verifier_trace(self):
        c,s=self.pipeline()
        first=c.response_generator.compose(c,s,'selected')
        self.assertEqual(first.type,ResponseType.SUPPORTED)
        second=c.response_generator.compose(c,s,'selected')
        self.assertIn('LIVE_CALL_NOT_AUTHORIZED',second.reason_codes)
        trace=c.response_generator.last_trace
        self.assertEqual(trace['verifier_calls'],0)
        self.assertIsNone(trace.get('verifier_transport'))

    def test_required_picture_without_category_still_blocks_text_verifier(self):
        from test_constrained_generator import approve
        c,s=self.pipeline()
        c.registry.evidence['fact']['type']='picture'
        approve(c.registry)
        s=replace(s,version_lock=c.registry.lock)
        _,r,_=c.next(s,'synthetic')
        self.assertIn('FIGURE_SEMANTIC_ADAPTER_UNAVAILABLE',r.reason_codes)
        self.assertEqual((self.composer_calls,self.verifier_calls),(0,0))

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
