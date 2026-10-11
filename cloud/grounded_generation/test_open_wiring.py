"""Private backend/client delivery integration; synthetic drafting and verifier.

No model request, source approval or semantic-quality claim is made. The test
blocks each private stage and durable save to prove progress timing and secrecy.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import threading
import types
import sys
import unittest
from unittest.mock import patch
from flask import Flask
from cloud.arm_a.rider_api import install
from cloud.arm_a.store import FirestoreState
from cloud.arm_a.visitor import issue
from cloud.arm_a.test_store import Client,transactional
from controller_contracts import DiagnosticSession
from rider_ui.client import MANUAL_SHA,INDEX_ID,validate_view
from rider_ui.verified_sse import read_verified_stream,response_hash
from rider_ui.tests.test_client import view as fixture_view

OP='c'*32
LOCK='e'*64

class ScriptedQuestions:
    open_verification=True
    def __init__(self):
        self.controller=types.SimpleNamespace(response_generator=types.SimpleNamespace(config=types.SimpleNamespace(lock=LOCK)))
        self.registry=types.SimpleNamespace(source={'variant':'Himalayan BS6'},checksum=MANUAL_SHA,index_id=INDEX_ID,source_ready=lambda:True)
        self.source_authority=types.SimpleNamespace(lock='3'*64,check=lambda:None)
        self.retrieving=threading.Event();self.drafting=threading.Event();self.verifying=threading.Event()
        self.continue_retrieval=threading.Event();self.continue_draft=threading.Event();self.continue_verify=threading.Event()
        self.calls=0;self.fail_verifier=False;self.show_fallback=False
    def new_session(self):
        return DiagnosticSession('a'*32,'synthetic-manual',MANUAL_SHA,'Himalayan BS6','synthetic-test-edition',(),LOCK,generation_lock=LOCK)
    def answer(self,session,query,*,history=(),progress=None,operation_id=None):
        self.calls+=1
        progress('retrieving');self.retrieving.set()
        if not self.continue_retrieval.wait(5):raise RuntimeError('Test retrieval blocked')
        progress('drafting');self.drafting.set()
        if not self.continue_draft.wait(5):raise RuntimeError('Test draft blocked')
        progress('verifying');self.verifying.set()
        if not self.continue_verify.wait(5):raise RuntimeError('Test verifier blocked')
        session=replace(session,version=session.version+1)
        v=fixture_view();v['session_id']=session.session_id;v['version']=session.version
        v['response']['natural_language']='Synthetic accepted wording only. '+('Exact buffered text. '*12)+'café.'
        if self.fail_verifier:
            v['response'].update(type='SYSTEM_ERROR',technical_content=False,release_gate_passed=False,cited_pages=[])
            v['response']['natural_language']='I couldn’t check the answer right now. Please try again shortly.'
        elif self.show_fallback:
            v['response'].update(type='UNSUPPORTED',technical_content=False,release_gate_passed=False,cited_pages=[])
            v['response']['natural_language']='I couldn’t find relevant information in the selected manual to answer your question. Please contact Royal Enfield or an authorised service centre.'
            v['escalation_uri']='mailto:support@royalenfield.com'
        else:
            from cloud.grounded_generation.verified_qa import VERSION
            v['runtime_policy']=VERSION
            v['response']['semantic_verification_passed']=True
            v['verified_delivery']={'operation_id':operation_id,'runtime_lock':LOCK,'manual_checksum':MANUAL_SHA,
                'index_id':INDEX_ID,'source_authority_lock':'3'*64,'presentation_sha256':response_hash(v),
                'evidence_payload_sha256':'1'*64,'binding_sha256':'2'*64,'text_sha256':hashlib.sha256(v['response']['natural_language'].encode()).hexdigest()}
        return session,v,{}
    def release(self):
        self.continue_retrieval.set();self.continue_draft.set();self.continue_verify.set()

class BlockingState(FirestoreState):
    def __init__(self,client,owner,entered,release):
        super().__init__(client,owner);self.entered=entered;self.release=release
    def commit_answer(self,*args,**kwargs):
        self.entered.set()
        if not self.release.wait(5):raise RuntimeError('Test commit blocked')
        return super().commit_answer(*args,**kwargs)

class OpenWiringTests(unittest.TestCase):
    def setUp(self):
        google=types.ModuleType('google');cloud=types.ModuleType('google.cloud')
        firestore=types.ModuleType('google.cloud.firestore');firestore.transactional=transactional
        cloud.firestore=firestore;google.cloud=cloud
        self.modules=patch.dict(sys.modules,{'google':google,'google.cloud':cloud,'google.cloud.firestore':firestore});self.modules.start()
        self.database=Client();self.questions=ScriptedQuestions()
        self.commit_entered=threading.Event();self.release_commit=threading.Event()
        self.secret='synthetic-private-test-only-'+'x'*32;self.capability=issue(self.secret)
        self.factory=lambda owner:BlockingState(self.database,owner,self.commit_entered,self.release_commit)
        self.app=Flask(__name__)
        @self.app.before_request
        def private_fixture_identity():
            from flask import request
            request.environ['arm_a_owner']='synthetic-platform-verified-owner'
        install(self.app,self.questions,self.factory,self.secret)
        self.client=self.app.test_client()
        self.headers={'X-MotoMedic-Visitor':self.capability,'Idempotency-Key':OP,'Accept':'text/event-stream'}
        self.body={'query':'Synthetic unseen question without catalogue entry','bike_variant':'Himalayan BS6',
            'confirmed_himalayan_bs6':True,'manual_checksum':MANUAL_SHA,'index_id':INDEX_ID,'cache_mode':'enabled'}
    def tearDown(self):
        self.questions.release();self.release_commit.set();self.modules.stop()
    def post(self):return self.client.post('/v1/sessions',json=self.body,headers=self.headers,buffered=False)
    def recover(self):return self.client.get('/v1/operations/'+OP,headers=self.headers)
    def event(self,raw):
        text=raw.decode();kind=text.split('event: ')[1].split('\n')[0]
        return kind,json.loads(text.split('data: ')[1])

    def test_prompt_progress_private_verifier_and_commit_barriers_then_exact_recovery(self):
        response=self.post();self.assertEqual(response.status_code,200)
        iterator=iter(response.response);frames=[next(iterator)]
        self.assertEqual(self.event(frames[-1]),('progress',{'operation_id':OP,'stage':'retrieving'}))
        self.assertFalse(self.questions.continue_retrieval.is_set())
        self.assertEqual(self.recover().status_code,202)
        self.questions.continue_retrieval.set();frames.append(next(iterator))
        self.assertEqual(self.event(frames[-1])[1]['stage'],'drafting')
        self.questions.continue_draft.set();frames.append(next(iterator))
        self.assertEqual(self.event(frames[-1])[1]['stage'],'verifying')
        self.assertTrue(self.questions.verifying.is_set());self.assertFalse(self.commit_entered.is_set())
        remaining=[];finished=threading.Event()
        def collect():
            remaining.extend(iterator);finished.set()
        worker=threading.Thread(target=collect);worker.start()
        self.assertFalse(finished.wait(0.05));self.assertEqual(remaining,[])
        self.questions.continue_verify.set();self.assertTrue(self.commit_entered.wait(2))
        self.assertEqual(self.recover().status_code,202)
        self.assertFalse(finished.wait(0.05));self.assertEqual(remaining,[])
        self.assertFalse(any(p.startswith('arm_a_sessions/') for p in self.database.data))
        self.release_commit.set();worker.join(3);self.assertTrue(finished.is_set())
        frames+=remaining;published=[];parts=[];stages=[]
        accepted=read_verified_stream(frames,published.append,operation_id=OP,on_progress=stages.append,on_chunk=parts.append)
        recovered=validate_view(self.recover().get_json())
        self.assertEqual(accepted,recovered);self.assertEqual(published,[recovered])
        self.assertEqual(''.join(parts),recovered['response']['natural_language'])
        self.assertEqual(response_hash(accepted),recovered['delivery']['response_sha256'])
        self.assertEqual(stages,['retrieving','drafting','verifying','displaying'])
        self.assertEqual(self.questions.calls,1)
        replay=self.client.post('/v1/sessions',json=self.body,headers=self.headers)
        self.assertEqual(read_verified_stream([replay.data],operation_id=OP),recovered)
        self.assertEqual(self.questions.calls,1)
        self.assertEqual(replay.headers.get('X-Operation-Replay'),'true')

    def test_disconnected_progress_worker_saves_for_idempotent_recovery(self):
        response=self.post();iterator=iter(response.response);first=next(iterator)
        self.assertEqual(self.event(first)[0],'progress')
        response.close();self.questions.release();self.release_commit.set()
        self.assertTrue(self.commit_entered.wait(2))
        # Wait on actual store completion, not a simulated operational stage.
        finished=threading.Event()
        def read_saved():
            for _ in range(1000):
                if any(v.get('state')=='COMPLETE' for k,v in self.database.data.items() if k.startswith('arm_a_operations/')):
                    finished.set();return
                threading.Event().wait(0.001)
        waiter=threading.Thread(target=read_saved);waiter.start();waiter.join(2)
        self.assertTrue(finished.is_set());self.assertEqual(self.recover().status_code,200)
        self.assertEqual(self.questions.calls,1)

    def test_fixed_fallback_stays_neutral_with_no_displaying_or_answer_events(self):
        self.questions.show_fallback=True;self.questions.release();self.release_commit.set()
        response=self.post();frames=list(response.response)
        self.assertEqual([self.event(f)[0] for f in frames],['progress','progress','progress','complete'])
        labels=[];published=[];parts=[]
        result=read_verified_stream(frames,published.append,operation_id=OP,on_progress=labels.append,on_chunk=parts.append)
        self.assertEqual(result['response']['type'],'UNSUPPORTED')
        self.assertEqual(result['response']['technical_content'],False)
        self.assertNotIn('displaying',labels);self.assertEqual(published,[]);self.assertEqual(parts,[])
        self.assertEqual(self.recover().get_json(),result)

    def test_retired_or_forged_saved_answer_cannot_recover_or_replay(self):
        self.questions.release();self.release_commit.set()
        response=self.post();list(response.response)
        records=[(key,deepcopy(record)) for key,record in self.database.data.items()
                 if key.startswith(('arm_a_operations/','arm_a_sessions/')) and 'view' in record]
        self.assertTrue(records)
        mutations=(lambda v:v.update(runtime_policy='GROUNDED_PRIMARY'),
                   lambda v:v['response'].update(semantic_verification_passed=False),
                   lambda v:v['delivery'].update(runtime_lock='f'*64),
                   lambda v:v['verified_delivery'].update(operation_id='d'*32),
                   lambda v:v['verified_delivery'].update(source_authority_lock='4'*64))
        for mutate in mutations:
            for key,original in records:
                forged=deepcopy(original);mutate(forged['view']);self.database.data[key]=forged
            self.assertEqual(self.recover().status_code,503)
            saved=self.client.get('/v1/sessions/'+'a'*32,headers=self.headers)
            self.assertEqual(saved.status_code,503)
            replay=self.client.post('/v1/sessions',json=self.body,headers=self.headers)
            self.assertEqual(replay.status_code,409)
            self.assertEqual(self.questions.calls,1)
            for key,original in records:self.database.data[key]=deepcopy(original)

    def test_changed_source_authority_or_version_blocks_saved_technical_response(self):
        self.questions.release();self.release_commit.set()
        response=self.post();list(response.response)
        self.assertEqual(self.recover().status_code,200)
        original=self.questions.source_authority.lock
        self.questions.source_authority.lock='4'*64
        self.assertEqual(self.recover().status_code,503)
        self.questions.source_authority.lock=original
        self.questions.registry.index_id='changed-index'
        self.assertEqual(self.recover().status_code,503)
        self.questions.registry.index_id=INDEX_ID
        self.questions.registry.source_ready=lambda:False
        self.assertEqual(self.recover().status_code,503)
        self.assertEqual(self.questions.calls,1)

    def test_verifier_outage_neutral_complete_no_answer_chunks(self):
        self.questions.fail_verifier=True;self.questions.release();self.release_commit.set()
        response=self.post();frames=list(response.response)
        kinds=[self.event(f)[0] for f in frames]
        self.assertEqual(kinds,['progress','progress','progress','complete'])
        result=read_verified_stream(frames,operation_id=OP)
        self.assertEqual(result['response']['type'],'SYSTEM_ERROR')
        self.assertEqual(result['response']['technical_content'],False)
        self.assertEqual(self.recover().get_json(),result)

if __name__=='__main__':unittest.main()
