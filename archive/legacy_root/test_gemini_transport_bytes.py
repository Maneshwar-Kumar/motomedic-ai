"""Actual curl loopback byte checks; no credentials or external provider requests."""
import http.server
import json
import shutil
import subprocess
import threading
import unittest

from gemini_transport import _curl_config, TRANSPORT_VERSION


class CaptureHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.server.captured_body = self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, *_):
        pass


class CurlPayloadBytes(unittest.TestCase):
    def capture(self, payload):
        curl = shutil.which('curl.exe') or shutil.which('curl')
        self.assertIsNotNone(curl, 'Actual curl is required for this byte regression')
        server = http.server.HTTPServer(('127.0.0.1', 0), CaptureHandler)
        server.timeout = 5
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        try:
            config = _curl_config('gemma-4-31b-it', 'SYNTHETIC_NOT_A_KEY', payload)
            # Replace only the fixed endpoint; production quoting and body are
            # unchanged. The sole destination is an ephemeral loopback receiver.
            _, rest = config.split('\n', 1)
            config = 'url = ' + json.dumps('http://127.0.0.1:' + str(server.server_port)) + '\n' + rest
            result = subprocess.run([curl, '--disable', '--noproxy', '*', '--silent',
                                     '--show-error', '--max-time', '5', '--connect-timeout', '2',
                                     '--retry', '0', '--config', '-'], input=config.encode('utf-8'),
                                    capture_output=True, timeout=8)
            thread.join(6)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(thread.is_alive())
            return server.captured_body
        finally:
            server.server_close()

    def assert_round_trip(self, payload):
        captured = self.capture(payload)
        self.assertEqual(captured, json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8'))
        self.assertEqual(json.loads(captured), payload)

    def test_unicode_units_punctuation_hindi_and_emoji_are_byte_exact(self):
        self.assert_round_trip({'contents': [{'parts': [{'text': '20\u00b0C; rider\u2019s check \u2013 \u0915\u093e\u0930\u094d\u092f \U0001f3cd'}]}]})

    def test_nested_json_quotes_control_characters_and_backslashes_are_byte_exact(self):
        payload = {'quoted"key': 'line 1\nline 2\r\ntab\tbackslash\\literal \\u00b0',
                   'contents': [{'parts': [{'text': json.dumps({'text': '\u21e6 \"left\" \\ path'}, ensure_ascii=False)}]}]}
        self.assert_round_trip(payload)

    def test_revision_identifies_utf8_transport(self):
        self.assertEqual(TRANSPORT_VERSION, 'gemini-curl-sse-utf8-v2')


if __name__ == '__main__':
    unittest.main()
