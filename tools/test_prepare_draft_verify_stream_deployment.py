"""Offline packaging integrity checks; no Docker, providers or cloud access."""
import hashlib
import tempfile
from pathlib import Path
import unittest

from tools.prepare_draft_verify_stream_deployment import (
    REQUIRED, production_files, release_check, safe_path, verify_bindings, write_exact)


class PackagingTests(unittest.TestCase):
    def test_mutated_worktree_or_git_never_authorized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'runtime.py').write_bytes(b'original')
            bindings = {'runtime.py': hashlib.sha256(b'original').hexdigest()}
            verify_bindings(root, bindings, {'runtime.py': b'original'})
            with self.assertRaisesRegex(ValueError, 'FROZEN_GIT_CHANGED'):
                verify_bindings(root, bindings, {'runtime.py': b'uncommitted prior bytes'})
            (root / 'runtime.py').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'FROZEN_WORKTREE_CHANGED'):
                verify_bindings(root, bindings, {'runtime.py': b'original'})

    def test_heldout_runners_excluded_and_budget_required(self):
        paths = dict.fromkeys(REQUIRED | {'tools/validate_claude_fallback.py',
            '.github/workflows/claude-evidence-fallback.yml',
            'cloud/grounded_generation/test_claude_fallback.py',
            'rider_ui/tests/test_client.py'}, 'fixture')
        self.assertEqual(set(production_files(paths)), REQUIRED)
        paths.pop('cloud/grounded_generation/claude_budget.py')
        with self.assertRaisesRegex(ValueError, 'MISSING_REQUIRED_ADAPTER_OR_STORE'):
            production_files(paths)

    def test_full_installed_release_rejects_inherited_or_overlay_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = {'inherited_index.json': b'index', 'claude_provider.py': b'adapter'}
            for name, raw in names.items():
                (root / name).write_bytes(raw)
            release = {'file_sha256': {n: hashlib.sha256(raw).hexdigest() for n, raw in names.items()}}
            release_check(root, release)
            for name, raw in names.items():
                with self.subTest(name=name):
                    (root / name).write_bytes(b'corrupt')
                    with self.assertRaisesRegex(ValueError, 'Production runtime binding mismatch'):
                        release_check(root, release)
                    (root / name).write_bytes(raw)

    def test_package_paths_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'UNSAFE_PACKAGE_PATH'):
                safe_path(Path(directory), '../elsewhere')

    def test_reconstruct_preserves_saved_report_and_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'receipt.json'
            write_exact(path, b'bound')
            before = path.stat().st_mtime_ns
            write_exact(path, b'bound')
            self.assertEqual(path.stat().st_mtime_ns, before)
            with self.assertRaisesRegex(ValueError, 'PREPARED_REPORT_CHANGED'):
                write_exact(path, b'changed')
            self.assertEqual(path.read_bytes(), b'bound')


if __name__ == '__main__':
    unittest.main()
