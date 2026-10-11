"""Read-only fresh budget/guard proof after owner-authorized warming."""
import json,subprocess,urllib.request,urllib.error,time
from pathlib import Path
from datetime import datetime,timezone
PROJECT='motomedic-ai-20261009'
def read(*args):return json.loads(subprocess.check_output(['gcloud.cmd',*args,'--project='+PROJECT,'--quiet','--format=json'],text=True))
main=read('billing','projects','describe',PROJECT)
infer=read('billing','projects','describe','motomedic-inference-20261009')
guard=read('run','services','describe','motomedic-budget-guard','--region=us-central1')
qdrant=read('run','services','describe','motomedic-qdrant','--region=us-central1')
subs=read('pubsub','subscriptions','list')
budget=read('billing','budgets','describe','381ad343-2da4-4676-b9a3-f180783b26d1','--billing-account=013BB2-A5996E-B48AB5')
env={e['name']:e.get('value') for e in guard['spec']['template']['spec']['containers'][0]['env']}
ready=lambda s:any(c['type']=='Ready' and c['status']=='True' for c in s['status']['conditions'])
retry=any('motomedic-budget-guard' in s.get('pushConfig',{}).get('pushEndpoint','') and s.get('retryPolicy')=={'maximumBackoff':'600s','minimumBackoff':'10s'} for s in subs)
assert main['billingEnabled'] is True and infer['billingEnabled'] is False and ready(guard) and ready(qdrant) and retry
assert env.get('SIMULATE')=='false' and env.get('BUDGET_INR')=='2700' and env.get('STOP_INR')=='2540' and env.get('BUDGET_DISPLAY_NAME')=='MotoMedic lifetime INR2700'
assert budget['amount']['specifiedAmount']=={'currencyCode':'INR','units':'2700'} and budget['displayName']==env['BUDGET_DISPLAY_NAME']
assert budget['budgetFilter']['projects']==['projects/279945185781'] and 'customPeriod' in budget['budgetFilter']
assert qdrant['metadata']['annotations'].get('run.googleapis.com/minScale')=='1'
assert qdrant['metadata']['annotations'].get('run.googleapis.com/maxScale')=='1'
assert qdrant['spec']['template']['metadata']['annotations'].get('run.googleapis.com/startup-cpu-boost')=='true'
token=subprocess.check_output(['gcloud.cmd','auth','print-identity-token'],text=True).strip()
url=qdrant['status']['url']; before=time.perf_counter()
health=json.loads(urllib.request.urlopen(urllib.request.Request(url+'/health',headers={'Authorization':'Bearer '+token}),timeout=60).read())
assert health['index_id']=='index_a3282c4d98cf54595e4ba168'
healthseconds=time.perf_counter()-before
try:
 urllib.request.urlopen(url+'/health',timeout=30)
 raise AssertionError('Private service accepted unauthenticated request')
except urllib.error.HTTPError as exc:assert exc.code in (401,403)
stamp=datetime.now(timezone.utc).isoformat()
proof=dict(schema_version='ab30-budget-v1',checked_at_utc=stamp,project_id=PROJECT,main_billing_enabled=True,inference_billing_enabled=False,billing_stop_guard_ready=True,guard_live_simulate_false_observed=True,guard_retry_policy='ACTIVE_PUBSUB_RETRY_10S_TO_600S',live_calls_authorized=True,maximum_provider_calls=90,retries=0,main_lifetime_budget_inr=2700,main_billing_stop_inr=2540,instantaneous_spend_known=False,inference_cost_basis='FREE_ONLY_BILLING_DISABLED',selected_comparison_model='gemma-4-26b-a4b-it',owner_authorized_model_comparison=True,allocation_id='owner-ab30-initial-matched-v1',maximum_live_runs=1,old_allocations_reused=False)
Path('reports/ab30_v1_budget.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
receipt=dict(schema_version='owner-warm-instance-budget-change-v1',checked_at_utc=stamp,owner_authorization='Additional US$20 and warm instance with CPU boost,11October2026',prior_budget_inr=800,additional_inr=1900,additional_usd_planning=1900/96.73076923076923,budget=budget,main_billing_enabled=True,inference_billing_enabled=False,billing_reenabled=False,guard_revision=guard['status']['latestReadyRevisionName'],guard_budget_env={k:env[k] for k in ('SIMULATE','BUDGET_DISPLAY_NAME','BUDGET_INR','STOP_INR')},guard_retry_retained=retry,qdrant_revision=qdrant['status']['latestReadyRevisionName'],qdrant_service_annotations={k:v for k,v in qdrant['metadata']['annotations'].items() if k in ('run.googleapis.com/minScale','run.googleapis.com/maxScale')},qdrant_revision_annotations=qdrant['spec']['template']['metadata']['annotations'],qdrant_limits=qdrant['spec']['template']['spec']['containers'][0]['resources']['limits'],qdrant_image=qdrant['spec']['template']['spec']['containers'][0]['image'],health=health,health_request_seconds=healthseconds,unauthenticated_health_rejected=True,billing_mode='REQUEST_BASED_DEFAULT',minimum_instance_idle_gross_usd_day=.324,minimum_instance_idle_gross_inr_day=.324*96.73076923076923,scope='Existing private Qdrant only; query/LLM/API service not deployed; benchmark worker timing distinct',rollback_command='gcloud run services update motomedic-qdrant --min=0 --project=motomedic-ai-20261009 --region=us-central1')
Path('reports/warm_instance_budget_20261011.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print('Fresh90call proof and live min1/max1/boost/auth/health receipt saved; no mutations by this preflight.')
