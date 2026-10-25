"""Owned durable operations, bounded leases and immutable session transactions."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from cloud.common import content_hash
from cloud.common.session import decode, SessionConflict


class Limited(Exception):
    pass


class OperationConflict(Exception):
    pass


OPERATION_SECONDS = 1200
LEASE_SECONDS = 1200
PRIVATE_STAGES = {'retrieving', 'drafting', 'checking'}


class FirestoreState:
    def __init__(self, client, owner, now=None, network_owner=None):
        self.client, self.owner = client, owner
        self.network_owner = network_owner
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _operation(self, key):
        return self.client.collection('arm_a_operations').document(
            hashlib.sha256((self.owner+':'+key).encode()).hexdigest())

    def _session_operation(self, session_id):
        return self.client.collection('arm_a_session_operations').document(session_id)

    def _reconcile(self, tx, ref, body, now):
        """An expired worker never resumes inference, even before paid-call proof.

        We cannot distinguish a crash before transmission from a crash after
        transmission. Releasing a lease therefore cannot authorize paid replay.
        Reservations remain the provider ledger's reconciliation responsibility.
        """
        if body['state'] not in ('QUEUED', 'RUNNING'):
            return body
        deadline = body.get('deadline_at')
        lease = body.get('lease_expires_at')
        code = None
        if deadline and deadline <= now:
            code = 'OPERATION_DEADLINE_EXCEEDED'
        elif body['state'] == 'RUNNING' and lease and lease <= now:
            code = ('PROVIDER_RESULT_UNCERTAIN' if body.get('provider_may_have_run')
                    else 'WORKER_LEASE_EXPIRED')
        if code:
            update = {'state': 'FAILED', 'error': code, 'http_status': 503,
                      'completed_at': now, 'work': None, 'operation_terminal': True}
            tx.update(ref, update)
            self._release_session(tx, body)
            body = {**body, **update}
        return body

    def _release_session(self, tx, body):
        if body.get('session_id'):
            tx.set(self._session_operation(body['session_id']), {
                'owner': self.owner, 'operation_key': body.get('operation_key'),
                'active': False, 'expires_at': body['expires_at']})

    def begin(self, key, payload_hash, work=None):
        from google.cloud import firestore
        op = self._operation(key)
        usage = self.client.collection('arm_a_usage').document(self.owner)
        shared = self.client.collection('arm_a_usage').document('global')
        @firestore.transactional
        def reserve(tx):
            now = self.now()
            old = op.get(transaction=tx)
            if old.exists:
                body = old.to_dict()
                if body['payload_hash'] != payload_hash or body['owner'] != self.owner:
                    raise OperationConflict()
                if body['expires_at'] <= now:
                    raise OperationConflict()
                return self._reconcile(tx, op, body, now)
            session_lock = None
            abandoned = None
            if work is not None:
                session_id = work['session_id']
                session_lock = self._session_operation(session_id)
                active = session_lock.get(transaction=tx)
                current = self.client.collection('arm_a_sessions').document(session_id).get(transaction=tx)
                if active.exists and active.to_dict().get('active') and active.to_dict()['deadline_at'] > now:
                    raise SessionConflict('A session turn is already processing')
                if active.exists and active.to_dict().get('active'):
                    abandoned_ref = self._operation(active.to_dict()['operation_key'])
                    abandoned_snap = abandoned_ref.get(transaction=tx)
                    if abandoned_snap.exists:
                        abandoned = (abandoned_ref, abandoned_snap.to_dict())
                saved = current.to_dict() if current.exists else None
                if (saved['version'] if saved else None) != work['expected_version']:
                    raise SessionConflict('Concurrent or stale session update')
                if saved and (saved['owner'] != self.owner or saved['expires_at'] <= now or saved['idle_expires_at'] <= now):
                    raise SessionConflict('Session ownership or expiry')
            own = usage.get(transaction=tx)
            global_usage = shared.get(transaction=tx)
            buckets = [(usage, own, 6, 30), (shared, global_usage, 60, 250)]
            if self.network_owner:
                network = self.client.collection('arm_a_usage').document('network-'+self.network_owner)
                buckets.append((network, network.get(transaction=tx), 6, 30))
            pending = []
            for ref, snap, minute_cap, day_cap in buckets:
                times = [t for t in (snap.to_dict().get('turns', []) if snap.exists else [])
                         if t > now-timedelta(hours=24)]
                if len(times) >= day_cap or sum(t > now-timedelta(minutes=1) for t in times) >= minute_cap:
                    raise Limited()
                pending.append((ref, times+[now]))
            body = {'owner':self.owner, 'payload_hash':payload_hash, 'state':'RUNNING',
                    'created_at':now, 'expires_at':now+timedelta(hours=24)}
            if work is not None:
                body.update(state='QUEUED', operation_key=key, work=work,
                    session_id=work['session_id'], dispatch_state='PENDING',
                    work_sha256=hashlib.sha256(json.dumps(work, sort_keys=True,
                        separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest(),
                    deadline_at=now+timedelta(seconds=OPERATION_SECONDS),
                    provider_may_have_run=False, progress=[])
            if abandoned:
                self._reconcile(tx, abandoned[0], abandoned[1], now)
            tx.create(op, body)
            if session_lock:
                tx.set(session_lock, {'owner': self.owner, 'operation_key': key,
                    'active': True, 'deadline_at': body['deadline_at'], 'expires_at': body['expires_at']})
            for ref, times in pending:
                tx.set(ref, {'turns':times, 'expires_at':now+timedelta(hours=24)})
            return None
        return reserve(self.client.transaction())

    def mark_dispatched(self, key):
        from google.cloud import firestore
        ref = self._operation(key)
        @firestore.transactional
        def mark(tx):
            snap = ref.get(transaction=tx)
            if not snap.exists or snap.to_dict()['owner'] != self.owner:
                raise OperationConflict()
            if snap.to_dict()['state'] == 'QUEUED':
                tx.update(ref, {'dispatch_state': 'DISPATCHED'})
        return mark(self.client.transaction())

    def claim_operation(self, key, payload_hash, lease_token):
        """At most one worker may execute a durable operation."""
        from google.cloud import firestore
        ref = self._operation(key)
        @firestore.transactional
        def claim(tx):
            now = self.now()
            snap = ref.get(transaction=tx)
            if not snap.exists:
                raise KeyError(key)
            body = snap.to_dict()
            if body['owner'] != self.owner or body['payload_hash'] != payload_hash or body['expires_at'] <= now:
                raise OperationConflict()
            # Read all records before reconciliation/lease writes (Firestore).
            lock = self._session_operation(body['session_id']).get(transaction=tx)
            saved = self.client.collection('arm_a_sessions').document(body['session_id']).get(transaction=tx)
            body = self._reconcile(tx, ref, body, now)
            if body['state'] != 'QUEUED':
                return None
            work = body['work']
            digest = hashlib.sha256(json.dumps(work, sort_keys=True, separators=(',', ':'),
                ensure_ascii=False, allow_nan=False).encode()).hexdigest()
            head = saved.to_dict() if saved.exists else None
            if (digest != body['work_sha256'] or not lock.exists or
                    lock.to_dict().get('operation_key') != key or
                    lock.to_dict().get('owner') != self.owner or not lock.to_dict().get('active') or
                    (head['version'] if head else None) != work['expected_version'] or
                    (head and (head['owner'] != self.owner or head['expires_at'] <= now or head['idle_expires_at'] <= now))):
                raise OperationConflict()
            tx.update(ref, {'state': 'RUNNING', 'started_at': now,
                'lease_token': lease_token, 'lease_expires_at': min(body['deadline_at'], now+timedelta(seconds=LEASE_SECONDS))})
            return work
        return claim(self.client.transaction())

    def progress_operation(self, key, lease_token, stage):
        if stage not in PRIVATE_STAGES:
            raise ValueError('INVALID_PRIVATE_PROGRESS_STAGE')
        from google.cloud import firestore
        ref = self._operation(key)
        @firestore.transactional
        def progress(tx):
            now = self.now()
            snap = ref.get(transaction=tx)
            body = snap.to_dict() if snap.exists else {}
            self._require_lease(body, lease_token, now)
            events = body.get('progress', [])
            if len(events) >= 8:
                raise OperationConflict()
            # The pre-provider drafting receipt is durable before transport.
            tx.update(ref, {'progress': events+[{'stage': stage, 'sequence': len(events)+1}],
                'provider_may_have_run': body.get('provider_may_have_run', False) or stage in ('drafting','verifying'),
                'lease_expires_at': min(body['deadline_at'], now+timedelta(seconds=LEASE_SECONDS))})
        return progress(self.client.transaction())

    def _require_lease(self, body, lease_token, now):
        if (body.get('owner') != self.owner or body.get('state') != 'RUNNING' or
                body.get('expires_at', now) <= now):
            raise OperationConflict()
        if body.get('work_sha256') and (lease_token != body.get('lease_token') or
                body.get('lease_expires_at', now) <= now or body['deadline_at'] <= now):
            raise OperationConflict()

    def finish(self, key, view):
        from google.cloud import firestore
        ref = self._operation(key)
        @firestore.transactional
        def commit(tx):
            snap = ref.get(transaction=tx)
            if not snap.exists or snap.to_dict()['owner'] != self.owner:
                raise OperationConflict()
            if snap.to_dict()['state'] == 'COMPLETE':
                return snap.to_dict()['view']
            self._require_lease(snap.to_dict(), None, self.now())
            tx.update(ref, {'state':'COMPLETE', 'view':view})
            return view
        return commit(self.client.transaction())

    def operation(self, key):
        from google.cloud import firestore
        ref = self._operation(key)
        @firestore.transactional
        def read(tx):
            snap = ref.get(transaction=tx)
            now = self.now()
            if not snap.exists or snap.to_dict()['expires_at'] <= now or snap.to_dict()['owner'] != self.owner:
                raise KeyError(key)
            return self._reconcile(tx, ref, snap.to_dict(), now)
        return read(self.client.transaction())

    def fail_operation(self, key, code, status, lease_token=None):
        from google.cloud import firestore
        ref=self._operation(key)
        @firestore.transactional
        def fail(tx):
            snap=ref.get(transaction=tx)
            if not snap.exists or snap.to_dict()['owner']!=self.owner or snap.to_dict()['expires_at']<=self.now():
                raise OperationConflict()
            if snap.to_dict()['state']=='COMPLETE':
                return False
            body = snap.to_dict()
            if body['state'] == 'FAILED':
                return False
            if body.get('work_sha256') and body['state'] == 'RUNNING' and body.get('lease_token') != lease_token:
                raise OperationConflict()
            tx.update(ref,{'state':'FAILED','error':code,'http_status':status,
                'completed_at':self.now(),'work':None,'operation_terminal':True})
            self._release_session(tx, body)
            return True
        return fail(self.client.transaction())

    def load(self, session_id):
        head = self.client.collection('arm_a_sessions').document(session_id).get()
        if not head.exists:
            raise KeyError(session_id)
        body = head.to_dict()
        if body['owner'] != self.owner or body['idle_expires_at'] <= self.now() or body['expires_at'] <= self.now():
            raise KeyError(session_id)
        return decode(body['snapshot'])

    def saved(self, session_id):
        """Latest owner-bound presentation; never an authoritative local cache."""
        self.load(session_id)  # Same ownership, idle and fixed lifetime checks.
        body = self.client.collection('arm_a_sessions').document(session_id).get().to_dict()
        if body['owner'] != self.owner or body['expires_at'] <= self.now() or body['idle_expires_at'] <= self.now():
            raise KeyError(session_id)
        return body

    def commit_answer(self, key, session, view, choices, expected_version=None, query=None, lease_token=None):
        """Atomically commit session, immutable snapshot and completed operation.

        No technical stream is constructed before this transaction succeeds.
        """
        from google.cloud import firestore
        operation = self._operation(key)
        head = self.client.collection('arm_a_sessions').document(session.session_id)
        @firestore.transactional
        def commit(tx):
            now = self.now()
            op = operation.get(transaction=tx)
            old_head = head.get(transaction=tx)
            if not op.exists or op.to_dict()['owner'] != self.owner or op.to_dict()['expires_at'] <= now:
                raise OperationConflict()
            if op.to_dict()['state'] == 'COMPLETE':
                return op.to_dict()['view']
            self._require_lease(op.to_dict(), lease_token, now)
            operation_body = op.to_dict()
            if operation_body.get('work_sha256'):
                from cloud.grounded_generation.delivery import response_hash
                work = operation_body['work']
                if (content_hash(work) != operation_body['work_sha256'] or query != work['query'] or
                        session.session_id != operation_body['session_id'] or
                        expected_version != operation_body['work']['expected_version'] or
                        view.get('session_id') != session.session_id or view.get('version') != session.version or
                        view.get('delivery', {}).get('operation_id') != key or
                        view['delivery'].get('runtime_lock') != session.generation_lock or
                        view['delivery'].get('response_sha256') != response_hash(view)):
                    raise OperationConflict()
            old = old_head.to_dict() if old_head.exists else None
            if (old['version'] if old else None) != expected_version:
                raise SessionConflict('Concurrent or stale session update')
            count = old.get('accepted_turns', 0) if old else 0
            if count >= 20:
                raise Limited()
            if old:
                if old['owner'] != self.owner or old['expires_at'] <= now or old['idle_expires_at'] <= now:
                    raise SessionConflict('Session ownership or expiry')
                prior = decode(old['snapshot'])
                if session.version <= prior.version or session.attempted_steps[:len(prior.attempted_steps)] != prior.attempted_steps:
                    raise SessionConflict('Immutable state changed')
                fields = ('manual_id','manual_checksum','bike_variant','edition','version_lock','generation_lock')
                if any(getattr(session,k) != getattr(prior,k) for k in fields):
                    raise SessionConflict('Scope/version changed')
            expiry = old['expires_at'] if old else now+timedelta(hours=24)
            snapshot = json.dumps(asdict(session), allow_nan=False)
            body = {'owner':self.owner, 'version':session.version, 'snapshot':snapshot,
                    'view':view, 'choices':choices, 'accepted_turns':count+1,
                    'query':query if query is not None else (old or {}).get('query'),
                    'conversation': ((old or {}).get('conversation', []) +
                        ([{'question':query, 'response':view['response']['natural_language'],
                           'route':view['response']['type']}] if query is not None else [])),
                    'expires_at':expiry, 'idle_expires_at':min(expiry, now+timedelta(minutes=30))}
            tx.set(head, body)
            tx.create(head.collection('arm_a_session_versions').document(str(session.version)),
                      {'snapshot':snapshot, 'view':view, 'expires_at':expiry})
            tx.update(operation, {'state':'COMPLETE', 'view':view, 'completed_at':now, 'work':None})
            self._release_session(tx, op.to_dict())
            return view
        return commit(self.client.transaction())

    def save(self, session, expected_version=None):
        from google.cloud import firestore
        ref = self.client.collection('arm_a_sessions').document(session.session_id)
        @firestore.transactional
        def commit(tx):
            now = self.now()
            snap = ref.get(transaction=tx)
            old = snap.to_dict() if snap.exists else None
            current = old['version'] if old else None
            if current != expected_version or (current is not None and session.version <= current):
                raise SessionConflict('Concurrent or stale session update')
            if old:
                if old['owner'] != self.owner or old['expires_at'] <= now or old['idle_expires_at'] <= now:
                    raise SessionConflict('Session ownership or expiry')
                prior = decode(old['snapshot'])
                if session.attempted_steps[:len(prior.attempted_steps)] != prior.attempted_steps:
                    raise SessionConflict('Immutable attempts changed')
                fields = ('manual_id','manual_checksum','bike_variant','edition','version_lock','generation_lock')
                if any(getattr(session,k) != getattr(prior,k) for k in fields):
                    raise SessionConflict('Scope/version changed')
            snapshot = json.dumps(asdict(session), allow_nan=False)
            expiry = old['expires_at'] if old else now+timedelta(hours=24)
            body = {'owner':self.owner, 'version':session.version, 'snapshot':snapshot,
                    'expires_at':expiry, 'idle_expires_at':min(expiry, now+timedelta(minutes=30))}
            tx.set(ref, body)
            tx.create(ref.collection('arm_a_session_versions').document(str(session.version)),
                      {'snapshot':snapshot, 'expires_at':expiry})
        return commit(self.client.transaction())
