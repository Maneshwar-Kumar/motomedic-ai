"""Synthetic transactional capacity checks; no cloud or provider requests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import threading
import types
import unittest
from unittest.mock import patch
from dataclasses import replace
from evidence_registry import content_hash
from controller_contracts import DiagnosticSession, Response, ResponseType
import cloud.grounded_generation.test_verified_qa as verified
from cloud.grounded_generation.whole_turn_admission import (WholeTurnAdmission, ALLOCATION,
    operation_deadline, MAX_SLEEP_SECONDS, PACING_VERSION)
from cloud.grounded_generation.provider import GemmaProvider, ProviderFailure
from cloud.grounded_generation.fallback_provider import FallbackProvider
from cloud.grounded_generation.claude_provider import ClaudeProvider, MAX_CALL_USD


class Reference:
    def __init__(self, client, name):self.client, self.name = client, name
    def get(self, transaction=None):
        if self.client.fail:raise RuntimeError('synthetic outage')
        body=deepcopy(self.client.documents.get(self.name))
        return types.SimpleNamespace(exists=body is not None, to_dict=lambda:body)


class Client:
    def __init__(self):self.documents={};self.lock=threading.RLock();self.fail=False
    def collection(self, name):assert name=='arm_a_usage';return self
    def document(self, name):return Reference(self, name)
    def transaction(self):return self
    def set(self, ref, body):self.documents[ref.name]=deepcopy(body)


def atomic(fn):
    def run(tx):
        with tx.lock:return fn(tx)
    return run


class Tests(unittest.TestCase):
    def setUp(self):
        self.client=Client();self.now=datetime(2026,10,12,tzinfo=timezone.utc)
        self.waits=[]
        def sleep(seconds):
            self.waits.append(seconds);self.now+=timedelta(seconds=seconds)
        self.admit=WholeTurnAdmission(self.client,now=lambda:self.now,sleep=sleep)
        google=types.ModuleType('google');cloud=types.ModuleType('google.cloud')
        cloud.firestore=types.SimpleNamespace(transactional=atomic);google.cloud=cloud
        self.patch=patch.dict('sys.modules',{'google':google,'google.cloud':cloud});self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_reserves_correction_and_retry_capacity_before_first_call(self):
        receipt=self.admit.begin_turn('operation-1')
        self.assertEqual(receipt['reserved_attempts'],8)
        self.assertEqual(receipt['reserved_tokens'],79936)
        self.assertFalse(self.waits)
        times=[]
        for _ in range(8):
            self.admit(9992,'generation');times.append(self.now)
        self.assertEqual([(b-a).total_seconds() for a,b in zip(times,times[1:])],[61]*7)
        self.assertTrue(all(wait<=MAX_SLEEP_SECONDS for wait in self.waits))
        with self.assertRaisesRegex(ProviderFailure,'UNRESERVED'):self.admit(1,'generation')

    def test_delayed_attempts_still_obey_rolling_minute(self):
        self.admit.begin_turn('delayed')
        self.now+=timedelta(seconds=120)
        self.admit(5000,'generation');self.admit(5000,'generation')
        self.assertEqual(sum(self.waits),61)
        events=self.client.documents['grounded-provider-global-v1']['events']
        consumed=[e['at'] for e in events if e.get('consumed')]
        self.assertEqual((consumed[1]-consumed[0]).total_seconds(),61)

    def test_oversleep_repositions_consumed_permit_before_paid_transmission(self):
        def oversleep(seconds):self.now+=timedelta(seconds=seconds+120)
        self.admit.sleep=oversleep
        self.admit.begin_turn('oversleep');times=[]
        for _ in range(3):
            self.admit(9992,'generation');times.append(self.now)
        self.assertTrue(all((b-a).total_seconds()>=60 for a,b in zip(times,times[1:])))
        consumed=[e['at'] for e in self.client.documents['grounded-provider-global-v1']['events'] if e.get('consumed')]
        self.assertEqual(consumed,times)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],8)

    def test_slow_commit_rechecks_before_returning_a_stale_permit(self):
        original=self.client.set;delayed=[]
        def slow_set(ref,body):
            original(ref,body)
            if ref.name=='grounded-provider-global-v1' and any(e.get('consumed') for e in body['events']) and not delayed:
                delayed.append(True);self.now+=timedelta(seconds=120)
        self.client.set=slow_set
        self.admit.begin_turn('slow-commit');self.admit(9992,'generation')
        consumed=[e['at'] for e in self.client.documents['grounded-provider-global-v1']['events'] if e.get('consumed')]
        self.assertEqual(consumed,[self.now])

    def test_deadline_binds_capacity_and_blocks_expired_turn_before_reserving(self):
        before=deepcopy(self.client.documents)
        with operation_deadline(self.now+timedelta(seconds=427)):
            with self.assertRaisesRegex(ProviderFailure,'DEADLINE_EXCEEDED'):self.admit.begin_turn('too-short')
        self.assertEqual(self.client.documents,before)
        with operation_deadline(self.now):
            with self.assertRaisesRegex(ProviderFailure,'DEADLINE_EXCEEDED'):self.admit.begin_turn('expired')
        self.assertEqual(self.client.documents,before)
        self.admit.begin_turn('unscoped-synthetic')

    def test_oversleep_past_deadline_stops_paid_transport_and_retains_reservation(self):
        from cloud.grounded_generation.test_provider import Transport
        transport=Transport();provider=GemmaProvider(self.admit,transport=transport,key='synthetic')
        with operation_deadline(self.now+timedelta(seconds=500)):
            provider.begin_turn('deadline')
            provider.complete('policy',{}, {}, {})
            self.admit.sleep=lambda seconds:setattr(self,'now',self.now+timedelta(seconds=seconds+500))
            with self.assertRaisesRegex(ProviderFailure,'DEADLINE_EXCEEDED'):
                provider.complete('policy',{}, {}, {})
            provider.end_turn()
        self.assertEqual(sum(path.endswith(':generateContent') for path,_ in transport.calls),1)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],8)
        events=self.client.documents['grounded-provider-global-v1']['events']
        self.assertEqual(sum(bool(e.get('consumed')) for e in events),2)

    def test_oversleep_queue_bound_never_restarts_the_wait_budget(self):
        self.admit.begin_turn('queue-bound');self.admit(9992,'generation')
        self.admit.sleep=lambda seconds:setattr(self,'now',self.now+timedelta(seconds=seconds+800))
        with self.assertRaisesRegex(ProviderFailure,'QUEUE_BOUND'):self.admit(9992,'generation')
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],8)

    def test_store_outage_after_wait_keeps_slot_consumed_without_paid_call(self):
        self.admit.begin_turn('wait-outage');self.admit(9992,'generation')
        def failed_wait(seconds):
            self.now+=timedelta(seconds=seconds);self.client.fail=True
        self.admit.sleep=failed_wait
        with self.assertRaisesRegex(ProviderFailure,'STORE_UNAVAILABLE'):self.admit(9992,'generation')
        events=self.client.documents['grounded-provider-global-v1']['events']
        self.assertEqual(sum(bool(e.get('consumed')) for e in events),2)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],8)

    def test_duplicate_and_uncertain_calls_do_not_reopen_reservations(self):
        self.admit.begin_turn('same');self.admit(100,'generation');self.admit.end_turn()
        before=deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure,'NO_REPLAY'):self.admit.begin_turn('same')
        self.assertEqual(before,self.client.documents)

    def test_lifetime_allocation_survives_new_days_and_instances(self):
        for i in range(12):
            self.admit.begin_turn('day-'+str(i));self.admit.end_turn()
            self.now+=timedelta(days=2)
        other=WholeTurnAdmission(self.client,now=lambda:self.now,sleep=lambda _:None)
        with self.assertRaisesRegex(ProviderFailure,'ALLOCATION_LIMIT'):other.begin_turn('exhausted')
        self.assertNotIn('expires_at',self.client.documents[ALLOCATION])

    def test_store_outage_or_entire_turn_limit_blocks_first_generation(self):
        self.client.fail=True
        with self.assertRaisesRegex(ProviderFailure,'STORE_UNAVAILABLE'):self.admit.begin_turn('outage')
        self.assertFalse(self.client.documents)
        self.client.fail=False
        self.client.documents[ALLOCATION]={'version':'changed'}
        with self.assertRaisesRegex(ProviderFailure,'BINDING_CHANGED'):self.admit.begin_turn('binding')

    def test_active_future_slots_still_bound_a_different_worker(self):
        self.admit.begin_turn('first')
        other=WholeTurnAdmission(self.client,now=lambda:self.now,sleep=lambda _:None)
        with self.assertRaisesRegex(ProviderFailure,'QUEUE_BOUND'):other.begin_turn('second')
        self.assertEqual(len(self.client.documents['grounded-provider-global-v1']['events']),8)

    def test_completed_two_call_turn_releases_only_pacing_and_retains_sixteen_reserved_slots(self):
        receipt=self.admit.begin_turn('first')
        self.admit(9992,'generation');self.admit(9992,'generation')
        last_actual=self.now
        allocation_before=deepcopy(self.client.documents[ALLOCATION])
        self.assertIs(self.admit.end_turn(),receipt)
        self.assertEqual(receipt['pacing_version'],PACING_VERSION)
        self.assertEqual(receipt['sealing_status'],'SEALED_UNUSED_CONFIRMED')
        self.assertEqual(receipt['sealed_unused_slots'],6)
        self.assertEqual(self.client.documents[ALLOCATION],allocation_before)
        self.admit.begin_turn('second');self.admit(9992,'generation')
        self.assertEqual((self.now-last_actual).total_seconds(),61)
        events=self.client.documents['grounded-provider-global-v1']['events']
        self.assertEqual(len(events),16)
        self.assertEqual(sum(e.get('state')=='SEALED_UNUSED' for e in events),6)
        self.assertEqual(sum(e['tokens'] for e in events),16*9992)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],16)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_tokens'],16*9992)

    def test_uncertain_consumed_future_permit_stays_active_after_turn_ends(self):
        self.admit.begin_turn('interrupted');self.admit(9992,'generation')
        def worker_interrupted(_):raise RuntimeError('synthetic worker interrupted before transport')
        normal_sleep=self.admit.sleep;self.admit.sleep=worker_interrupted
        with self.assertRaisesRegex(RuntimeError,'interrupted'):self.admit(9992,'generation')
        self.assertEqual(self.now,datetime(2026,10,12,tzinfo=timezone.utc))
        self.admit.end_turn();self.admit.sleep=normal_sleep
        old=self.client.documents['grounded-provider-global-v1']['events']
        self.assertTrue(old[1]['consumed'])
        self.assertNotIn('state',old[1])
        self.admit.begin_turn('next');self.admit(9992,'generation')
        self.assertEqual(self.now,datetime(2026,10,12,tzinfo=timezone.utc)+timedelta(seconds=122))
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],16)

    def test_sealed_slot_cannot_be_consumed_even_if_a_stale_worker_restores_its_turn(self):
        self.admit.begin_turn('sealed');self.admit(9992,'generation');self.admit(9992,'generation')
        stale_turn=dict(self.admit.local.turn)
        self.admit.end_turn()
        before=deepcopy(self.client.documents)
        self.admit.local.turn=stale_turn
        with self.assertRaisesRegex(ProviderFailure,'SEALED_UNUSED_ATTEMPT_FORBIDDEN'):
            self.admit(9992,'generation')
        self.assertEqual(self.client.documents,before)

    def test_sealing_outage_clears_thread_state_preserves_original_error_and_active_events(self):
        receipt=self.admit.begin_turn('seal-outage');self.admit(9992,'generation')
        before=deepcopy(self.client.documents);self.client.fail=True
        with self.assertRaisesRegex(ProviderFailure,'ORIGINAL_GENERATION_ERROR'):
            try:raise ProviderFailure('ORIGINAL_GENERATION_ERROR')
            finally:self.admit.end_turn()
        self.assertIsNone(self.admit.local.turn)
        self.assertEqual(receipt['sealing_status'],'SEALING_UNCONFIRMED_ACTIVE_POLICY_RETAINED')
        self.assertEqual(receipt['sealed_unused_slots'],0)
        self.assertEqual(self.client.documents,before)
        self.client.fail=False
        with self.assertRaisesRegex(ProviderFailure,'QUEUE_BOUND'):self.admit.begin_turn('after-outage')
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],8)

    def test_failed_sealing_write_leaves_all_slots_active(self):
        receipt=self.admit.begin_turn('write-outage');self.admit(9992,'generation')
        before=deepcopy(self.client.documents)
        def unavailable_set(ref,body):raise RuntimeError('synthetic failed commit')
        self.client.set=unavailable_set
        self.admit.end_turn()
        self.assertEqual(self.client.documents,before)
        self.assertEqual(receipt['sealed_unused_slots'],0)
        self.assertEqual(receipt['sealing_status'],'SEALING_UNCONFIRMED_ACTIVE_POLICY_RETAINED')
        self.assertIsNone(self.admit.local.turn)

    def test_consumed_or_unproved_sealing_markers_fail_closed(self):
        self.admit.begin_turn('original');self.admit(9992,'generation');self.admit.end_turn()
        events=self.client.documents['grounded-provider-global-v1']['events']
        events[0].update(state='SEALED_UNUSED',sealed_version=PACING_VERSION,sealed_at=self.now)
        before=deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure,'STORE_INVALID'):self.admit.begin_turn('new')
        self.assertEqual(self.client.documents,before)

    def test_shorter_next_turn_does_not_shorten_retention_of_sealed_future_events(self):
        self.admit.begin_turn('twelve',attempts=12);self.admit.end_turn()
        old_last=self.client.documents['grounded-provider-global-v1']['events'][-1]['at']
        self.admit.begin_turn('eight',attempts=8)
        ledger=self.client.documents['grounded-provider-global-v1']
        self.assertEqual(len(ledger['events']),20)
        self.assertEqual(ledger['expires_at'],old_last+timedelta(hours=24))
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'],20)

    def test_unconfigured_primary_count_uses_native_fallback_counter(self):
        calls=[]
        def transport(method,path,body,key):
            calls.append((path,body))
            return {'input_tokens':7}
        primary=GemmaProvider(self.admit,key='')
        primary.key=None
        fallback=ClaudeProvider(self.admit,reserve_cost=lambda n,m:None,
                                transport=transport,key='synthetic')
        chain=FallbackProvider(primary,fallback)
        self.assertEqual(chain.count({'contents':[{'parts':[{'text':'presentation'}]}]}),7)
        self.assertEqual(calls[0][0],'messages/count_tokens')
        self.assertEqual(calls[0][1]['model'],'claude-haiku-5-5')

    def test_enabled_fallback_reserves_all_cost_before_primary_generation(self):
        costs=[]
        primary=GemmaProvider(self.admit,key='synthetic')
        fallback=ClaudeProvider(self.admit,reserve_cost=lambda n,m:costs.append((n,m)),key='synthetic')
        chain=FallbackProvider(primary,fallback)
        receipt=chain.begin_turn('fallback')
        self.assertEqual(receipt['reserved_attempts'],12)
        self.assertEqual(costs,[(4*MAX_CALL_USD,'claude-haiku-5-5')])
        chain.end_turn()


class AdmissionIdentityTests(unittest.TestCase):
    def setup_runtime(self,p):
        """Exercise real composition/delivery with synthetic source boundaries only."""
        # Exercise the real bound model/prompt contract with synthetic sources
        # and providers. A partial Config double cannot represent v10 binding.
        from cloud.grounded_generation.verified_qa import Config
        config=Config()
        eid='synthetic-evidence'
        registry=types.SimpleNamespace(checksum=content_hash({'fixture':'synthetic-manual'}),
            index_id='synthetic-index',source={'pdf_pages':1},source_ready=lambda:True,
            support_uri=lambda:None,evidence={eid:{'provenance':[{'page_no':1}]}})
        admitted={'authority_lock':content_hash({'fixture':'synthetic-authority'}),
            'evidence':{eid:{'source_object':{'content':{'text':'Synthetic fixture value is 7 units.'}}}},
            'required_evidence_ids':[eid],'required_display':[],'gaps':[]}
        admitted['payload_sha256']=content_hash(admitted)
        def select(payload,ids):
            self.assertEqual(ids,{eid});self.assertEqual(payload,admitted)
            return deepcopy(admitted)
        authority=types.SimpleNamespace(validate=lambda payload:self.assertEqual(payload,admitted),select=select)
        composer=verified.Composer(p,authority)
        controller=types.SimpleNamespace(registry=registry,scope_status=lambda session:'CONFIRMED',
            response=lambda kind,text,session,**kwargs:Response(ResponseType(kind),text,
                trace_id='synthetic-trace',session_status=session.status,**kwargs))
        session=DiagnosticSession('a'*32,'synthetic-manual',registry.checksum,
            'synthetic-variant','synthetic-edition',(),'synthetic-source-lock',generation_lock=config.lock)
        def run(current,query,*,operation_id):
            response=composer.compose_open(controller,current,admitted,query,{'operation_id':operation_id})
            view,choices=verified.saved_view(registry,current,response,authority,composer.last_admitted,operation_id)
            return current,view,choices
        return types.SimpleNamespace(answer=run),p,composer,session

    def test_same_rider_key_in_distinct_sessions_has_distinct_admission_and_same_proof_identity(self):
        identities=[];p=verified.Provider([verified.draft('synthetic-evidence','Synthetic fixture value is 7 units.')])
        p.begin_turn=lambda identity:identities.append(identity) or {'synthetic':True}
        q,p,composer,session=self.setup_runtime(p)
        for session_id in ('a'*32,'b'*32):
            current=replace(session,session_id=session_id)
            _,view,_=q.answer(current,'What is the synthetic fixture value?',operation_id='c'*32)
            self.assertEqual(view['response']['type'],'SUPPORTED')
            self.assertEqual(composer.last_admitted['binding']['operation_id'],'c'*32)
            self.assertEqual(view['verified_delivery']['operation_id'],'c'*32)
        self.assertEqual(identities,[content_hash({'session_id':sid,'operation_id':'c'*32}) for sid in ('a'*32,'b'*32)])
        self.assertNotEqual(*identities)
        self.assertEqual([call[0] for call in p.calls],[verified.DRAFT_SCHEMA,verified.VERIFY_SCHEMA]*2)


if __name__=='__main__':unittest.main()
