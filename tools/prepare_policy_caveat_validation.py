"""Freeze an authorized policy-caveat candidate; preserve baseline and source bytes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
BASE='us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:9d92653a7984cea1a21f132752d961dbd1eb79140380d6d30773ea5ae3cf0969'
OUT=ROOT/'reports/arm_a/policy_caveats_v2'
CONTEXT=ROOT/'build/arm-a-policy-caveats-v2'
FILES=['approved_registry.py','constrained_generator.py','reviewed_controller.py','cloud/arm_a/composer.py','cloud/arm_a/rider_contract.py','cloud/arm_a/test_composer.py','cloud/arm_a/test_policy_caveats.py','cloud/arm_a/test_api.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not CONTEXT.exists(),'Preserve frozen context'
 baseline=ROOT/'reports/arm_a/golden161_validation_v1'
 verified=json.loads((baseline/'verified_results.json').read_text(encoding='utf-8'))
 rows=json.loads((baseline/'partial_results.json').read_text(encoding='utf-8'))['cases']
 findings=verified['policy_only_claim_incompatibilities']
 targets=[x['record_id'] for x in findings if x['actual_route']=='SYSTEM_ERROR' and next(r for r in rows if r['record_id']==x['record_id'])['selected_records']==[x['record_id']]]
 assert targets
 release_path=ROOT/'build/arm-a-ui-wiring-v2/arm_a_release.json'
 assert sha(release_path)=='e2806fe205e6d5a1b81d1cc87b788e648818a8449d12c0b252b0d212a41956c0'
 release=json.loads(release_path.read_text(encoding='utf-8'))
 release.update(created_at=datetime.now(timezone.utc).isoformat(),patch_version='arm-a-policy-caveats-v2',base_image=BASE)
 bindings={}
 for name in FILES:
  dst=CONTEXT/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dst)
  release['file_sha256'][name]=bindings[name]=sha(dst)
 (CONTEXT/'arm_a_release.json').write_text(json.dumps(release,indent=2)+'\n',encoding='utf-8')
 release_sha=sha(CONTEXT/'arm_a_release.json')
 runner=(ROOT/'tools/validate_golden161.py').read_text(encoding='utf-8')
 runner=runner.replace("RELEASE='e2806fe205e6d5a1b81d1cc87b788e648818a8449d12c0b252b0d212a41956c0'",'RELEASE='+repr(release_sha))
 runner=runner.replace("RUN='golden161-ui-arm-a-20261011-v1'", "RUN='golden161-policy-caveats-20261011-v2'\nTARGETS="+repr(targets))
 runner=runner.replace('for number,(rid,record) in enumerate(consumer.records.items(),1):','for number,(rid,record) in enumerate(((rid,record) for rid,record in consumer.records.items() if rid in TARGETS),1):')
 runner=runner.replace('record_count=161','record_count=len(TARGETS)')
 runner=runner.replace('assert len(rows)==161','assert len(rows)==len(TARGETS)')
 runner=runner.replace("'error':error,'trusted_fixture_injected':False", "'error':error,'trusted_fixture_injected':False,'response_reason_codes':list(response.get('reason_codes',[])) if error is None else [],'composer_trace':q.controller.response_generator.last_trace")
 # Capture internal reason codes by wrapping controller.response; serving wording remains identical.
 runner=runner.replace('original=retriever.search;captures=[]','original=retriever.search;captures=[];reason_codes=[]\n original_response=q.controller.response\n def capture_response(*args,**kwargs):\n  result=original_response(*args,**kwargs);reason_codes[:]=result.reason_codes;return result\n q.controller.response=capture_response')
 runner=runner.replace("expected=record['initial_route'];captures.clear();error=None", "expected=record['initial_route'];captures.clear();reason_codes.clear();error=None")
 runner=runner.replace("list(response.get('reason_codes',[])) if error is None else []","list(reason_codes)")
 dst=CONTEXT/'tools/validate_policy_caveats.py';dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(runner,encoding='utf-8')
 compile(runner,str(dst),'exec')
 tests=['cloud.arm_a.test_api','cloud.arm_a.test_store','cloud.arm_a.test_composer','cloud.arm_a.test_policy_caveats','test_approved_integration','test_text_journeys','test_constrained_generator','cloud.arm_a.test_rider_contract','cloud.arm_a.test_question_wiring','rider_ui.tests.test_client','rider_ui.tests.test_identity','rider_ui.tests.test_verified_sse']
 code="from pathlib import Path; import unittest; import test_approved_integration as f; f.ROOT=Path('/app'); f.INDEX=Path('/app/build/index'); suite=unittest.defaultTestLoader.loadTestsFromNames("+repr(tests)+"); r=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not r.wasSuccessful())"
 docker='FROM '+BASE+'\nUSER root\nCOPY --chown=motomedic:motomedic . /app\nRUN python -B -c '+json.dumps(code)+'\nUSER motomedic\nRUN MOTOMEDIC_VALIDATION_HOSTED=cloudbuild python -B /app/tools/validate_policy_caveats.py\n'
 (CONTEXT/'Dockerfile').write_text(docker,encoding='utf-8')
 recipe={'steps':[{'name':'gcr.io/cloud-builders/docker','args':['build','-t','arm-a-policy-caveats:v2','.']}], 'timeout':'2400s','options':{'machineType':'E2_HIGHCPU_8','logging':'CLOUD_LOGGING_ONLY'}}
 (CONTEXT/'cloudbuild.json').write_text(json.dumps(recipe,indent=2)+'\n',encoding='utf-8')
 OUT.mkdir(parents=True,exist_ok=True)
 receipt={'base_image':BASE,'release_sha256':release_sha,'changed_bindings':bindings,'runner_sha256':sha(dst),'baseline_build_id':verified['build_id'],'baseline_verified_results_sha256':sha(baseline/'verified_results.json'),'target_records':targets,'gap_seconds':7,'provider_calls':0,'production_deployed':False,'scope':'Only exact approved product-policy caveats may omit OEM evidence IDs. Technical/manual evidence, eligibility, mandatory warnings and citation gates retained. B generator remains strict.','owner_authorization':'User approved separate technical claim and policy caveat validation on 2026-10-11; preserve baseline and rerun caveat failures at 5-7-second intervals.','source_approval_manifest_unchanged':True}
 (OUT/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'context':str(CONTEXT),'target_count':len(targets),'targets':targets,'release_sha256':release_sha}))
if __name__=='__main__':main()
