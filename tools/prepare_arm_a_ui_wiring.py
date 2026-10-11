"""Freeze independent backend/UI contexts; no inference or ingestion."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = 'us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:32bdd105dcee611002240ec86ab7d3f78ce1b3e882bc23f7c7d89c75082b4f96'
FILES = ['cloud/arm_a/'+n+'.py' for n in ('app','store','questions','rider_api','rider_contract','visitor','test_question_wiring','test_rider_contract')]
FILES += ['rider_ui/'+n+'.py' for n in ('__init__','identity','safeguards','verified_sse','client')]
FILES += ['rider_ui/tests/'+n+'.py' for n in ('test_client','test_identity','test_verified_sse')]
TESTS = ['cloud.arm_a.test_api','cloud.arm_a.test_store','cloud.arm_a.test_composer','test_approved_integration','test_text_journeys','test_constrained_generator','cloud.arm_a.test_rider_contract','cloud.arm_a.test_question_wiring','rider_ui.tests.test_client','rider_ui.tests.test_identity','rider_ui.tests.test_verified_sse']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    backend=ROOT/'build/arm-a-ui-wiring-v1'
    ui=ROOT/'build/rider-ui-wiring-v1'
    if backend.exists() or ui.exists():
        raise ValueError('Preserve frozen contexts; use a new version')
    previous=ROOT/'build/arm-a-auth-retention-v3/arm_a_release.json'
    assert sha(previous)=='15e0786b62bf09e453f384b9b32edf71431c93c3987d7a3c411a5d45b1bf8a4f'
    release=json.loads(previous.read_text())
    release.update(created_at=datetime.now(timezone.utc).isoformat(),patch_version='arm-a-ui-wiring-v1',base_image=BASE)
    bindings={}
    for name in FILES:
        target=backend/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target)
        release['file_sha256'][name]=bindings[name]=sha(target)
    (backend/'arm_a_release.json').write_text(json.dumps(release,indent=2)+'\n',encoding='utf-8')
    code="from pathlib import Path; import unittest; import test_approved_integration as f; f.ROOT=Path('/app'); f.INDEX=Path('/app/build/index'); suite=unittest.defaultTestLoader.loadTestsFromNames("+repr(TESTS)+"); r=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not r.wasSuccessful())"
    (backend/'Dockerfile').write_text('FROM '+BASE+'\nUSER root\nCOPY --chown=motomedic:motomedic . /app\nRUN python -B -c '+json.dumps(code)+'\nUSER motomedic\n',encoding='utf-8')
    ui_bindings={}
    for source in (ROOT/'rider_ui').rglob('*'):
        if not source.is_file() or '__pycache__' in source.parts:
            continue
        relative=source.relative_to(ROOT)
        # Only runtime modules/style/requirements and software checks.
        if relative.suffix not in ('.py','.css','.txt','.json') or 'design_review' in relative.parts:
            continue
        target=ui/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        ui_bindings[str(relative).replace('\\','/')]=sha(target)
    shutil.copyfile(ROOT/'rider_ui/Dockerfile',ui/'Dockerfile')
    for context,name in ((backend,'arm-a'),(ui,'rider-ui')):
        image='us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/'+name+':ui-wiring-v1'
        recipe={'steps':[{'name':'gcr.io/cloud-builders/docker','args':['build','-t',image,'.']}], 'images':[image], 'timeout':'1200s','options':{'machineType':'E2_HIGHCPU_8','logging':'CLOUD_LOGGING_ONLY'}}
        (context/'cloudbuild.json').write_text(json.dumps(recipe,indent=2)+'\n',encoding='utf-8')
    receipt={'schema_version':'arm-a-ui-wiring-preparation-v1','created_at':datetime.now(timezone.utc).isoformat(),'base_image':BASE,'backend_context':str(backend.relative_to(ROOT)), 'ui_context':str(ui.relative_to(ROOT)), 'backend_bindings':bindings,'ui_bindings':ui_bindings,'release_sha256':sha(backend/'arm_a_release.json'),'backend_recipe_sha256':sha(backend/'Dockerfile'),'ui_recipe_sha256':sha(ui/'Dockerfile'),'independent_review':'PENDING','hosted_tests':'PENDING','deployed':False,'provider_calls':0,'public_access':False}
    output=ROOT/'reports/arm_a/ui_wiring_v1/preparation.json'
    output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'backend':str(backend),'ui':str(ui),'release_sha256':receipt['release_sha256']}))


if __name__=='__main__':
    main()
