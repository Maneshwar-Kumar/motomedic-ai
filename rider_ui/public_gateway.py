"""Public Cloud Run gateway with signed visitors and private durable admission.

Client forwarding/IP headers supply no authority. The private backend's global
and visitor limits and permanent provider allocation bound usage across resets.
Only the gateway can reach Streamlit's loopback socket or mint its signed cookie.
"""
import asyncio
from collections import deque
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit

from rider_ui.identity import issue, verify, cloud_run_token
from rider_ui.public_edge import COOKIE, challenge, check_proof

VERSION = 'cloud-run-public-gateway-v2'
POLICY = 'gcp-public-cloud-run-cookie-v2'


def configured():
    secret = os.environ.get('MOTOMEDIC_VISITOR_SECRET', '')
    host = os.environ.get('MOTOMEDIC_PUBLIC_HOST', '')
    backend = os.environ.get('MOTOMEDIC_RIDER_API_URL', '')
    parsed = urlsplit(backend)
    if (not os.environ.get('K_SERVICE') or len(secret.encode()) < 32 or
            not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)*\.run\.app', host) or
            os.environ.get('MOTOMEDIC_EDGE_POLICY') != POLICY or
            os.environ.get('MOTOMEDIC_RIDER_ACCESS') != 'public_gateway' or
            parsed.scheme != 'https' or not parsed.hostname or
            not parsed.hostname.endswith('.run.app') or parsed.path or
            parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise RuntimeError('Reviewed public gateway configuration required')
    return secret, host, backend


def reserve_visitor(backend, proof):
    """No secrets, cookies, raw IPs or rider content leave this gateway call."""
    import requests
    token = cloud_run_token(backend)
    with requests.post(backend + '/internal/visitors/reserve',
            headers={'Authorization': 'Bearer ' + token},
            json={'proof_sha256': proof}, timeout=(5, 20),
            allow_redirects=False) as response:
        if response.status_code != 200 or response.json() != {'ready': True}:
            raise PermissionError('PUBLIC_VISITOR_ADMISSION_UNAVAILABLE')


def health_routes(worker, client, upstream):
    """Expose routable readiness and retain the internal startup-probe alias."""
    import tornado.web

    class Health(tornado.web.RequestHandler):
        async def get(self):
            try:
                if worker.poll() is not None:
                    raise RuntimeError()
                response = await client.fetch(upstream + '/_stcore/health', request_timeout=2)
                self.set_status(200 if response.code == 200 else 503)
            except Exception:
                self.set_status(503)
            self.finish({'ready': self.get_status() == 200})

    return [(r'/health', Health), (r'/healthz', Health)]


def main():
    import logging
    import tornado.httpclient
    import tornado.httpserver
    import tornado.ioloop
    import tornado.web
    import tornado.websocket
    from tornado.httputil import HTTPHeaders
    logging.getLogger('tornado.access').setLevel(logging.CRITICAL)
    secret, host, backend = configured()
    # A public host has no authenticated client network identifier. Never derive
    # identity or quota from a caller-controlled forwarding header.
    scope = hmac.new(secret.encode(), b'cloud-run-public-challenge-v2', hashlib.sha256).hexdigest()
    starts = deque()
    client = tornado.httpclient.AsyncHTTPClient()
    upstream = 'http://127.0.0.1:8501'
    worker = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'rider_ui/app.py',
        '--server.address=127.0.0.1', '--server.port=8501', '--server.headless=true',
        '--global.developmentMode=false', '--server.enableXsrfProtection=true',
        '--server.enableCORS=true', '--server.maxUploadSize=5',
        '--browser.serverAddress=' + host, '--browser.serverPort=443',
        '--browser.gatherUsageStats=false'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    class Gate:
        def gate(self, require_cookie=True):
            if self.request.host != host:
                raise tornado.web.HTTPError(403)
            capability = self.get_cookie(COOKIE)
            if capability:
                try:
                    verify(secret, capability, 'anonymous-edge-v1')
                except PermissionError:
                    capability = None
            self.visitor = capability
            if require_cookie and not capability:
                raise tornado.web.HTTPError(401)
            return bool(capability)

        def safe_headers(self):
            headers = HTTPHeaders()
            for name in ('Content-Type', 'Cookie', 'Origin', 'User-Agent', 'Accept',
                         'Accept-Encoding', 'X-Xsrftoken', 'X-Xsrf-Token'):
                if name in self.request.headers:
                    headers[name] = self.request.headers[name]
            headers['Host'] = host
            headers['X-MotoMedic-Edge-Visitor'] = self.visitor
            return headers

    class Entry(Gate, tornado.web.RequestHandler):
        async def get(self):
            if self.gate(require_cookie=False):
                return await self.proxy()
            now = time.monotonic()
            while starts and starts[0] < now - 60:
                starts.popleft()
            if len(starts) >= 60:
                raise tornado.web.HTTPError(429)
            starts.append(now)
            token = challenge(secret, scope)
            self.set_header('Cache-Control', 'no-store')
            self.set_header('Content-Security-Policy', "default-src 'none'; script-src 'nonce-mm-entry'; style-src 'unsafe-inline'; connect-src 'self'")
            self.set_header('X-Content-Type-Options', 'nosniff')
            self.finish('''<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><title>MotoMedic</title>
<body style="background:#101917;color:#edf4ed;font:18px system-ui;padding:12vh 10vw"><h1>MotoMedic</h1>
<p id="status">Connecting securely...</p><script nonce="mm-entry">
const token=''' + json.dumps(token) + ''';
(async()=>{const enc=new TextEncoder();let n=0;
for(;n<1000000;n++){const hash=new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(token+':'+n)));
if(hash[0]===0 && hash[1]<4)break;}
if(n===1000000)throw Error('challenge');
const res=await fetch('/_visitor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({challenge:token,solution:String(n)})});
if(!res.ok)throw Error('admission');location.replace('/');})().catch(()=>{
document.getElementById('status').textContent='Unable to connect right now. Please try again later.';});
</script></body></html>''')

        async def proxy(self):
            response = await client.fetch(tornado.httpclient.HTTPRequest(
                upstream + self.request.uri, method=self.request.method, headers=self.safe_headers(),
                follow_redirects=False, request_timeout=30), raise_error=False)
            self.set_status(response.code)
            for name, value in response.headers.get_all():
                if name.lower() not in ('content-length', 'transfer-encoding', 'connection', 'content-encoding'):
                    if name.lower() == 'set-cookie':
                        self.add_header(name, value)
                    else:
                        self.set_header(name, value)
            self.set_header('Cache-Control', 'no-store')
            self.set_header('X-Content-Type-Options', 'nosniff')
            self.finish(response.body)

    class Visitor(Gate, tornado.web.RequestHandler):
        async def post(self):
            self.gate(require_cookie=False)
            if self.request.headers.get('Origin') != 'https://' + host or self.request.headers.get('Content-Type') != 'application/json':
                raise tornado.web.HTTPError(403)
            try:
                body = json.loads(self.request.body)
                if type(body) is not dict or set(body) != {'challenge', 'solution'}:
                    raise ValueError()
                proof = check_proof(secret, scope, body['challenge'], body['solution'])
                await asyncio.to_thread(reserve_visitor, backend, proof)
            except (ValueError, PermissionError):
                raise tornado.web.HTTPError(429) from None
            except Exception:
                raise tornado.web.HTTPError(503) from None
            self.set_cookie(COOKIE, issue(secret), secure=True, httponly=True,
                            samesite='Lax', max_age=86400, path='/')
            self.set_header('Cache-Control', 'no-store')
            self.finish({'ready': True})

    class Assets(Entry):
        async def get(self):
            self.gate()
            if 'upload' in self.request.path or len(self.request.uri) > 2048:
                raise tornado.web.HTTPError(404)
            await self.proxy()

    class Socket(Gate, tornado.websocket.WebSocketHandler):
        async def prepare(self):
            self.upstream = None
            self.reader = None
            self.gate()

        def check_origin(self, origin):
            return origin == 'https://' + host

        def select_subprotocol(self, protocols):
            return 'streamlit' if 'streamlit' in protocols else None

        async def open(self):
            try:
                protocols = self.request.headers.get('Sec-WebSocket-Protocol', '').split(',')
                self.upstream = await tornado.websocket.websocket_connect(
                    tornado.httpclient.HTTPRequest('ws://127.0.0.1:8501/_stcore/stream',
                        headers=self.safe_headers(), connect_timeout=5, request_timeout=30),
                    subprotocols=[p.strip() for p in protocols if p.strip()], max_message_size=262144)
                # Return from open so incoming widget messages can be consumed.
                self.reader = asyncio.create_task(self.read_upstream())
            except Exception:
                self.close(code=1011)

        async def read_upstream(self):
            try:
                while True:
                    message = await self.upstream.read_message()
                    if message is None:
                        break
                    await self.write_message(message, binary=isinstance(message, bytes))
            except Exception:
                pass
            finally:
                self.close()

        async def on_message(self, message):
            if not self.upstream:
                self.close(code=1011)
                return
            size = len(message if isinstance(message, bytes) else message.encode())
            if size > 16384:
                self.close(code=1009)
                return
            try:
                await self.upstream.write_message(message, binary=isinstance(message, bytes))
            except Exception:
                self.close(code=1011)

        def on_close(self):
            if self.upstream:
                self.upstream.close()
            if self.reader:
                self.reader.cancel()

    application = tornado.web.Application(health_routes(worker, client, upstream) + [
        (r'/', Entry), (r'/_visitor', Visitor),
        (r'/_stcore/stream', Socket), (r'/(?:_stcore/(?!upload)|static/|media/).*', Assets)],
        websocket_max_message_size=16384, websocket_ping_interval=30, websocket_ping_timeout=30)
    server = tornado.httpserver.HTTPServer(application, max_body_size=16384, max_buffer_size=32768)
    server.listen(int(os.environ.get('PORT', '8080')), address='0.0.0.0')
    print(json.dumps({'event': 'public_gateway_started', 'version': VERSION,
                      'raw_identifiers_logged': False}), flush=True)
    try:
        tornado.ioloop.IOLoop.current().start()
    finally:
        worker.terminate()


if __name__ == '__main__':
    main()
