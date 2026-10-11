"""Prepare a small reviewed overlay on the immutable hosted Arm A image.

No model download, parsing, embedding or inference. Original source bindings
remain frozen; changed runtime/test files get exact new patch bindings.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = 'us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:69111a77da8a045b5b870e95ed2305c63d8c26cac2732a1a33a515489ef7bad6'
FILES = ['cloud/arm_a/app.py', 'cloud/arm_a/store.py', 'cloud/arm_a/test_api.py',
         'cloud/arm_a/test_store.py', 'cloud/arm_a/test_composer.py',
         'test_approved_integration.py', 'test_text_journeys.py', 'test_constrained_generator.py',
         'verify_controller.py', 'reports/ab30_v2_source_assessment_baseline.json']


def main():
    destination = ROOT/'build/arm-a-auth-retention-v3'
    if destination.exists():
        raise ValueError('Patch context already exists; preserve prior bytes')
    original = ROOT/'build/arm-a-release-v5/arm_a_release.json'
    assert hashlib.sha256(original.read_bytes()).hexdigest() == '66fb99d81a8c7acc4a22c620aed2c028a75765ff4bcea5e96e85ea17429991b4'
    release = json.loads(original.read_text())
    release['created_at'] = datetime.now(timezone.utc).isoformat()
    release['patch_version'] = 'arm-a-auth-retention-v3'
    release['base_image'] = BASE
    patch = {}
    for name in FILES:
        target = destination/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        release['file_sha256'][name] = patch[name] = digest
    (destination/'arm_a_release.json').write_text(json.dumps(release,indent=2)+'\n',encoding='utf-8')
    docker = ('FROM '+BASE+'\nUSER root\nCOPY --chown=motomedic:motomedic . /app\n'
        'RUN python -B -c "from pathlib import Path; import unittest; '
        'import test_approved_integration as f; f.ROOT=Path(\'/app\'); f.INDEX=Path(\'/app/build/index\'); '
        'suite=unittest.defaultTestLoader.loadTestsFromNames([\'cloud.arm_a.test_api\', '
        '\'cloud.arm_a.test_store\', \'cloud.arm_a.test_composer\', \'test_approved_integration\', '
        '\'test_text_journeys\', \'test_constrained_generator\']); '
        'r=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not r.wasSuccessful())"\n'
        'USER motomedic\n')
    (destination/'Dockerfile').write_text(docker,encoding='utf-8')
    recipe = {'steps':[{'name':'gcr.io/cloud-builders/docker','args':['build','-t',
        'us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a:auth-retention-v3','.' ]}],
        'images':['us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a:auth-retention-v3'],
        'timeout':'900s','options':{'machineType':'E2_HIGHCPU_8','logging':'CLOUD_LOGGING_ONLY'}}
    (destination/'cloudbuild.json').write_text(json.dumps(recipe,indent=2)+'\n',encoding='utf-8')
    receipt = {'schema_version':'arm-a-patch-preparation-v3','base_image':BASE,
        'context':str(destination.relative_to(ROOT)).replace('\\','/'),
        'patch_file_sha256':patch, 'release_sha256':hashlib.sha256((destination/'arm_a_release.json').read_bytes()).hexdigest(),
        'recipe_sha256':hashlib.sha256((destination/'Dockerfile').read_bytes()).hexdigest(),
        'cloudbuild_sha256':hashlib.sha256((destination/'cloudbuild.json').read_bytes()).hexdigest(),
        'scope':'Sanitized auth rejection diagnostics and RFC case-insensitive bearer scheme; dedicated24h snapshot namespace; initial30 only',
        'provider_calls':0,'source_scope_changed':False,'shared_versions_ttl':False,
        'new_private_rollout_authorized_by_original_integration_instruction':True,
        'independent_review_status':'PENDING','hosted_tests':'PENDING','deployed':False}
    output=ROOT/'reports/arm_a/integration_v1/patch_preparation_v3.json'
    output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    main()
