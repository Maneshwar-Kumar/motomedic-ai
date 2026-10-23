"""Synthetic local health routing/identity checks; no cloud/model/providers."""
import base64
import json
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch  # noqa: F401  (used by subclasses)

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
        source = SimpleNamespace(checksum='a'*64,index_id='synthetic-index',variant='Himalayan BS6')
        self.app = create_app(source)
        self.app.config.update(DURABLE_DISPATCH_CONFIGURED=True,ANSWER_PROVIDER='claude-haiku-5-5',
            PROMPT_CACHE='ANTHROPIC_SYSTEM_PROMPT_5M',RETRIEVAL='section-top5-hybrid-v1',
            DENSE_BACKEND='EXACT_PINNED_VECTORS',RUNTIME_LOCK='b'*64)
        self.client = self.app.test_client()
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
        self.assertIsNone(external.json['verifier_provider'])
        self.assertEqual(external.json['review_layer'],'NONE')
        self.assertEqual(external.json['architecture'],'SECTION_TOP5_SINGLE_CALL_TEMPLATE_GATE')
        self.assertEqual(external.json['prompt_cache'],'ANTHROPIC_SYSTEM_PROMPT_5M')
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
