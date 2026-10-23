"""Offline real-composer/provider-adapter/API/UI-client wiring; no paid transport."""
from copy import deepcopy
import io
import json
import sys
import types
import unittest
from email.message import Message
from unittest.mock import patch
from flask import Flask, request
from cloud.arm_a.rider_api import install
from cloud.arm_a.store import FirestoreState
from cloud.arm_a.visitor import issue
from cloud.arm_a.test_store import Client, transactional
from cloud.grounded_generation.test_generic_runtime import Tests as SourceTests, ScriptedRetriever, BORE
from cloud.grounded_generation.test_verified_qa import Provider, draft
from cloud.grounded_generation.test_claude_fallback import Primary
from cloud.grounded_generation.claude_provider import ClaudeProvider, MODEL
from cloud.grounded_generation.fallback_provider import FallbackProvider
from cloud.grounded_generation.verified_qa import Composer, DRAFT_SCHEMA
from cloud.grounded_generation.open_questions import Questions
from cloud.grounded_generation.test_open_wiring import SyntheticTaskDispatcher
from rider_ui.client import RiderAPI
from generation_providers import ProviderFailure


class TurnPrimary(Primary):
    """Availability fixture implements the new whole-turn reservation contract."""
    def context(self,*args):
        raise ProviderFailure(self.failure)
    def begin_turn(self,operation_id,availability_fallback=False):
        return {'operation_id':operation_id,'synthetic':True,'availability_fallback':availability_fallback}
    def end_turn(self):pass


class ScriptedHTTP:
    """Exercises actual Claude schema/count/reservation adapter without network."""
    def __init__(self, reject=False, malformed=False):
        def verdict(output, *_):
            if reject:
                output.update(decision='SHOW_FALLBACK', question_coverage='IRRELEVANT', release_eligible=False)
            return output
        self.script = Provider([draft()], verdict)
        self.malformed = malformed
        self.paths = []

    def __call__(self, method, path, body, key):
        self.paths.append(path)
        if path.endswith('count_tokens'):
            return {'input_tokens': 100}
        payload = json.loads(body['messages'][0]['content'])
        schema = body['output_config']['format']['schema']
        output = self.script.complete(body['system'], payload['assembled_evidence'], payload['request'], schema).output
        if self.malformed and schema != DRAFT_SCHEMA:
            output = {}
        return {'model': MODEL, 'stop_reason': 'end_turn',
                'content': [{'type': 'text', 'text': json.dumps(output)}],
                'usage': {'input_tokens': 100, 'output_tokens': 20}}


class APIResponse(io.BytesIO):
    def __init__(self, response):
        super().__init__(response.data)
        self.status = response.status_code
        self.headers = Message()
        self.headers['Content-Type'] = response.content_type
    def read1(self, size=-1):
        return self.read(size)


class FlaskTransport:
    def __init__(self, app):
        self.app = app
    def open(self, req, timeout=None):
        # This adapter replaces only HTTP I/O; RiderAPI validation is production strict.
        from urllib.parse import urlsplit
        with self.app.test_client() as client:
            response = client.open(urlsplit(req.full_url).path, method=req.method,
                                   data=req.data, headers=dict(req.header_items()))
            if response.status_code != 200:
                raise AssertionError('Unexpected private test API status: '+str(response.status_code))
            return APIResponse(response)


class UIFallbackWiringTests(unittest.TestCase):
    setUpClass = classmethod(SourceTests.setUpClass.__func__)
    chunk = SourceTests.chunk
    source_setup = SourceTests.setUp

    def run_case(self, *, reject=False, malformed=False):
        self.source_setup()
        transport = ScriptedHTTP(reject, malformed)
        reservations = []; costs = []
        primary = TurnPrimary('PROVIDER_HTTP_500')
        fallback = ClaudeProvider(lambda n, k: reservations.append((n, k)),
            reserve_cost=lambda n, m: costs.append((n, m)), transport=transport, key='offline-fixture-only')
        chain = FallbackProvider(primary, fallback)
        composer = Composer(chain, self.authority)
        questions = Questions(self.registry, ScriptedRetriever(self.authority, [self.chunk(BORE)]), composer, self.authority)
        database = Client()
        google = types.ModuleType('google'); cloud = types.ModuleType('google.cloud')
        firestore = types.ModuleType('google.cloud.firestore'); firestore.transactional = transactional
        google.cloud = cloud; cloud.firestore = firestore
        with patch.dict(sys.modules, {'google': google, 'google.cloud': cloud, 'google.cloud.firestore': firestore}):
            app = Flask(__name__)
            @app.before_request
            def identity():
                request.environ['arm_a_owner'] = 'synthetic-platform-owner'
            secret = 'offline-test-only-'+'x'*40
            dispatcher = SyntheticTaskDispatcher(); dispatcher.app = app
            install(app, questions, lambda owner: FirestoreState(database, owner), secret, dispatcher=dispatcher)
            client = RiderAPI('https://offline.invalid', 'offline-token', visitor=issue(secret))
            client.opener = FlaskTransport(app)
            self.assertFalse(client.engineering_loopback)
            self.assertEqual(client.catalogue()['streaming'], 'DRAFT_VERIFY_STREAM')
            accepted = []; pieces = []; stages = []
            def on_verified(view):
                self.assertTrue(any(row.get('state') == 'COMPLETE' for key, row in database.data.items()
                                    if key.startswith('arm_a_operations/')))
                accepted.append(deepcopy(view))
            op = 'b'*32
            view = client.start('How wide is the cylinder bore?', op, on_verified=on_verified,
                                on_progress=stages.append, on_chunk=pieces.append)
            self.assertEqual(client.recover_operation(op), view)
            call_count = len(transport.paths)
            self.assertEqual(client.start('How wide is the cylinder bore?', op), view)
            self.assertEqual(len(transport.paths), call_count)
            self.assertEqual(len(reservations), 2)
            self.assertEqual(len(costs), 1)
            from cloud.grounded_generation.claude_provider import MAX_CALL_USD
            self.assertEqual(costs[0], (4*MAX_CALL_USD, MODEL))
            self.assertEqual(primary.calls, 2)
            self.assertEqual(len(transport.script.calls), 2)
            self.assertTrue(chain.last_trace['fallback_used'])
            self.assertEqual(stages[:3], ['retrieving', 'drafting', 'verifying'])
            # Authenticated server telemetry exists in the saved view; product text
            # never displays it. Raw drafts/verdicts and keys must remain absent.
            self.assertNotIn('last_trace', view)
            self.assertNotIn('offline-fixture-only', json.dumps(view))
            self.assertNotIn('complete_proposed_response', json.dumps(view))
            self.assertNotIn('per_claim_support', json.dumps(view))
            self.assertNotIn(MODEL, view['response']['natural_language'])
            dispatcher.join()
            return view, accepted, pieces, stages

    def test_actual_composer_haiku_adapter_saved_stream_and_ui_recovery(self):
        view, accepted, pieces, stages = self.run_case()
        self.assertEqual(view['response']['type'], 'SUPPORTED')
        self.assertEqual(accepted, [view])
        self.assertEqual(''.join(pieces), view['response']['natural_language'])
        self.assertEqual(stages[-1], 'displaying')
        self.assertTrue(view['response']['semantic_verification_passed'])

    def test_haiku_semantic_rejection_never_displays_private_draft(self):
        view, accepted, pieces, stages = self.run_case(reject=True)
        self.assertEqual(view['response']['type'], 'UNSUPPORTED')
        self.assertEqual(view['response']['natural_language'], 'I couldn\u2019t find relevant information in the selected manual to answer your question. Please contact Royal Enfield or an authorised service centre.')
        self.assertEqual(accepted, []); self.assertEqual(pieces, [])
        self.assertNotIn('displaying', stages)

    def test_haiku_malformed_verdict_returns_exact_neutral_error(self):
        view, accepted, pieces, stages = self.run_case(malformed=True)
        self.assertEqual(view['response']['type'], 'SYSTEM_ERROR')
        self.assertEqual(view['response']['natural_language'], 'I couldn\u2019t check the answer right now. Please try again shortly.')
        self.assertEqual(accepted, []); self.assertEqual(pieces, [])
        self.assertNotIn('displaying', stages)


del SourceTests
if __name__ == '__main__':
    unittest.main()
