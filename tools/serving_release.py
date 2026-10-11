"""Preserve history, freeze current serving inputs and prepare hosted image contexts.

Preparation and checks use no providers, cloud writes, builds or secret reads.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import gzip
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cloud.serving_artifacts import (ObjectReference, confined, digest,
    ORIGINAL_INDEX_MANIFEST_SHA256, qdrant_lock_policy, restore_qdrant_lock, verify_index)

BASELINE = '7cd58405e5e8a98abc0c272336249443d231d7ad'
HISTORICAL = 'reports/grounded_generation/v8/runtime_freeze.json'
HISTORICAL_SHA = 'd7990e2fc2863c05f9c4332d4a2df76354be6fbfe49c2430bbbc7f83990c70e0'
PRESERVED = 'reports/build/20261012/frozen_v8_runtime'
MIGRATION = 'reports/build/20261012/v8_preservation.json'
CURRENT = 'reports/build/20261012/serving_manifest_v9_1.json'
INDEX = 'index_a3282c4d98cf54595e4ba168'
MANUAL_SHA = 'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'
APPROVAL = 'human_review/agent_release_161/coordinator/release_manifest_v3.json'
APPROVAL_SHA = 'b8f8c7b5a9e1a299f0a90eecbf10127779b62b35fc105f0cd587de433e235298'
BASE_IMAGE = 'us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:a8946299f34177aeda76cadbbd7fce0a33c5fd8f574438d823281ee78eb045e4'
IMAGE_REPOSITORY = 'us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic'
UI_BASE_IMAGE = 'docker.io/library/python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1'


def dump(path, value, *, exclusive=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
    if path.exists():
        if exclusive and path.read_bytes() != raw:
            raise ValueError('NEVER_OVERWRITE_VERSIONED_RELEASE:' + str(path))
        if path.read_bytes() == raw:
            return
    path.write_bytes(raw)


def git_blobs(root, names, revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('FULL_COMMIT_REQUIRED')
    names = sorted(names)
    for name in names:
        confined(root, name)
        if '\r' in name or '\n' in name:
            raise ValueError('INVALID_GIT_PATH')
    value = subprocess.run(['git', 'cat-file', '--batch'], cwd=root, check=True,
        input=''.join(revision + ':' + name + '\n' for name in names).encode(), capture_output=True)
    reader, result = io.BytesIO(value.stdout), {}
    for name in names:
        header = reader.readline().split()
        if len(header) != 3 or header[1] != b'blob':
            raise ValueError('COMMITTED_INPUT_MISSING:' + name)
        result[name] = reader.read(int(header[2]))
        if reader.read(1) != b'\n':
            raise ValueError('GIT_BATCH_PROTOCOL')
    return result


def historical_bindings(root):
    path = confined(root, HISTORICAL)
    if digest(path) != HISTORICAL_SHA:
        raise ValueError('HISTORICAL_FREEZE_CHANGED')
    return json.loads(path.read_bytes())['file_sha256']


def preserve_v8(root=ROOT):
    bindings = historical_bindings(root)
    blobs = git_blobs(root, bindings, BASELINE)
    mapping = {}
    for name, expected in bindings.items():
        raw = blobs[name]
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('BASELINE_FROZEN_OBJECT_MISMATCH:' + name)
        target_name = PRESERVED + '/' + name
        target = confined(root, target_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != raw:
            raise ValueError('PRESERVED_HISTORICAL_BYTES_CHANGED:' + name)
        if not target.exists():
            target.write_bytes(raw)
        mapping[name] = {'preserved_path': target_name, 'sha256': expected}
    receipt = {'schema_version': 'v8-exact-runtime-preservation-v1',
        'baseline_commit': BASELINE, 'frozen_manifest': HISTORICAL,
        'frozen_manifest_sha256': HISTORICAL_SHA, 'objects': mapping,
        'original_source_approval_paths_changed': False,
        'purpose': 'Historical failed-run reproducibility; current serving is separately bound in v9.'}
    dump(confined(root, MIGRATION), receipt)
    return receipt


def verify_history(root=ROOT):
    bindings = historical_bindings(root)
    receipt = json.loads(confined(root, MIGRATION).read_bytes())
    if (receipt['baseline_commit'] != BASELINE or receipt['frozen_manifest'] != HISTORICAL
            or receipt['frozen_manifest_sha256'] != HISTORICAL_SHA
            or set(receipt['objects']) != set(bindings)):
        raise ValueError('HISTORICAL_MIGRATION_BINDING_CHANGED')
    for name, expected in bindings.items():
        entry = receipt['objects'][name]
        if entry != {'preserved_path': PRESERVED + '/' + name, 'sha256': expected}:
            raise ValueError('HISTORICAL_MIGRATION_OBJECT_CHANGED:' + name)
        if digest(confined(root, entry['preserved_path'])) != expected:
            raise ValueError('HISTORICAL_SNAPSHOT_CHANGED:' + name)
    return len(bindings)


def serving_inputs(root=ROOT):
    """Discover complete code/UI/build inputs so added unbound modules fail CI."""
    names = set(historical_bindings(root))
    for folder in ('cloud/arm_a', 'cloud/grounded_generation', 'rider_ui'):
        for path in (Path(root) / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py', '.css', '.txt', '.yaml', '.json'):
                names.add(path.relative_to(root).as_posix())
    for path in (Path(root) / '.github/workflows').glob('*'):
        if path.suffix in ('.yml', '.yaml'):
            names.add(path.relative_to(root).as_posix())
    names.update(('cloud/serving_artifacts.py', 'cloud/test_serving_artifacts.py',
        'cloud/deployment_status.json', 'cloud/live_smoke.json',
        'cloud/arm_a/Dockerfile', 'rider_ui/Dockerfile', 'tools/serving_release.py',
        'tools/test_serving_release.py', 'tools/check_repository_structure.py',
        'tools/capture_serving_artifact.py', 'tools/check_installed_serving_release.py',
        'tools/test_build_candidate.py', 'tools/resolve_container_base.py',
        'tools/bind_serving_images.py', 'tools/test_bind_serving_images.py',
        'tools/validate_serving_artifacts_hosted.py',
        'reports/build/20261012/ui_base_image.json',
        'reports/build/20261012/ui_dependency_lock.json',
        'reports/build/20261012/index_snapshot_reference.json', MIGRATION))
    names.add('reports/build/20261012/qdrant_lock_recovery.json')
    # Retained root compatibility modules consumed by the serving imports.
    names.update(path.name for path in Path(root).glob('*.py') if not path.name.startswith('test_'))
    # All exact source approvals remain at original immutable paths.
    approved = json.loads(confined(root, APPROVAL).read_bytes())
    names.update(approved['outputs'])
    names.update((APPROVAL, 'human_review/agent_release_161/owner_authority.json',
        'human_review/agent_release_161/approval_consumer.py',
        'human_review/agent_release_161/root_validation_v3.json'))
    for path in (Path(root) / 'reports/build/20261012/source_context_refinement_v2').glob('*.json'):
        names.add(path.relative_to(root).as_posix())
    return sorted(names)


def index_policy(root, index_dir, reference_path=None):
    index_dir = Path(index_dir)
    manifest = json.loads((index_dir / 'manifest.json').read_bytes())
    if manifest['index_id'] != INDEX or manifest['source_sha256'] != MANUAL_SHA:
        raise ValueError('IMMUTABLE_INDEX_IDENTITY_CHANGED')
    if digest(index_dir / 'manifest.json') != ORIGINAL_INDEX_MANIFEST_SHA256:
        raise ValueError('IMMUTABLE_INDEX_MANIFEST_CHANGED')
    identity = {'index_id': INDEX, 'manual_sha256': MANUAL_SHA,
        'manifest_sha256': ORIGINAL_INDEX_MANIFEST_SHA256,
        'file_sha256': manifest['file_checksums'], 'embedding': manifest['embedding'],
        'chunker': manifest['chunker'], 'chunks': manifest['counts']['chunks'],
        'parents': manifest['counts']['parent_sections'],
        'deterministic_file_recovery':qdrant_lock_policy()}
    restore_qdrant_lock(index_dir, identity)
    verify_index(index_dir, identity)
    recorded = json.loads((Path(root) / 'cloud/deployment_status.json').read_bytes())
    snapshot = {'uri': recorded['snapshot_uri'], 'sha256': recorded['snapshot_sha256'],
        'generation': None, 'maximum_bytes': 1024**3}
    if reference_path:
        snapshot = json.loads(Path(reference_path).read_bytes())
        ObjectReference(**snapshot)
        if snapshot['uri'] != recorded['snapshot_uri'] or snapshot['sha256'] != recorded['snapshot_sha256']:
            raise ValueError('RECORDED_IMMUTABLE_SNAPSHOT_CHANGED')
    return {**identity,
        'parser_gap_pages': manifest['counts']['parser_gap_pages'],
        'snapshot': snapshot,
        'durable_reference_status': 'PINNED' if snapshot['generation'] else 'OBJECT_GENERATION_RECEIPT_REQUIRED',
        'query_models': 'Inherited exact base image assets; no document embedding or request-time model download.'}


def freeze(root=ROOT, *, index_dir=None, reference_path=None, destination=CURRENT):
    root = Path(root).resolve()
    target = confined(root, destination)
    if target.exists():
        raise ValueError('NEVER_OVERWRITE_SERVING_FREEZE')
    verify_history(root)
    if digest(confined(root, APPROVAL)) != APPROVAL_SHA:
        raise ValueError('EXACT_SOURCE_APPROVAL_CHANGED')
    names = serving_inputs(root)
    bindings = {name: digest(confined(root, name)) for name in names}
    value = {'schema_version': 'motomedic-serving-release-v9',
        'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'architecture': 'DRAFT_VERIFY_STREAM_OPEN_MANUAL_QA',
        'source_baseline_commit': BASELINE, 'candidate_source_commit': None,
        'source_commit_status': 'COMMITTED_BLOB_CHECK_REQUIRED_BEFORE_HOSTED_BUILD',
        'file_sha256': bindings,
        'input_tree_sha256': hashlib.sha256(json.dumps(bindings, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'source_approval': {'path': APPROVAL, 'sha256': APPROVAL_SHA,
            'scope': 'EXACT_SOURCE_CONTENT_AND_INITIAL_SCOPES; NOT_DEPLOYMENT_OR_GENERAL_GENERATION_ACCEPTANCE'},
        'manual_checksum': MANUAL_SHA, 'index_id': INDEX,
        'index': index_policy(root, index_dir or root / 'build/index-bge-final', reference_path),
        'primary_model': 'gemma-4-26b-a4b-it', 'fallback_model': 'claude-haiku-5-5',
        'fallback_enabled': False, 'answer_cache_enabled': False,
        'backend_base_image': BASE_IMAGE,
        'ui_base_image': UI_BASE_IMAGE,
        'backend_image_digest': None, 'ui_image_digest': None,
        'provider_calls': 0, 'build_executed': False, 'deployment_authorized': False,
        'public_release_approved': False, 'billing_changed': False,
        'acceptance': 'SYNTHETIC_BOUNDARY_CHECKS_ONLY; HOSTED_AND_ORIGINAL_SOURCE_ACCEPTANCE_REQUIRED'}
    dump(target, value)
    (target.with_suffix('.sha256')).write_text(digest(target) + '\n', encoding='ascii')
    return value


def verify(root=ROOT, manifest_path=CURRENT, *, committed_revision=None):
    root = Path(root).resolve()
    verify_history(root)
    path = confined(root, manifest_path)
    manifest = json.loads(path.read_bytes())
    if manifest.get('schema_version') != 'motomedic-serving-release-v9':
        raise ValueError('WRONG_SERVING_MANIFEST_SCHEMA')
    if path.with_suffix('.sha256').read_text().strip() != digest(path):
        raise ValueError('SERVING_MANIFEST_DIGEST_CHANGED')
    expected_names = set(serving_inputs(root))
    if set(manifest['file_sha256']) != expected_names:
        raise ValueError('SERVING_INPUT_INVENTORY_CHANGED')
    if (manifest['manual_checksum'] != MANUAL_SHA or manifest['index_id'] != INDEX
            or manifest['source_approval']['sha256'] != APPROVAL_SHA
            or manifest['fallback_enabled'] is not False or manifest['answer_cache_enabled'] is not False
            or manifest['backend_base_image'] != BASE_IMAGE
            or manifest.get('ui_base_image') != UI_BASE_IMAGE):
        raise ValueError('SERVING_POLICY_BINDING_CHANGED')
    tree_hash = hashlib.sha256(json.dumps(manifest['file_sha256'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if tree_hash != manifest['input_tree_sha256']:
        raise ValueError('SERVING_INPUT_TREE_CHANGED')
    for name, expected in manifest['file_sha256'].items():
        if digest(confined(root, name)) != expected:
            raise ValueError('SERVING_INPUT_CHANGED:' + name)
    if committed_revision:
        blobs = git_blobs(root, manifest['file_sha256'], committed_revision)
        for name, expected in manifest['file_sha256'].items():
            if hashlib.sha256(blobs[name]).hexdigest() != expected:
                raise ValueError('COMMITTED_SERVING_INPUT_CHANGED:' + name)
    return manifest


def prepare(root=ROOT, manifest_path=CURRENT, *, committed_revision=None):
    if not committed_revision:
        raise ValueError('COMMITTED_REVISION_REQUIRED_FOR_BUILD_CONTEXT')
    manifest = verify(root, manifest_path, committed_revision=committed_revision)
    ObjectReference(**manifest['index']['snapshot'])
    root = Path(root)
    revision = re.fullmatch(r'serving_manifest_(v9(?:_[1-9][0-9]*)?)', Path(manifest_path).stem)
    if revision is None:
        raise ValueError('VERSIONED_V9_SERVING_MANIFEST_NAME_REQUIRED')
    revision = revision.group(1)
    output = root / 'build' / ('serving-' + revision)
    if output.exists():
        raise ValueError('NEVER_OVERWRITE_PREPARED_BUILD_CONTEXT')
    blobs = git_blobs(root, manifest['file_sha256'], committed_revision)
    for kind in ('backend', 'ui'):
        context = output / kind
        context.mkdir(parents=True)
        for name, raw in blobs.items():
            if kind == 'ui' and not (name.startswith('rider_ui/') or name == 'controller_contracts.py'):
                continue
            if kind == 'backend' and ('/test_' in name or '/tests/' in name or name.startswith('.github/')
                    or (name.startswith('tools/') and name != 'tools/check_installed_serving_release.py')):
                continue
            target = confined(context, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        installed = dict(manifest)
        installed['candidate_source_commit'] = committed_revision
        installed['source_commit_status'] = 'EXACT_COMMITTED_BLOBS_VERIFIED'
        installed['file_sha256'] = {n: h for n, h in manifest['file_sha256'].items()
            if (context / n).is_file()}
        dump(context / 'arm_a_release.json', installed)
        if kind == 'backend':
            docker = (f'FROM {BASE_IMAGE}\nUSER root\nCOPY --chown=motomedic:motomedic . /app\n'
                'RUN python -B tools/check_installed_serving_release.py /app\n'
                'USER motomedic\n'
                'CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "1200", "--access-logfile", "-", "cloud.arm_a.app:load_production()"]\n')
        else:
            docker = blobs['rider_ui/Dockerfile'].decode()
        (context / 'Dockerfile').write_text(docker, encoding='utf-8', newline='\n')
        image = IMAGE_REPOSITORY + '/' + ('arm-a' if kind == 'backend' else 'rider-ui') + ':serving-v9-' + manifest['input_tree_sha256'][:12]
        substitutions = {'_SERVING_MANIFEST_SHA256': digest(root / manifest_path),
            '_INPUT_TREE_SHA256': manifest['input_tree_sha256'], '_SOURCE_COMMIT': committed_revision}
        labels = ['--label', 'org.motomedic.serving-manifest-sha256=' + substitutions['_SERVING_MANIFEST_SHA256'],
            '--label', 'org.motomedic.input-tree-sha256=' + substitutions['_INPUT_TREE_SHA256'],
            '--label', 'org.opencontainers.image.revision=' + committed_revision]
        dump(context / 'cloudbuild.json', {'steps': [{'name': 'gcr.io/cloud-builders/docker',
            'args': ['build', '--platform=linux/amd64', *labels, '-t', image, '.']}],
            'substitutions': substitutions, 'images': [image], 'timeout': '1800s',
            'options': {'logging': 'CLOUD_LOGGING_ONLY', 'substitutionOption':'ALLOW_LOOSE'}})
        # Canonical archive bytes can be uploaded later under a generation-pinned
        # reference. Never rely on an expiring Actions artifact as a build source.
        with (output / (kind + '.tar.gz')).open('xb') as packed:
            with gzip.GzipFile(fileobj=packed, filename='', mode='wb', mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode='w') as archive:
                    for path in sorted(p for p in context.rglob('*') if p.is_file()):
                        info = tarfile.TarInfo(path.relative_to(context).as_posix())
                        info.size, info.mode, info.mtime = path.stat().st_size, 0o644, 0
                        with path.open('rb') as source:
                            archive.addfile(info, source)
    receipt = {'schema_version': 'serving-v9-hosted-build-preparation-v1',
        'source_commit': committed_revision, 'serving_manifest_sha256': digest(root / manifest_path),
        'input_tree_sha256': manifest['input_tree_sha256'], 'base_image': BASE_IMAGE,
        'contexts': {kind: {'path': str((output / kind).relative_to(root)).replace('\\', '/'),
            'dockerfile_sha256': digest(output / kind / 'Dockerfile'),
            'cloudbuild_sha256': digest(output / kind / 'cloudbuild.json'),
            'build_steps': json.loads((output / kind / 'cloudbuild.json').read_bytes())['steps'],
            'build_options': json.loads((output / kind / 'cloudbuild.json').read_bytes())['options'],
            'build_timeout': '1800s',
            'source_archive': str((output / (kind + '.tar.gz')).relative_to(root)).replace('\\', '/'),
            'source_archive_sha256': digest(output / (kind + '.tar.gz')),
            'installed_manifest_sha256': digest(output / kind / 'arm_a_release.json'),
            'image_tag': IMAGE_REPOSITORY + '/' + ('arm-a' if kind == 'backend' else 'rider-ui')
                + ':serving-v9-' + manifest['input_tree_sha256'][:12]}
            for kind in ('backend', 'ui')},
        'build_executed': False, 'provider_calls': 0, 'deployment_changed': False,
        'required_future_receipts': ['Cloud Build image digests and exact source/context receipts',
            'Independent original-page and hosted private service acceptance',
            'Compatible backend/UI revisions and preserved rollback images',
            'Exact deployment and spending authorization']}
    dump(root / 'reports/build/20261012' / ('hosted_build_preparation_' + revision + '.json'), receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('preserve-v8', 'freeze', 'verify', 'prepare'))
    parser.add_argument('--manifest', default=CURRENT)
    parser.add_argument('--index')
    parser.add_argument('--artifact-reference')
    parser.add_argument('--committed-revision')
    args = parser.parse_args()
    if args.command == 'preserve-v8':
        result = preserve_v8()
        print(json.dumps({'preserved_files': len(result['objects']), 'baseline_commit': BASELINE}))
    elif args.command == 'freeze':
        result = freeze(index_dir=args.index, reference_path=args.artifact_reference, destination=args.manifest)
        print(json.dumps({'files': len(result['file_sha256']), 'manifest_sha256': digest(ROOT / args.manifest),
            'durable_reference_status': result['index']['durable_reference_status']}))
    elif args.command == 'verify':
        result = verify(manifest_path=args.manifest, committed_revision=args.committed_revision)
        print(json.dumps({'files_verified': len(result['file_sha256']), 'provider_calls': 0}))
    else:
        print(json.dumps(prepare(manifest_path=args.manifest, committed_revision=args.committed_revision)))


if __name__ == '__main__':
    main()
