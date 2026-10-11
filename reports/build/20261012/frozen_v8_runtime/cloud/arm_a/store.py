"""Managed transactional sessions and idempotent initial-answer operations."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from session_store import decode, SessionConflict


class Limited(Exception):
    pass


class OperationConflict(Exception):
    pass


class FirestoreState:
    def __init__(self, client, owner, now=None, network_owner=None):
        self.client, self.owner = client, owner
        self.network_owner = network_owner
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _operation(self, key):
        return self.client.collection('arm_a_operations').document(
            hashlib.sha256((self.owner+':'+key).encode()).hexdigest())

    def begin(self, key, payload_hash):
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
                return body
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
            tx.create(op, body)
            for ref, times in pending:
                tx.set(ref, {'turns':times, 'expires_at':now+timedelta(hours=24)})
            return None
        return reserve(self.client.transaction())

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
            tx.update(ref, {'state':'COMPLETE', 'view':view})
            return view
        return commit(self.client.transaction())

    def operation(self, key):
        snap = self._operation(key).get()
        if not snap.exists or snap.to_dict()['expires_at'] <= self.now():
            raise KeyError(key)
        return snap.to_dict()

    def fail_operation(self, key, code, status):
        from google.cloud import firestore
        ref=self._operation(key)
        @firestore.transactional
        def fail(tx):
            snap=ref.get(transaction=tx)
            if not snap.exists or snap.to_dict()['owner']!=self.owner or snap.to_dict()['expires_at']<=self.now():
                raise OperationConflict()
            if snap.to_dict()['state']=='COMPLETE':
                return False
            tx.update(ref,{'state':'FAILED','error':code,'http_status':status})
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

    def commit_answer(self, key, session, view, choices, expected_version=None, query=None):
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
            tx.update(operation, {'state':'COMPLETE', 'view':view})
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
