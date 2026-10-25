"""Cloud Tasks dispatch and authenticated, fenced durable answer execution.

No provider work runs on a browser request or a background daemon. Creating a
queue, granting IAM, deploying this endpoint and activating hosting are separate
operational actions. The default is disabled without complete dispatch settings.
"""
from dataclasses import asdict
import base64
import hashlib
import json
import os
import re
from urllib.parse import urlsplit
import uuid

from cloud.arm_a.store import OperationConflict, OPERATION_SECONDS
from cloud.common.session import decode, SessionConflict

VERSION = 'durable-cloud-tasks-operations-v2'
WORKER_PATH = '/internal/operations/run'


class DispatchError(RuntimeError):
    pass


def make_work(session, query, history, expected_version, questions):
    """An immutable owner-private work snapshot, never placed in a task body."""
    return {'version': VERSION, 'session_id': session.session_id,
        'session_snapshot': json.dumps(asdict(session), allow_nan=False),
        'query': query, 'history': list(history), 'expected_version': expected_version,
        'runtime_lock': session.generation_lock,
        'manual_checksum': questions.source.checksum,
        'index_id': questions.source.index_id,
        'index_lock': questions.index_lock}


class CloudTasksDispatcher:
    def __init__(self, queue, worker_url, service_account, *, audience=None,
                 transport=None, verifier=None):
        if not re.fullmatch(r'projects/[A-Za-z0-9_.:-]+/locations/[a-z0-9-]+/queues/[A-Za-z0-9-]{1,100}', queue):
            raise ValueError('INVALID_TASK_QUEUE')
        parsed = urlsplit(worker_url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or
                parsed.query or parsed.fragment or parsed.path != WORKER_PATH):
            raise ValueError('INVALID_TASK_WORKER_URL')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+\.iam\.gserviceaccount\.com', service_account):
            raise ValueError('INVALID_TASK_WORKER_IDENTITY')
        self.queue, self.worker_url, self.service_account = queue, worker_url, service_account
        self.audience = audience or parsed.scheme+'://'+parsed.netloc
        if self.audience != parsed.scheme+'://'+parsed.netloc:
            raise ValueError('INVALID_TASK_AUDIENCE')
        self.transport, self.verifier = transport, verifier

    def enqueue(self, owner, key, payload_hash):
        payload = {'owner': owner, 'operation_id': key, 'payload_hash': payload_hash}
        task_id = hashlib.sha256((VERSION+':'+owner+':'+key+':'+payload_hash).encode()).hexdigest()
        body = {'task': {'name': self.queue+'/tasks/'+task_id,
            'dispatchDeadline': str(OPERATION_SECONDS)+'s',
            'httpRequest': {'httpMethod': 'POST', 'url': self.worker_url,
                'headers': {'Content-Type': 'application/json'},
                'body': base64.b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode(),
                'oidcToken': {'serviceAccountEmail': self.service_account, 'audience': self.audience}}}}
        try:
            if self.transport:
                status = self.transport('https://cloudtasks.googleapis.com/v2/'+self.queue+'/tasks', body)
            else:
                import google.auth
                from google.auth.transport.requests import AuthorizedSession
                credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
                with AuthorizedSession(credentials) as session:
                    response = session.post('https://cloudtasks.googleapis.com/v2/'+self.queue+'/tasks',
                        json=body, timeout=15)
                    status = response.status_code
                    response.close()
            # Named task deduplication resolves uncertain create responses.
            if status not in (200, 201, 409):
                raise DispatchError('TASK_DISPATCH_UNAVAILABLE')
        except Exception:
            raise DispatchError('TASK_DISPATCH_UNAVAILABLE') from None

    def authenticate(self, headers):
        # Never trust a Cloud Tasks header or a rider-supplied owner by itself.
        value = headers.get('Authorization', '')
        scheme, separator, token = value.partition(' ')
        if not separator or scheme.casefold() != 'bearer' or not token or len(value) > 16000:
            raise PermissionError()
        try:
            if self.verifier:
                claims = self.verifier(token, self.audience)
            else:
                from google.oauth2.id_token import verify_oauth2_token
                from google.auth.transport.requests import Request
                claims = verify_oauth2_token(token, Request(), audience=self.audience)
            if (claims.get('email') != self.service_account or claims.get('email_verified') is not True or
                    claims.get('aud') != self.audience or
                    claims.get('iss') not in ('https://accounts.google.com', 'accounts.google.com')):
                raise PermissionError()
        except Exception:
            raise PermissionError() from None


def configured_dispatcher():
    names = ('MOTOMEDIC_TASK_QUEUE', 'MOTOMEDIC_TASK_WORKER_URL', 'MOTOMEDIC_TASK_SERVICE_ACCOUNT')
    values = [os.environ.get(name) for name in names]
    if not any(values):
        return None
    if not all(values):
        raise RuntimeError('INCOMPLETE_DURABLE_DISPATCH_CONFIGURATION')
    return CloudTasksDispatcher(*values)


class DurableWorker:
    def __init__(self, questions, state_factory, validate_saved):
        self.questions, self.state_factory, self.validate_saved = questions, state_factory, validate_saved

    def run(self, owner, key, payload_hash):
        """Task retries observe terminal results or a lease; they never redo work."""
        store = self.state_factory(owner)
        token = uuid.uuid4().hex
        claimed = False
        try:
            work = store.claim_operation(key, payload_hash, token)
            if work is None:
                operation = store.operation(key)
                return 204 if operation['state'] in ('COMPLETE', 'FAILED') else 503
            claimed = True
            q = self.questions
            if (work['version'] != VERSION or work['manual_checksum'] != q.source.checksum or
                    work['index_id'] != q.source.index_id or work['index_lock'] != q.index_lock or
                    work['runtime_lock'] != q.runtime_lock):
                raise OperationConflict()
            session = decode(work['session_snapshot'])
            if session.session_id != work['session_id'] or session.generation_lock != work['runtime_lock']:
                raise OperationConflict()
            operation = store.operation(key)
            if (operation['state'] != 'RUNNING' or operation.get('lease_token') != token or
                    operation['payload_hash'] != payload_hash or operation['session_id'] != session.session_id):
                raise OperationConflict()
            from cloud.grounded_generation.whole_turn_admission import operation_deadline
            with operation_deadline(operation['deadline_at']):
                updated, view, choices = q.answer(session, work['query'], history=work['history'],
                    progress=lambda stage: store.progress_operation(key, token, stage), operation_id=key)
            from cloud.grounded_generation.delivery import bind_view
            view = bind_view(view, key, updated.generation_lock)
            self.validate_saved(view)
            store.commit_answer(key, updated, view, choices,
                expected_version=work['expected_version'], query=work['query'], lease_token=token)
            return 204
        except (OperationConflict, SessionConflict):
            code = 'OPERATION_OR_SESSION_CONFLICT'
        except Exception:
            code = 'OPERATION_NOT_COMMITTED'
        # A possibly successful commit remains successful. Never save a private
        # answer on an uncertain transaction, and never retry generation.
        try:
            if not claimed:
                current = store.operation(key)
                if current['payload_hash'] != payload_hash or current['state'] in ('COMPLETE', 'FAILED'):
                    return 204
                if current['state'] == 'RUNNING':
                    return 503
            store.fail_operation(key, code, 503, lease_token=token)
            return 204
        except Exception:
            # Store outage: redelivery only reconciles/observes the same lease.
            return 503
