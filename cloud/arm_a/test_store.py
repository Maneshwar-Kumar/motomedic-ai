"""Managed-store contracts using an atomic Firestore software double."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sys
import threading
import types
import unittest
from unittest.mock import patch

from cloud.arm_a.store import FirestoreState, Limited, OperationConflict
from controller_contracts import DiagnosticSession, StepAttempt, Outcome
from session_store import SessionConflict

class Snapshot:
    def __init__(self, body): self.body=deepcopy(body); self.exists=body is not None
    def to_dict(self): return deepcopy(self.body)

class Ref:
    def __init__(self,client,path): self.client,self.path=client,path
    def document(self,name): return Ref(self.client,self.path+'/'+name)
    def collection(self,name): return Ref(self.client,self.path+'/'+name)
    def get(self,transaction=None):
        return Snapshot((transaction.data if transaction else self.client.data).get(self.path))

class Transaction:
    def __init__(self,client): self.client=client
    def set(self,ref,body): self.data[ref.path]=deepcopy(body)
    def create(self,ref,body):
        if ref.path in self.data: raise SessionConflict('Duplicate immutable snapshot')
        self.set(ref,body)
    def update(self,ref,body): self.data[ref.path].update(deepcopy(body))

class Client:
    def __init__(self): self.data={}; self.lock=threading.Lock()
    def collection(self,name): return Ref(self,name)
    def transaction(self): return Transaction(self)

def transactional(fn):
    def run(tx):
        with tx.client.lock:
            tx.data=deepcopy(tx.client.data)
            result=fn(tx)
            tx.client.data=tx.data
            return result
    return run

class StoreTests(unittest.TestCase):
    def setUp(self):
        google=types.ModuleType('google'); cloud=types.ModuleType('google.cloud')
        firestore=types.ModuleType('google.cloud.firestore'); firestore.transactional=transactional
        cloud.firestore=firestore; google.cloud=cloud
        self.modules=patch.dict(sys.modules,{'google':google,'google.cloud':cloud,'google.cloud.firestore':firestore})
        self.modules.start()
        self.client=Client(); self.now=datetime(2026,10,11,tzinfo=timezone.utc)
        self.state=FirestoreState(self.client,'owner',lambda:self.now)
        self.session=DiagnosticSession('session','manual','checksum','variant','edition',('GEN007',),'lock')

    def tearDown(self): self.modules.stop()

    def test_operation_replay_conflict_and_expiry(self):
        self.assertIsNone(self.state.begin('key','hash'))
        self.assertEqual(self.state.begin('key','hash')['state'],'RUNNING')
        with self.assertRaises(OperationConflict): self.state.begin('key','other')
        view={'answer':'verified'}
        self.assertEqual(self.state.finish('key',view),view)
        self.assertEqual(self.state.finish('key',{'answer':'changed'}),view)
        other=FirestoreState(self.client,'other',lambda:self.now)
        with self.assertRaises(KeyError): other.operation('key')
        self.now+=timedelta(hours=24)
        with self.assertRaises(KeyError): self.state.operation('key')
        with self.assertRaises(OperationConflict): self.state.begin('key','hash')

    def test_admission_is_atomic_and_limits_without_waiting(self):
        for i in range(6): self.state.begin(str(i),'hash')
        before=deepcopy(self.client.data)
        with self.assertRaises(Limited): self.state.begin('excess','hash')
        self.assertEqual(before,self.client.data)
        self.now+=timedelta(minutes=1,seconds=1)
        self.assertIsNone(self.state.begin('next','hash'))

    def test_cas_owner_scope_expiry_and_immutable_attempts(self):
        self.state.save(self.session)
        self.assertEqual(self.state.load('session'),self.session)
        with self.assertRaises(SessionConflict): self.state.save(replace(self.session,version=1))
        other=FirestoreState(self.client,'other',lambda:self.now)
        with self.assertRaises(KeyError): other.load('session')
        with self.assertRaises(SessionConflict):
            other.save(replace(self.session,version=1),expected_version=0)
        with self.assertRaises(SessionConflict):
            self.state.save(replace(self.session,version=1,manual_checksum='other'),expected_version=0)
        attempt=StepAttempt('a','step',None,Outcome.ACTION_COMPLETED_UNRESOLVED,(),'turn','date')
        updated=replace(self.session,version=1,attempted_steps=(attempt,))
        self.state.save(updated,expected_version=0)
        with self.assertRaises(SessionConflict):
            self.state.save(replace(updated,version=2,attempted_steps=()),expected_version=1)
        self.now+=timedelta(minutes=31)
        with self.assertRaises(KeyError): self.state.load('session')
        with self.assertRaises(SessionConflict): self.state.save(replace(updated,version=2),expected_version=1)

    def test_concurrent_same_key_admits_once(self):
        results=[]
        def reserve(): results.append(self.state.begin('same','hash'))
        threads=[threading.Thread(target=reserve) for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sum(result is None for result in results),1)
        self.assertEqual(len(self.client.data['arm_a_usage/owner']['turns']),1)

    def test_snapshots_use_dedicated_group_and_fixed_24h_expiry(self):
        self.state.save(self.session)
        self.now += timedelta(minutes=10)
        self.state.save(replace(self.session,version=1), expected_version=0)
        snapshots = {k:v for k,v in self.client.data.items() if '/arm_a_session_versions/' in k}
        self.assertEqual(len(snapshots),2)
        self.assertFalse(any('/versions/' in k for k in self.client.data))
        expiry = self.client.data['arm_a_sessions/session']['expires_at']
        self.assertTrue(all(v['expires_at']==expiry for v in snapshots.values()))
        self.assertEqual(expiry, datetime(2026,10,12,tzinfo=timezone.utc))

if __name__=='__main__': unittest.main()
