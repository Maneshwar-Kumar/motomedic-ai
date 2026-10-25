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
        manifest.update(candidate_source_commit='c' * 40, source_commit_status='EXACT_COMMITTED_BLOBS_VERIFIED')
        self.save(root, manifest)
        return manifest

    def save(self, root, manifest):
        (root / 'arm_a_release.json').write_text(json.dumps(manifest), encoding='utf-8')

    def check(self, root):
        with patch('cloud.grounded_generation.haiku_answer.HaikuAnswer.__init__',
                   side_effect=AssertionError('MUST_NOT_CREATE_PROVIDER')):
            return check(root)

    def test_exact_installed_runtime_and_section_index_checked_without_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            self.assertEqual(self.check(root), 1)

    def test_modified_installed_file_or_index_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / 'runtime.py').write_bytes(b'changed after commit')
            with self.assertRaisesRegex(ValueError, 'INSTALLED_SERVING_INPUT_CHANGED:runtime.py'):
                self.check(root)
            (root / 'runtime.py').write_bytes(b'candidate-runtime')
            (root / 'build/section-index/chunks.jsonl').write_text('', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'SECTION_INDEX_FILE_CHANGED:chunks.jsonl'):
                self.check(root)

    def test_unbound_commit_schema_or_policy_change_is_rejected(self):
        for name, changed in (('candidate_source_commit', 'main'), ('source_commit_status', 'UNVERIFIED'),
                              ('schema_version', 'motomedic-serving-release-v10'), ('verifier', 'claude-haiku-5-5'),
                              ('manual_checksum', 'f' * 64), ('index_id', 'another-index')):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                candidate = self.fixture(root)
                candidate[name] = changed
                self.save(root, candidate)
                with self.assertRaises(ValueError):
                    self.check(root)

    def test_installed_release_cannot_grant_quality_or_operation_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = self.fixture(root)
            candidate['acceptance']['runtime_quality'] = 'ACCEPTED_BY_DOCKER_BUILD'
            self.save(root, candidate)
            with self.assertRaisesRegex(ValueError, 'BUILD_CANNOT_GRANT_RUNTIME_ACCEPTANCE'):
                self.check(root)


if __name__ == '__main__':
    unittest.main()
