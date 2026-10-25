"""Synthetic durable task/lease/stream failure checks; no providers or cloud."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import base64
import json
import sys
import threading
import types
import unittest
from unittest.mock import patch
from flask import Flask, request

from cloud.arm_a.durable_dispatch import (CloudTasksDispatcher, DispatchError,
    DurableWorker, configured_dispatcher, make_work)
from cloud.arm_a.store import FirestoreState, OperationConflict
from cloud.arm_a.test_store import Client, Ref, Transaction, transactional
from cloud.arm_a.visitor import issue
from cloud.grounded_generation.test_section_wiring import ScriptedQuestions, OP
from cloud.grounded_generation.delivery import bind_view, accepted_events, encode, stream_operation
from rider_ui.client import APIError
from rider_ui.verified_sse import read_verified_stream
from session_store import SessionConflict


class DurableOperationTests(unittest.TestCase):
    def setUp(self):
        google=types.ModuleType('google'); cloud=types.ModuleType('google.cloud')
        firestore=types.ModuleType('google.cloud.firestore'); firestore.transactional=transactional
        cloud.firestore=firestore; google.cloud=cloud
        self.modules=patch.dict(sys.modules,{'google':google,'google.cloud':cloud,'google.cloud.firestore':firestore})
        self.modules.start()
        self.database=Client();self.now=datetime(2026,10,12,tzinfo=timezone.utc)
        self.factory=lambda owner:FirestoreState(self.database,owner,lambda:self.now)
        self.store=self.factory('b'*64);self.questions=ScriptedQuestions();self.questions.release()
        self.session=self.questions.new_session()
        self.work=make_work(self.session,'Synthetic question',[],None,self.questions)
        self.worker=DurableWorker(self.questions,self.factory,lambda view:view)
    def tearDown(self):self.modules.stop()
    def queue(self,key=OP,work=None):self.store.begin(key,'d'*64,work=work or self.work)
    def raw_operation(self):return self.database.data[self.store._operation(OP).path]

    def test_task_claim_is_atomic_and_redelivery_never_calls_provider_twice(self):
        self.queue();claimed=[]
        def claim():claimed.append(self.store.claim_operation(OP,'d'*64,'lease'))
        threads=[threading.Thread(target=claim) for _ in range(6)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(sum(work is not None for work in claimed),1)
        self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),503)
        self.assertEqual(self.questions.calls,0)
        self.store.fail_operation(OP,'SYNTHETIC_CANCELED',503,lease_token='lease')
        self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)

    def test_worker_admission_uses_exact_stored_deadline_and_resets_scope(self):
        from cloud.grounded_generation.whole_turn_admission import _OPERATION_DEADLINE
        self.queue();expected=self.raw_operation()['deadline_at'];observed=[]
        answer=self.questions.answer
        def scoped_answer(*args,**kwargs):
            observed.append(_OPERATION_DEADLINE.get())
            return answer(*args,**kwargs)
        self.questions.answer=scoped_answer
        self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)
        self.assertEqual(observed,[expected])
        self.assertIsNone(_OPERATION_DEADLINE.get())

    def test_deadline_expiring_during_startup_stops_worker_before_generation(self):
        self.queue()
        import cloud.arm_a.durable_dispatch as dispatch
        real_decode=dispatch.decode
        def slow_decode(raw):
            self.now+=timedelta(seconds=1201)
            return real_decode(raw)
        with patch.object(dispatch,'decode',slow_decode):
            self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)
        self.assertEqual(self.questions.calls,0)
        self.assertEqual(self.store.operation(OP)['error'],'OPERATION_DEADLINE_EXCEEDED')

    def test_completed_worker_saved_streamed_and_recovered_hashes_are_equal(self):
        self.queue()
        self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)
        self.assertEqual(self.questions.calls,1)
        operation=self.store.operation(OP);saved=operation['view']
        stream=stream_operation(lambda:self.store.operation(OP),OP)
        frames=[frame.encode() if isinstance(frame,str) else frame for frame in stream.response]
        chunks=[]
        recovered=read_verified_stream(frames,operation_id=OP,on_chunk=chunks.append)
        self.assertEqual(recovered,saved)
        self.assertEqual(''.join(chunks),saved['response']['natural_language'])
        self.assertIsNone(operation['work'])
        self.assertFalse(self.database.data['arm_a_session_operations/'+self.session.session_id]['active'])
        self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)
        self.assertEqual(self.questions.calls,1)

    def test_concurrent_turn_and_conflicting_payload_do_not_cancel_owner_operation(self):
        self.queue();before=deepcopy(self.database.data)
        with self.assertRaises(SessionConflict):self.queue('f'*32)
        with self.assertRaises(OperationConflict):self.store.begin(OP,'e'*64,work=self.work)
        self.assertEqual(self.database.data,before)
        self.assertEqual(self.worker.run(self.store.owner,OP,'e'*64),204)
        self.assertEqual(self.store.operation(OP)['state'],'QUEUED')
        self.assertEqual(self.questions.calls,0)

    def test_uncertain_provider_lease_expires_terminal_without_replay(self):
        self.queue();self.store.claim_operation(OP,'d'*64,'lease')
        self.store.progress_operation(OP,'lease','drafting')
        self.raw_operation()['lease_expires_at']=self.now+timedelta(seconds=1)
        self.now+=timedelta(seconds=2)
        expired=self.store.operation(OP)
        self.assertEqual(expired['state'],'FAILED')
        self.assertEqual(expired['error'],'PROVIDER_RESULT_UNCERTAIN')
        self.assertTrue(expired['provider_may_have_run'])
        self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)
        self.assertEqual(self.questions.calls,0)

    def test_abandoned_queue_and_running_state_deadlines_are_terminal(self):
        for running in (False,True):
            with self.subTest(running=running):
                self.database.data.clear();self.queue()
                if running:self.store.claim_operation(OP,'d'*64,'lease')
                self.now+=timedelta(seconds=1201)
                expired=self.store.operation(OP)
                self.assertEqual(expired['state'],'FAILED')
                self.assertEqual(expired['error'],'OPERATION_DEADLINE_EXCEEDED')
                self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)
        self.assertEqual(self.questions.calls,0)

    def test_store_outage_retains_lease_and_redelivery_only_reconciles(self):
        self.queue()
        with patch.object(FirestoreState,'commit_answer',side_effect=OSError('private store details')), \
             patch.object(FirestoreState,'fail_operation',side_effect=OSError('private store details')):
            self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),503)
        self.assertEqual(self.store.operation(OP)['state'],'RUNNING')
        self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),503)
        self.assertEqual(self.questions.calls,1)
        self.now+=timedelta(seconds=1201)
        self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)
        self.assertEqual(self.store.operation(OP)['state'],'FAILED')
        self.assertEqual(self.questions.calls,1)

    def test_uncertain_successful_commit_is_preserved_and_never_regenerated(self):
        self.queue();original=FirestoreState.commit_answer
        def uncertain(state,*args,**kwargs):
            original(state,*args,**kwargs)
            raise OSError('lost commit acknowledgement')
        with patch.object(FirestoreState,'commit_answer',uncertain):
            self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)
        self.assertEqual(self.store.operation(OP)['state'],'COMPLETE')
        self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)
        self.assertEqual(self.questions.calls,1)

    def test_work_tamper_or_wrong_worker_runtime_fails_before_provider(self):
        self.queue();self.raw_operation()['work']['query']='Changed question'
        self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)
        self.assertEqual(self.store.operation(OP)['state'],'FAILED')
        self.assertEqual(self.questions.calls,0)

    def test_old_terminal_reconciliation_cannot_clear_a_new_session_turn(self):
        self.queue();self.now+=timedelta(seconds=1201)
        self.queue('f'*32)
        self.assertEqual(self.store.operation(OP)['state'],'FAILED')
        self.assertTrue(self.database.data['arm_a_session_operations/'+self.session.session_id]['active'])
        self.assertEqual(self.database.data['arm_a_session_operations/'+self.session.session_id]['operation_key'],'f'*32)

    def test_sse_is_observation_only_and_sequence_reordering_is_rejected(self):
        self.queue();self.worker.run(self.store.owner,OP,'d'*64)
        saved=self.store.operation(OP)['view']
        frames=[encode(kind,body).encode() for kind,body in accepted_events(saved,OP)]
        self.assertEqual(read_verified_stream(frames,operation_id=OP),saved)
        raw=json.loads(frames[1].decode().split('data: ')[1]);raw['sequence']=1
        seen=[]
        with self.assertRaises(APIError):read_verified_stream([frames[0],encode('verified_block',raw).encode()],seen.append,operation_id=OP)
        self.assertEqual(seen,[])

    def test_expired_lease_cannot_commit_an_answer(self):
        self.queue();self.store.claim_operation(OP,'d'*64,'lease')
        updated,view,choices=self.questions.answer(self.session,'query',progress=lambda stage:None,operation_id=OP)
        view=bind_view(view,OP,updated.generation_lock)
        with self.assertRaises(OperationConflict):
            self.store.commit_answer(OP,updated,view,choices,lease_token='other')
        self.now+=timedelta(seconds=1201)
        with self.assertRaises(OperationConflict):
            self.store.commit_answer(OP,updated,view,choices,lease_token='lease')
        self.assertFalse(any(path.startswith('arm_a_sessions/') for path in self.database.data))

    def test_uncertain_named_dispatch_recovers_outbox_without_paid_replay(self):
        from cloud.arm_a.rider_api import install
        owner=self.store.owner;received=[]
        class Queue:
            def enqueue(queue,received_owner,key,payload_hash):
                received.append((received_owner,key,payload_hash))
                if len(received)==1:raise DispatchError('TASK_DISPATCH_UNAVAILABLE')
            def authenticate(queue,headers):
                raise PermissionError()
        secret='synthetic-private-test-only-'+'x'*32
        app=Flask(__name__)
        @app.before_request
        def identity():request.environ['arm_a_owner']='synthetic-platform-owner'
        install(app,self.questions,self.factory,secret,dispatcher=Queue())
        headers={'X-MotoMedic-Visitor':issue(secret),'Idempotency-Key':OP,'Accept':'application/json'}
        body={'query':'Synthetic arbitrary question','bike_variant':'Himalayan BS6',
            'confirmed_himalayan_bs6':True,'manual_checksum':self.questions.source.checksum,
            'index_id':self.questions.source.index_id}
        with app.test_client() as client:
            failed=client.post('/v1/sessions',json=body,headers=headers)
            self.assertEqual(failed.status_code,503)
            self.assertFalse(failed.json['operation_terminal'])
            processing=client.get('/v1/operations/'+OP,headers=headers)
            self.assertEqual(processing.status_code,202)
            self.assertEqual(received[0],received[1])
            self.assertEqual(self.questions.calls,0)
            conflicted=client.post('/v1/sessions',json={**body,'query':'Other payload'},headers=headers)
            self.assertEqual(conflicted.status_code,409)
            received_owner,key,payload_hash=received[0]
            self.assertEqual(self.factory(received_owner).operation(OP)['state'],'QUEUED')
            self.assertEqual(self.worker.run(received_owner,key,payload_hash),204)
            recovered=client.get('/v1/operations/'+OP,headers=headers)
            self.assertEqual(recovered.status_code,200)
            replay=client.post('/v1/sessions',json=body,headers=headers)
            self.assertEqual(replay.json,recovered.json)
            self.assertEqual(self.questions.calls,1)
            self.assertEqual(client.post('/internal/operations/run',json={},headers=headers).status_code,403)

    def test_missing_dispatch_configuration_rejects_before_admission_or_work(self):
        from cloud.arm_a.rider_api import install
        secret='synthetic-private-test-only-'+'x'*32;app=Flask(__name__)
        @app.before_request
        def identity():request.environ['arm_a_owner']='synthetic-platform-owner'
        install(app,self.questions,self.factory,secret)
        with app.test_client() as client:
            result=client.post('/v1/sessions',json={'query':'Synthetic arbitrary question','bike_variant':'Himalayan BS6',
                'confirmed_himalayan_bs6':True,'manual_checksum':self.questions.source.checksum,
                'index_id':self.questions.source.index_id},headers={'X-MotoMedic-Visitor':issue(secret),'Idempotency-Key':OP})
        self.assertEqual(result.status_code,503)
        self.assertEqual(result.json['error'],'DURABLE_DISPATCH_UNCONFIGURED')
        self.assertFalse(self.database.data)
        self.assertEqual(self.questions.calls,0)

    def test_transactions_read_all_records_before_first_write(self):
        read=Ref.get;set_record=Transaction.set;update=Transaction.update
        def strict_read(ref,transaction=None):
            if transaction is not None and getattr(transaction,'has_writes',False):
                raise AssertionError('Firestore forbids a read after a write')
            return read(ref,transaction)
        def strict_set(tx,*args):
            tx.has_writes=True;return set_record(tx,*args)
        def strict_update(tx,*args):
            tx.has_writes=True;return update(tx,*args)
        with patch.object(Ref,'get',strict_read),patch.object(Transaction,'set',strict_set),patch.object(Transaction,'update',strict_update):
            self.queue();self.store.mark_dispatched(OP)
            self.assertEqual(self.worker.run(self.store.owner,OP,'d'*64),204)
            self.assertEqual(self.store.operation(OP)['state'],'COMPLETE')


class DispatcherTests(unittest.TestCase):
    def dispatcher(self,**kwargs):
        return CloudTasksDispatcher('projects/test/locations/us-central1/queues/private',
            'https://worker.example.com/internal/operations/run',
            'worker@test.iam.gserviceaccount.com',**kwargs)
    def test_task_uses_oidc_named_dedup_and_no_rider_query(self):
        sent=[];dispatcher=self.dispatcher(transport=lambda url,body:sent.append((url,body)) or 409)
        dispatcher.enqueue('a'*64,OP,'d'*64);dispatcher.enqueue('a'*64,OP,'d'*64)
        self.assertEqual(sent[0],sent[1])
        task=sent[0][1]['task'];request=task['httpRequest']
        self.assertEqual(task['dispatchDeadline'],'1200s')
        self.assertEqual(request['oidcToken']['audience'],'https://worker.example.com')
        self.assertEqual(set(json.loads(base64.b64decode(request['body']))),{'owner','operation_id','payload_hash'})
    def test_worker_uses_verified_dedicated_identity_not_tasks_header(self):
        claims={'email':'worker@test.iam.gserviceaccount.com','email_verified':True,
                'aud':'https://worker.example.com','iss':'https://accounts.google.com'}
        dispatcher=self.dispatcher(verifier=lambda token,audience:claims)
        dispatcher.authenticate({'Authorization':'Bearer synthetic-verified-token'})
        for field,value in [('email','rider@example.com'),('email_verified',False),('aud','https://other.example.com'),('iss','other')]:
            original=claims[field];claims[field]=value
            with self.assertRaises(PermissionError):dispatcher.authenticate({'Authorization':'Bearer synthetic-verified-token'})
            claims[field]=original
        with self.assertRaises(PermissionError):dispatcher.authenticate({'X-CloudTasks-TaskName':'forged'})
    def test_dispatch_failure_sanitizes_and_incomplete_config_fails_closed(self):
        dispatcher=self.dispatcher(transport=lambda *args:503)
        with self.assertRaisesRegex(DispatchError,'^TASK_DISPATCH_UNAVAILABLE$'):dispatcher.enqueue('a'*64,OP,'d'*64)
        with patch.dict('os.environ',{},clear=True):self.assertIsNone(configured_dispatcher())
        with patch.dict('os.environ',{'MOTOMEDIC_TASK_QUEUE':'projects/test/locations/us-central1/queues/private'},clear=True):
            with self.assertRaisesRegex(RuntimeError,'INCOMPLETE'):configured_dispatcher()


if __name__=='__main__':unittest.main()
