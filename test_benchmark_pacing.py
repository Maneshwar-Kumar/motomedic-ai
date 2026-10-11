"""Quota scheduling and finite retry contracts without external requests."""
import unittest
from unittest.mock import patch
from benchmark_pacing import Admission, AdmissionFailure
from architecture_benchmark import Allocation, STREAM_POLICY, WRITE_POLICY
from generation_providers import ProviderFailure, ProviderResult


class Clock:
    def __init__(self): self.now = 0.0
    def clock(self): return self.now
    def sleep(self, seconds): self.now += seconds


class Scheduling(unittest.TestCase):
    def test_shared_rpm_spacing_and_rolling_window(self):
        clock = Clock()
        admission = Admission(clock.clock, clock.sleep)
        records = [admission.admit('', {}, {}) for _ in range(8)]
        self.assertEqual(clock.now, 70)
        self.assertEqual(records[0]['admission_wait_seconds'], 0)
        self.assertEqual(records[1]['admission_wait_seconds'], 10)
        self.assertTrue(all(r['requests_in_rolling_minute'] <= 6 for r in records))

    def test_input_pressure_defers_even_when_request_slots_remain(self):
        clock = Clock()
        admission = Admission(clock.clock, clock.sleep)
        admission.admit('x' * 6000, {}, {})
        second = admission.admit('x' * 6000, {}, {})
        self.assertEqual(second['admission_wait_seconds'], 60)
        self.assertLessEqual(second['reserved_input_tokens_in_rolling_minute'], 12000)

    def test_oversized_input_fails_before_admission(self):
        clock = Clock()
        with self.assertRaises(AdmissionFailure):
            Admission(clock.clock, clock.sleep).admit('x' * 12000, {}, {})
        self.assertEqual(clock.now, 0)

    def test_admission_failure_is_reported_without_counting_provider_call(self):
        allocation = Allocation(paced=True)
        with self.assertRaises(AdmissionFailure):
            allocation.invoke(object(), 'x' * 12000, {}, {})
        self.assertEqual(allocation.calls, 0)
        self.assertEqual(allocation.admission_failures[0]['failure_reason'],
                         'INPUT_RESERVATION_EXCEEDS_EXPERIMENT_LIMIT')
        self.assertFalse(allocation.admission_failures[0]['external_request_sent'])

    def test_two_global_retries_leave_thirty_two_base_attempts(self):
        class Provider:
            last_telemetry = {'http_status': 500}
            def complete(self, *args): raise ProviderFailure('PROVIDER_SERVICE_ERROR')
        clock = Clock()
        allocation = Allocation(paced=True)
        allocation.admission = Admission(clock.clock, clock.sleep)
        with patch('architecture_benchmark.time.sleep', clock.sleep):
            for _ in range(32):
                with self.assertRaises(ProviderFailure):
                    allocation.invoke(Provider(), WRITE_POLICY, {}, {})
        self.assertEqual(allocation.calls, 34)
        self.assertEqual(allocation.retry_used, 2)
        self.assertEqual(sum(r['attempt_index'] == 1 for r in allocation.records), 2)
        self.assertTrue(all('admission_wait_seconds' in r for r in allocation.records))
        with self.assertRaises(ProviderFailure):
            allocation.invoke(Provider(), WRITE_POLICY, {}, {})
        self.assertEqual(allocation.calls, 34)

    def test_stream_or_protocol_failures_never_retry(self):
        class Provider:
            last_telemetry = {'http_status': 500}
            def complete(self, *args): raise ProviderFailure('PROVIDER_SERVICE_ERROR')
        class Malformed(Provider):
            def complete(self, *args): raise ProviderFailure('PROVIDER_REFUSAL_OR_MALFORMED')
        for policy, provider in ((STREAM_POLICY, Provider()), (WRITE_POLICY, Malformed())):
            clock = Clock()
            allocation = Allocation(paced=True)
            allocation.admission = Admission(clock.clock, clock.sleep)
            with self.assertRaises(ProviderFailure): allocation.invoke(provider, policy, {}, {})
            self.assertEqual(allocation.calls, 1)
            self.assertEqual(allocation.retry_used, 0)

    def test_success_after_failure_keeps_both_attempts(self):
        class Provider:
            last_telemetry = {'http_status': 500}
            calls = 0
            def complete(self, *args):
                self.calls += 1
                if self.calls == 1: raise ProviderFailure('PROVIDER_QUOTA_EXHAUSTED')
                return ProviderResult({'texts': ['redacted']}, 1, 1, telemetry={'http_status': 200})
        clock = Clock()
        allocation = Allocation(paced=True)
        allocation.admission = Admission(clock.clock, clock.sleep)
        with patch('architecture_benchmark.time.sleep', clock.sleep):
            allocation.invoke(Provider(), WRITE_POLICY, {}, {})
        self.assertEqual([r['transport']['http_status'] for r in allocation.records], [500, 200])
        self.assertGreater(allocation.records[1]['preceding_retry_backoff_seconds'], 0)
        self.assertNotIn('redacted', str(allocation.records))


if __name__ == '__main__': unittest.main()
