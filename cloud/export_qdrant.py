import argparse
import json
from pathlib import Path
import uuid
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ingest.online_ingest import digest, write_json
import numpy as np

p=argparse.ArgumentParser()
p.add_argument("--index",type=Path,required=True)
p.add_argument("--out",type=Path,required=True)
a=p.parse_args()
m=json.loads((a.index/"manifest.json").read_text(encoding="utf-8"))
# Original indexes record file_checksums; section indexes record file_sha256.
checks=m.get("file_checksums") or m["file_sha256"]
for name in ["chunks.jsonl","embeddings.npy"]:
    if digest(a.index/name)!=checks[name]:raise ValueError("Index integrity failure")
chunks=[json.loads(l) for l in (a.index/"chunks.jsonl").read_text(encoding="utf-8").splitlines()]
vectors=np.load(a.index/"embeddings.npy",allow_pickle=False)
if len(chunks)!=len(vectors):raise ValueError("Index row mismatch")
points=[{"id":str(uuid.uuid5(uuid.NAMESPACE_URL,c["id"])),"vector":v.tolist(),"payload":{"chunk_id":c["id"],"source_sha256":m["source_sha256"],"index_id":m["index_id"],**c.get("scope",{})}} for c,v in zip(chunks,vectors)]
write_json(a.out,{"index_id":m["index_id"],"source_sha256":m["source_sha256"],"dimensions":m["embedding"]["dimensions"],"points":points})
print(json.dumps({"index_id":m["index_id"],"points":len(points),"bundle_sha256":digest(a.out)}))
