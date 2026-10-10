import json,collections
from pathlib import Path
p=Path('human_review/record_workflow/batch_100');latest={};bad=[]
for f in sorted((p/'reviews').glob('GEN*_review.json')):
 x=json.loads(f.read_text(encoding='utf8'));a=json.loads((p/'receipts'/('{}{}_v{}_author.json'.format('',x['record_id'],x['version']))).read_text(encoding='utf8'))
 if x['author_sha256']!=a['payload_sha256'] or x['context_sha256']!=a['context_sha256'] or x['manual_sha256']!='cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89':bad.append(f.name)
 latest[x['record_id']]=x
print('Exact binding errors',bad);print('Reviewed IDs',len(latest));print('latest verdicts',dict(collections.Counter(x['verdict'] for x in latest.values())));print('Still reviewer revisions',[(k,x['version']) for k,x in latest.items() if x['verdict']!='PASS'])
