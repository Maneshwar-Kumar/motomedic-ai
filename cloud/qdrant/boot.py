"""Private, immutable Qdrant service. Rehydrate stored vectors at cold start."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import subprocess
import time
import urllib.request


def request(url, body=None, method=None, headers=None):
    payload=json.dumps(body).encode() if body is not None else None
    hdr={"Content-Type":"application/json",**(headers or {})}
    with urllib.request.urlopen(urllib.request.Request(url,data=payload,method=method,headers=hdr),timeout=30) as response:
        return response.read()


def backend(path,body=None,method=None):
    return json.loads(request("http://127.0.0.1:6333"+path,body,method))


token=json.loads(request("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",headers={"Metadata-Flavor":"Google"}))["access_token"]
raw=request(os.environ["INDEX_BUNDLE_URL"],headers={"Authorization":"Bearer "+token})
if hashlib.sha256(raw).hexdigest()!=os.environ["INDEX_BUNDLE_SHA256"]:
    raise RuntimeError("Immutable index checksum mismatch")
bundle=json.loads(raw)
if bundle["index_id"]!=os.environ["INDEX_ID"]:
    raise RuntimeError("Index version mismatch")
process=subprocess.Popen(["/qdrant/qdrant"],cwd="/qdrant")
for _ in range(100):
    if process.poll() is not None:raise RuntimeError("Qdrant exited during startup")
    try:
        backend("/collections")
        break
    except Exception:time.sleep(.1)
else:raise RuntimeError("Qdrant failed startup")
backend("/collections/owner_manual",{"vectors":{"size":bundle["dimensions"],"distance":"Cosine"}},"PUT")
for start in range(0,len(bundle["points"]),128):
    backend("/collections/owner_manual/points?wait=true",{"points":bundle["points"][start:start+128]},"PUT")
print(json.dumps({"ready":True,"index_id":bundle["index_id"],"points":len(bundle["points"])}),flush=True)


class Handler(BaseHTTPRequestHandler):
    def respond(self,status,value):
        raw=json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        if self.path!="/health":return self.respond(404,{"error":"Unknown endpoint"})
        return self.respond(200,{"index_id":bundle["index_id"],"points":len(bundle["points"]),"source_sha256":bundle["source_sha256"]})
    def do_POST(self):
        if self.path!="/query":return self.respond(404,{"error":"Unknown endpoint"})
        try:
            length=int(self.headers.get("Content-Length",0))
            if not 0<length<=65536:raise ValueError("Invalid request size")
            data=json.loads(self.rfile.read(length))
            vector=data["vector"]
            if not isinstance(vector,list) or len(vector)!=bundle["dimensions"] or any(not isinstance(v,(float,int)) or not math.isfinite(v) for v in vector):raise ValueError("Invalid query vector")
            if data.get("source_sha256")!=bundle["source_sha256"] or data.get("index_id")!=bundle["index_id"]:raise ValueError("Source or index mismatch")
            limit=data.get("limit",5)
            if not isinstance(limit,int) or not 1<=limit<=20:raise ValueError("Invalid limit")
            result=backend("/collections/owner_manual/points/query",{"query":vector,"limit":limit,"with_payload":True,"filter":{"must":[{"key":"source_sha256","match":{"value":bundle["source_sha256"]}}]}})
            self.respond(200,{"index_id":bundle["index_id"],"result":result["result"],"candidate_evidence_only":True})
        except (ValueError,KeyError,TypeError,json.JSONDecodeError) as error:
            self.respond(400,{"error":str(error)})
        except Exception:
            self.respond(503,{"error":"Vector retrieval unavailable","status":"SYSTEM_ERROR"})

ThreadingHTTPServer(("0.0.0.0",int(os.environ.get("PORT","8080"))),Handler).serve_forever()
