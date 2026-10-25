"""Cloud Build: exact committed source + private GCS reload, synthetic tests only."""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', default='/workspace')
parser.add_argument('--source-commit', required=True)
parser.add_argument('--expected-manifest-sha256', required=True)
args = parser.parse_args()
root = Path(args.root).resolve()
os.chdir(root)
sys.path.insert(0, str(root))
started = time.monotonic()
receipt = {'schema_version': 'cloudbuild-read-only-source-validation-v1',
    'label': 'HOSTED_GCS_SOURCE_RELOAD_WITH_SYNTHETIC_PROVIDER_FREE_TESTS',
    'source_commit': args.source_commit, 'provider_calls': 0, 'models_loaded': False,
    'index_rebuilt': False, 'cloud_mutations': 0, 'quality_acceptance': False,
    'deployed_request_acceptance': False, 'latency_acceptance': False,
    'committed_blob_check': 'PRECHECKED_OUTSIDE_HOSTED_JOB',
    'validation_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
stage = 'source_archive'
try:
    if not re.fullmatch(r'[0-9a-f]{40}', args.source_commit):
        raise ValueError('COMMITTED_REVISION_REQUIRED')
    if not re.fullmatch(r'[0-9a-f]{64}', args.expected_manifest_sha256):
        raise ValueError('EXTERNAL_MANIFEST_HASH_REQUIRED')
    from tools.serving_release import verify, CURRENT, verify_history
    from cloud.serving_artifacts import load_index, digest
    if digest(root / CURRENT) != args.expected_manifest_sha256:
        raise ValueError('EXTERNAL_MANIFEST_BINDING_CHANGED')
    release = verify(root)  # No Git invocation; the source archive was prechecked.
    receipt.update(serving_manifest_sha256=digest(root / CURRENT),
        frozen_inputs_verified=len(release['file_sha256']),
        historical_inputs_verified=verify_history(root),
        input_tree_sha256=release['input_tree_sha256'])
    stage = 'authenticated_gcs_reload'
    index = load_index(release, root / 'build/cloudbuild-source-validation/cache')
    os.environ['MOTOMEDIC_TEST_INDEX'] = str(index)
    stage = 'exact_source_authority'
    from approved_registry import ApprovedEvidenceRegistry
    from cloud.grounded_generation.serving_source_authority import SourceAuthority
    base = ApprovedEvidenceRegistry.load(root, index)
    authority = SourceAuthority(base, index)
    authority.check()
    receipt.update(snapshot=release['index']['snapshot'], index_id=release['index_id'],
        manual_checksum=release['manual_checksum'], source_authority_lock=authority.lock,
        index_manifest_sha256=digest(index / 'manifest.json'),
        index_files_verified=len(release['index']['file_sha256']),
        parser_gap_pages=release['index']['parser_gap_pages'],
        local_artifact_recovery=release['index'].get('deterministic_file_recovery'))
    stage = 'synthetic_boundary_tests'
    names = ['cloud.grounded_generation.test_serving_retrieval',
        'cloud.grounded_generation.test_serving_context',
        'cloud.grounded_generation.test_serving_source_authority',
        'cloud.grounded_generation.test_serving_safety', 'tools.test_build_candidate']
    captured = io.StringIO()
    from cloud.grounded_generation.provider import GemmaProvider
    from cloud.grounded_generation.claude_provider import ClaudeProvider
    with contextlib.ExitStack() as guard:
        for provider in (GemmaProvider, ClaudeProvider):
            guard.enter_context(patch.object(provider, '__init__', side_effect=AssertionError(
                'REAL_PROVIDER_CONSTRUCTION_PROHIBITED_IN_SOURCE_VALIDATION')))
        guard.enter_context(contextlib.redirect_stdout(captured))
        guard.enter_context(contextlib.redirect_stderr(captured))
        suite = unittest.defaultTestLoader.loadTestsFromNames(names)
        result = unittest.TextTestRunner(stream=captured, verbosity=0).run(suite)
    receipt.update(test_modules=names, synthetic_tests_run=result.testsRun,
        synthetic_test_failures=[test.id() for test, _ in result.failures],
        synthetic_test_errors=[test.id() for test, _ in result.errors],
        synthetic_test_skips=len(result.skipped), test_output_sha256=hashlib.sha256(
            captured.getvalue().encode('utf-8')).hexdigest())
    if not result.wasSuccessful() or result.testsRun != 36 or result.skipped:
        raise ValueError('SYNTHETIC_BOUNDARY_TESTS_FAILED_OR_INCOMPLETE')
    if any(name.split('.')[0] in ('transformers', 'sentence_transformers', 'torch', 'docling') for name in sys.modules):
        raise ValueError('MODEL_OR_PARSER_IMPORT_PROHIBITED')
    receipt['real_provider_construction_guard'] = 'ENFORCED'
    stage = 'final_integrity_recheck'
    verify(root)
    authority.check()
    receipt['status'] = 'PASS'
except Exception as exc:
    receipt.update(status='FAIL', failed_stage=stage, error_class=type(exc).__name__)
    filename = Path(exc.filename).resolve() if isinstance(exc, FileNotFoundError) and exc.filename else None
    if filename and filename.is_relative_to(root) and (filename.name in ('royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf', 'source_manifest.json') or filename.relative_to(root).parts[0] in ('human_review', 'reports', 'cloud', 'tools')):
        receipt['missing_workspace_file'] = filename.relative_to(root).as_posix()
finally:
    receipt['duration_seconds'] = round(time.monotonic() - started, 3)
    print(json.dumps(receipt, sort_keys=True, ensure_ascii=True, allow_nan=False))
sys.exit(0 if receipt['status'] == 'PASS' else 1)
