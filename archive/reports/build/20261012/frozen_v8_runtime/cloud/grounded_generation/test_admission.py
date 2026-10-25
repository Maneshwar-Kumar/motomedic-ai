"""Reservation accounting at mocked Firestore transaction boundary, not live IAM proof."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import threading
import types
import unittest
from unittest.mock import patch
from cloud.grounded_generation.admission import ProviderAdmission,ProviderFailure

class Client:
    def __init__(self):self.body={};self.lock=threading.RLock();self.fail=False
    def collection(self,name):assert name=='arm_a_usage';return self
    def document(self,name):assert name=='grounded-provider-global-v1';return self
    def transaction(self):return self
    def get(self,transaction=None):
        if self.fail:raise RuntimeError('store outage')
        return types.SimpleNamespace(exists=bool(self.body),to_dict=lambda:deepcopy(self.body))
    def set(self,ref,body):self.body=deepcopy(body)

def atomic(function):
    def run(tx):
        with tx.lock:return function(tx)
    return run

class Tests(unittest.TestCase):
    def setUp(self):
        self.client=Client();self.now=datetime(2026,10,11,tzinfo=timezone.utc)
        self.admit=ProviderAdmission(self.client,now=lambda:self.now)
        google=types.ModuleType('google');cloud=types.ModuleType('google.cloud')
        cloud.firestore=types.SimpleNamespace(transactional=atomic);google.cloud=cloud
        self.patch=patch.dict('sys.modules',{'google':google,'google.cloud':cloud});self.patch.start()
        self.addCleanup(self.patch.stop)
    def seed(self,events):self.client.body={'events':events}
    def event(self,kind='generation',tokens=9992,age=120):
        return {'at':self.now-timedelta(seconds=age),'tokens':tokens,'kind':kind}
    def test_each_attempt_and_cache_prefix_reserves_tokens_and_ttl(self):
        self.admit(9000,'generation');self.now+=timedelta(seconds=61);self.admit(8000,'prompt_cache')
        self.assertEqual(sum(e['tokens'] for e in self.client.body['events']),17000)
        self.assertEqual(self.client.body['expires_at'],self.now+timedelta(hours=24))
    def test_six_per_minute_then_reopens_without_resetting_day(self):
        for _ in range(6):self.admit(1000,'generation')
        with self.assertRaises(ProviderFailure):self.admit(9992,'generation')
        self.now+=timedelta(seconds=61);self.admit(9992,'generation')
        self.assertEqual(len(self.client.body['events']),7)
    def test_reserved_token_minute_includes_cache_and_reopens(self):
        self.admit(8000,'generation')
        with self.assertRaises(ProviderFailure):self.admit(3000,'prompt_cache')
        self.admit(2000,'prompt_cache')
        self.now+=timedelta(seconds=61);self.admit(9992,'generation')
        self.assertEqual(len(self.client.body['events']),3)
    def test_daily_generation_and_all_event_caps(self):
        self.seed([self.event(tokens=1) for _ in range(100)])
        with self.assertRaises(ProviderFailure):self.admit(1,'generation')
        self.seed([self.event(kind='prompt_cache',tokens=1) for _ in range(120)])
        with self.assertRaises(ProviderFailure):self.admit(1,'prompt_cache')
    def test_worst_case_tokens_include_cache_prefix(self):
        self.seed([self.event(kind='prompt_cache',tokens=8192) for _ in range(100)]+[self.event() for _ in range(18)])
        self.assertEqual(sum(e['tokens'] for e in self.client.body['events']),999056)
        with self.assertRaises(ProviderFailure):self.admit(9992,'generation')
        self.assertEqual(len(self.client.body['events']),118)
    def test_expired_reservations_drop_after_full_day(self):
        self.seed([self.event(age=86401) for _ in range(100)])
        self.admit(9992,'generation');self.assertEqual(len(self.client.body['events']),1)
    def test_invalid_bounds_and_store_outage_fail_closed(self):
        for tokens,kind in [(-1,'generation'),(9993,'generation'),(True,'generation'),(1,'unknown')]:
            with self.assertRaises(ProviderFailure):self.admit(tokens,kind)
        self.client.fail=True
        with self.assertRaisesRegex(ProviderFailure,'STORE_UNAVAILABLE'):self.admit(9992,'generation')
        self.assertFalse(self.client.body)
    def test_concurrent_transaction_reservations_do_not_overadmit(self):
        results=[]
        def call():
            try:self.admit(1000,'generation');results.append('accepted')
            except ProviderFailure:results.append('limited')
        workers=[threading.Thread(target=call) for _ in range(20)]
        for worker in workers:worker.start()
        for worker in workers:worker.join()
        self.assertEqual(results.count('accepted'),6);self.assertEqual(len(self.client.body['events']),6)

if __name__=='__main__':unittest.main()