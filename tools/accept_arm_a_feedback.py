"""Bounded private live feedback and owner isolation check; no credentials logged."""
import json,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.connect_arm_a_ui import run,OUT,SECRET
from tools.accept_arm_a_initial import OPENER
from rider_ui.client import RiderAPI
from rider_ui.identity import issue
from urllib.request import Request
from urllib.error import HTTPError
API='https://motomedic-arm-a-279945185781.us-central1.run.app'
secret=run(['secrets','versions','access','1','--secret='+SECRET]).strip()
identity=run(['auth','print-identity-token']).strip()
cap=issue(secret);other=issue(secret)
api=RiderAPI(API,lambda:identity,visitor=cap,timeout=190)
key=uuid.uuid4().hex
view=api.start('How do I cancel the turn signal?',key)
assert view['response']['type']=='AMBIGUOUS'
checks=[]
for path in ('/v1/sessions/'+view['session_id'],'/v1/operations/'+key):
 try:
  with OPENER.open(Request(API+path,headers={'Authorization':'Bearer '+identity,'X-MotoMedic-Visitor':other}),timeout=30):
   raise AssertionError('Other visitor obtained a saved object')
 except HTTPError as exc:
  assert exc.code==404;exc.close()
 checks.append({'name':'other_visitor_denied_'+('session' if '/sessions/' in path else 'operation'),'status':404})
choice=next(c['id'] for c in view['choices'] if c['outcome']=='OBSERVED_NORMAL')
action=api.feedback(view,choice,uuid.uuid4().hex)
assert action['response']['type']=='SUPPORTED' and action['response']['release_gate_passed'] is True
choice=next(c['id'] for c in action['choices'] if c['outcome']=='ACTION_COMPLETED_UNRESOLVED')
stopped=api.feedback(action,choice,uuid.uuid4().hex)
assert stopped['response']['type']=='UNSUPPORTED' and not stopped['choices']
assert {'label':'Action completed; symptom remains'} in stopped['history']
assert [h for h in action['history'] if 'Turn switch' in h['label']]==[h for h in stopped['history'] if 'Turn switch' in h['label']]
checks.append({'name':'exact_scoped_EXP003_clarification_action_unresolved','routes':[view['response']['type'],action['response']['type'],stopped['response']['type']],'no_repeated_step_or_inferred_normal':True,'source_pages':sorted(set(c['pdf_page'] for c in action['response']['cited_pages']))})
receipt={'schema_version':'private-arm-a-feedback-acceptance-v1','passed':True,'checks':checks,'scope':'Only previously reviewed EXP003 exact issued choices; no broad adaptive release','provider_calls':0}
(OUT/'live_feedback_acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
