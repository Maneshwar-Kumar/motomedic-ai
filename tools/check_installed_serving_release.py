"""Hosted image-stage binding check; does not create any provider or model."""
import json
from pathlib import Path
import sys


def check(root):
    root = Path(root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from cloud.serving_artifacts import confined, digest, ObjectReference
    release = json.loads((root / 'arm_a_release.json').read_bytes())
    if release.get('schema_version') != 'motomedic-serving-release-v9':
        raise ValueError('INSTALLED_SERVING_SCHEMA_CHANGED')
    if release.get('source_commit_status') != 'EXACT_COMMITTED_BLOBS_VERIFIED':
        raise ValueError('UNBOUND_SOURCE_COMMIT')
    ObjectReference(**release['index']['snapshot'])
    for name, checksum in release['file_sha256'].items():
        if digest(confined(root, name)) != checksum:
            raise ValueError('INSTALLED_SERVING_INPUT_CHANGED:' + name)
    if release['fallback_enabled'] is not False or release['answer_cache_enabled'] is not False:
        raise ValueError('UNAUTHORIZED_SERVING_ACTIVATION')
    # Exact approval consumer verifies original immutable source-context scopes.
    from human_review.agent_release_161.approval_consumer import ApprovalConsumer
    ApprovalConsumer(root, release['source_approval']['path'])
    return len(release['file_sha256'])


if __name__ == '__main__':
    print(json.dumps({'installed_files_verified': check(sys.argv[1]), 'provider_calls': 0}))
