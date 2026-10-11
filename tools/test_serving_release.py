"""Synthetic release binding checks, with no cloud, images or providers."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import serving_release as release
from tools.validate_serving_artifacts_hosted import check_snapshot_binding


class ReleaseTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'runtime.py').write_bytes(b'candidate-runtime')
        bindings = {'runtime.py': hashlib.sha256(b'candidate-runtime').hexdigest()}
        manifest = {'schema_version': 'motomedic-serving-release-v9',
            'file_sha256': bindings, 'manual_checksum': release.MANUAL_SHA,
            'index_id': release.INDEX, 'source_approval': {'sha256': release.APPROVAL_SHA},
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
