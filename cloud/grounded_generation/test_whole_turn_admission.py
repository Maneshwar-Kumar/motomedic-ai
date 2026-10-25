"""Synthetic transactional capacity checks; no cloud or provider requests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import threading
import types
import unittest
from unittest.mock import patch
from cloud.common import ProviderFailure
from cloud.grounded_generation.whole_turn_admission import (WholeTurnAdmission, ALLOCATION,
    operation_deadline, MAX_SLEEP_SECONDS, PACING_VERSION, GEMMA, HAIKU,
    PLAN_VERSION, SEALED_VERSIONS)
from cloud.grounded_generation.claude_budget import ALLOCATION as CLAUDE_ALLOCATION, VERSION as CLAUDE_VERSION


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

    def plan(self, *, haiku_input=20000, **changes):
        slot = {'model': HAIKU, 'stage': 'generate', 'input_tokens': haiku_input, 'output_tokens': 1800, 'attempt': 1}
        slot.update(changes)
        return {'slots': [slot], 'request_sha256': 'a' * 64}

    def test_single_generation_reserves_tokens_and_haiku_cost_atomically(self):
        self.client.documents[ALLOCATION] = {'version': 'whole-turn-capacity-v1',
            'maximum_attempts': 100, 'maximum_tokens': 999200, 'reserved_attempts': 24, 'reserved_tokens': 239808}
        self.client.documents[CLAUDE_ALLOCATION] = {'version': CLAUDE_VERSION, 'model': HAIKU,
            'maximum_nanodollars': 1000000000, 'reserved_nanodollars': 11544000, 'reservation_count': 3}
        receipt = self.admit.begin_turn('single', plan=self.plan())
        cost = 20000 * 125 + 1800 * 500
        self.assertEqual(receipt['plan_version'], PLAN_VERSION)
        self.assertEqual(receipt['reservation_mode'], 'SINGLE_GENERATION_CALL')
        self.assertEqual((receipt['reserved_attempts'], receipt['reserved_tokens'], receipt['reserved_nanodollars']),
                         (1, 21800, cost))
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 25)
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_tokens'], 239808 + 21800)
        self.assertEqual(self.client.documents[CLAUDE_ALLOCATION]['reserved_nanodollars'], 11544000 + cost)
        self.assertEqual(self.client.documents[CLAUDE_ALLOCATION]['reservation_count'], 4)
        self.assertNotIn('expires_at', self.client.documents[ALLOCATION])
        permit = self.admit.for_model(HAIKU, role='generation')(21800, 'generation')
        self.assertEqual((permit['stage'], permit['input_tokens'], permit['maximum_nanodollars']), ('generate', 20000, cost))
        with self.assertRaisesRegex(ProviderFailure, 'UNRESERVED'):
            self.admit.for_model(HAIKU, role='generation')(21800, 'generation')
        ended = self.admit.end_turn()
        self.assertEqual(ended['sealing_status'], 'SEALED_UNUSED_CONFIRMED')
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_tokens'], 239808 + 21800)

    def test_no_token_ceiling_but_attempts_and_haiku_money_still_bind(self):
        # The ledger as recorded under the retired 2,000,000-token grant, already past it.
        self.client.documents[ALLOCATION] = {'version': 'whole-turn-capacity-v1', 'maximum_attempts': 100,
            'maximum_tokens': 2000000, 'token_ceiling_authorization': {'scope_sha256': 'a' * 64},
            'reserved_attempts': 72, 'reserved_tokens': 2100000}
        old_event = {'at': self.now - timedelta(hours=2), 'tokens': 21800, 'kind': 'generation',
            'operation_id': 'old', 'slot': 0, 'consumed': True, 'primary_token_ceiling': 2000000,
            'token_ceiling_scope_sha256': 'a' * 64}
        self.client.documents['grounded-provider-global-v1'] = {'events': [old_event]}
        receipt = self.admit.begin_turn('beyond-old-ceiling', plan=self.plan(haiku_input=500000))
        self.assertEqual(receipt['token_ceiling'], 'NONE')
        allocation = self.client.documents[ALLOCATION]
        self.assertEqual((allocation['reserved_tokens'], allocation['reserved_attempts'], allocation['token_ceiling']),
                         (2100000 + 501800, 73, 'NONE'))
        self.assertNotIn('maximum_tokens', allocation)
        new_event = self.client.documents['grounded-provider-global-v1']['events'][-1]
        self.assertNotIn('primary_token_ceiling', new_event)
        self.admit.for_model(HAIKU, role='generation')(501800, 'generation')
        self.admit.end_turn()
        allocation['reserved_attempts'] = 100
        with self.assertRaisesRegex(ProviderFailure, 'ALLOCATION_LIMIT'):
            self.admit.begin_turn('no-attempts-left', plan=self.plan())
        allocation['reserved_attempts'] = 80
        self.client.documents[CLAUDE_ALLOCATION] = {'version': CLAUDE_VERSION, 'model': HAIKU,
            'maximum_nanodollars': 1000000000, 'reserved_nanodollars': 999999000, 'reservation_count': 9}
        with self.assertRaisesRegex(ProviderFailure, 'CLAUDE_SPEND_LIMIT'):
            self.admit.begin_turn('no-money-left', plan=self.plan())

    def test_large_input_reserves_the_long_context_price_tier(self):
        receipt = self.admit.begin_turn('large', plan=self.plan(haiku_input=120000))
        self.assertEqual(receipt['reserved_nanodollars'], 120000 * 625 + 1800 * 2500)

    def test_invalid_single_generation_plans_fail_before_any_write(self):
        two = self.plan();two['slots'].append(dict(two['slots'][0]))
        bad = [two, self.plan(stage='draft'), self.plan(stage='verify'), self.plan(model=GEMMA),
               self.plan(output_tokens=1000), self.plan(attempt=2), self.plan(haiku_input=0),
               self.plan(haiku_input=1000000), {'slots': self.plan()['slots'], 'request_sha256': 'x'},
               {'slots': self.plan()['slots'], 'role_plan': {}}, {'slots': []}]
        for plan in bad:
            with self.subTest(plan=plan), self.assertRaises(ProviderFailure):
                self.admit.begin_turn('bad', plan=plan)
        with self.assertRaisesRegex(ProviderFailure, 'COST_RESERVATION_INVALID'):
            self.admit.begin_turn('cheap', plan=self.plan(maximum_nanodollars=1))
        self.assertFalse(self.client.documents)

    def test_wrong_role_model_or_envelope_never_gets_a_permit(self):
        self.admit.begin_turn('roles', plan=self.plan())
        with self.assertRaisesRegex(ProviderFailure, 'MODEL_ROLE_MISMATCH'):
            self.admit.for_model(HAIKU, role='private_draft')
        with self.assertRaisesRegex(ProviderFailure, 'MODEL_ROLE_MISMATCH'):
            self.admit.for_model(GEMMA, role='generation')
        with self.assertRaisesRegex(ProviderFailure, 'NATIVE_ENVELOPE_EXCEEDED'):
            self.admit.for_model(HAIKU, role='generation')(21801, 'generation')
        with self.assertRaisesRegex(ProviderFailure, 'MODEL_ROLE_MISMATCH'):
            self.admit(21800, 'generation')

    def test_same_operation_cannot_reserve_twice(self):
        self.admit.begin_turn('once', plan=self.plan());self.admit.end_turn()
        before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'ALREADY_RESERVED_NO_REPLAY'):
            self.admit.begin_turn('once', plan=self.plan())
        self.assertEqual(self.client.documents, before)

    def test_haiku_spend_limit_leaves_all_capacity_untouched(self):
        self.client.documents[CLAUDE_ALLOCATION] = {'version': CLAUDE_VERSION, 'model': HAIKU,
            'maximum_nanodollars': 1000000000, 'reserved_nanodollars': 999999999, 'reservation_count': 9}
        before = deepcopy(self.client.documents)
        with self.assertRaisesRegex(ProviderFailure, 'CLAUDE_SPEND_LIMIT'):
            self.admit.begin_turn('broke', plan=self.plan())
        self.assertEqual(self.client.documents, before)

    def test_historical_draft_verify_events_stay_charged_and_readable(self):
        events = [{'at': self.now - timedelta(seconds=30), 'tokens': 21800, 'kind': 'generation',
            'operation_id': 'old-pair', 'slot': 0, 'consumed': True, 'model': HAIKU, 'stage': 'draft',
            'input_tokens': 20000, 'output_tokens': 1800, 'attempt': 1},
            {'at': self.now + timedelta(seconds=31), 'tokens': 21800, 'kind': 'generation',
            'operation_id': 'old-pair', 'slot': 1, 'consumed': False, 'model': HAIKU, 'stage': 'verify',
            'input_tokens': 20000, 'output_tokens': 1800, 'attempt': 1, 'state': 'SEALED_UNUSED',
            'sealed_at': self.now - timedelta(seconds=1), 'sealed_version': SEALED_VERSIONS[1]}]
        self.client.documents['grounded-provider-global-v1'] = {'events': deepcopy(events)}
        self.admit.begin_turn('new', plan=self.plan())
        self.assertEqual(self.client.documents['grounded-provider-global-v1']['events'][:2], events)
        self.admit.for_model(HAIKU, role='generation')(21800, 'generation')
        # The consumed historical draft still paces the new call by the rolling minute.
        self.assertEqual(sum(self.waits), 31)

    def test_deadline_binds_the_single_generation_reservation(self):
        with operation_deadline(self.now + timedelta(seconds=30)):
            self.admit.begin_turn('deadline', plan=self.plan())
            self.now += timedelta(seconds=31)
            with self.assertRaisesRegex(ProviderFailure, 'DEADLINE_EXCEEDED'):
                self.admit.for_model(HAIKU, role='generation')(21800, 'generation')
        self.assertEqual(self.client.documents[ALLOCATION]['reserved_attempts'], 1)

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



if __name__ == '__main__':
    unittest.main()
