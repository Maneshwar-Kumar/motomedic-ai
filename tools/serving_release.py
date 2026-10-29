"""Freeze and verify the serving inputs of the section-template answer path (schema v11).

The manifest binds every serving code/UI/workflow file, the manual and its source manifest, the
section index identity, the single generation contract, the owner decisions and the evaluation.
It also binds the previous v11 manifest as history. The v8-v10.14 manifests and the review
packages now live in archive/; their bindings were last verified in the original layout at
HISTORY_LAYOUT_COMMIT. Freezing and checking use no providers, cloud writes, builds or secrets,
and authorize no deployment.

Shipping means freezing. A freeze is refused unless the answer-quality regression receipt
(tools/regression.py) names the current answer identity and meets its thresholds. Verify, which CI
runs, recomputes that check and requires it to match the frozen binding.
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
from tools.check_installed_serving_release import (ARCHITECTURE, OWNER_DECISIONS, EVALUATION, SCHEMA,
    INDEX, MANUAL_SHA, BASE_IMAGE, UI_BASE_IMAGE, confined, digest, validate_policy)

CURRENT = 'releases/serving_manifest_v11_3.json'
MANUAL = 'source/royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf'
PREVIOUS = {'releases/serving_manifest_v11.json': 'aaea45999d2297c56910b2a701795a75fe20766e2574d7d74d632885cea6f32d',
            'releases/serving_manifest_v11_1.json': 'bf56799a2a94037c5ee38dba0fc2f7924bc270071573edf404bee103aac4eae5',
            'releases/serving_manifest_v11_2.json': '59245da529365627c6bc99785f7d8c99cf450eff9a56dff004672a6ed3364efa'}
HISTORY_LAYOUT_COMMIT = '7c412369f055b4d0ee747501e6b026f5987d1564'
SERVING_FOLDERS = ('cloud/arm_a', 'cloud/common', 'cloud/grounded_generation', 'rider_ui')
NAMED_INPUTS = ('ingest/online_ingest.py', 'source/source_manifest.json', MANUAL,
    'cloud/deployment_status.json', 'cloud/export_qdrant.py', 'cloud/arm_a/Dockerfile', 'rider_ui/Dockerfile',
    'tools/serving_release.py', 'tools/test_serving_release.py', 'tools/check_repository_structure.py',
    'tools/check_installed_serving_release.py', 'tools/test_check_installed_serving_release.py',
    'tools/resolve_container_base.py', 'tools/provision_evaluator_secret_hosted.py',
    *OWNER_DECISIONS, EVALUATION, 'evals/20261025_answer_release_v3/README.md',
    'evals/20261025_heldout_v1/README.md', 'tools/regression.py', 'tools/test_regression.py',
    'evals/regression/set_v1.json')


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


def verify_previous(root=ROOT):
    """The superseded v11 manifest stays byte-exact as history; it binds the pre-layout paths."""
    for name, expected in PREVIOUS.items():
        path = confined(root, name)
        if digest(path) != expected or path.with_suffix('.sha256').read_text().strip() != expected:
            raise ValueError('PREVIOUS_SERVING_MANIFEST_CHANGED:' + name)
    return dict(PREVIOUS)


def serving_inputs(root=ROOT):
    """Discover complete code/UI/workflow inputs so an added unbound module fails CI."""
    root = Path(root)
    names = set()
    for folder in SERVING_FOLDERS:
        for path in (root / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py', '.css', '.txt', '.yaml', '.json'):
                names.add(path.relative_to(root).as_posix())
    for path in (root / '.github/workflows').glob('*'):
        if path.suffix in ('.yml', '.yaml'):
            names.add(path.relative_to(root).as_posix())
    names.update(NAMED_INPUTS)
    for name in PREVIOUS:
        names.update((name, str(Path(name).with_suffix('.sha256')).replace('\\', '/')))
    return sorted(names)


def regression_binding(root=ROOT):
    """The passing regression receipt for the current answer path; anything else is refused."""
    from tools import regression
    result = regression.check(root=root)
    if not result['passed']:
        reasons = (result.get('problems') or []) + (result.get('shortfalls') or [])
        raise ValueError('REGRESSION_GATE_NOT_PASSED:' + ','.join(reasons)[:400])
    identity = json.dumps(result['answer_identity'], sort_keys=True, separators=(',', ':')).encode()
    return {'run': regression.CURRENT, 'receipt_sha256': result['receipt_sha256'], 'set': regression.SET,
            'set_sha256': result['set_sha256'], 'answer_identity_sha256': hashlib.sha256(identity).hexdigest(),
            'totals': result['totals'], 'thresholds': result['thresholds']}


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
    verify_previous(root)
    names = serving_inputs(root)
    bindings = {name: digest(confined(root, name)) for name in names}
    identity, index_release = index_policy(index_dir)
    regression = regression_binding(root)
    value = {'schema_version': SCHEMA, 'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'architecture': ARCHITECTURE, 'runtime_policy': RUNTIME_POLICY,
        'previous_serving_manifests': dict(PREVIOUS), 'history_layout_commit': HISTORY_LAYOUT_COMMIT,
        'source_commit_status': 'COMMITTED_BLOB_CHECK_REQUIRED_BEFORE_HOSTED_BUILD',
        'file_sha256': bindings,
        'input_tree_sha256': hashlib.sha256(json.dumps(bindings, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'manual_checksum': MANUAL_SHA, 'index_id': INDEX, 'index': identity, 'index_release': index_release,
        'retrieval_version': section_retrieval.VERSION, 'assembly_version': section_assembly.VERSION,
        'template_version': template_answer.VERSION,
        'generation_model': CONTRACT['model'], 'generation_contract': CONTRACT,
        'review_layer': 'NONE', 'verifier': 'NONE', 'token_ceiling': 'NONE',
        'fallback_enabled': False, 'answer_cache_enabled': False,
        'prompt_cache': 'ANTHROPIC_SYSTEM_PROMPT_5M',
        'owner_decisions': [{'path': p, 'sha256': digest(confined(root, p))} for p in OWNER_DECISIONS],
        'evaluation': {'path': EVALUATION, 'sha256': digest(confined(root, EVALUATION)),
            'label': 'AGENT_SCORED_LOCAL_SUBAGENT_RUN_NOT_INDEPENDENT_ACCEPTANCE'},
        'regression': regression,
        'backend_base_image': BASE_IMAGE, 'ui_base_image': UI_BASE_IMAGE,
        'backend_image_digest': None, 'ui_image_digest': None,
        'provider_calls': 0, 'build_executed': False, 'deployment_authorized': False,
        'public_opening_authorized': False, 'billing_changed': False, 'ledger_documents_changed': False,
        'acceptance': {'runtime_quality': 'HOSTED_REAL_MODEL_RUN_REQUIRED',
            'hosted_operations': 'NEW_OWNER_DEPLOYMENT_SCOPE_REQUIRED',
            'build_checks': 'PROVIDER_FREE_BINDINGS_ONLY'}}
    validate_policy(value, root)
    dump(target, value)
    target.with_suffix('.sha256').write_bytes((digest(target) + '\n').encode('ascii'))
    return value


def verify(root=ROOT, manifest_path=CURRENT, *, committed_revision=None):
    root = Path(root).resolve()
    verify_previous(root)
    path = confined(root, manifest_path)
    manifest = json.loads(path.read_bytes())
    if manifest.get('schema_version') != SCHEMA:
        raise ValueError('WRONG_SERVING_MANIFEST_SCHEMA')
    if path.with_suffix('.sha256').read_text().strip() != digest(path):
        raise ValueError('SERVING_MANIFEST_DIGEST_CHANGED')
    if set(manifest['file_sha256']) != set(serving_inputs(root)):
        raise ValueError('SERVING_INPUT_INVENTORY_CHANGED')
    if (manifest.get('previous_serving_manifests') != PREVIOUS
            or manifest.get('history_layout_commit') != HISTORY_LAYOUT_COMMIT):
        raise ValueError('SERVING_HISTORY_BINDING_CHANGED')
    validate_policy(manifest, root)
    if manifest.get('regression') != regression_binding(root):
        raise ValueError('REGRESSION_BINDING_CHANGED')
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
    parser.add_argument('command', choices=('freeze', 'verify'))
    parser.add_argument('--manifest', default=CURRENT)
    parser.add_argument('--index', help='section index directory (freeze only)')
    parser.add_argument('--committed-revision')
    args = parser.parse_args()
    if args.command == 'freeze':
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
