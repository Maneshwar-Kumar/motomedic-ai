"""Bind hosted Cloud Build results; promotion additionally binds a rollback pair.

This records evidence only. It does not build, deploy, shift traffic or modify IAM.
"""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cloud.serving_artifacts import ObjectReference, digest
from tools.serving_release import dump
from tools.check_installed_serving_release import OWNER_SCOPE, OWNER_SCOPE_SHA


def immutable_image(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9./_-]+@sha256:[0-9a-f]{64}', value):
        raise ValueError('IMMUTABLE_IMAGE_DIGEST_REQUIRED')
    return value


def bind_build(preparation, results, uploads):
    """Record build provenance without inventing deployment or rollback evidence."""
    schema = preparation.get('schema_version')
    if schema not in ('serving-v9-hosted-build-preparation-v1', 'serving-v10-hosted-build-preparation-v1'):
        raise ValueError('VERSIONED_HOSTED_PREPARATION_REQUIRED')
    version = 'v10' if schema == 'serving-v10-hosted-build-preparation-v1' else 'v9'
    if version == 'v10':
        if (preparation.get('serving_schema_version') != 'motomedic-serving-release-v10'
                or not re.fullmatch(r'v10(?:_[1-9][0-9]*)?', preparation.get('runtime_revision', ''))
                or preparation.get('quality_acceptance') is not False
                or preparation.get('hosted_operations_acceptance') is not False
                or preparation.get('owner_authorization') != {
                    'path': OWNER_SCOPE, 'sha256': OWNER_SCOPE_SHA,
                    'authority': 'DIRECT_USER_INSTRUCTION',
                    'scope': 'PUBLIC_EVALUATOR_DEPLOYMENT_AND_BOUNDED_PROVIDER_VALIDATION'}):
            raise ValueError('PREPARATION_CANNOT_GRANT_RUNTIME_ACCEPTANCE')
        if any(not preparation['contexts'][kind]['image_tag'].endswith(
                ':serving-' + preparation['runtime_revision'] + '-' + preparation['input_tree_sha256'][:12])
                for kind in ('backend', 'ui')):
            raise ValueError('VERSIONED_IMAGE_TAG_CHANGED')
    if set(results) != {'backend', 'ui'} or set(uploads) != {'backend', 'ui'}:
        raise ValueError('COMPATIBLE_BUILD_PAIR_REQUIRED')
    images, provenance = {}, {}
    expected_substitutions = {
        '_SOURCE_COMMIT': preparation['source_commit'],
        '_SERVING_MANIFEST_SHA256': preparation['serving_manifest_sha256'],
        '_INPUT_TREE_SHA256': preparation['input_tree_sha256']}
    for kind in ('backend', 'ui'):
        build = results[kind]
        if build.get('status') != 'SUCCESS' or not build.get('id'):
            raise ValueError('HOSTED_BUILD_NOT_SUCCESSFUL:' + kind)
        if any(build.get('substitutions', {}).get(k) != v for k, v in expected_substitutions.items()):
            raise ValueError('HOSTED_BUILD_SOURCE_BINDING_CHANGED:' + kind)
        actual_steps = [{k: v for k, v in step.items() if k not in
            ('status', 'timing', 'pullTiming', 'exitCode')} for step in build.get('steps', [])]
        if actual_steps != preparation['contexts'][kind]['build_steps']:
            raise ValueError('HOSTED_BUILD_RECIPE_CHANGED:' + kind)
        expected_options = preparation['contexts'][kind]['build_options']
        actual_options = build.get('options', {})
        if (any(actual_options.get(k) != v for k, v in expected_options.items())
                or actual_options.get('machineType') not in (None, 'UNSPECIFIED')
                or build.get('timeout') != preparation['contexts'][kind]['build_timeout']):
            raise ValueError('HOSTED_BUILD_EXECUTION_OPTIONS_CHANGED:' + kind)
        ref = ObjectReference(**uploads[kind])
        if ref.sha256 != preparation['contexts'][kind]['source_archive_sha256']:
            raise ValueError('UPLOADED_BUILD_CONTEXT_CHANGED:' + kind)
        source = build.get('sourceProvenance', {}).get('resolvedStorageSource', {})
        parsed = urlsplit(ref.uri)
        if source != {'bucket': parsed.netloc, 'object': parsed.path.lstrip('/'), 'generation': ref.generation}:
            raise ValueError('HOSTED_BUILD_STORAGE_GENERATION_CHANGED:' + kind)
        candidates = build.get('results', {}).get('images', [])
        image_tag = preparation['contexts'][kind]['image_tag']
        matches = [row for row in candidates if row.get('name') == image_tag]
        if len(matches) != 1 or not re.fullmatch(r'sha256:[0-9a-f]{64}', matches[0].get('digest', '')):
            raise ValueError('HOSTED_IMAGE_DIGEST_MISSING_OR_AMBIGUOUS:' + kind)
        images[kind] = immutable_image(image_tag.rsplit(':', 1)[0] + '@' + matches[0]['digest'])
        provenance[kind] = {'build_id': build['id'], 'source_archive': uploads[kind],
            'installed_manifest_sha256': preparation['contexts'][kind]['installed_manifest_sha256'],
            'dockerfile_sha256': preparation['contexts'][kind]['dockerfile_sha256'],
            'cloudbuild_sha256': preparation['contexts'][kind]['cloudbuild_sha256']}
        provenance[kind].update(build_options=expected_options,
            build_timeout=preparation['contexts'][kind]['build_timeout'])
    receipt = {'schema_version': 'motomedic-serving-' + version + '-build-binding-v1',
        'binding_scope': 'HOSTED_BUILD_PROVENANCE_ONLY',
        'source_commit': preparation['source_commit'],
        'serving_manifest_sha256': preparation['serving_manifest_sha256'],
        'input_tree_sha256': preparation['input_tree_sha256'],
        'images': images, 'hosted_provenance': provenance,
        'rollback_verified': False, 'promotion_ready': False,
        'provider_calls': 0, 'deployment_changed': False,
        'quality_acceptance': False, 'deployment_authorized': False,
        'hosted_operations_acceptance': False,
        'promotion_requirement': 'Same frozen runtime independent original-source/current-model quality and hosted operations acceptance, compatible rollback, recorded owner authorization and existing spend guard.'}
    if version == 'v10':
        receipt.update(serving_schema_version=preparation['serving_schema_version'],
            runtime_revision=preparation['runtime_revision'],
            owner_authorization=preparation['owner_authorization'])
    return receipt


def bind(preparation, results, uploads, rollback):
    """A promotion receipt cannot omit a compatible backend/UI rollback pair."""
    receipt = bind_build(preparation, results, uploads)
    if set(rollback) != {'backend', 'ui', 'session_schema', 'runtime_lock'}:
        raise ValueError('COMPATIBLE_ROLLBACK_PAIR_REQUIRED')
    for kind in ('backend', 'ui'):
        row = rollback[kind]
        immutable_image(row['image'])
        if not isinstance(row.get('revision'), str) or not row['revision'] or not row.get('service'):
            raise ValueError('EXACT_ROLLBACK_REVISION_REQUIRED')
    if not rollback['session_schema'] or not rollback['runtime_lock']:
        raise ValueError('ROLLBACK_STATE_COMPATIBILITY_REQUIRED')
    receipt.update(schema_version=receipt['schema_version'].replace('-build-binding-', '-image-binding-'),
        binding_scope='HOSTED_BUILD_AND_COMPATIBLE_ROLLBACK', rollback=rollback,
        rollback_verified=True)
    # Factual/hosted acceptance and exact operational authorization remain open.
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', required=True)
    parser.add_argument('--build-results', required=True)
    parser.add_argument('--upload-references', required=True)
    parser.add_argument('--mode', choices=('build-only', 'promotion'), default='promotion')
    parser.add_argument('--rollback-pair')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    values = [json.loads(Path(path).read_bytes()) for path in (
        args.preparation, args.build_results, args.upload_references)]
    if args.mode == 'promotion':
        if not args.rollback_pair:
            parser.error('promotion requires --rollback-pair; build-only grants no promotion authority')
        receipt = bind(*values, json.loads(Path(args.rollback_pair).read_bytes()))
    else:
        if args.rollback_pair:
            parser.error('build-only does not accept or validate rollback evidence')
        receipt = bind_build(*values)
    dump(args.out, receipt)
    print(json.dumps({'image_binding_sha256': digest(args.out), 'deployment_changed': False}))


if __name__ == '__main__':
    main()
