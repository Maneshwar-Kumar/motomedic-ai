"""Prepare a private overlay; no cloud mutation and no evaluation answers packaged."""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:a8946299f34177aeda76cadbbd7fce0a33c5fd8f574438d823281ee78eb045e4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',choices=('v4','v5'),default='v4')
    version=parser.parse_args().version
    frozen=ROOT/f'reports/grounded_generation/{version}/runtime_freeze.json'
    manifest=json.loads(frozen.read_bytes())
    context=ROOT/f'build/grounded-private-{version}'
    assert not context.exists(),'Do not overwrite an existing frozen context'
    release=json.loads((ROOT/'reports/arm_a/policy_caveats_v2/frozen_context/arm_a_release.json').read_bytes())
    files=[name for name in manifest['file_sha256'] if name.startswith('cloud/') or name.startswith('reports/grounded_generation/')]
    for name in files:
        assert sha(ROOT/name)==manifest['file_sha256'][name],name
        target=context/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target);release['file_sha256'][name]=sha(target)
    release.update(schema_version='grounded-serving-release-'+version,architecture='MANUAL_EVIDENCE_GROUNDED_LLM',
        scope='Private open-question generation from applicable complete reviewed evidence; typed controller, source-context holds, deterministic citation/step/warning gates. No separate semantic verifier; no public source delivery or vision acceptance.',
        provider_calls='COUNTED_PER_REQUEST',separate_semantic_verifier_calls=0,
        patch_version='grounded-private-'+version,base_image=BASE,public_release_approved=False,
        runtime_freeze_sha256=sha(frozen),source_context_approved=184,source_context_held=334)
    (context/'arm_a_release.json').write_text(json.dumps(release,indent=2)+'\n',encoding='utf-8',newline='\n')
    tests=['cloud.grounded_generation.test_provider','cloud.grounded_generation.test_context','cloud.grounded_generation.test_admission','cloud.grounded_generation.test_scope','cloud.grounded_generation.test_source_context','cloud.grounded_generation.test_fuse_refusal','cloud.grounded_generation.test_feedback','cloud.grounded_generation.test_runtime','cloud.arm_a.test_api','cloud.arm_a.test_store','test_approved_integration']
    if version=='v5':tests+=['cloud.grounded_generation.test_source_authority','cloud.grounded_generation.test_generic_runtime','cloud.grounded_generation.test_transitions']
    command='python -B -m unittest -v '+' '.join(tests)
    docker='FROM '+BASE+'\nUSER root\nCOPY --chown=motomedic:motomedic . /app\nENV MOTOMEDIC_TEST_INDEX=/app/build/index\nRUN '+command+'\nUSER motomedic\n'
    (context/'Dockerfile').write_text(docker,encoding='utf-8',newline='\n')
    image='us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a:grounded-private-'+version
    build={'steps':[{'name':'gcr.io/cloud-builders/docker','args':['build','-t',image,'.']}],
        'images':[image],'timeout':'1800s','options':{'machineType':'E2_HIGHCPU_8','logging':'CLOUD_LOGGING_ONLY'}}
    (context/'cloudbuild.json').write_text(json.dumps(build,indent=2)+'\n',encoding='utf-8',newline='\n')
    out=ROOT/f'reports/grounded_generation/{version}/deployment_preparation.json'
    out.write_text(json.dumps({'base_image':BASE,'context':str(context.relative_to(ROOT)),
        'image_tag':image,'release_sha256':sha(context/'arm_a_release.json'),
        'files':{name:sha(context/name) for name in files},'heldout_questions_packaged':False,
        'public_access_opened':False,'source_approval_bytes_changed':False},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'context':str(context.relative_to(ROOT)),'release_sha256':sha(context/'arm_a_release.json'),'files':len(files)}))
if __name__=='__main__':main()
