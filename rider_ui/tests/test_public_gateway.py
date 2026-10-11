"""Synthetic trust and hosted visitor boundary checks; no cloud/providers."""
import os
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from tornado.testing import AsyncHTTPTestCase
import tornado.web
from rider_ui.public_gateway import configured, reserve_visitor, health_routes, POLICY


class PublicGatewayTests(unittest.TestCase):
    def env(self):
        return {'K_SERVICE': 'motomedic-evaluator', 'MOTOMEDIC_VISITOR_SECRET': 'x' * 64,
                'MOTOMEDIC_PUBLIC_HOST': 'motomedic-evaluator-123.us-central1.run.app',
                'MOTOMEDIC_RIDER_API_URL': 'https://motomedic-arm-a-123.us-central1.run.app',
                'MOTOMEDIC_EDGE_POLICY': POLICY, 'MOTOMEDIC_RIDER_ACCESS': 'public_gateway'}

    def test_reviewed_host_configuration_required(self):
        with patch.dict(os.environ, self.env(), clear=True):
            self.assertEqual(configured()[1], self.env()['MOTOMEDIC_PUBLIC_HOST'])
        for name, wrong in [('K_SERVICE', ''), ('MOTOMEDIC_VISITOR_SECRET', 'short'),
                            ('MOTOMEDIC_PUBLIC_HOST', 'attacker.example'),
                            ('MOTOMEDIC_EDGE_POLICY', 'gcp-external-alb-v1'),
                            ('MOTOMEDIC_RIDER_API_URL', 'https://user:pass@foo.run.app')]:
            values = self.env(); values[name] = wrong
            with patch.dict(os.environ, values, clear=True), self.assertRaises(RuntimeError):
                configured()

    def test_only_hashed_proof_reaches_private_managed_backend(self):
        response = MagicMock(); response.status_code = 200
        response.json.return_value = {'ready': True}
        response.__enter__.return_value = response
        with patch('rider_ui.public_gateway.cloud_run_token', return_value='synthetic-id-token') as identity, \
                patch('requests.post', return_value=response) as send:
            reserve_visitor(self.env()['MOTOMEDIC_RIDER_API_URL'], 'a' * 64)
            identity.assert_called_once_with(self.env()['MOTOMEDIC_RIDER_API_URL'])
            self.assertEqual(send.call_args.kwargs['json'], {'proof_sha256': 'a' * 64})
            self.assertFalse(send.call_args.kwargs['allow_redirects'])

    def test_admission_redirect_or_incomplete_receipt_fails_closed(self):
        for status, result in [(302, {'ready': True}), (200, {}), (429, {'ready': False})]:
            response = MagicMock(); response.status_code = status
            response.json.return_value = result; response.__enter__.return_value = response
            with patch('rider_ui.public_gateway.cloud_run_token', return_value='synthetic'), \
                    patch('requests.post', return_value=response), self.assertRaises(PermissionError):
                reserve_visitor(self.env()['MOTOMEDIC_RIDER_API_URL'], 'a' * 64)


class GatewayHealthTests(AsyncHTTPTestCase):
    """Real loopback HTTP exercises health routing with an in-memory upstream."""

    def get_app(self):
        self.worker = MagicMock()
        self.worker.poll.return_value = None
        self.calls = []
        self.upstream_code = 200
        self.upstream_error = None

        async def fetch(url, **kwargs):
            self.calls.append((url, kwargs))
            if self.upstream_error:
                raise self.upstream_error
            return SimpleNamespace(code=self.upstream_code, body=b'private-upstream-state')

        return tornado.web.Application(health_routes(
            self.worker, SimpleNamespace(fetch=fetch), 'http://127.0.0.1:8501'))

    def assert_health(self, path, code, ready):
        response = self.fetch(path)
        self.assertEqual(response.code, code)
        self.assertEqual(json.loads(response.body), {'ready': ready})
        self.assertNotIn('Set-Cookie', response.headers)
        self.assertNotIn(b'private-upstream-state', response.body)

    def test_external_and_internal_health_paths_report_live_upstream(self):
        for path in ('/health', '/healthz'):
            self.assert_health(path, 200, True)
        self.assertEqual(self.calls, [
            ('http://127.0.0.1:8501/_stcore/health', {'request_timeout': 2}),
            ('http://127.0.0.1:8501/_stcore/health', {'request_timeout': 2})])

    def test_exited_streamlit_is_unready_without_querying_upstream(self):
        self.worker.poll.return_value = 1
        self.assert_health('/health', 503, False)
        self.assert_health('/healthz', 503, False)
        self.assertEqual(self.calls, [])

    def test_unhealthy_or_unreachable_upstream_returns_sanitized_unready(self):
        self.upstream_code = 503
        self.assert_health('/health', 503, False)
        self.upstream_error = RuntimeError('private-upstream-state')
        self.assert_health('/health', 503, False)


if __name__ == '__main__':
    unittest.main()
