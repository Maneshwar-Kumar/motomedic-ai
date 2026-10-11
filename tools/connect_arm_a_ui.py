"""Private managed wiring for the exact reviewed UI/backend build version.

Credentials stay in memory/stdin. No anonymous grant or billing re-enable.
"""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/arm_a/ui_wiring_v1'
PROJECT='motomedic-ai-20261009'
REGION='us-central1'
UI_ACCOUNT='motomedic-rider-ui@'+PROJECT+'.iam.gserviceaccount.com'
BACKEND_ACCOUNT='motomedic-arm-a@'+PROJECT+'.iam.gserviceaccount.com'
SECRET='motomedic-rider-visitor-v1'
GCLOUD=shutil.which('gcloud.cmd') or shutil.which('gcloud')


def run(args,stdin=None):
    # The Windows launcher uses a cwd-relative tmpfile; isolate each invocation.
    with tempfile.TemporaryDirectory(prefix='motomedic-gcloud-') as working:
        result=subprocess.run([GCLOUD,*args,'--project='+PROJECT,'--quiet'],input=stdin,
                              text=True,capture_output=True,cwd=working)
    if result.returncode:
        raise RuntimeError('gcloud operation failed: '+result.stderr[:2000])
    return result.stdout


def document(args):
    return json.loads(run(args+['--format=json']))


def preflight():
    billing=document(['billing','projects','describe',PROJECT])
    guard=document(['run','services','describe','motomedic-budget-guard','--region='+REGION])
    env={v['name']:v.get('value') for v in guard['spec']['template']['spec']['containers'][0]['env']}
    assert billing['billingEnabled'] is True
    assert env['SIMULATE']=='false' and env['STOP_INR']=='2540' and env['BUDGET_INR']=='2700'
    (OUT/'connection_preflight.json').write_text(json.dumps({'billing_enabled':True,'stop_inr':2540,'budget_inr':2700,'guard_revision':guard['status']['latestReadyRevisionName']},indent=2)+'\n')


def credentials():
    preflight()
    present=document(['secrets','list','--filter=name:'+SECRET])
    if not present:
        run(['secrets','create',SECRET,'--replication-policy=automatic'])
        run(['secrets','versions','add',SECRET,'--data-file=-'],secrets.token_hex(32))
    for account in (UI_ACCOUNT,BACKEND_ACCOUNT):
        run(['secrets','add-iam-policy-binding',SECRET,'--member=serviceAccount:'+account,
             '--role=roles/secretmanager.secretAccessor'])
    run(['run','services','add-iam-policy-binding','motomedic-arm-a','--region='+REGION,
         '--member=serviceAccount:'+UI_ACCOUNT,'--role=roles/run.invoker'])
    (OUT/'managed_connection.json').write_text(json.dumps({'ui_account':UI_ACCOUNT,'backend_account':BACKEND_ACCOUNT,'secret_resource':SECRET,'grants':'resource-scoped secret accessor; backend service-scoped invoker','secret_values_recorded':False,'public_access':False},indent=2)+'\n')
    print('Managed private connection configured; no credentials printed.')


def deploy(kind,build_id):
    preflight()
    review=json.loads((OUT/'context_review.json').read_text())
    assert review['private_deployment_approved'] is True
    expected='e2806fe205e6d5a1b81d1cc87b788e648818a8449d12c0b252b0d212a41956c0'
    assert hashlib.sha256((ROOT/'build/arm-a-ui-wiring-v2/arm_a_release.json').read_bytes()).hexdigest()==expected
    build=document(['builds','describe',build_id,'--region='+REGION])
    assert build['status']=='SUCCESS'
    image=build['results']['images'][0]
    immutable=image['name'].split(':')[0]+'@'+image['digest']
    assert immutable.startswith('us-central1-docker.pkg.dev/'+PROJECT+'/motomedic/')
    if kind=='backend':
        service='motomedic-arm-a'
        args=['run','deploy',service,'--image='+immutable,'--region='+REGION,
              '--service-account='+BACKEND_ACCOUNT,'--update-secrets=MOTOMEDIC_VISITOR_SECRET='+SECRET+':1',
              '--no-allow-unauthenticated']
    else:
        service='motomedic-rider-ui'
        args=['run','deploy',service,'--image='+immutable,'--region='+REGION,
              '--service-account='+UI_ACCOUNT,'--set-secrets=MOTOMEDIC_VISITOR_SECRET='+SECRET+':1',
              '--set-env-vars=MOTOMEDIC_RIDER_AUTH=cloud_run,MOTOMEDIC_RIDER_API_URL=https://motomedic-arm-a-279945185781.us-central1.run.app',
              '--cpu=1','--memory=512Mi','--min=0','--max=1','--concurrency=4','--timeout=300',
              '--cpu-throttling','--cpu-boost','--no-allow-unauthenticated']
    run(args)
    status=document(['run','services','describe',service,'--region='+REGION])
    policy=document(['run','services','get-iam-policy',service,'--region='+REGION])
    assert not any(m in ('allUsers','allAuthenticatedUsers') for b in policy.get('bindings',[]) for m in b.get('members',[]))
    (OUT/(kind+'_deployment.json')).write_text(json.dumps({'build':build,'service':status,'iam':policy},indent=2)+'\n')
    print(json.dumps({'service':service,'revision':status['status']['latestReadyRevisionName'],'url':status['status']['url'],'image':immutable,'private':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('credentials','backend','ui'))
    parser.add_argument('--build-id')
    args=parser.parse_args()
    if args.action=='credentials': credentials()
    else: deploy(args.action,args.build_id)
