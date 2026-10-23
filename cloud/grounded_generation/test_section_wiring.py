"""Private backend/client delivery integration with the real answer path on a synthetic index.

The generation call is a fake; no model request, cloud store or manual content is used. Each
private stage and the durable save block until released, proving progress timing and that no
answer byte reaches the rider before the gate-released view is saved.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
from flask import Flask
from cloud.arm_a.rider_api import install
from cloud.arm_a.store import FirestoreState
from cloud.arm_a.visitor import issue
from cloud.arm_a.test_store import Client, transactional
from cloud.grounded_generation import section_index as si
from cloud.grounded_generation.section_assembly import SectionIndex
from cloud.grounded_generation.section_questions import ManualSource, Questions
from cloud.grounded_generation.section_retrieval import SectionRetriever
from cloud.grounded_generation.test_section_answer import EmptyRetriever, FakeGenerate, located
from cloud.grounded_generation.test_section_fixture import CrossEncoder, Embedder, SOURCE_MANIFEST, build
from rider_ui.client import MANUAL_SHA, INDEX_ID, validate_view
from rider_ui.verified_sse import read_verified_stream, response_hash

OP = 'c' * 32
FALLBACK = ('I couldn’t find relevant information in the selected manual to answer your question. '
            'Please contact Royal Enfield or an authorised service centre.')
CHECK_ERROR = 'I couldn’t check the answer right now. Please try again shortly.'


class ScriptedQuestions:
    """The real Questions pipeline, paused at each progress stage until the test releases it."""
    STAGES = ('retrieving', 'drafting', 'checking')

    def __init__(self, generate=None):
        root = build(Path(tempfile.mkdtemp(prefix='motomedic-wiring-')))
        identity = si.identity(root)
        self.real = Questions(ManualSource(SOURCE_MANIFEST, identity), SectionIndex(root),
                              SectionRetriever(root, Embedder(), CrossEncoder()), generate or FakeGenerate(located), identity)
        self.reached = {s: threading.Event() for s in self.STAGES}
        self.proceed = {s: threading.Event() for s in self.STAGES}
        self.calls = 0

    source = property(lambda self: self.real.source)
    index_lock = property(lambda self: self.real.index_lock)
    runtime_lock = property(lambda self: self.real.runtime_lock)
    generate = property(lambda self: self.real.generate)

    def new_session(self):
        return self.real.new_session()

    def validate_saved(self, view):
        return self.real.validate_saved(view)

    def fallback(self):
        self.real.retriever = EmptyRetriever(self.real.index.manifest)

    def fail_generation(self, code='CLAUDE_HTTP_529'):
        self.real.generate.failure = code

    def answer(self, session, query, *, history=(), progress=None, operation_id=None):
        self.calls += 1
        def staged(stage):
            progress(stage)
            self.reached[stage].set()
            if not self.proceed[stage].wait(5):
                raise RuntimeError('Test stage blocked: ' + stage)
        return self.real.answer(session, query, history=history, progress=staged, operation_id=operation_id)

    def release(self):
        for event in self.proceed.values():
            event.set()


class BlockingState(FirestoreState):
    def __init__(self, client, owner, entered, release):
        super().__init__(client, owner)
        self.entered, self.release = entered, release

    def commit_answer(self, *args, **kwargs):
        self.entered.set()
        if not self.release.wait(5):
            raise RuntimeError('Test commit blocked')
        return super().commit_answer(*args, **kwargs)


class SyntheticTaskDispatcher:
    """Test-only task executor with its own HTTP request and non-daemon lifetime."""
    def __init__(self):
        self.app, self.threads, self.keys, self.lock = None, [], set(), threading.Lock()

    def authenticate(self, headers):
        if headers.get('Authorization') != 'Bearer synthetic-task-identity':
            raise PermissionError()

    def enqueue(self, owner, key, payload_hash):
        with self.lock:
            if (owner, key) in self.keys:
                return
            self.keys.add((owner, key))
            def execute():
                with self.app.test_client() as client:
                    client.post('/internal/operations/run', json={'owner': owner, 'operation_id': key,
                        'payload_hash': payload_hash}, headers={'Authorization': 'Bearer synthetic-task-identity'})
            thread = threading.Thread(target=execute)
            self.threads.append(thread)
            thread.start()

    def join(self):
        for thread in self.threads:
            thread.join(6)


class SectionWiringTests(unittest.TestCase):
    def setUp(self):
        google = types.ModuleType('google'); cloud = types.ModuleType('google.cloud')
        firestore = types.ModuleType('google.cloud.firestore'); firestore.transactional = transactional
        cloud.firestore = firestore; google.cloud = cloud
        self.modules = patch.dict(sys.modules, {'google': google, 'google.cloud': cloud, 'google.cloud.firestore': firestore})
        self.modules.start()
        self.database = Client(); self.questions = ScriptedQuestions()
        self.commit_entered = threading.Event(); self.release_commit = threading.Event()
        self.secret = 'synthetic-private-test-only-' + 'x' * 32; self.capability = issue(self.secret)
        self.factory = lambda owner: BlockingState(self.database, owner, self.commit_entered, self.release_commit)
        self.app = Flask(__name__)
        @self.app.before_request
        def private_fixture_identity():
            from flask import request
            request.environ['arm_a_owner'] = 'synthetic-platform-verified-owner'
        self.dispatcher = SyntheticTaskDispatcher(); self.dispatcher.app = self.app
        install(self.app, self.questions, self.factory, self.secret, dispatcher=self.dispatcher)
        self.client = self.app.test_client()
        self.headers = {'X-MotoMedic-Visitor': self.capability, 'Idempotency-Key': OP, 'Accept': 'text/event-stream'}
        self.body = {'query': 'Where is the charger port?', 'bike_variant': 'Himalayan BS6',
            'confirmed_himalayan_bs6': True, 'manual_checksum': MANUAL_SHA, 'index_id': INDEX_ID, 'cache_mode': 'enabled'}

    def tearDown(self):
        self.questions.release(); self.release_commit.set(); self.dispatcher.join(); self.modules.stop()

    def post(self):
        return self.client.post('/v1/sessions', json=self.body, headers=self.headers, buffered=False)

    def recover(self):
        return self.client.get('/v1/operations/' + OP, headers={**self.headers, 'Accept': 'application/json'})

    def event(self, raw):
        text = raw.decode(); kind = text.split('event: ')[1].split('\n')[0]
        body = json.loads(text.split('data: ')[1]); body.pop('sequence', None)
        return kind, body

    def test_progress_private_stages_and_commit_barrier_then_exact_recovery(self):
        response = self.post(); self.assertEqual(response.status_code, 200)
        iterator = iter(response.response); frames = [next(iterator)]
        self.assertEqual(self.event(frames[-1]), ('progress', {'operation_id': OP, 'stage': 'retrieving'}))
        self.assertEqual(self.recover().status_code, 202)
        self.questions.proceed['retrieving'].set(); frames.append(next(iterator))
        self.assertEqual(self.event(frames[-1])[1]['stage'], 'drafting')
        self.questions.proceed['drafting'].set(); frames.append(next(iterator))
        self.assertEqual(self.event(frames[-1])[1]['stage'], 'checking')
        self.assertFalse(self.commit_entered.is_set())
        remaining = []; finished = threading.Event()
        def collect():
            remaining.extend(iterator); finished.set()
        worker = threading.Thread(target=collect); worker.start()
        self.assertFalse(finished.wait(0.05)); self.assertEqual(remaining, [])
        self.questions.proceed['checking'].set(); self.assertTrue(self.commit_entered.wait(2))
        self.assertEqual(self.recover().status_code, 202)
        self.assertFalse(finished.wait(0.05)); self.assertEqual(remaining, [])
        self.assertFalse(any(p.startswith('arm_a_sessions/') for p in self.database.data))
        self.release_commit.set(); worker.join(3); self.assertTrue(finished.is_set())
        frames += remaining; published = []; parts = []; stages = []
        accepted = read_verified_stream(frames, published.append, operation_id=OP, on_progress=stages.append,
                                        on_chunk=parts.append)
        recovered = validate_view(self.recover().get_json())
        self.assertEqual(accepted, recovered); self.assertEqual(published, [recovered])
        self.assertEqual(''.join(parts), 'The charger port is on the centre of the handlebar.')
        self.assertEqual(response_hash(accepted), recovered['delivery']['response_sha256'])
        self.assertEqual(stages, ['retrieving', 'drafting', 'checking', 'displaying'])
        self.assertEqual(recovered['response']['cited_pages'][0]['pdf_page'], 64)
        self.assertEqual(self.questions.calls, 1)
        replay = self.client.post('/v1/sessions', json=self.body, headers=self.headers)
        self.assertEqual(read_verified_stream([replay.data], operation_id=OP), recovered)
        self.assertEqual(self.questions.calls, 1)
        self.assertEqual(replay.headers.get('X-Operation-Replay'), 'true')
        catalogue = self.client.get('/v1/catalogue', headers=self.headers).get_json()
        self.assertEqual((catalogue['streaming'], catalogue['answer_provider'], catalogue['index_id']),
                         ('SAVED_RELEASE_STREAM', 'claude-haiku-5-5', INDEX_ID))

    def test_follow_up_question_runs_against_the_saved_conversation(self):
        self.questions.release(); self.release_commit.set()
        list(self.post().response)
        first = validate_view(self.recover().get_json())
        follow = dict(self.body, query='Can I use it in rain?', expected_version=first['version'])
        headers = dict(self.headers, **{'Idempotency-Key': 'd' * 32})
        frames = list(self.client.post('/v1/sessions/' + first['session_id'] + '/questions', json=follow,
                                       headers=headers, buffered=False).response)
        second = read_verified_stream(frames, operation_id='d' * 32)
        self.assertEqual(second['version'], first['version'] + 1)
        sent = self.questions.real.generate.calls[-1][1]
        self.assertIn('Rider: Where is the charger port?', sent)
        self.assertIn('MotoMedic: The charger port is on the centre of the handlebar.', sent)

    def test_disconnected_progress_worker_saves_for_idempotent_recovery(self):
        response = self.post(); iterator = iter(response.response); first = next(iterator)
        self.assertEqual(self.event(first)[0], 'progress')
        response.close(); self.questions.release(); self.release_commit.set()
        self.assertTrue(self.commit_entered.wait(2))
        finished = threading.Event()
        def read_saved():
            for _ in range(1000):
                if any(v.get('state') == 'COMPLETE' for k, v in self.database.data.items() if k.startswith('arm_a_operations/')):
                    finished.set(); return
                threading.Event().wait(0.001)
        waiter = threading.Thread(target=read_saved); waiter.start(); waiter.join(2)
        self.assertTrue(finished.is_set()); self.assertEqual(self.recover().status_code, 200)
        self.assertEqual(self.questions.calls, 1)

    def test_nothing_retrieved_stays_neutral_with_no_call_or_answer_events(self):
        self.questions.fallback(); self.questions.release(); self.release_commit.set()
        frames = list(self.post().response)
        self.assertEqual([self.event(f)[0] for f in frames], ['progress', 'complete'])
        labels = []; published = []; parts = []
        result = read_verified_stream(frames, published.append, operation_id=OP, on_progress=labels.append, on_chunk=parts.append)
        self.assertEqual((result['response']['type'], result['response']['natural_language']), ('UNSUPPORTED', FALLBACK))
        self.assertEqual((result['response']['technical_content'], result['escalation_uri']),
                         (False, 'mailto:support@royalenfield.com'))
        self.assertEqual((labels, published, parts), (['retrieving'], [], []))
        self.assertEqual(self.questions.real.generate.calls, [])
        self.assertEqual(self.recover().get_json(), result)

    def test_generation_failure_is_neutral_complete_with_no_answer_chunks(self):
        self.questions.fail_generation(); self.questions.release(); self.release_commit.set()
        frames = list(self.post().response)
        self.assertEqual([self.event(f)[0] for f in frames], ['progress', 'progress', 'complete'])
        result = read_verified_stream(frames, operation_id=OP)
        self.assertEqual((result['response']['type'], result['response']['natural_language']), ('SYSTEM_ERROR', CHECK_ERROR))
        self.assertEqual(result['response']['technical_content'], False)
        self.assertEqual(self.recover().get_json(), result)

    def test_forged_or_retired_saved_answer_cannot_recover_or_replay(self):
        self.questions.release(); self.release_commit.set()
        list(self.post().response)
        records = [(key, deepcopy(record)) for key, record in self.database.data.items()
                   if key.startswith(('arm_a_operations/', 'arm_a_sessions/')) and 'view' in record]
        self.assertTrue(records)
        mutations = (lambda v: v.update(runtime_policy='open-manual-haiku-draft-verify-v10_13'),
                     lambda v: v['delivery'].update(runtime_lock='f' * 64),
                     lambda v: v['release_delivery'].update(operation_id='d' * 32),
                     lambda v: v['release_delivery'].update(release_sha256='4' * 64),
                     lambda v: v['response'].update(natural_language='Forged advice.'))
        for mutate in mutations:
            for key, original in records:
                forged = deepcopy(original); mutate(forged['view']); self.database.data[key] = forged
            self.assertEqual(self.recover().status_code, 503)
            saved = self.client.get('/v1/sessions/' + records[0][1]['view']['session_id'], headers=self.headers)
            self.assertEqual(saved.status_code, 503)
            replay = self.client.post('/v1/sessions', json=self.body, headers=self.headers)
            self.assertEqual(replay.status_code, 409)
            self.assertEqual(self.questions.calls, 1)
            for key, original in records:
                self.database.data[key] = deepcopy(original)
        self.assertEqual(self.recover().status_code, 200)

    def test_changed_index_or_runtime_blocks_saved_technical_response(self):
        self.questions.release(); self.release_commit.set()
        list(self.post().response)
        self.assertEqual(self.recover().status_code, 200)
        self.questions.real.source.index_id = 'changed-index'
        self.assertEqual(self.recover().status_code, 503)
        self.questions.real.source.index_id = INDEX_ID
        self.questions.real.runtime_lock = '0' * 64
        self.assertEqual(self.recover().status_code, 503)
        self.assertEqual(self.questions.calls, 1)

    def test_wrong_source_or_variant_is_rejected_before_any_work(self):
        for change in ({'index_id': 'index_a3282c4d98cf54595e4ba168'}, {'bike_variant': 'Classic 350'},
                       {'manual_checksum': '0' * 64}):
            response = self.client.post('/v1/sessions', json=dict(self.body, **change), headers=self.headers)
            self.assertEqual((response.status_code, response.get_json()['error']), (400, 'SOURCE_OR_VARIANT_MISMATCH'))
        response = self.client.post('/v1/sessions/' + 'a' * 32 + '/feedback', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.questions.calls, 0)


if __name__ == '__main__':
    unittest.main()
