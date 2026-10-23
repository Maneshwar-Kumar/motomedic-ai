"""Prepare exact v8 image overlays offline. Never build, deploy or read secrets."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FREEZE = 'reports/grounded_generation/v8/runtime_manifest.json'
BASE_RELEASE = 'reports/arm_a/policy_caveats_v2/frozen_context/arm_a_release.json'
BASE_RELEASE_SHA = '53263ad531b6ce0170ef6fa6bce511375a4fc1bf1abf24377c6841dda5a15ad8'
BASE_IMAGE = 'us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:a8946299f34177aeda76cadbbd7fce0a33c5fd8f574438d823281ee78eb045e4'
OUT = 'reports/grounded_generation/v8/release_readiness/packaging'
BACKEND = 'build/draft-verify-stream-backend-v8'
UI = 'build/draft-verify-stream-ui-v8'
REQUIRED = {'cloud/grounded_generation/' + name + '.py' for name in
            ('verified_qa', 'open_questions', 'source_authority', 'provider',
             'claude_provider', 'fallback_provider', 'claude_budget', 'admission', 'delivery')}
REQUIRED.update(('cloud/arm_a/app.py', 'cloud/arm_a/store.py', 'cloud/arm_a/rider_api.py'))
UI_RUNTIME = ['rider_ui/' + name for name in ('__init__.py', 'app.py', 'client.py',
              'safeguards.py', 'identity.py', 'verified_sse.py', 'theme.css', 'requirements.txt')]
UI_TESTS = ['rider_ui/tests/' + name for name in ('__init__.py', 'test_client.py',
            'test_identity.py', 'test_safeguards.py', 'test_verified_sse.py',
            'test_progress_stream.py', 'test_app.py', 'fixture_api.py')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(root, name):
    p = root / name
    if not p.resolve().is_relative_to(root.resolve()) or Path(name).is_absolute():
        raise ValueError('UNSAFE_PACKAGE_PATH:' + name)
    return p


def git_blobs(root, names):
    """One Git request verifies exact committed bytes; no shell interpolation."""
    if any('\n' in n or '\r' in n for n in names):
        raise ValueError('INVALID_GIT_PATH')
    result = subprocess.run(['git', 'cat-file', '--batch'], cwd=root,
                            input=''.join('HEAD:' + n + '\n' for n in names).encode(),
                            capture_output=True, check=True)
    reader = io.BytesIO(result.stdout)
    values = {}
    for name in names:
        header = reader.readline().split()
        if len(header) != 3 or header[1] != b'blob':
            raise ValueError('FILE_NOT_COMMITTED:' + name)
        values[name] = reader.read(int(header[2]))
        if reader.read(1) != b'\n':
            raise ValueError('GIT_BLOB_PROTOCOL')
    return values


def verify_bindings(root, bindings, committed):
    for name, expected in bindings.items():
        if sha(safe_path(root, name)) != expected:
            raise ValueError('FROZEN_WORKTREE_CHANGED:' + name)
        if hashlib.sha256(committed[name]).hexdigest() != expected:
            raise ValueError('FROZEN_GIT_CHANGED:' + name)


def release_check(root, release):
    """Same complete file-hash check that load_production performs before startup."""
    for name, expected in release['file_sha256'].items():
        if sha(safe_path(root, name)) != expected:
            raise ValueError('Production runtime binding mismatch:' + name)


def production_files(bindings):
    # Evaluation datasets, provider runners, tests and workflows are not serving inputs.
    names = {n for n in bindings if not n.startswith(('tools/', '.github/'))
             and '/tests/' not in n and not Path(n).name.startswith('test_')}
    if not REQUIRED <= names:
        raise ValueError('MISSING_REQUIRED_ADAPTER_OR_STORE')
    return sorted(names)


def recipe(image):
    return {'steps': [{'name': 'gcr.io/cloud-builders/docker',
                      'args': ['build', '-t', image, '.']}], 'images': [image],
            'timeout': '1800s',
            'options': {'machineType': 'E2_HIGHCPU_8', 'logging': 'CLOUD_LOGGING_ONLY'}}


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    write_exact(path, (json.dumps(data, indent=2, sort_keys=True) + '\n').encode())


def write_exact(path, raw):
    """A fresh checkout can reconstruct contexts without rewriting saved receipts."""
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('PREPARED_REPORT_CHANGED:' + str(path))
        return
    path.write_bytes(raw)


def prepare(root=ROOT):
    root = root.resolve()
    manifest = json.loads((root / FREEZE).read_bytes())
    serving = root / 'reports/grounded_generation/v8/runtime_freeze.json'
    if sha(serving) != manifest['serving_freeze_manifest_sha256']:
        raise ValueError('SERVING_FREEZE_BINDING_CHANGED')
    if json.loads(serving.read_bytes())['file_sha256'] != manifest['file_sha256']:
        raise ValueError('SERVING_EVALUATION_FREEZE_DIFFER')
    if sha(root / BASE_RELEASE) != BASE_RELEASE_SHA:
        raise ValueError('BASE_RELEASE_CHANGED')
    names = production_files(manifest['file_sha256'])
    ui_files = UI_RUNTIME + UI_TESTS + ['controller_contracts.py', 'rider_ui/Dockerfile']
    all_inputs = sorted(set(manifest['file_sha256']) | set(ui_files))
    committed = git_blobs(root, all_inputs)
    verify_bindings(root, manifest['file_sha256'], committed)
    # Dependencies outside the serving freeze are packaged only if unchanged in Git.
    extra_names = sorted(n for n in ui_files if n not in manifest['file_sha256'])
    # Supplementary UI assets can have checkout CRLF conversion. Package their
    # committed blobs, after Git confirms there are no unpublished modifications.
    clean = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', *extra_names], cwd=root)
    if clean.returncode:
        raise ValueError('UNCOMMITTED_UI_DEPENDENCY')
    extras = {n: hashlib.sha256(committed[n]).hexdigest() for n in extra_names}
    destinations = [root / BACKEND, root / UI, root / OUT]
    if any(p.exists() for p in destinations[:2]):
        raise ValueError('Preserve prepared contexts; never overwrite a version')
    backend, ui, report = destinations
    for p in destinations:
        p.mkdir(parents=True, exist_ok=True)
    base = json.loads((root / BASE_RELEASE).read_bytes())
    release = dict(base)
    release['file_sha256'] = dict(base['file_sha256'])
    overlay = {}
    for name in names:
        target = backend / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(committed[name])
        overlay[name] = release['file_sha256'][name] = sha(target)
    # Remove old method/held-count fields rather than carrying historical approval labels forward.
    for key in ('created_at', 'question_policy', 'source_context_approved', 'source_context_held'):
        release.pop(key, None)
    release.update(schema_version='draft-verify-stream-prepared-release-v8',
        architecture='DRAFT_VERIFY_STREAM_OPEN_MANUAL_QA', streaming='DRAFT_VERIFY_STREAM',
        question_policy='open-manual-draft-verify-v8', patch_version='draft-verify-stream-private-v8',
        base_image=BASE_IMAGE, source_authority='EXACT_EXISTING_SOURCE_OBJECT_BINDINGS_UNCHANGED',
        scope='Applicable manual evidence; private complete draft, separate exact-final-response semantic verification, final integrity and durable save before buffered delivery. No universal authored action/question gates.',
        provider_calls='COUNTED_ALL_PAID_ATTEMPTS', separate_semantic_verifier_calls='REQUIRED_PER_TECHNICAL_RESPONSE',
        provider_default='gemma-4-26b-a4b-it', provider_optional_fallback='claude-haiku-5-5',
        fallback_disabled_by_default=True, maximum_nonrecurring_claude_usd=1,
        exact_response_cache='DISABLED', benchmark_pacing=False,
        runtime_freeze_sha256=sha(serving), evaluation_manifest_sha256=sha(root / FREEZE),
        manual_checksum=manifest['manual_checksum'], index_id=manifest['index_id'],
        prepared_only=True, deployment_authorized=False, public_release_approved=False,
        actual_output_acceptance='SEPARATE_VERSION_BOUND_REVIEW_REQUIRED')
    dump(backend / 'arm_a_release.json', release)
    release_check(backend, {'file_sha256': overlay})
    # Run the full inherited+overlay check against the actual base filesystem only
    # during an independently authorized build. No model or provider is initialized.
    check = ('from pathlib import Path\nimport hashlib,json\n'
             'root=Path("/app")\nrelease=json.loads((root/"arm_a_release.json").read_bytes())\n'
             'for name,expected in release["file_sha256"].items():\n'
             '    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:\n'
             '        raise RuntimeError("Production runtime binding mismatch:"+name)\n'
             'print("Complete installed release bindings verified; no provider calls")\n')
    (backend / 'verify_installed_release.py').write_text(check, encoding='utf-8', newline='\n')
    docker = (f'FROM {BASE_IMAGE}\nUSER root\nCOPY --chown=motomedic:motomedic . /app\n'
              'RUN python -B /app/verify_installed_release.py\nUSER motomedic\n')
    (backend / 'Dockerfile').write_text(docker, encoding='utf-8', newline='\n')
    dump(backend / 'cloudbuild.json', recipe('us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a:draft-verify-stream-v8'))
    for name in ui_files:
        target = ui / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(committed[name])
    (ui / 'Dockerfile').write_bytes(committed['rider_ui/Dockerfile'])
    dump(ui / 'cloudbuild.json', recipe('us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/rider-ui:draft-verify-stream-v8'))
    ui_bindings = {n: sha(ui / n) for n in ui_files}
    for prefix, context in [('backend', backend), ('ui', ui)]:
        for name in ('Dockerfile', 'cloudbuild.json'):
            write_exact(report / (prefix + '_' + name), (context / name).read_bytes())
    write_exact(report / 'backend_release.json', (backend / 'arm_a_release.json').read_bytes())
    dump(report / 'ui_release.json', {'schema_version': 'draft-verify-stream-ui-prepared-v8',
         'runtime_policy': 'open-manual-draft-verify-v8', 'file_sha256': ui_bindings,
         'runtime_image_files': UI_RUNTIME, 'test_files_only_in_build_stage': UI_TESTS,
         'provider_keys_in_ui': False, 'prepared_only': True})
    inherited = {n: h for n, h in release['file_sha256'].items() if n not in overlay}
    receipt = {'schema_version': 'draft-verify-stream-packaging-v8',
         'freeze_sha256': sha(serving), 'evaluation_manifest_sha256': sha(root / FREEZE),
         'frozen_git_and_worktree_objects_verified': len(manifest['file_sha256']),
         'base_image': BASE_IMAGE, 'base_release_sha256': BASE_RELEASE_SHA,
         'backend_context': BACKEND, 'ui_context': UI, 'release_sha256': sha(backend / 'arm_a_release.json'),
         'backend_overlay_bindings': overlay, 'ui_bindings': ui_bindings,
         'supplemental_committed_ui_dependencies': extras,
         'inherited_bindings': inherited, 'inherited_image_bytes_verified_offline': False,
         'installed_full_release_check': 'Mandatory Docker RUN before future build can succeed',
         'backend_overlay_release_check': 'PASS',
         'heldout_questions_or_answers_packaged': False,
         'no_whole_manual_new_copy': True, 'source_approval_bytes_changed': False,
         'build_executed': False, 'provider_calls': 0, 'deployment_changed': False,
         'billing_changed': False, 'secrets_read_or_transferred': False,
         'future_activation': 'Requires separate authorization, managed backend provider secrets, compatible service revisions and live durable-stream/recovery acceptance.'}
    dump(report / 'preparation.json', receipt)
    return receipt


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    receipt = prepare()
    print(json.dumps({k: receipt[k] for k in ('backend_context', 'ui_context',
                                            'frozen_git_and_worktree_objects_verified', 'release_sha256')}))


if __name__ == '__main__':
    main()
