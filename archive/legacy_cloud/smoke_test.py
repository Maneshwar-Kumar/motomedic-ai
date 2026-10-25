import argparse
import json
from pathlib import Path
import subprocess
import urllib.request
import urllib.error

p=argparse.ArgumentParser()
p.add_argument("--url",required=True)
p.add_argument("--index",type=Path,required=True)
p.add_argument("--out",type=Path,required=True)
a=p.parse_args()
token=subprocess.check_output(["gcloud.cmd","auth","print-identity-token"],text=True).strip()
headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"}
def call(path,body=None,auth=True):
    data=json.dumps(body).encode() if body is not None else None
    return json.loads(urllib.request.urlopen(urllib.request.Request(a.url+path,data=data,headers=headers if auth else {}),timeout=60).read())
source=json.loads((a.index/"server_smoke.json").read_text())
report={"index_id":source["index_id"],"tests":[]}
health=call("/health")
assert health["index_id"]==source["index_id"] and health["source_sha256"]==source["source_sha256"]
report["tests"].append({"name":"immutable_source_and_version","passed":True})
try:
    call("/health",auth=False)
    raise AssertionError("Unauthenticated request was accepted")
except urllib.error.HTTPError as error:
    assert error.code in (401,403)
    report["tests"].append({"name":"unauthenticated_access_rejected","passed":True,"http_status":error.code})
for case in source["cases"]:
    body={"vector":case["vector"],"source_sha256":source["source_sha256"],"index_id":source["index_id"],"limit":5}
    result=call("/query",body)
    assert result["candidate_evidence_only"] is True
    assert result["result"]["points"][0]["payload"]["chunk_id"]==case["expected_dense_chunk_id"]
    assert all(point["payload"]["source_sha256"]==source["source_sha256"] for point in result["result"]["points"])
    report["tests"].append({"name":case["query"],"passed":True})
for change in [{"source_sha256":"wrong"},{"vector":[0.0]},{"index_id":"stale"},{"limit":1000}]:
    body={"vector":source["cases"][0]["vector"],"source_sha256":source["source_sha256"],"index_id":source["index_id"],"limit":5,**change}
    try:
        call("/query",body)
        raise AssertionError("Invalid query was accepted")
    except urllib.error.HTTPError as error:
        assert error.code==400
        report["tests"].append({"name":"reject_"+next(iter(change)),"passed":True})
a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,indent=2))
