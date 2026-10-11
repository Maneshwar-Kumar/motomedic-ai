"""Synthetic transactional capacity checks; no cloud or provider requests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import threading
import types
import unittest
from unittest.mock import patch
from dataclasses import replace
from evidence_registry import content_hash
import cloud.grounded_generation.test_verified_qa as verified
from cloud.grounded_generation.whole_turn_admission import (WholeTurnAdmission, ALLOCATION,
    operation_deadline, MAX_SLEEP_SECONDS)
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

    def test_future_slots_are_bounded_without_raising_existing_rate(self):
        self.admit.begin_turn('first');self.admit.end_turn()
        with self.assertRaisesRegex(ProviderFailure,'QUEUE_BOUND'):self.admit.begin_turn('second')
        self.assertEqual(len(self.client.documents['grounded-provider-global-v1']['events']),8)

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
    setUpClass=classmethod(verified.VerifiedTests.setUpClass.__func__)
    setUp=verified.VerifiedTests.setUp
    chunk=verified.VerifiedTests.chunk
    setup_runtime=verified.VerifiedTests.setup_runtime

    def test_same_rider_key_in_distinct_sessions_has_distinct_admission_and_same_proof_identity(self):
        identities=[];p=verified.Provider()
        p.begin_turn=lambda identity:identities.append(identity) or {'synthetic':True}
        q,p,composer,session=self.setup_runtime(p)
        for session_id in ('a'*32,'b'*32):
            current=replace(session,session_id=session_id)
            _,view,_=q.answer(current,'How wide is the bore?',operation_id='c'*32)
            self.assertEqual(view['response']['type'],'SUPPORTED')
            self.assertEqual(composer.last_admitted['binding']['operation_id'],'c'*32)
            self.assertEqual(view['verified_delivery']['operation_id'],'c'*32)
        self.assertEqual(identities,[content_hash({'session_id':sid,'operation_id':'c'*32}) for sid in ('a'*32,'b'*32)])
        self.assertNotEqual(*identities)


if __name__=='__main__':unittest.main()
