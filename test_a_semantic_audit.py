import unittest
from unittest.mock import patch, Mock
from dataclasses import asdict
import json
from pathlib import Path
from audit_a_semantic import recover, obj_sha, RUN, MODEL
from approved_registry import ApprovedEvidenceRegistry
from architecture_benchmark import check_texts
from generation_providers import ProviderResult
from constrained_generator import ValidationFailure
from audit_a_semantic import classify


class StrictAuditTests(unittest.TestCase):
    def test_acceptance(self):
        self.assertEqual(classify({'supported': [True, True], 'complete': [True, True],
                                   'unsupported_additions': False}, 2), 'VALID_ACCEPTANCE')

    def test_rejections(self):
        for output in ({'supported': [False, True], 'complete': [True, True], 'unsupported_additions': False},
                       {'supported': [True, True], 'complete': [False, True], 'unsupported_additions': False},
                       {'supported': [True, True], 'complete': [True, True], 'unsupported_additions': True}):
            self.assertEqual(classify(output, 2), 'VALID_REJECTION')

    def test_malformed_never_accepts(self):
        for output in ({'supported': [True, True], 'complete': [True, True], 'unsupported_additions': [False, False]},
                       {'supported': [True], 'complete': [True], 'unsupported_additions': False},
                       {'supported': [1, 1], 'complete': [True, True], 'unsupported_additions': False},
                       {'supported': [True, True], 'complete': [True, True], 'unsupported_additions': False, 'extra': 1}):
            self.assertEqual(classify(output, 2), 'MALFORMED_SCHEMA')


class ExactReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        index = Path('build/index-bge-final')
        if not index.exists():
            index = Path('build/index')
        cls.registry = ApprovedEvidenceRegistry.load('.', index)
        cls.bundles = recover(cls.registry)

    def test_all_initial_repeat_hashes_and_unique_inputs(self):
        self.assertEqual(len(self.bundles), 3)
        self.assertEqual(len({b['verifier_input_sha256'] for b in self.bundles}), 3)
        for b in self.bundles:
            self.assertEqual(len(b['provenance']), 2)
            self.assertEqual({p['content_sha256'] for p in b['provenance']}, {b['delivery_sha256']})

    def test_original_check_texts_byte_equivalent_inputs(self):
        class Capture:
            def complete(self, policy, payload, schema):
                self.input = [policy, payload, schema]
                return ProviderResult({'supported': [True] * len(payload['claims']),
                                       'complete': [True] * len(payload['claims']),
                                       'unsupported_additions': False}, 0, 0, None, {})
        for b in self.bundles:
            step = self.registry.step(b['step_id'])
            allowed = {'kind': step.kind, 'claims': [
                {'wording': [c['text'], *c.get('reviewed_wording_variants', [])],
                 'role': c['response_role'], 'evidence_ids': c['evidence_ids']}
                for c in step.claims]}
            capture = Capture()
            check_texts(capture, self.registry, allowed, list(range(len(b['texts']))), b['texts'])
            self.assertEqual(capture.input, [b['policy'], b['payload'], b['schema']])
            self.assertEqual(obj_sha(capture.input), b['verifier_input_sha256'])

    def test_original_run_mutation_rejects(self):
        with patch('audit_a_semantic.sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'Original run changed'):
                recover(self.registry)

    def test_original_runtime_mutation_rejects(self):
        with patch('audit_a_semantic.audit_config') as config:
            from generation_providers import gemma_runtime_config
            from dataclasses import replace
            config.return_value = replace(gemma_runtime_config(MODEL), max_output_tokens=399)
            with self.assertRaisesRegex(ValueError, 'Original runtime/source binding changed'):
                recover(self.registry)


class LiveBoundaryTests(unittest.TestCase):
    def test_local_live_rejected_before_provider(self):
        from audit_a_semantic import run
        with patch('audit_a_semantic.ApprovedEvidenceRegistry.load', return_value=Mock()), \
             patch('audit_a_semantic.recover', return_value=[]), \
             patch.dict('os.environ', {'GITHUB_ACTIONS': 'false'}), \
             patch('audit_a_semantic.GeminiJSONProvider') as provider:
            with self.assertRaisesRegex(ValueError, 'Provider calls must run hosted'):
                run('unused-index', 'unused-output', True)
            provider.assert_not_called()

    def test_denied_engineering_review_cannot_construct_provider(self):
        from audit_a_semantic import run
        review = {'decision': 'REJECTED'}
        approval = {'decision': 'APPROVED_EXACT_VERIFIER_ONLY_AUDIT'}
        def read_text(path, *args, **kwargs):
            return json.dumps(review if str(path).endswith('_review.json') else approval)
        with patch('audit_a_semantic.ApprovedEvidenceRegistry.load', return_value=Mock()), \
             patch('audit_a_semantic.recover', return_value=[]), \
             patch.dict('os.environ', {'GITHUB_ACTIONS': 'true'}), \
             patch.object(Path, 'read_text', read_text), \
             patch('audit_a_semantic.GeminiJSONProvider') as provider:
            with self.assertRaisesRegex(ValueError, 'Fresh audit approval binding missing'):
                run('unused-index', 'unused-output', True)
            provider.assert_not_called()
