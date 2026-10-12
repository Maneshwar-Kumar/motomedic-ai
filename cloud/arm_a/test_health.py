"""Synthetic local health routing/identity checks; no cloud/model/providers."""
import base64
import json
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cloud.arm_a.app import create_app


def platform_verified_token():
    # Cloud Run validates this identity before app code in production.
    # This is only the request-layer fixture, never a minted credential.
    body = {'sub':'synthetic-platform-owner','iss':'https://accounts.google.com',
            'exp':time.time()+600}
    encoded = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip('=')
    return 'Bearer e30.'+encoded+'.synthetic_platform_verified_signature'


class HealthTests(unittest.TestCase):
    def setUp(self):
        registry = SimpleNamespace(checksum='a'*64,index_id='synthetic-index',
                                   source={'variant':'Himalayan BS6'})
        def no_state(_):
            raise AssertionError('Health must not load rider state or generate answers')
        self.app = create_app(registry,None,no_state,[])
        self.app.config.update(GROUNDED_PRIMARY=True,DURABLE_DISPATCH_CONFIGURED=True,
            SERVING_ARCHITECTURE='DRAFT_VERIFY_STREAM_OPEN_MANUAL_QA',
            ANSWER_PROVIDER='claude-haiku-5-5',VERIFIER_PROVIDER='claude-haiku-5-5',
            PROMPT_CACHE='ANTHROPIC_ROLE_EVIDENCE_PREFIX_5M',ARM_A_RUNTIME_LOCK='b'*64)
        self.client = self.app.test_client()
        composer = patch('cloud.arm_a.app.ArmAComposer',
            return_value=SimpleNamespace(config=SimpleNamespace(lock='c'*64)))
        composer.start()
        self.addCleanup(composer.stop)
        self.headers = {'Authorization':platform_verified_token()}

    def test_external_health_matches_startup_metadata_with_platform_identity(self):
        external = self.client.get('/v1/health',headers=self.headers)
        startup = self.client.get('/healthz')
        self.assertEqual(external.status_code,200)
        self.assertEqual(startup.status_code,200)
        self.assertEqual(external.json,startup.json)
        self.assertEqual(external.json['runtime_lock'],'b'*64)
        self.assertEqual(external.json['manual_checksum'],'a'*64)
        self.assertEqual(external.json['index_id'],'synthetic-index')
        self.assertEqual(external.json['answer_provider'],'claude-haiku-5-5')
        self.assertEqual(external.json['verifier_provider'],'claude-haiku-5-5')
        self.assertEqual(external.json['prompt_cache'],'ANTHROPIC_ROLE_EVIDENCE_PREFIX_5M')
        self.assertEqual(external.headers['Cache-Control'],'no-store')

    def test_external_health_requires_application_identity_but_startup_probe_does_not(self):
        with patch('builtins.print'):
            denied = self.client.get('/v1/health')
        self.assertEqual(denied.status_code,401)
        self.assertEqual(denied.json['error'],'AUTH_REQUIRED')
        self.assertEqual(self.client.get('/healthz').status_code,200)

    def test_both_paths_preserve_dispatcher_not_ready_status(self):
        self.app.config['DURABLE_DISPATCH_CONFIGURED'] = False
        external = self.client.get('/v1/health',headers=self.headers)
        startup = self.client.get('/healthz')
        self.assertEqual(external.status_code,503)
        self.assertEqual(startup.status_code,503)
        self.assertEqual(external.json,startup.json)
        self.assertFalse(external.json['ready'])


if __name__=='__main__':
    unittest.main()
