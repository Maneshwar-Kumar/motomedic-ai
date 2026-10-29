"""Synthetic v11 release binding checks, with no cloud, images or providers."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch

from tools import serving_release as release
from tools import check_installed_serving_release as policy
from cloud.grounded_generation import section_index
from cloud.grounded_generation.test_section_fixture import build


def synthetic_index(path):
    """The synthetic fixture plus the manifest fields a real build records."""
    build(path)
    manifest = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    manifest.update(built_from_index_id='index_a3282c4d98cf54595e4ba168', cached_parse_sha256='p' * 64,
                    review_layer='NONE')
    manifest['qa'].update(box_chunks=2, box_chunks_attached=2, page_break_continuations=0, pages_covered=3,
                          pdf_pages=149, parser_gap_pages=[103])
    (path / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8')
    (path / 'reranker_model').mkdir()
    return path


class ReleaseTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'runtime.py').write_bytes(b'candidate-runtime')
        for name in (*policy.OWNER_DECISIONS, policy.EVALUATION):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(release.ROOT / name, target)
        index = synthetic_index(root / 'build/section-index')
        identity, index_release = release.index_policy(index)
        with self.patched():
            manifest = release.freeze(root, index_dir=index)
        return root / release.CURRENT, manifest

    def patched(self):
        class Both:
            def __enter__(inner):
                inner.patches = [patch.object(release, 'verify_previous', return_value=release.PREVIOUS),
                    patch.object(release, 'serving_inputs', return_value=['runtime.py']),
                    patch.object(release, 'regression_binding', return_value={'run': 'synthetic', 'passed': True})]
                for p in inner.patches:
                    p.start()
            def __exit__(inner, *exc):
                for p in inner.patches:
                    p.stop()
        return Both()

    def verify(self, root, **options):
        with self.patched():
            return release.verify(root, **options)

    def rewrite(self, target, manifest):
        release.dump(target, manifest, exclusive=False)
        target.with_suffix('.sha256').write_text(release.digest(target))

    def test_freeze_binds_inputs_index_contract_and_authorizes_no_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, manifest = self.fixture(root)
            self.assertEqual(self.verify(root), manifest)
            self.assertEqual(manifest['file_sha256'], {'runtime.py': hashlib.sha256(b'candidate-runtime').hexdigest()})
            self.assertEqual(manifest['index'], section_index.identity(root / 'build/section-index'))
            self.assertEqual((manifest['review_layer'], manifest['verifier'], manifest['generation_contract']['effort'],
                              manifest['token_ceiling']), ('NONE', 'NONE', 'high', 'NONE'))
            self.assertEqual([row['path'] for row in manifest['owner_decisions']], list(policy.OWNER_DECISIONS))
            self.assertEqual((manifest['deployment_authorized'], manifest['billing_changed'], manifest['provider_calls']),
                             (False, False, 0))
            self.assertEqual(manifest['index_release']['hosted_qdrant_collection'], 'NOT_UPLOADED')
            with self.patched(), self.assertRaisesRegex(ValueError, 'NEVER_OVERWRITE'):
                release.freeze(root, index_dir=root / 'build/section-index')

    def test_changed_runtime_or_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, manifest = self.fixture(root)
            (root / 'runtime.py').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SERVING_INPUT_CHANGED:runtime.py'):
                self.verify(root)
            (root / 'runtime.py').write_bytes(b'candidate-runtime')
            manifest['file_sha256']['new_unreviewed.py'] = 'a' * 64
            self.rewrite(target, manifest)
            with self.assertRaisesRegex(ValueError, 'SERVING_INPUT_INVENTORY_CHANGED'):
                self.verify(root)

    def test_edited_manifest_needs_its_digest_and_cannot_change_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, manifest = self.fixture(root)
            changed = deepcopy(manifest); changed['verifier'] = 'claude-haiku-5-5'
            release.dump(target, changed, exclusive=False)
            with self.assertRaisesRegex(ValueError, 'DIGEST_CHANGED'):
                self.verify(root)
            for field, value in (('verifier', 'claude-haiku-5-5'), ('review_layer', 'AGENT_RELEASE_161'),
                                 ('deployment_authorized', True), ('fallback_enabled', True), ('token_ceiling', 2000000),
                                 ('schema_version', 'motomedic-serving-release-v10'), ('index_id', 'index_a3282c4d98cf54595e4ba168')):
                changed = deepcopy(manifest); changed[field] = value
                self.rewrite(target, changed)
                with self.subTest(field=field), self.assertRaises(ValueError):
                    self.verify(root)
            changed = deepcopy(manifest); changed['generation_contract']['effort'] = 'medium'
            self.rewrite(target, changed)
            with self.assertRaisesRegex(ValueError, 'POLICY_CHANGED'):
                self.verify(root)
            changed = deepcopy(manifest); changed['acceptance']['runtime_quality'] = 'ACCEPTED'
            self.rewrite(target, changed)
            with self.assertRaisesRegex(ValueError, 'BUILD_CANNOT_GRANT_RUNTIME_ACCEPTANCE'):
                self.verify(root)

    def test_changed_owner_decision_or_evaluation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / policy.EVALUATION).write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'BINDING_CHANGED:evaluation'):
                self.verify(root)
            shutil.copyfile(release.ROOT / policy.EVALUATION, root / policy.EVALUATION)
            (root / policy.OWNER_DECISIONS[-1]).write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'BINDING_CHANGED:owner_decisions'):
                self.verify(root)

    def test_index_policy_refuses_a_changed_index(self):
        with tempfile.TemporaryDirectory() as directory:
            index = synthetic_index(Path(directory) / 'index')
            shutil.rmtree(index / 'reranker_model')
            with self.assertRaisesRegex(ValueError, 'RERANKER_MISSING'):
                release.index_policy(index)

    def test_serving_inventory_covers_code_ui_workflows_and_history(self):
        names = set(release.serving_inputs(release.ROOT))
        for required in ('cloud/grounded_generation/section_questions.py', 'cloud/grounded_generation/haiku_answer.py',
                         'cloud/common/session.py', 'cloud/arm_a/app.py', 'rider_ui/client.py', '.github/workflows/ci.yml',
                         'source/source_manifest.json', 'ingest/online_ingest.py', release.MANUAL, *policy.OWNER_DECISIONS,
                         'releases/serving_manifest_v11.sha256'):
            self.assertIn(required, names)
        for retired in ('cloud/grounded_generation/verified_qa.py', 'cloud/grounded_generation/token_ceiling.py',
                        'archive/legacy_root/approved_registry.py', 'tools/manage_primary_token_ceiling.py'):
            self.assertNotIn(retired, names)
        self.assertFalse([n for n in names if n.startswith(('archive/', 'reports/', 'human_review/'))])


if __name__ == '__main__':
    unittest.main()
