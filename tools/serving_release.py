"""Freeze and verify the serving inputs of the section-template answer path (schema v11).

The v11 manifest binds every serving code/UI/workflow file, the manual, the section index
identity, the single generation contract and the owner decision. Earlier v8-v10 manifests stay
verifiable as history. Freezing and checking use no providers, cloud writes, builds or secrets,
and authorize no deployment; hosted build preparation for v11 is a later owner scope.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.check_installed_serving_release import (ARCHITECTURE, OWNER_DECISION, EVALUATION, SCHEMA,
    INDEX, MANUAL_SHA, BASE_IMAGE, UI_BASE_IMAGE, confined, digest, validate_policy)

BASELINE = '7cd58405e5e8a98abc0c272336249443d231d7ad'
HISTORICAL = 'reports/grounded_generation/v8/runtime_freeze.json'
HISTORICAL_SHA = 'd7990e2fc2863c05f9c4332d4a2df76354be6fbfe49c2430bbbc7f83990c70e0'
PRESERVED = 'reports/build/20261012/frozen_v8_runtime'
MIGRATION = 'reports/build/20261012/v8_preservation.json'
CURRENT = 'reports/public_evaluator/20261025/serving_manifest_v11.json'
MANUAL = 'royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf'
HISTORICAL_SERVING = {
    'reports/public_evaluator/20261012/serving_manifest_v10_14.json':
        'b8d39544a9cc216b7bd6d37dd741c12e95f6e1d2694a59eaf573cb51195962f5',
    'reports/public_evaluator/20261012/serving_manifest_v10_13.json':
        '3d1d01d09c1929a8c1e52e698a3b4ca9b48c14a14954b82f7d6c795ab6bf031c',
    'reports/public_evaluator/20261012/serving_manifest_v10_12.json':
        'ff82ee677ada2e42fc08b5ea710ebe05cef7dac527f7008785ed0320bf58e8fb',
    'reports/public_evaluator/20261012/serving_manifest_v10_11.json':
        'c4f87a48fcb3645c46b74734ffd1df6b8faaa735e54d2286d6f3b099700d06f1',
    'reports/public_evaluator/20261012/serving_manifest_v10_10.json':
        'eb3a853947507b8739886a43f62dfc3fbd447b406d0ce9f4f7db12a172341dde',
    'reports/public_evaluator/20261012/serving_manifest_v10_9.json':
        '1056a3e5aaccec418a7fe36e7a2b0acd65b1ee5653a951aa03a1da05e116f6e6',
    'reports/public_evaluator/20261012/serving_manifest_v10_8.json':
        '7e5896add721d18ec186f272dda481a6aedc475c0274bf9281cf1802bb7510d0',
    'reports/public_evaluator/20261012/serving_manifest_v10_7.json':
        '27510150635230629284f0c6ae89d36a6beb546695b94a4da63e47c67387826d',
    'reports/public_evaluator/20261012/serving_manifest_v10_6.json':
        'b94faeb2c4774cd121c4e6f622a5b2371cd9c9df0147fe40b4ddbb25af9bed52',
    'reports/public_evaluator/20261012/serving_manifest_v10_5.json':
        'b95d89b5d95641f39ef7c3961233a99fb2824fa1320aff0c6e6d808772b7fb2a',
    'reports/public_evaluator/20261012/serving_manifest_v10_4.json':
        'b6aadba39d309bf90a50be93aecc947a3cfb44357f15cd40dd5c4dd3672f2fd3',
    'reports/public_evaluator/20261012/serving_manifest_v10_3.json':
        '1ec0f19b5a4cad2543018d1a793b41f0a50bd0004ace61a1c61d839252532d16',
    'reports/public_evaluator/20261012/serving_manifest_v10_2.json':
        '2b5638cbc0e98369fa1488f89f823a736ed84a618e4e6670935919a0a0c05898',
    'reports/public_evaluator/20261012/serving_manifest_v10_1.json':
        'abbf41b0ecd5301a56f8abe96ecce53c853eac35de651d1c71fb5318f9b9f172',
    'reports/public_evaluator/20261012/serving_manifest_v10.json':
        '398f48d44aedf8648bde2582ff76058ee917f8f59b7b4576726387077e919f13',
    'reports/build/20261012/serving_manifest_v9.json':
        'a5604aaa277b4095fb3aebc95703cfd7c128e1d609cde80965c18d1791b98a84',
    'reports/build/20261012/serving_manifest_v9_1.json':
        '474566cd3698bfc31f3186906d63fecd1198a98e926afc4701da733821c7f19d',
}
# Root modules the serving import graph reaches; the rest of the root is historical tooling.
ROOT_MODULES = ('controller_contracts.py', 'evidence_registry.py', 'generation_contracts.py',
                'generation_providers.py', 'online_ingest.py', 'session_store.py')
NAMED_INPUTS = ('cloud/deployment_status.json', 'cloud/live_smoke.json', 'cloud/export_qdrant.py',
    'cloud/arm_a/Dockerfile', 'rider_ui/Dockerfile', 'source_manifest.json', MANUAL,
    'tools/serving_release.py', 'tools/test_serving_release.py', 'tools/check_repository_structure.py',
    'tools/check_installed_serving_release.py', 'tools/test_check_installed_serving_release.py',
    'tools/resolve_container_base.py', 'tools/manage_primary_token_ceiling.py',
    'tools/test_manage_primary_token_ceiling.py', 'tools/provision_evaluator_secret_hosted.py',
    'reports/build/20261012/ui_base_image.json', 'reports/build/20261012/ui_dependency_lock.json',
    'reports/public_evaluator/20261012/ui_dependency_lock_v2.json', OWNER_DECISION, EVALUATION,
    'reports/evals/20261025_answer_release_v3/README.md', MIGRATION)


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


def verify_serving_history(root=ROOT):
    """Retain prior serving manifests as history; none of them binds the current runtime."""
    for name, expected in HISTORICAL_SERVING.items():
        path = confined(root, name)
        if digest(path) != expected or path.with_suffix('.sha256').read_text().strip() != expected:
            raise ValueError('HISTORICAL_SERVING_MANIFEST_CHANGED:' + name)
    return dict(HISTORICAL_SERVING)


def serving_inputs(root=ROOT):
    """Discover complete code/UI/workflow inputs so an added unbound module fails CI."""
    root = Path(root)
    names = set()
    for folder in ('cloud/arm_a', 'cloud/grounded_generation', 'rider_ui'):
        for path in (root / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py', '.css', '.txt', '.yaml', '.json'):
                names.add(path.relative_to(root).as_posix())
    for path in (root / '.github/workflows').glob('*'):
        if path.suffix in ('.yml', '.yaml'):
            names.add(path.relative_to(root).as_posix())
    names.update(ROOT_MODULES)
    names.update(NAMED_INPUTS)
    for name in HISTORICAL_SERVING:
        names.update((name, str(Path(name).with_suffix('.sha256')).replace('\\', '/')))
    return sorted(names)


def index_policy(index_dir):
    """The exact section index the runtime must load; its files are verified at startup."""
    from cloud.grounded_generation import section_index
    identity = section_index.identity(index_dir)
    section_index.verify(index_dir, identity)
    if identity['index_id'] != INDEX or identity['manual_sha256'] != MANUAL_SHA:
        raise ValueError('SECTION_INDEX_IDENTITY_CHANGED')
    if not (Path(index_dir) / 'reranker_model').is_dir():
        raise ValueError('SECTION_INDEX_RERANKER_MISSING')
    manifest = json.loads((Path(index_dir) / 'manifest.json').read_bytes())
    return identity, {'built_from_index_id': manifest['built_from_index_id'],
        'cached_parse_sha256': manifest['cached_parse_sha256'], 'review_layer': manifest['review_layer'],
        'qa': {k: manifest['qa'][k] for k in ('chunks', 'sections', 'box_chunks', 'box_chunks_attached',
               'page_break_continuations', 'pages_covered', 'pdf_pages', 'parser_gap_pages')},
        'durable_reference_status': 'OBJECT_GENERATION_RECEIPT_REQUIRED',
        'hosted_qdrant_collection': 'NOT_UPLOADED',
        'serving_path': 'build/section-index',
        'query_models': 'BGE-M3 query encoder from the base image at the index revision; '
                        'MiniLM cross-encoder copied with the index. No request embeds the manual.'}


def freeze(root=ROOT, *, index_dir, destination=CURRENT):
    from cloud.grounded_generation import section_assembly, section_retrieval, template_answer
    from cloud.grounded_generation.haiku_answer import CONTRACT
    from cloud.grounded_generation.section_questions import RUNTIME_POLICY
    root = Path(root).resolve()
    target = confined(root, destination)
    if target.exists():
        raise ValueError('NEVER_OVERWRITE_SERVING_FREEZE')
    verify_history(root)
    verify_serving_history(root)
    names = serving_inputs(root)
    bindings = {name: digest(confined(root, name)) for name in names}
    identity, index_release = index_policy(index_dir)
    value = {'schema_version': SCHEMA, 'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'architecture': ARCHITECTURE, 'runtime_policy': RUNTIME_POLICY,
        'historical_serving_manifests': dict(HISTORICAL_SERVING),
        'source_commit_status': 'COMMITTED_BLOB_CHECK_REQUIRED_BEFORE_HOSTED_BUILD',
        'file_sha256': bindings,
        'input_tree_sha256': hashlib.sha256(json.dumps(bindings, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'manual_checksum': MANUAL_SHA, 'index_id': INDEX, 'index': identity, 'index_release': index_release,
        'retrieval_version': section_retrieval.VERSION, 'assembly_version': section_assembly.VERSION,
        'template_version': template_answer.VERSION,
        'generation_model': CONTRACT['model'], 'generation_contract': CONTRACT,
        'review_layer': 'NONE', 'verifier': 'NONE', 'fallback_enabled': False, 'answer_cache_enabled': False,
        'prompt_cache': 'ANTHROPIC_SYSTEM_PROMPT_5M',
        'owner_decision': {'path': OWNER_DECISION, 'sha256': digest(confined(root, OWNER_DECISION))},
        'evaluation': {'path': EVALUATION, 'sha256': digest(confined(root, EVALUATION)),
            'label': 'AGENT_SCORED_LOCAL_SUBAGENT_RUN_NOT_INDEPENDENT_ACCEPTANCE'},
        'backend_base_image': BASE_IMAGE, 'ui_base_image': UI_BASE_IMAGE,
        'backend_image_digest': None, 'ui_image_digest': None,
        'provider_calls': 0, 'build_executed': False, 'deployment_authorized': False,
        'public_opening_authorized': False, 'billing_changed': False, 'ledger_changed': False,
        'acceptance': {'runtime_quality': 'HOSTED_REAL_MODEL_RUN_REQUIRED',
            'hosted_operations': 'NEW_OWNER_DEPLOYMENT_SCOPE_REQUIRED',
            'build_checks': 'PROVIDER_FREE_BINDINGS_ONLY'}}
    validate_policy(value, root)
    dump(target, value)
    target.with_suffix('.sha256').write_bytes((digest(target) + '\n').encode('ascii'))
    return value


def verify(root=ROOT, manifest_path=CURRENT, *, committed_revision=None):
    root = Path(root).resolve()
    verify_history(root)
    verify_serving_history(root)
    path = confined(root, manifest_path)
    manifest = json.loads(path.read_bytes())
    if manifest.get('schema_version') != SCHEMA:
        raise ValueError('WRONG_SERVING_MANIFEST_SCHEMA')
    if path.with_suffix('.sha256').read_text().strip() != digest(path):
        raise ValueError('SERVING_MANIFEST_DIGEST_CHANGED')
    if set(manifest['file_sha256']) != set(serving_inputs(root)):
        raise ValueError('SERVING_INPUT_INVENTORY_CHANGED')
    if manifest.get('historical_serving_manifests') != HISTORICAL_SERVING:
        raise ValueError('SERVING_HISTORY_BINDING_CHANGED')
    validate_policy(manifest, root)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('preserve-v8', 'freeze', 'verify'))
    parser.add_argument('--manifest', default=CURRENT)
    parser.add_argument('--index', help='section index directory (freeze only)')
    parser.add_argument('--committed-revision')
    args = parser.parse_args()
    if args.command == 'preserve-v8':
        result = preserve_v8()
        print(json.dumps({'preserved_files': len(result['objects']), 'baseline_commit': BASELINE}))
    elif args.command == 'freeze':
        if not args.index:
            parser.error('freeze requires --index')
        result = freeze(index_dir=args.index, destination=args.manifest)
        print(json.dumps({'files': len(result['file_sha256']), 'manifest_sha256': digest(ROOT / args.manifest),
            'index_id': result['index_id']}))
    else:
        result = verify(manifest_path=args.manifest, committed_revision=args.committed_revision)
        print(json.dumps({'files_verified': len(result['file_sha256']), 'provider_calls': 0}))


if __name__ == '__main__':
    main()
