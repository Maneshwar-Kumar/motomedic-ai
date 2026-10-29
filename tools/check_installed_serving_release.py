"""Serving release policy (schema v11) and the image-stage installed-release check.

Neither function creates a model, provider, store or network request. Passing them is binding
evidence only: it grants no factual-quality, hosted-operation or deployment acceptance.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = 'motomedic-serving-release-v11'
ARCHITECTURE = 'SECTION_TOP5_SINGLE_CALL_TEMPLATE_GATE'
MANUAL_SHA = 'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'
INDEX = 'index_f768fbb216836c003701079e'
# The design (v3), the integration bar (v4), the token-ceiling removal and layout (v5), the
# quality round (v6) and the regression gate and observability (v7).
OWNER_DECISIONS = ('evals/20261025_answer_release_v3/owner_decision_v3.json',
                   'evals/20261025_answer_release_v3/owner_decision_v4.json',
                   'releases/owner_decision_v5.json', 'releases/owner_decision_v6.json',
                   'releases/owner_decision_v7.json')
EVALUATION = 'evals/20261025_heldout_v1/comparison.json'
BASE_IMAGE = 'us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:a8946299f34177aeda76cadbbd7fce0a33c5fd8f574438d823281ee78eb045e4'
UI_BASE_IMAGE = 'docker.io/library/python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1'
ACCEPTANCE = {'runtime_quality': 'HOSTED_REAL_MODEL_RUN_REQUIRED',
              'hosted_operations': 'NEW_OWNER_DEPLOYMENT_SCOPE_REQUIRED',
              'build_checks': 'PROVIDER_FREE_BINDINGS_ONLY'}


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def confined(root, name):
    """Portable names reject traversal, Windows drive paths and separator tricks."""
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('UNSAFE_RELEASE_PATH')
    result = Path(root) / name
    if not result.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('UNSAFE_RELEASE_PATH')
    return result


def validate_policy(release, root):
    """The exact answer path: section index, top-5 retrieval, one Haiku call, the gate."""
    from cloud.grounded_generation import section_assembly, section_retrieval, template_answer
    from cloud.grounded_generation.haiku_answer import CONTRACT
    from cloud.grounded_generation.section_questions import RUNTIME_POLICY
    index = release.get('index')
    if (release.get('schema_version') != SCHEMA or release.get('architecture') != ARCHITECTURE
            or release.get('runtime_policy') != RUNTIME_POLICY
            or release.get('manual_checksum') != MANUAL_SHA or release.get('index_id') != INDEX
            or type(index) is not dict or index.get('index_id') != INDEX or index.get('manual_sha256') != MANUAL_SHA
            or release.get('generation_model') != CONTRACT['model'] or release.get('generation_contract') != CONTRACT
            or release.get('retrieval_version') != section_retrieval.VERSION
            or release.get('assembly_version') != section_assembly.VERSION
            or release.get('template_version') != template_answer.VERSION
            or release.get('review_layer') != 'NONE' or release.get('verifier') != 'NONE'
            or release.get('token_ceiling') != 'NONE'
            or release.get('fallback_enabled') is not False or release.get('answer_cache_enabled') is not False
            or release.get('prompt_cache') != 'ANTHROPIC_SYSTEM_PROMPT_5M'
            or release.get('backend_base_image') != BASE_IMAGE or release.get('ui_base_image') != UI_BASE_IMAGE
            or release.get('deployment_authorized') is not False or release.get('public_opening_authorized') is not False
            or release.get('billing_changed') is not False or release.get('ledger_documents_changed') is not False):
        raise ValueError('SERVING_MODEL_OR_OPERATIONAL_POLICY_CHANGED')
    if release.get('acceptance') != ACCEPTANCE:
        raise ValueError('BUILD_CANNOT_GRANT_RUNTIME_ACCEPTANCE')
    bound = release.get('owner_decisions')
    if (type(bound) is not list or [row.get('path') for row in bound] != list(OWNER_DECISIONS)
            or any(row.get('sha256') != digest(confined(root, row['path'])) for row in bound)):
        raise ValueError('SERVING_DECISION_OR_EVALUATION_BINDING_CHANGED:owner_decisions')
    evaluation = release.get('evaluation') or {}
    if evaluation.get('path') != EVALUATION or evaluation.get('sha256') != digest(confined(root, EVALUATION)):
        raise ValueError('SERVING_DECISION_OR_EVALUATION_BINDING_CHANGED:evaluation')
    for path in OWNER_DECISIONS:
        decision = json.loads(confined(root, path).read_bytes())
        if (decision.get('authority') != 'DIRECT_USER_INSTRUCTION' or decision.get('review_layer', 'NONE') != 'NONE'
                or decision.get('deployment_authorized') is not False
                or decision.get('billing_restart_authorized') is not False):
            raise ValueError('SERVING_OWNER_DECISION_SCOPE_CHANGED:' + path)
    return True


def check(root):
    """Run inside a built image: every installed byte, the policy and the pinned section index."""
    root = Path(root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    release = json.loads((root / 'arm_a_release.json').read_bytes())
    if release.get('schema_version') != SCHEMA:
        raise ValueError('INSTALLED_SERVING_SCHEMA_CHANGED')
    if release.get('source_commit_status') != 'EXACT_COMMITTED_BLOBS_VERIFIED':
        raise ValueError('UNBOUND_SOURCE_COMMIT')
    if not re.fullmatch(r'[0-9a-f]{40}', release.get('candidate_source_commit') or ''):
        raise ValueError('UNBOUND_SOURCE_COMMIT')
    for name, checksum in release['file_sha256'].items():
        if digest(confined(root, name)) != checksum:
            raise ValueError('INSTALLED_SERVING_INPUT_CHANGED:' + name)
    validate_policy(release, root)
    from cloud.grounded_generation.section_index import verify
    verify(root / 'build/section-index', release['index'])
    return len(release['file_sha256'])


if __name__ == '__main__':
    print(json.dumps({'installed_files_verified': check(sys.argv[1]), 'provider_calls': 0}))
