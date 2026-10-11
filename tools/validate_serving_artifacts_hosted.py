"""Hosted-only read-only GCS/index/source validation. No model/provider or writes."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.capture_serving_artifact import capture
from tools.serving_release import verify, dump, CURRENT
from cloud.serving_artifacts import load_index, digest


def check_snapshot_binding(release, reference):
    if reference != release['index']['snapshot']:
        raise ValueError('HOSTED_SNAPSHOT_DIFFERS_FROM_FROZEN_REFERENCE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--committed-revision', required=True)
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('HOSTED_EXECUTION_REQUIRED')
    output = ROOT / 'build/hosted-serving-validation'
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    release = verify(ROOT, committed_revision=args.committed_revision)
    reference = capture(ROOT, output / 'index_snapshot_reference.json', output / 'cache')
    check_snapshot_binding(release, reference)
    index = load_index(release, output / 'cache')
    from approved_registry import ApprovedEvidenceRegistry
    from cloud.grounded_generation.serving_source_authority import SourceAuthority
    base = ApprovedEvidenceRegistry.load(ROOT, index)
    authority = SourceAuthority(base, index)
    authority.check()
    receipt = {'schema_version': 'hosted-read-only-serving-validation-v1',
        'source_commit': args.committed_revision, 'serving_manifest_sha256': digest(ROOT / CURRENT),
        'snapshot': reference, 'index_id': release['index_id'],
        'manual_checksum': release['manual_checksum'],
        'index_manifest_sha256': digest(index / 'manifest.json'),
        'files_verified': len(release['index']['file_sha256']),
        'source_authority_lock': authority.lock, 'source_assembly_integrity': 'PASS',
        'duration_seconds': time.monotonic() - started,
        'provider_calls': 0, 'cloud_mutations': 0, 'index_rebuilt': False,
        'quality_acceptance': False, 'deployment_acceptance': False,
        'scope': 'Original immutable GCS generation/hash plus scoped source reload; no answer generation or deployed request.'}
    dump(output / 'validation.json', receipt)
    print(json.dumps({'index_files_verified': receipt['files_verified'], 'provider_calls': 0,
        'quality_acceptance': False, 'deployment_acceptance': False}))


if __name__ == '__main__':
    main()
