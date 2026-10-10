import copy
import io
import unittest
from email.message import Message
from urllib.error import HTTPError, URLError
from rider_ui.client import APIError, RiderAPI, validate_view, MANUAL_SHA, INDEX_ID

def view():
    return {'schema_version':'motomedic-rider-api-v1','manual_checksum':MANUAL_SHA,'index_id':INDEX_ID,
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

