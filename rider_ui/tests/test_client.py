import copy
import io
import json
import unittest
from email.message import Message
from urllib.error import HTTPError, URLError
from rider_ui.client import APIError, RiderAPI, validate_view, MANUAL_SHA, INDEX_ID

def view():
    return {'runtime_policy':'open-manual-draft-verify-v10','schema_version':'motomedic-rider-api-v1','manual_checksum':MANUAL_SHA,'index_id':INDEX_ID,
            'session_id':'a'*32,'version':1,'choices':[],'history':[],
            'response':{'type':'SUPPORTED','technical_content':True,'release_gate_passed':True,
                        'natural_language':'Engineering fixture only.',
                        'cited_pages':[{'pdf_page':10,'pdf_page_index':9,'manual_checksum':MANUAL_SHA,
                                        'index_id':INDEX_ID,'evidence_id':'synthetic-test-only'}]}}

class Transport:
    def __init__(self, result=None, error=None):
        self.calls=0
        self.result=result
        self.error=error
        self.request=None
    def open(self, request, timeout):
        self.calls+=1
        self.request=request
        if self.error: raise self.error
        class Response(io.BytesIO):
            def __init__(self, data):
                super().__init__(data)
                self.headers=Message()
                self.headers['Content-Type']='application/json'
        return Response(self.result)

class ClientTests(unittest.TestCase):
    def test_v10_policy_acceptance_rejects_v9_recovery_continuation_and_feedback(self):
        from rider_ui.client import RUNTIME_POLICY
        self.assertEqual(RUNTIME_POLICY,'open-manual-draft-verify-v10')
        current=view();old=copy.deepcopy(current);old['runtime_policy']='open-manual-draft-verify-v9'
        api=RiderAPI('https://example.com','engineering-fixture')
        api.opener=Transport(result=json.dumps(current).encode())
        self.assertEqual(api.recover_operation('c'*32),current)
        api.opener=Transport(result=json.dumps(old).encode())
        with self.assertRaises(APIError):api.recover_operation('c'*32)
        api.opener=Transport(result=json.dumps(current).encode())
        with self.assertRaises(APIError):api.start('Synthetic continuation','c'*32,view=old)
        with self.assertRaises(APIError):api.feedback(old,'synthetic-feedback','c'*32)
        self.assertEqual(api.opener.calls,0)

    def test_retired_policy_only_allowed_by_explicit_engineering_loopback(self):
        old=view();old['runtime_policy']='open-manual-draft-verify-v9'
        api=RiderAPI('http://127.0.0.1:9999','engineering-fixture',allow_loopback=True)
        api.opener=Transport(result=json.dumps(old).encode())
        self.assertTrue(api.engineering_loopback)
        self.assertEqual(api.recover_operation('c'*32),old)
        remote=RiderAPI('https://example.com','engineering-fixture',allow_loopback=True)
        remote.opener=Transport(result=json.dumps(old).encode())
        self.assertFalse(remote.engineering_loopback)
        with self.assertRaises(APIError):remote.recover_operation('c'*32)

    def test_real_stream_callback_refresh_credentials_and_question_continuation(self):
        from rider_ui.tests.test_verified_sse import frame
        from rider_ui.tests.test_progress_stream import accepted_frames
        v=view(); raw=b''.join(accepted_frames(v))
        transport=Transport(result=raw)
        original=transport.open
        def streaming(request,timeout):
            result=original(request,timeout)
            result.headers.replace_header('Content-Type','text/event-stream')
            return result
        transport.open=streaming
        tokens=[]
        def credential():
            tokens.append(True)
            return 'managed-token-'+str(len(tokens))
        api=RiderAPI('https://example.com',credential,visitor='signed-visitor')
        api.opener=transport
        received=[];stages=[];parts=[]
        self.assertEqual(api.start('A raw question','c'*32,on_verified=received.append,on_progress=stages.append,on_chunk=parts.append),v)
        self.assertEqual(stages,['retrieving','drafting','verifying','displaying'])
        self.assertEqual(''.join(parts),v['response']['natural_language'])
        self.assertEqual(received,[v])
        transport.result=b''.join(accepted_frames(v,key='d'*32))
        api.start('Another raw question','d'*32,view=v)
        self.assertEqual(transport.request.full_url,'https://example.com/v1/sessions/'+'a'*32+'/questions')
        self.assertEqual(json.loads(transport.request.data)['expected_version'],1)
        self.assertEqual(tokens,[True,True])
        self.assertEqual(transport.request.get_header('X-motomedic-visitor'),'signed-visitor')

    def test_processing_operation_remains_pending_without_retry(self):
        api=RiderAPI('https://example.com','secret')
        transport=Transport(result=b'{}'); original=transport.open
        def processing(request,timeout):
            result=original(request,timeout);result.status=202;return result
        transport.open=processing;api.opener=transport
        with self.assertRaisesRegex(APIError,'still processing'):
            api.recover_operation('c'*32)
        self.assertEqual(transport.calls,1)
    def test_supported_requires_gate_and_citations(self):
        for key, val in [('release_gate_passed',False),('cited_pages',[])]:
            with self.subTest(key=key):
                v=view(); v['response'][key]=val
                with self.assertRaises(APIError): validate_view(v)
    def test_wrong_manual_index_and_page_block(self):
        for key, val in [('manual_checksum','0'*64),('index_id','other')]:
            v=view(); v[key]=val
            with self.assertRaises(APIError): validate_view(v)
        for key, val in [('pdf_page',150),('pdf_page',True),('pdf_page_index',10),('manual_checksum','other')]:
            v=view(); v['response']['cited_pages'][0][key]=val
            with self.assertRaises(APIError): validate_view(v)
    def test_source_content_delivery_blocked(self):
        for key in ('evidence_uri','excerpt','crop','image','text'):
            v=view(); v['response']['cited_pages'][0][key]='prohibited'
            with self.assertRaises(APIError): validate_view(v)
    def test_all_five_states_remain_distinct(self):
        for state in ('SUPPORTED','AMBIGUOUS','UNSUPPORTED','SAFETY_STOP','SYSTEM_ERROR'):
            v=view(); v['response']['type']=state
            self.assertEqual(validate_view(v)['response']['type'],state)
    def test_unresolved_is_distinct_from_normal(self):
        v=view(); v['choices']=[
            {'id':'normal','label':'Normal','outcome':'OBSERVED_NORMAL'},
            {'id':'unresolved','label':'Tried, not fixed','outcome':'ACTION_COMPLETED_UNRESOLVED'}]
        self.assertNotEqual(validate_view(v)['choices'][0]['outcome'],v['choices'][1]['outcome'])
    def test_bad_choices_and_escalation_blocked(self):
        for bad in ([{'id':'x','label':'X','outcome':'MADE_UP'}],
                    [{'id':'x','label':'X','outcome':'UNCLEAR'}]*2):
            v=view();v['choices']=bad
            with self.assertRaises(APIError): validate_view(v)
        v=view();v['escalation_uri']='javascript:alert(1)'
        with self.assertRaises(APIError): validate_view(v)
        v=view();v['response']['type']='SAFETY_STOP';v['choices']=[{'id':'x','label':'Continue','outcome':'NOT_TRIED'}]
        with self.assertRaises(APIError): validate_view(v)
    def test_configuration_requires_secure_connection(self):
        for url in ('http://example.com','https://user:password@example.com','https://example.com?key=secret'):
            with self.assertRaises(APIError): RiderAPI(url,'secret')
        with self.assertRaises(APIError): RiderAPI('https://example.com','x\nAuthorization: leaked')
        RiderAPI('http://127.0.0.1:9999','fixture',allow_loopback=True)
    def test_timeout_never_retries_and_sanitizes(self):
        api=RiderAPI('https://example.com','secret')
        api.opener=Transport(error=URLError('private provider body with secret'))
        with self.assertRaises(APIError) as e: api.catalogue()
        self.assertEqual(api.opener.calls,1)
        self.assertNotIn('secret',str(e.exception))
    def test_http_failure_never_exposes_body(self):
        for status in (401,403,409,429,500):
            api=RiderAPI('https://example.com','secret')
            api.opener=Transport(error=HTTPError('https://example.com',status,'PRIVATE SECRET',{},None))
            with self.assertRaises(APIError) as e: api.catalogue()
            self.assertNotIn('PRIVATE',str(e.exception))
            self.assertEqual(api.opener.calls,1)
    def test_feedback_only_sends_server_choice_and_version(self):
        import json
        api=RiderAPI('https://example.com','secret')
        api.opener=Transport(result=json.dumps(view()).encode())
        api.feedback(view(),'unresolved','b'*32)
        req=api.opener.request
        self.assertEqual(json.loads(req.data),{'expected_version':1,'choice_id':'unresolved','cache_mode':'bypass'})
        self.assertNotIn(b'fact',req.data)
        self.assertEqual(req.get_header('Idempotency-key'),'b'*32)
    def test_start_sends_raw_question_without_category_or_record(self):
        import json
        api=RiderAPI('https://example.com','secret');api.opener=Transport(result=json.dumps(view()).encode())
        api.start('My question is an engineering fixture','c'*32)
        payload=json.loads(api.opener.request.data)
        self.assertNotIn('intent_mode',payload)
        self.assertNotIn('record_id',payload)
        self.assertNotIn('topic_id',payload)
        self.assertEqual(payload['query'],'My question is an engineering fixture')

    def test_catalogue_requires_open_question_capability(self):
        api=RiderAPI('https://example.com','secret')
        base={'schema_version':'motomedic-rider-api-v1','manual_checksum':MANUAL_SHA,'index_id':INDEX_ID}
        api.opener=Transport(result=json.dumps(base).encode())
        with self.assertRaises(APIError): api.catalogue()
        api.opener=Transport(result=json.dumps({**base,'question_input':'open','streaming':'DRAFT_VERIFY_STREAM'}).encode())
        self.assertEqual(api.catalogue()['question_input'],'open')
        api.opener=Transport(result=json.dumps({**base,'question_input':'open','streaming':'VERIFIED_COMPLETE_UNIT_SSE'}).encode())
        with self.assertRaises(APIError):api.catalogue()

    def test_session_identifiers_cannot_inject_path(self):
        api=RiderAPI('https://example.com','secret')
        with self.assertRaises(APIError): api.recover('../other')
        with self.assertRaises(APIError): api.recover_operation('../other')
    def test_invalid_json_and_response_bound(self):
        for data in (b'not-json',b' '* (256*1024+1)):
            api=RiderAPI('https://example.com','secret');api.opener=Transport(result=data)
            with self.assertRaises(APIError): api.catalogue()
    def test_redirects_rejected(self):
        from rider_ui.client import NoRedirect
        with self.assertRaises(APIError): NoRedirect().redirect_request(None,None,None,None,None,None)

if __name__=='__main__': unittest.main()

