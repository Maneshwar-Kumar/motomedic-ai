"""Synthetic image/source-generation/rollback rejection tests; no cloud builds."""
from copy import deepcopy
import unittest
from tools.bind_serving_images import bind, bind_build


class ImageBindingTests(unittest.TestCase):
    def fixture(self):
        preparation = {'source_commit': 'c' * 40, 'serving_manifest_sha256': 'a' * 64,
            'input_tree_sha256': 'b' * 64, 'contexts': {kind: {
                'source_archive_sha256': 'e' * 64, 'image_tag': 'registry.example/repo/' + kind + ':version',
                'installed_manifest_sha256': 'f' * 64, 'dockerfile_sha256': '1' * 64,
                'build_steps': [{'name': 'synthetic-docker-builder', 'args': ['build', '.']}],
                'build_options': {'logging':'CLOUD_LOGGING_ONLY','substitutionOption':'ALLOW_LOOSE'},
                'build_timeout':'1800s',
                'cloudbuild_sha256': '2' * 64} for kind in ('backend', 'ui')}}
        uploads = {kind: {'uri': 'gs://private-build-bucket/' + kind + '.tar.gz',
            'generation': '123', 'sha256': 'e' * 64, 'maximum_bytes': 1024} for kind in ('backend', 'ui')}
        builds = {kind: {'id': 'synthetic-' + kind, 'status': 'SUCCESS',
            'options':{'logging':'CLOUD_LOGGING_ONLY','substitutionOption':'ALLOW_LOOSE'},
            'timeout':'1800s',
            'steps': [{'name': 'synthetic-docker-builder', 'args': ['build', '.']}],
            'substitutions': {'_SOURCE_COMMIT': 'c' * 40, '_SERVING_MANIFEST_SHA256': 'a' * 64,
                '_INPUT_TREE_SHA256': 'b' * 64},
            'sourceProvenance': {'resolvedStorageSource': {'bucket': 'private-build-bucket',
                'object': kind + '.tar.gz', 'generation': '123'}},
            'results': {'images': [{'name': preparation['contexts'][kind]['image_tag'],
                'digest': 'sha256:' + 'd' * 64}]}} for kind in ('backend', 'ui')}
        rollback = {kind: {'image': 'registry.example/repo/' + kind + '@sha256:' + '9' * 64,
            'revision': 'prior-' + kind, 'service': 'service-' + kind} for kind in ('backend', 'ui')}
        rollback.update(session_schema='previous-synthetic-schema', runtime_lock='previous-runtime-lock')
        return preparation, builds, uploads, rollback

    def test_exact_pair_bound_without_promotion_claim(self):
        receipt = bind(*self.fixture())
        self.assertEqual(set(receipt['images']), {'backend', 'ui'})
        self.assertFalse(receipt['quality_acceptance'])
        self.assertFalse(receipt['deployment_authorized'])
        self.assertFalse(receipt['deployment_changed'])

    def test_build_only_requires_no_fictional_rollback_and_cannot_claim_promotion(self):
        receipt = bind_build(*self.fixture()[:3])
        self.assertEqual(receipt['binding_scope'], 'HOSTED_BUILD_PROVENANCE_ONLY')
        self.assertEqual(set(receipt['images']), {'backend', 'ui'})
        self.assertNotIn('rollback', receipt)
        for field in ('rollback_verified', 'promotion_ready', 'quality_acceptance',
                      'deployment_authorized', 'deployment_changed'):
            self.assertIs(receipt[field], False)

    def test_build_only_rejects_every_altered_build_binding(self):
        for change in ('commit', 'manifest', 'tree', 'recipe', 'generation', 'archive', 'digest', 'pair'):
            preparation, builds, uploads, _ = self.fixture()
            if change in ('commit', 'manifest', 'tree'):
                key = {'commit':'_SOURCE_COMMIT', 'manifest':'_SERVING_MANIFEST_SHA256',
                       'tree':'_INPUT_TREE_SHA256'}[change]
                builds['backend']['substitutions'][key] = 'altered'
            elif change == 'recipe':
                builds['backend']['steps'][0]['args'] = ['altered']
            elif change == 'generation':
                builds['backend']['sourceProvenance']['resolvedStorageSource']['generation'] = '124'
            elif change == 'archive':
                uploads['backend']['sha256'] = '0'*64
            elif change == 'digest':
                builds['backend']['results']['images'][0]['digest'] = 'latest'
            else:
                builds.pop('ui')
            with self.subTest(change=change), self.assertRaises(ValueError):
                bind_build(preparation, builds, uploads)

    def test_altered_source_commit_manifest_tree_or_generation_rejected(self):
        for change in ('commit', 'manifest', 'tree', 'generation', 'archive'):
            preparation, builds, uploads, rollback = self.fixture()
            if change == 'generation':
                builds['backend']['sourceProvenance']['resolvedStorageSource']['generation'] = '124'
            elif change == 'archive':
                uploads['backend']['sha256'] = '0' * 64
            else:
                key = {'commit': '_SOURCE_COMMIT', 'manifest': '_SERVING_MANIFEST_SHA256',
                    'tree': '_INPUT_TREE_SHA256'}[change]
                builds['backend']['substitutions'][key] = 'changed'
            with self.subTest(change=change), self.assertRaises(ValueError):
                bind(preparation, builds, uploads, rollback)

    def test_failed_build_mutable_digest_or_duplicate_digest_rejected(self):
        for change in ('failed', 'mutable', 'duplicate', 'wrong-tag', 'recipe', 'machine', 'timeout', 'substitution'):
            preparation, builds, uploads, rollback = self.fixture()
            if change == 'failed':
                builds['ui']['status'] = 'FAILURE'
            elif change == 'mutable':
                builds['ui']['results']['images'][0]['digest'] = 'latest'
            elif change == 'duplicate':
                builds['ui']['results']['images'].append(deepcopy(builds['ui']['results']['images'][0]))
            elif change == 'wrong-tag':
                builds['ui']['results']['images'][0]['name'] = 'wrong-image:latest'
            elif change=='machine':
                builds['ui']['options']['machineType']='E2_HIGHCPU_8'
            elif change=='timeout':
                builds['ui']['timeout']='7200s'
            elif change=='substitution':
                builds['ui']['options']['substitutionOption']='MUST_MATCH'
            else:
                builds['ui']['steps'][0]['args'] = ['changed-build-recipe']
            with self.subTest(change=change), self.assertRaises(ValueError):
                bind(preparation, builds, uploads, rollback)

    def test_rollback_requires_both_images_revisions_and_state_schema(self):
        for change in ('pair', 'digest', 'revision', 'schema'):
            preparation, builds, uploads, rollback = self.fixture()
            if change == 'pair':
                rollback.pop('ui')
            elif change == 'digest':
                rollback['ui']['image'] = 'registry.example/repo/ui:latest'
            elif change == 'revision':
                rollback['backend']['revision'] = ''
            else:
                rollback['session_schema'] = ''
            with self.subTest(change=change), self.assertRaises(ValueError):
                bind(preparation, builds, uploads, rollback)


if __name__ == '__main__':
    unittest.main()
