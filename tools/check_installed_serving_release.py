"""Hosted image-stage binding check; does not create any provider or model."""
import json
from pathlib import Path
import re
import sys

SCHEMA = 'motomedic-serving-release-v10'
OWNER_SCOPE = 'reports/public_evaluator/20261012/owner_scope_v1.json'
OWNER_SCOPE_SHA = '65c42d40b4a882972570e377b4a314abd2767be7fb8fb8129e7bfe9c2a436b0d'
PRIMARY_MODEL = 'gemma-4-26b-a4b-it'
VERIFIER_MODEL = 'claude-haiku-5-5'
PROMPT_CACHE = 'ANTHROPIC_ROLE_EVIDENCE_PREFIX_5M'
OWNER_MODEL_SCOPE = 'reports/public_evaluator/20261012/owner_model_scope_v1.json'
OWNER_MODEL_SCOPE_SHA = '05145aff6facd33a6e22c86696bf9a4c16a15ae08bd5b28b9706358b69b08cfb'
MANUAL_SHA = 'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'
INDEX = 'index_a3282c4d98cf54595e4ba168'
APPROVAL = 'human_review/agent_release_161/coordinator/release_manifest_v3.json'
APPROVAL_SHA = 'b8f8c7b5a9e1a299f0a90eecbf10127779b62b35fc105f0cd587de433e235298'


def validate_policy(release, root):
    """Exact operational scope selects roles; it grants no factual acceptance."""
    from cloud.serving_artifacts import confined, digest
    from cloud.grounded_generation.cached_verifier import DRAFT_CONTRACT, CONTRACT
    from cloud.grounded_generation.role_router import ROUTING_CONTRACT
    if (release.get('schema_version') != SCHEMA
            or release.get('manual_checksum') != MANUAL_SHA
            or release.get('index_id') != INDEX
            or release.get('source_approval', {}).get('path') != APPROVAL
            or release.get('source_approval', {}).get('sha256') != APPROVAL_SHA
            or release.get('primary_model') != PRIMARY_MODEL
            or release.get('draft_model_contract') != DRAFT_CONTRACT
            or release.get('verifier_model') != VERIFIER_MODEL
            or release.get('verifier_contract') != CONTRACT
            or release.get('model_routing_contract') != ROUTING_CONTRACT
            or release.get('verifier_enabled') is not True
            or release.get('verification_authority') != 'EXACT_FINALIZED_RESPONSE_AND_IMMUTABLE_EVIDENCE'
            or release.get('fallback_enabled') is not False
            or release.get('answer_cache_enabled') is not False
            or release.get('prompt_cache') != PROMPT_CACHE
            or release.get('deployment_authorized') is not True
            or release.get('public_opening_authorized') is not True
            or release.get('public_release_approved') is not False
            or release.get('billing_changed') is not False):
        raise ValueError('SERVING_MODEL_OR_OPERATIONAL_POLICY_CHANGED')
    if release.get('acceptance') != {
            'source_approval': 'EXACT_UNCHANGED_SCOPED_SOURCE_APPROVAL',
            'runtime_quality': 'INDEPENDENT_ORIGINAL_SOURCE_AND_CURRENT_MODEL_ACCEPTANCE_REQUIRED',
            'hosted_operations': 'CURRENT_RUNTIME_HOSTED_ACCEPTANCE_REQUIRED',
            'build_checks': 'PROVIDER_FREE_BINDINGS_ONLY'}:
        raise ValueError('BUILD_CANNOT_GRANT_RUNTIME_ACCEPTANCE')
    expected = {'path': OWNER_SCOPE, 'sha256': OWNER_SCOPE_SHA,
        'authority': 'DIRECT_USER_INSTRUCTION',
        'scope': 'PUBLIC_EVALUATOR_DEPLOYMENT_AND_BOUNDED_PROVIDER_VALIDATION'}
    if release.get('owner_authorization') != expected:
        raise ValueError('SERVING_OWNER_AUTHORIZATION_BINDING_CHANGED')
    scope_path = confined(root, OWNER_SCOPE)
    if digest(scope_path) != OWNER_SCOPE_SHA:
        raise ValueError('SERVING_OWNER_AUTHORIZATION_CHANGED')
    scope = json.loads(scope_path.read_bytes())
    if (scope.get('authority') != expected['authority']
            or scope.get('billing_restart_authorized') is not False
            or scope.get('source_display_policy_changed') is not False
            or scope.get('human_factual_quality_approval') is not False):
        raise ValueError('SERVING_AUTHORIZATION_SCOPE_CHANGED')
    expected_model_scope = {'path': OWNER_MODEL_SCOPE, 'sha256': OWNER_MODEL_SCOPE_SHA,
        'authority': 'DIRECT_USER_INSTRUCTION',
        'scope': 'USER_QUESTION_LIMIT_AND_LARGE_CONTEXT_DISTINCT_MODEL_ROUTING'}
    if release.get('owner_model_authorization') != expected_model_scope:
        raise ValueError('SERVING_MODEL_AUTHORIZATION_BINDING_CHANGED')
    model_scope_path = confined(root, OWNER_MODEL_SCOPE)
    if digest(model_scope_path) != OWNER_MODEL_SCOPE_SHA:
        raise ValueError('SERVING_MODEL_AUTHORIZATION_CHANGED')
    model_scope = json.loads(model_scope_path.read_bytes())
    if (model_scope.get('authority') != 'DIRECT_USER_INSTRUCTION'
            or model_scope.get('billing_restart_authorized') is not False
            or model_scope.get('new_spend_allocation_authorized') is not False
            or model_scope.get('availability_fallback_enabled') is not False
            or model_scope.get('source_display_policy_changed') is not False
            or model_scope.get('human_factual_quality_approval') is not False):
        raise ValueError('SERVING_MODEL_AUTHORIZATION_SCOPE_CHANGED')
    quota_path = confined(root, model_scope['quota_summary_path'])
    if digest(quota_path) != model_scope['quota_summary_sha256']:
        raise ValueError('SERVING_MODEL_QUOTA_BINDING_CHANGED')
    return True


def check(root):
    root = Path(root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from cloud.serving_artifacts import confined, digest, ObjectReference
    release = json.loads((root / 'arm_a_release.json').read_bytes())
    if release.get('schema_version') != SCHEMA:
        raise ValueError('INSTALLED_SERVING_SCHEMA_CHANGED')
    if release.get('source_commit_status') != 'EXACT_COMMITTED_BLOBS_VERIFIED':
        raise ValueError('UNBOUND_SOURCE_COMMIT')
    if not re.fullmatch(r'[0-9a-f]{40}', release.get('candidate_source_commit', '')):
        raise ValueError('UNBOUND_SOURCE_COMMIT')
    ObjectReference(**release['index']['snapshot'])
    for name, checksum in release['file_sha256'].items():
        if digest(confined(root, name)) != checksum:
            raise ValueError('INSTALLED_SERVING_INPUT_CHANGED:' + name)
    validate_policy(release, root)
    # Exact approval consumer verifies original immutable source-context scopes.
    from human_review.agent_release_161.approval_consumer import ApprovalConsumer
    ApprovalConsumer(root, release['source_approval']['path'])
    return len(release['file_sha256'])


if __name__ == '__main__':
    print(json.dumps({'installed_files_verified': check(sys.argv[1]), 'provider_calls': 0}))
