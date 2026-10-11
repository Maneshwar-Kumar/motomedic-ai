"""Synthetic release binding checks, with no cloud, images or providers."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch

from tools import serving_release as release
from tools.validate_serving_artifacts_hosted import check_snapshot_binding
from tools.check_installed_serving_release import OWNER_SCOPE_SHA, validate_policy
from cloud.grounded_generation.cached_verifier import DRAFT_CONTRACT, CONTRACT


class ReleaseTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'runtime.py').write_bytes(b'candidate-runtime')
        bindings = {'runtime.py': hashlib.sha256(b'candidate-runtime').hexdigest()}
        authority = root / release.OWNER_SCOPE
        authority.parent.mkdir(parents=True, exist_ok=True)
        authority.write_bytes((release.ROOT / release.OWNER_SCOPE).read_bytes())
        manifest = {'schema_version': release.SCHEMA,
            'file_sha256': bindings, 'manual_checksum': release.MANUAL_SHA,
            'index_id': release.INDEX, 'source_approval': {'path': release.APPROVAL, 'sha256': release.APPROVAL_SHA},
            'source_baseline_commit': release.SOURCE_BASELINE,
            'historical_serving_manifests': dict(release.HISTORICAL_SERVING),
            'primary_model': 'gemma-4-26b-a4b-it', 'draft_model_contract': deepcopy(DRAFT_CONTRACT),
            'verifier_model': 'claude-haiku-5-5', 'verifier_contract': deepcopy(CONTRACT),
            'verifier_enabled': True,
            'verification_authority': 'EXACT_FINALIZED_RESPONSE_AND_IMMUTABLE_EVIDENCE',
            'prompt_cache': 'ANTHROPIC_VERIFIER_EVIDENCE_PREFIX_5M',
            'owner_authorization': {'path': release.OWNER_SCOPE, 'sha256': OWNER_SCOPE_SHA,
                'authority': 'DIRECT_USER_INSTRUCTION', 'scope': 'PUBLIC_EVALUATOR_DEPLOYMENT_AND_BOUNDED_PROVIDER_VALIDATION'},
            'deployment_authorized': True, 'public_opening_authorized': True,
            'public_release_approved': False, 'billing_changed': False,
            'acceptance': {'source_approval': 'EXACT_UNCHANGED_SCOPED_SOURCE_APPROVAL',
                'runtime_quality': 'INDEPENDENT_ORIGINAL_SOURCE_AND_CURRENT_MODEL_ACCEPTANCE_REQUIRED',
                'hosted_operations': 'CURRENT_RUNTIME_HOSTED_ACCEPTANCE_REQUIRED',
                'build_checks': 'PROVIDER_FREE_BINDINGS_ONLY'},
            'fallback_enabled': False, 'answer_cache_enabled': False,
            'backend_base_image': release.BASE_IMAGE,
            'ui_base_image': release.UI_BASE_IMAGE,
            'input_tree_sha256': hashlib.sha256(json.dumps(bindings, sort_keys=True,
                separators=(',', ':')).encode()).hexdigest()}
        target = root / release.CURRENT
        release.dump(target, manifest)
        target.with_suffix('.sha256').write_text(release.digest(target))
        return target, manifest

    def verify(self, root, **options):
        with patch.object(release, 'verify_history', return_value=64), patch.object(
                release, 'verify_serving_history', return_value=release.HISTORICAL_SERVING), patch.object(
                release, 'verify_source_bindings', return_value={}), patch.object(
                release, 'serving_inputs', return_value=['runtime.py']):
            return release.verify(root, **options)

    def test_changed_current_runtime_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            self.verify(root)
            (root / 'runtime.py').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SERVING_INPUT_CHANGED:runtime.py'):
                self.verify(root)

    def test_missing_or_extra_binding_rejected_even_with_new_manifest_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, manifest = self.fixture(root)
            manifest['file_sha256']['new_unreviewed.py'] = 'a' * 64
            release.dump(target, manifest, exclusive=False)
            target.with_suffix('.sha256').write_text(release.digest(target))
            with self.assertRaisesRegex(ValueError, 'SERVING_INPUT_INVENTORY_CHANGED'):
                self.verify(root)

    def test_manifest_digest_changed_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, manifest = self.fixture(root)
            manifest['fallback_enabled'] = True
            release.dump(target, manifest, exclusive=False)
            with self.assertRaisesRegex(ValueError, 'SERVING_MANIFEST_DIGEST_CHANGED'):
                self.verify(root)

    def test_activation_requires_new_explicit_scope_not_refrozen_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, manifest = self.fixture(root)
            manifest['answer_cache_enabled'] = True
            release.dump(target, manifest, exclusive=False)
            target.with_suffix('.sha256').write_text(release.digest(target))
            with self.assertRaisesRegex(ValueError, 'SERVING_POLICY_BINDING_CHANGED'):
                self.verify(root)

    def test_worktree_matching_but_commit_changed_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            with patch.object(release, 'git_blobs', return_value={'runtime.py': b'prior-version'}):
                with self.assertRaisesRegex(ValueError, 'COMMITTED_SERVING_INPUT_CHANGED'):
                    self.verify(root, committed_revision='b' * 40)

    def test_versioned_receipts_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'receipt.json'
            release.dump(path, {'version': 1})
            before = path.read_bytes()
            release.dump(path, {'version': 1})
            with self.assertRaisesRegex(ValueError, 'NEVER_OVERWRITE_VERSIONED_RELEASE'):
                release.dump(path, {'version': 2})
            self.assertEqual(path.read_bytes(), before)

    def test_build_context_requires_committed_revision(self):
        with self.assertRaisesRegex(ValueError, 'COMMITTED_REVISION_REQUIRED'):
            release.prepare()

    def test_all_historical_snapshots_still_match_immutable_v8(self):
        # Real retained bytes are read-only; no source or historical objects mutate.
        self.assertEqual(release.verify_history(), 64)

    def test_v9_manifests_retained_without_matching_changed_active_runtime(self):
        self.assertEqual(release.verify_serving_history(), release.HISTORICAL_SERVING)

    def test_historical_manifest_and_sidecar_cannot_be_refrozen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in release.HISTORICAL_SERVING:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((release.ROOT / name).read_bytes())
                target.with_suffix('.sha256').write_bytes((release.ROOT / name).with_suffix('.sha256').read_bytes())
            name = next(iter(release.HISTORICAL_SERVING))
            target = root / name
            target.write_bytes(target.read_bytes() + b' ')
            target.with_suffix('.sha256').write_text(release.digest(target))
            with self.assertRaisesRegex(ValueError, 'HISTORICAL_SERVING_MANIFEST_CHANGED'):
                release.verify_serving_history(root)

    def test_v10_binds_every_existing_canonical_source_dependency(self):
        bindings = release.verify_source_bindings()
        approved = json.loads((release.ROOT / release.APPROVAL).read_bytes())
        names = set(release.serving_inputs())
        self.assertEqual(bindings[release.MANUAL], release.MANUAL_SHA)
        self.assertTrue(set(bindings) <= names)
        planner_names = {r['artifact_bindings']['planner_case_locator']['file'] for r in approved['records']}
        self.assertEqual(len(planner_names), 161)
        self.assertTrue(planner_names <= names)
        self.assertIn('rider_ui/public_edge.py', names)

    def test_role_cache_and_authority_mutations_need_new_scope(self):
        changes = (
            ('primary_model', 'claude-haiku-5-5'), ('verifier_model', 'gemma-4-26b-a4b-it'),
            ('verifier_enabled', False), ('prompt_cache', 'ANSWER_CACHE'),
            ('verification_authority', 'RANKING_CONFIDENCE'), ('billing_changed', True),
            ('public_release_approved', True), ('fallback_enabled', True),
            ('answer_cache_enabled', True), ('deployment_authorized', False),
        )
        for name, value in changes:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _, manifest = self.fixture(root)
                manifest[name] = value
                with self.assertRaises(ValueError):
                    validate_policy(manifest, root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, manifest = self.fixture(root)
            for name, field, altered in (
                    ('draft_model_contract', 'model', 'alternate-draft'),
                    ('verifier_contract', 'fallback_role', True),
                    ('verifier_contract', 'cache_ttl', '1h'),
                    ('owner_authorization', 'sha256', '0' * 64),
                    ('acceptance', 'runtime_quality', 'ACCEPTED_BY_BUILD')):
                candidate = deepcopy(manifest)
                candidate[name][field] = altered
                with self.subTest(name=name, field=field), self.assertRaises(ValueError):
                    validate_policy(candidate, root)
            (root / release.OWNER_SCOPE).write_text('{}')
            with self.assertRaisesRegex(ValueError, 'SERVING_OWNER_AUTHORIZATION_CHANGED'):
                validate_policy(manifest, root)

    def test_prepare_v10_carries_public_edge_but_keeps_original_pdf_backend_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, manifest = self.fixture(root)
            manifest['index'] = {'snapshot': {'uri': 'gs://private/immutable.tar.gz',
                'generation': '123', 'sha256': 'a' * 64, 'maximum_bytes': 1024}}
            blobs = {'rider_ui/Dockerfile': b'FROM pinned-ui-base\nCMD ["public_edge"]\n',
                'rider_ui/public_edge.py': b'public edge code', 'controller_contracts.py': b'contracts',
                release.MANUAL: b'synthetic source PDF', 'runtime.py': b'candidate-runtime',
                release.OWNER_SCOPE: (release.ROOT / release.OWNER_SCOPE).read_bytes()}
            manifest['file_sha256'] = {n: hashlib.sha256(v).hexdigest() for n, v in blobs.items()}
            with patch.object(release, 'verify', return_value=manifest), patch.object(release, 'git_blobs', return_value=blobs):
                receipt = release.prepare(root, committed_revision='c' * 40)
            self.assertEqual(receipt['runtime_revision'], 'v10')
            self.assertEqual(receipt['schema_version'], 'serving-v10-hosted-build-preparation-v1')
            self.assertTrue((root / 'build/serving-v10/ui/rider_ui/public_edge.py').exists())
            self.assertFalse((root / 'build/serving-v10/ui' / release.MANUAL).exists())
            self.assertTrue((root / 'build/serving-v10/backend' / release.MANUAL).exists())
            self.assertIn('"--threads", "8"', (root / 'build/serving-v10/backend/Dockerfile').read_text())
            self.assertIn(':serving-v10-', receipt['contexts']['ui']['image_tag'])
            self.assertFalse(receipt['quality_acceptance'])
            self.assertFalse(receipt['hosted_operations_acceptance'])

    def test_hosted_validation_cannot_replace_frozen_generation_with_same_hash(self):
        reference = {'uri':'gs://private/index.tar.gz', 'generation':'123',
                     'sha256':'a'*64, 'maximum_bytes':1024}
        candidate = {'index':{'snapshot':reference}}
        check_snapshot_binding(candidate, dict(reference))
        for name, altered in (('generation','124'), ('uri','gs://other/index.tar.gz'),
                              ('sha256','b'*64), ('maximum_bytes',2048)):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError,
                    'HOSTED_SNAPSHOT_DIFFERS_FROM_FROZEN_REFERENCE'):
                check_snapshot_binding(candidate, dict(reference, **{name:altered}))


if __name__ == '__main__':
    unittest.main()
