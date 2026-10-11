"""Synthetic installed-image policy checks; no cloud, model or provider calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.check_installed_serving_release import check
from tools import test_serving_release as release_fixture


class InstalledReleaseTests(unittest.TestCase):
    def fixture(self, root):
        _, manifest = release_fixture.ReleaseTests().fixture(root)
        manifest.update(candidate_source_commit='c' * 40,
                        source_commit_status='EXACT_COMMITTED_BLOBS_VERIFIED',
                        index={'snapshot': {'uri': 'gs://private/index.tar.gz',
                            'generation': '123', 'sha256': 'a' * 64, 'maximum_bytes': 1024}})
        self.save(root, manifest)
        return manifest

    def save(self, root, manifest):
        (root / 'arm_a_release.json').write_text(json.dumps(manifest), encoding='utf-8')

    def check(self, root):
        with (patch('human_review.agent_release_161.approval_consumer.ApprovalConsumer') as consumer,
                patch('cloud.grounded_generation.cached_verifier.CachedVerifier.__init__',
                      side_effect=AssertionError('MUST_NOT_CREATE_PROVIDER'))):
            count = check(root)
        consumer.assert_called_once_with(root.resolve(),
            'human_review/agent_release_161/coordinator/release_manifest_v3.json')
        return count

    def test_exact_installed_runtime_checked_without_provider_construction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            self.assertEqual(self.check(root), 1)

    def test_modified_installed_file_rejected_before_approval_consumption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / 'runtime.py').write_bytes(b'changed after commit')
            with self.assertRaisesRegex(ValueError, 'INSTALLED_SERVING_INPUT_CHANGED:runtime.py'):
                self.check(root)

    def test_source_commit_or_role_swap_rejected(self):
        for name, changed in (('candidate_source_commit', 'main'),
                              ('source_commit_status', 'UNVERIFIED'),
                              ('schema_version', 'motomedic-serving-release-v9'),
                              ('verifier_model', 'gemma-4-26b-a4b-it'),
                              ('manual_checksum', 'f' * 64), ('index_id', 'another-index')):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                candidate = self.fixture(root)
                candidate[name] = changed
                self.save(root, candidate)
                with self.assertRaises(ValueError):
                    self.check(root)

    def test_installed_contract_cannot_replace_factual_or_operation_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = self.fixture(root)
            candidate['acceptance']['runtime_quality'] = 'ACCEPTED_BY_DOCKER_BUILD'
            self.save(root, candidate)
            with self.assertRaisesRegex(ValueError, 'BUILD_CANNOT_GRANT_RUNTIME_ACCEPTANCE'):
                self.check(root)


if __name__ == '__main__':
    unittest.main()
