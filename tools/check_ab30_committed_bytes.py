import json,hashlib,subprocess
from pathlib import Path
r=json.loads(Path('reports/ab30_v2_review.json').read_text()); entries=[(name,want) for group in ('code_sha256','source_sha256') for name,want in r[group].items()]
entries += [(name,hashlib.sha256(Path(name).read_bytes()).hexdigest()) for name in ('reports/ab30_v2_review.json','reports/ab30_v2_approval.json','reports/ab30_v2_budget.json')]
result=subprocess.run(['git','cat-file','--batch'],input=''.join('HEAD:'+name+'\n' for name,_ in entries).encode(),capture_output=True,check=True)
data=result.stdout;offset=0
for name,want in entries:
 end=data.index(b'\n',offset);meta=data[offset:end].split();assert len(meta)==3 and meta[1]==b'blob',name
 size=int(meta[2]);offset=end+1;raw=data[offset:offset+size];offset+=size+1
 assert hashlib.sha256(raw).hexdigest()==want,'Committed byte drift:'+name
assert offset==len(data)
print('PASS: all'+str(len(entries))+' committed runtime/source/receipt bytes exactly match. Push may proceed once.')
