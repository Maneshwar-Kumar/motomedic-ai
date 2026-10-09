import json
import subprocess
import sys
import unittest
from unittest.mock import patch
import gemma_api_smoke as smoke

class TimingTests(unittest.TestCase):
    def test_slow_server_wait_distinct_from_connect(self):
        chunks = [{"modelVersion": smoke.MODEL, "candidates": [{"content": {"parts": [{"text": "READY"}]}, "finishReason": "STOP"}], "usageMetadata": {"totalTokenCount": 5}}]
        result = smoke.summarize({"http_code": 200, "time_namelookup": .01, "time_connect": .02, "time_appconnect": .1, "time_pretransfer": .11, "time_starttransfer": 20},20,20,chunks,0,20.1)
        self.assertTrue(result['ok'])
        self.assertEqual(result['request_ready_to_first_byte_seconds'],19.89)
        self.assertEqual(result['tls_after_connect_seconds'],.08)
    def test_timeout_cannot_be_a_success(self):
        result=smoke.summarize({'http_code':0},None,None,[],28,30)
        self.assertFalse(result['ok'])
        self.assertIsNone(result['first_visible_text_seconds'])
    def test_thought_text_does_not_count_as_visible_success(self):
        chunk={'modelVersion':smoke.MODEL,'candidates':[{'content':{'parts':[{'text':'READY','thought':True}]},'finishReason':'STOP'}]}
        self.assertFalse(smoke.summarize({'http_code':200},1,None,[chunk],0,1)['ok'])
    def test_large_curl_stderr_does_not_block_or_leak(self):
        chunk={'modelVersion':smoke.MODEL,'candidates':[{'content':{'parts':[{'text':'READY'}]},'finishReason':'STOP'}]}
        metrics={'http_code':200,'time_total':.01}
        fake="import sys,json;m="+repr(metrics)+";m['certs']='PRIVATE_CERT_METADATA'*2000;sys.stderr.write('MM_METRICS '+json.dumps(m)+'\\n');sys.stderr.flush();sys.stdout.write('data: '+"+repr(json.dumps(chunk))+"+'\\n\\n');sys.stdout.flush()"
        real_popen=subprocess.Popen
        def spawn(_command,**kwargs):
            return real_popen([sys.executable,'-c',fake],**kwargs)
        with patch.object(smoke.shutil,'which',return_value='fake-curl'),patch.object(smoke.subprocess,'Popen',side_effect=spawn):
            result=smoke.probe('SECRET_SENTINEL')
        self.assertTrue(result['ok'])
        self.assertNotIn('SECRET_SENTINEL',json.dumps(result))
        self.assertNotIn('PRIVATE_CERT_METADATA',json.dumps(result))

if __name__=='__main__':unittest.main()
