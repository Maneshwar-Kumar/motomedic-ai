"""Index-free production startup policy checks; no stores, models or providers."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cloud.arm_a import app
from cloud.grounded_generation import section_assembly, section_retrieval, template_answer
from cloud.grounded_generation.haiku_answer import CONTRACT


class ProductionPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release = {'schema_version': 'motomedic-serving-release-v11',
            'architecture': 'SECTION_TOP5_SINGLE_CALL_TEMPLATE_GATE',
            'generation_model': 'claude-haiku-5-5', 'generation_contract': deepcopy(CONTRACT),
            'retrieval_version': section_retrieval.VERSION, 'assembly_version': section_assembly.VERSION,
            'template_version': template_answer.VERSION, 'review_layer': 'NONE', 'verifier': 'NONE',
            'answer_cache_enabled': False, 'fallback_enabled': False,
            'manual_checksum': 'm' * 64, 'index_id': 'index_synthetic',
            'index': {'index_id': 'index_synthetic', 'manual_sha256': 'm' * 64}}

    def test_current_policy_passes_without_models_or_providers(self):
        app.validate_production_policy(self.release)

    def test_verifier_review_fallback_cache_or_changed_contract_rejects(self):
        for field, value in [('schema_version', 'motomedic-serving-release-v10'), ('verifier', 'claude-haiku-5-5'),
                             ('review_layer', 'AGENT_RELEASE_161'), ('fallback_enabled', True),
                             ('answer_cache_enabled', True), ('generation_model', 'claude-sonnet-5-5'),
                             ('retrieval_version', 'open-hybrid-v5'), ('template_version', 'template-answer-v2'),
                             ('architecture', 'DRAFT_VERIFY_STREAM_OPEN_MANUAL_QA'), ('index_id', 'other')]:
            changed = deepcopy(self.release); changed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, 'serving policy mismatch'):
                app.validate_production_policy(changed)
        for key, value in [('effort', 'medium'), ('verifier', 'claude-haiku-5-5'), ('fallback_model', 'claude-sonnet-5-5')]:
            changed = deepcopy(self.release); changed['generation_contract'][key] = value
            with self.subTest(contract=key), self.assertRaisesRegex(RuntimeError, 'serving policy mismatch'):
                app.validate_production_policy(changed)

    def test_loader_checks_bytes_and_policy_before_loading_models_or_index(self):
        changed = deepcopy(self.release); changed['file_sha256'] = {}; changed['verifier'] = 'claude-haiku-5-5'
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); (root / 'arm_a_release.json').write_text(json.dumps(changed), encoding='utf-8')
            with patch.object(app, 'ROOT', root), patch.dict('os.environ', {'K_SERVICE': 'synthetic-test'}), \
                    patch('cloud.grounded_generation.section_index.verify',
                          side_effect=AssertionError('index load forbidden')):
                with self.assertRaisesRegex(RuntimeError, 'serving policy mismatch'):
                    app.load_production()
            changed = deepcopy(self.release); changed['file_sha256'] = {'arm_a_release.json': '0' * 64}
            (root / 'arm_a_release.json').write_text(json.dumps(changed), encoding='utf-8')
            with patch.object(app, 'ROOT', root), patch.dict('os.environ', {'K_SERVICE': 'synthetic-test'}):
                with self.assertRaisesRegex(RuntimeError, 'runtime binding mismatch'):
                    app.load_production()

    def test_availability_fallback_switch_and_missing_secret_refuse_startup(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); release = deepcopy(self.release); release['file_sha256'] = {}
            (root / 'arm_a_release.json').write_text(json.dumps(release), encoding='utf-8')
            for env, message in (({'MOTOMEDIC_CLAUDE_FALLBACK_ENABLED': 'true'}, 'fallback'),
                                 ({'ANTHROPIC_API_KEY': ''}, 'managed secret')):
                with self.subTest(env=env), patch.object(app, 'ROOT', root), \
                        patch.dict('os.environ', {'K_SERVICE': 'synthetic-test', **env}), \
                        self.assertRaisesRegex(RuntimeError, message):
                    app.load_production()


if __name__ == '__main__':
    unittest.main()
