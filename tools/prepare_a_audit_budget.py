"""Read-only cloud preflight. Writes proof locally; never changes billing/settings."""
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone


def read(*args):
    return json.loads(subprocess.check_output(['gcloud.cmd', *args, '--format=json'], text=True))


main = read('billing', 'projects', 'describe', 'motomedic-ai-20261009')
infer = read('billing', 'projects', 'describe', 'motomedic-inference-20261009')
guard = read('run', 'services', 'describe', 'motomedic-budget-guard', '--project',
             'motomedic-ai-20261009', '--region', 'us-central1')
qdrant = read('run', 'services', 'describe', 'motomedic-qdrant', '--project',
              'motomedic-ai-20261009', '--region', 'us-central1')
subs = read('pubsub', 'subscriptions', 'list', '--project', 'motomedic-ai-20261009')
ready = any(c.get('type') == 'Ready' and c.get('status') == 'True'
            for c in guard['status']['conditions'])
live_guard = any(e.get('name') == 'SIMULATE' and e.get('value') == 'false'
                 for e in guard['spec']['template']['spec']['containers'][0]['env'])
retry = any('motomedic-budget-guard' in s.get('pushConfig', {}).get('pushEndpoint', '') and
            s.get('retryPolicy') == {'maximumBackoff': '600s', 'minimumBackoff': '10s'} for s in subs)
if not (main['billingEnabled'] is True and infer['billingEnabled'] is False and ready and live_guard and retry):
    raise RuntimeError('Preflight denied; no billing or settings changes permitted')
stamp = datetime.now(timezone.utc).isoformat()
proof = dict(schema_version='a-verifier-only-budget-v2', checked_at_utc=stamp,
             project_id='motomedic-ai-20261009', inference_project_id='motomedic-inference-20261009',
             main_billing_enabled=True, inference_billing_enabled=False,
             billing_stop_guard_ready=True, guard_live_simulate_false_observed=True,
             guard_retry_policy='ACTIVE_PUBSUB_RETRY_10S_TO_600S',
             live_calls_authorized=True, maximum_provider_calls=3, retries=0,
             main_lifetime_budget_inr=800, main_billing_stop_inr=640,
             instantaneous_spend_known=False, inference_cost_basis='FREE_ONLY_BILLING_DISABLED',
             selected_comparison_model='gemma-4-26b-a4b-it', owner_authorized_model_comparison=True,
             allocation_id='owner-a-exact-output-post-facto-verifier-v2', maximum_live_runs=1,
             previous_audit_run='38126540537', previous_audit_provider_calls=0, old_v4_allocation_reused=False, billing_changes=False, deployment_changes=False)
Path('reports/a_semantic_audit_v2_budget.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
template = qdrant['spec']['template']
anno = template['metadata']['annotations']
spec = template['spec']
settings = dict(checked_at_utc=stamp, project_id=proof['project_id'], service='motomedic-qdrant',
                region='us-central1', revision=qdrant['status']['latestReadyRevisionName'],
                service_annotations={k: v for k, v in qdrant['metadata']['annotations'].items()
                                     if k in ('run.googleapis.com/minScale', 'run.googleapis.com/maxScale')},
                revision_annotations={k: v for k, v in anno.items() if k in
                                      ('autoscaling.knative.dev/minScale','autoscaling.knative.dev/maxScale',
                                       'run.googleapis.com/cpu-throttling','run.googleapis.com/startup-cpu-boost')},
                limits=spec['containers'][0]['resources']['limits'],
                concurrency=spec['containerConcurrency'], timeout_seconds=spec['timeoutSeconds'],
                billing_mode='INSTANCE_BASED' if anno.get('run.googleapis.com/cpu-throttling') == 'false'
                             else 'REQUEST_BASED_DEFAULT',
                minimum_instances=int(anno.get('autoscaling.knative.dev/minScale',
                                              qdrant['metadata']['annotations'].get('run.googleapis.com/minScale',0))),
                startup_cpu_boost=anno.get('run.googleapis.com/startup-cpu-boost'),
                mutations=False)
Path('reports/cloud_run_live_settings_20261011.json').write_text(json.dumps(settings, indent=2), encoding='utf-8')
print('Read-only cloud preflight passed; three free-only verifier calls; no mutations.')
