"""Anonymous gateway: ALB-only ingress, signed cookies, proof challenge and managed quotas.

The deployment MUST use internal-and-cloud-load-balancing ingress, with the ALB
overwriting X-MotoMedic-Edge-IP from client_ip_address. Direct run.app access is
blocked. No raw IP, cookies, headers or rider text is recorded by this module.
"""
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import subprocess
import sys
from urllib.parse import urlsplit

from rider_ui.identity import issue, verify

COOKIE = '__Host-motomedic-visitor'
BITS = 14
PROJECT = 'motomedic-ai-20261009'
VERSION = 'anonymous-alb-admission-v1'

def network_key(secret, value):
    # This value is ONLY the documented ALB-overwritten header, never XFF.
    if type(value) is not str or len(value)>64:
        raise PermissionError('TRUSTED_EDGE_REQUIRED')
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        raise PermissionError('TRUSTED_EDGE_REQUIRED') from None
    # Bucket IPv6 /64s to prevent trivial rotation of individual IPv6 addresses.
    normalized = str(ipaddress.ip_network(str(ip)+'/64', strict=False)) if ip.version==6 else str(ip)
    return hmac.new(secret.encode(), ('edge-network-v1:'+normalized).encode(), hashlib.sha256).hexdigest()

def challenge(secret, key, now=None):
    body = json.dumps({'nonce':secrets.token_hex(16),'network':key,
        'expires':int(now if now is not None else __import__('time').time())+120},
        sort_keys=True,separators=(',',':')).encode()
    encoded=base64.urlsafe_b64encode(body).decode().rstrip('=')
    return encoded+'.'+hmac.new(secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()

def check_proof(secret, key, token, solution, now=None):
    if (type(token) is not str or len(token)>512 or type(solution) is not str or
            not re.fullmatch(r'[0-9]{1,12}',solution)):
        raise PermissionError('INVALID_CHALLENGE')
    try:
        encoded, signature=token.split('.')
        expected=hmac.new(secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,expected):
            raise ValueError()
        body=json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)))
        clock=now if now is not None else __import__('time').time()
        if (body.get('network')!=key or type(body.get('expires')) is not int or
                not clock<body['expires']<=clock+120 or
                not re.fullmatch(r'[a-f0-9]{32}',body.get('nonce',''))):
            raise ValueError()
        digest=hashlib.sha256((token+':'+solution).encode()).digest()
        if int.from_bytes(digest[:2],'big') >= 1 << (16-BITS):
            raise ValueError()
        return hmac.new(secret.encode(),('spent:'+token).encode(),hashlib.sha256).hexdigest()
    except Exception:
        raise PermissionError('INVALID_CHALLENGE') from None

class EdgeLimits:
    def __init__(self, client):
        self.client=client

    def reserve(self, network, proof=None):
        from google.cloud import firestore
        own=self.client.collection('arm_a_usage').document('edge-'+network)
        shared=self.client.collection('arm_a_usage').document('edge-global')
        used=self.client.collection('arm_a_usage').document('edge-proof-'+proof) if proof else None
        @firestore.transactional
        def transaction(tx):
            now=datetime.now(timezone.utc)
            snapshots=[own.get(transaction=tx),shared.get(transaction=tx)]
            prior=used.get(transaction=tx) if used else None
            if prior and prior.exists:
                raise PermissionError('CHALLENGE_ALREADY_USED')
            updates=[]
            for ref,snap,minute_cap,day_cap,issue_cap in (
                (own,snapshots[0],180,5000,8),(shared,snapshots[1],600,10000,60)):
                data=snap.to_dict() if snap.exists else {}
                times=[t for t in data.get('edge_requests',[]) if t>now-timedelta(hours=24)]
                creations=[t for t in data.get('edge_visitors',[]) if t>now-timedelta(hours=24)]
                if len(times)>=day_cap or sum(t>now-timedelta(minutes=1) for t in times)>=minute_cap:
                    raise PermissionError('EDGE_USAGE_LIMIT')
                if used and len(creations)>=issue_cap:
                    raise PermissionError('VISITOR_RESET_LIMIT')
                updates.append((ref, {'edge_requests':times+[now],
                    'edge_visitors':creations+([now] if used else []),
                    'expires_at':now+timedelta(hours=24)}))
            for ref,data in updates:
                tx.set(ref,data)
            if used:
                tx.create(used,{'spent':True,'expires_at':now+timedelta(minutes=3)})
        transaction(self.client.transaction())

def main():
    import logging
    import tornado.httpclient
    import tornado.httpserver
    import tornado.ioloop
    import tornado.web
    import tornado.websocket
    from google.cloud import firestore
    logging.getLogger('tornado.access').setLevel(logging.CRITICAL)
    secret=os.environ.get('MOTOMEDIC_VISITOR_SECRET','')
    host=os.environ.get('MOTOMEDIC_PUBLIC_HOST','')
    if (not os.environ.get('K_SERVICE') or len(secret.encode())<32 or
            not re.fullmatch(r'[a-z0-9.-]{1,253}',host) or
            os.environ.get('MOTOMEDIC_EDGE_POLICY')!='gcp-external-alb-v1'):
        raise RuntimeError('Reviewed anonymous edge configuration required')
    limits=EdgeLimits(firestore.Client(project=PROJECT))
    client=tornado.httpclient.AsyncHTTPClient()
    upstream='http://127.0.0.1:8501'
    worker=subprocess.Popen([sys.executable,'-m','streamlit','run','rider_ui/app.py',
        '--server.address=127.0.0.1','--server.port=8501','--server.headless=true',
        '--global.developmentMode=false','--server.enableXsrfProtection=true',
        '--server.enableCORS=true','--server.maxUploadSize=5',
        '--browser.serverAddress='+host,'--browser.serverPort=443',
        '--browser.gatherUsageStats=false'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    class Gate:
        async def gate(self, require_cookie=True):
            if self.request.host != host or self.request.headers.get('X-Forwarded-Proto')!='https':
                raise tornado.web.HTTPError(403,reason='TRUSTED_EDGE_REQUIRED')
            try:
                key=network_key(secret,self.request.headers.get('X-MotoMedic-Edge-IP'))
                await asyncio.to_thread(limits.reserve,key)
            except PermissionError:
                raise tornado.web.HTTPError(429,reason='EDGE_USAGE_LIMIT') from None
            except Exception:
                raise tornado.web.HTTPError(503,reason='EDGE_ADMISSION_UNAVAILABLE') from None
            capability=self.get_cookie(COOKIE)
            if capability:
                try:
                    verify(secret,capability,'anonymous-edge-v1')
                except PermissionError:
                    capability=None
            self.network=key
            self.network_capability=issue(secret,principal='network:'+key)
            self.visitor=capability
            if require_cookie and not capability:
                raise tornado.web.HTTPError(401,reason='VISITOR_CHALLENGE_REQUIRED')
            return bool(capability)

        def safe_headers(self):
            from tornado.httputil import HTTPHeaders
            headers=HTTPHeaders()
            # Origin/XSRF and Streamlit protocol are retained. Client auth,
            # forwarding and all MotoMedic headers are never passed through.
            for name in ('Content-Type','Cookie','Origin','User-Agent','Accept',
                         'Accept-Encoding','X-Xsrftoken','X-Xsrf-Token'):
                if name in self.request.headers:
                    headers[name]=self.request.headers[name]
            headers['Host']=host
            headers['X-MotoMedic-Edge-Visitor']=self.visitor
            headers['X-MotoMedic-Edge-Network']=self.network_capability
            return headers

    class Health(tornado.web.RequestHandler):
        async def get(self):
            try:
                if worker.poll() is not None:
                    raise RuntimeError()
                response=await client.fetch(upstream+'/_stcore/health',request_timeout=2)
                self.set_status(200 if response.code==200 else 503)
            except Exception:
                self.set_status(503)
            self.finish({'ready':self.get_status()==200})

    class Entry(Gate,tornado.web.RequestHandler):
        async def get(self):
            if await self.gate(require_cookie=False):
                return await self.proxy()
            token=challenge(secret,self.network)
            # Automatic bounded browser work; no login or personal information.
            self.set_header('Cache-Control','no-store')
            self.set_header('Content-Security-Policy',"default-src 'none'; script-src 'nonce-mm-entry'; style-src 'unsafe-inline'; connect-src 'self'")
            self.set_header('X-Content-Type-Options','nosniff')
            self.finish("""<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><title>MotoMedic</title>
<body style="background:#101917;color:#edf4ed;font:18px system-ui;padding:12vh 10vw"><h1>MotoMedic</h1>
<p id="status">Connecting securely...</p><script nonce="mm-entry">
const token="""+json.dumps(token)+""";
(async()=>{const enc=new TextEncoder();let n=0;
for(;n<1000000;n++){const hash=new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(token+':'+n)));
if(hash[0]===0 && hash[1]<4)break;}
if(n===1000000)throw Error('challenge');
const res=await fetch('/_visitor',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({challenge:token,solution:String(n)})});
if(!res.ok)throw Error('admission');location.replace('/');})().catch(()=>{
document.getElementById('status').textContent='Unable to connect right now. Please try again later.';});
</script></body></html>""")

        async def proxy(self):
            response=await client.fetch(tornado.httpclient.HTTPRequest(
                upstream+self.request.uri,method=self.request.method,headers=self.safe_headers(),
                body=self.request.body if self.request.method=='POST' else None,
                follow_redirects=False,request_timeout=30),raise_error=False)
            self.set_status(response.code)
            for name,value in response.headers.get_all():
                if name.lower() not in ('content-length','transfer-encoding','connection','content-encoding'):
                    if name.lower()=='set-cookie':
                        self.add_header(name,value)
                    else:
                        self.set_header(name,value)
            self.set_header('Cache-Control','no-store')
            self.set_header('X-Content-Type-Options','nosniff')
            self.finish(response.body)

    class Visitor(Gate,tornado.web.RequestHandler):
        async def post(self):
            await self.gate(require_cookie=False)
            if self.request.headers.get('Origin')!='https://'+host or self.request.headers.get('Content-Type')!='application/json':
                raise tornado.web.HTTPError(403)
            try:
                body=json.loads(self.request.body)
                if type(body) is not dict or set(body)!={'challenge','solution'}:
                    raise ValueError()
                proof=check_proof(secret,self.network,body['challenge'],body['solution'])
                await asyncio.to_thread(limits.reserve,self.network,proof)
            except PermissionError:
                raise tornado.web.HTTPError(429,reason='VISITOR_ADMISSION_DENIED') from None
            except ValueError:
                raise tornado.web.HTTPError(400) from None
            except Exception:
                raise tornado.web.HTTPError(503,reason='EDGE_ADMISSION_UNAVAILABLE') from None
            capability=issue(secret)
            self.set_cookie(COOKIE,capability,secure=True,httponly=True,
                            samesite='Lax',max_age=86400,path='/')
            self.set_header('Cache-Control','no-store')
            self.finish({'ready':True})

    class Assets(Entry):
        async def get(self):
            await self.gate()
            if ('upload' in self.request.path or len(self.request.uri)>2048):
                raise tornado.web.HTTPError(404)
            await self.proxy()

    class Socket(Gate,tornado.websocket.WebSocketHandler):
        async def prepare(self):
            self.upstream=None
            await self.gate()
        def check_origin(self,origin):
            return origin=='https://'+host
        def select_subprotocol(self,subprotocols):
            return 'streamlit' if 'streamlit' in subprotocols else None
        async def open(self):
            try:
                protocols=self.request.headers.get('Sec-WebSocket-Protocol','').split(',')
                self.upstream=await tornado.websocket.websocket_connect(
                    tornado.httpclient.HTTPRequest('ws://127.0.0.1:8501/_stcore/stream',
                        headers=self.safe_headers(),connect_timeout=5,request_timeout=30),
                    subprotocols=[p.strip() for p in protocols if p.strip()],
                    max_message_size=262144)
                while True:
                    message=await self.upstream.read_message()
                    if message is None:break
                    await self.write_message(message,binary=isinstance(message,bytes))
            except Exception:
                pass
            finally:
                self.close()
        async def on_message(self,message):
            if not self.upstream:
                self.close(code=1011);return
            size=len(message if isinstance(message,bytes) else message.encode())
            if size>16384:
                self.close(code=1009);return
            try:
                await self.upstream.write_message(message,binary=isinstance(message,bytes))
            except Exception:
                self.close(code=1011)
        def on_close(self):
            if self.upstream:self.upstream.close()

    application=tornado.web.Application([
        (r'/healthz',Health),(r'/',Entry),(r'/_visitor',Visitor),
        (r'/_stcore/stream',Socket),(r'/(?:_stcore/(?!upload)|static/|media/).*',Assets)],
        websocket_max_message_size=16384,websocket_ping_interval=30,
        websocket_ping_timeout=30)
    server=tornado.httpserver.HTTPServer(application,max_body_size=16384,max_buffer_size=32768)
    server.listen(int(os.environ.get('PORT','8080')),address='0.0.0.0')
    print(json.dumps({'event':'anonymous_edge_started','version':VERSION,
                     'raw_identifiers_logged':False}),flush=True)
    try:tornado.ioloop.IOLoop.current().start()
    finally:worker.terminate()

if __name__=='__main__':main()
