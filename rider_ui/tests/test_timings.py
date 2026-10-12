"""Provider-free presentation/transport timing checks, without altering answers."""
import copy
import json
import unittest
from unittest.mock import patch
from rider_ui.client import APIError, RiderAPI
from rider_ui.timings import timing_summary
from rider_ui.tests.test_client import Transport, view
from rider_ui.tests.test_progress_stream import accepted_frames
from rider_ui.verified_sse import response_hash


def measured_view():
    result = view()
    result['runtime_controls'] = {
        'source_admission': {'retrieval_assembly_seconds': 2.4,
            'retrieval_policy': {'rerank_attempts': 1, 'stages_seconds': {'reranking': 1.6}}},
        'composition': {'draft_calls': 2, 'verifier_calls': 2, 'attempts': [
            {'draft_seconds': 20, 'verification_seconds': 60,
             'draft_provider': {'provider_seconds': 3}, 'verification_provider': {'provider_seconds': 2}},
            {'draft_seconds': 61, 'verification_seconds': 62,
             'draft_provider': {'provider_seconds': 4}, 'verification_provider': {'provider_seconds': 5}}]}}
    return result


class TimingSummaryTests(unittest.TestCase):
    def test_actual_phases_include_correction_and_do_not_double_count_ranking(self):
        original = measured_view(); frozen = copy.deepcopy(original)
        rows = timing_summary(original)
        self.assertEqual(list(rows), ['retrieval', 'ranking', 'generation', 'verification', 'streaming'])
        self.assertEqual(rows['retrieval']['seconds'], 2.4)
        self.assertEqual(rows['ranking']['seconds'], 1.6)
        self.assertEqual(rows['generation']['seconds'], 81)
        self.assertEqual(rows['verification']['seconds'], 122)
        self.assertIn('do not add ranking again', rows['retrieval']['note'])
        self.assertIn('rate-limit waits', rows['verification']['note'])
        self.assertIn('Model HTTP calls: 7.00 s', rows['generation']['note'])
        self.assertEqual(original, frozen)

    def test_missing_skipped_and_zero_timings_remain_distinct(self):
        rows = timing_summary({})
        self.assertTrue(all(row['seconds'] is None and row['status'] == 'not_recorded' for row in rows.values()))
        current = measured_view(); current['runtime_controls']['source_admission']['retrieval_policy'] = {'rerank_attempts': 0}
        rows = timing_summary(current)
        self.assertEqual(rows['ranking']['status'], 'not_required')
        self.assertIsNone(rows['ranking']['seconds'])
        current['runtime_controls']['source_admission']['retrieval_assembly_seconds'] = 0
        self.assertEqual(timing_summary(current)['retrieval']['seconds'], 0)
        current['runtime_controls']['composition'] = {'draft_calls': 0, 'verifier_calls': 0}
        self.assertEqual(timing_summary(current)['verification']['status'], 'not_required')

    def test_partial_attempts_invalid_numbers_and_raw_fields_are_not_presented(self):
        for bad in (True, -1, float('nan'), float('inf'), '7', 10**400):
            current = measured_view()
            current['runtime_controls']['source_admission']['retrieval_assembly_seconds'] = bad
            current['runtime_controls']['composition']['attempts'][1]['draft_seconds'] = bad
            rows = timing_summary(current)
            self.assertIsNone(rows['retrieval']['seconds'])
            self.assertIsNone(rows['generation']['seconds'])
        current = measured_view()
        current['runtime_controls']['composition']['attempts'][1].pop('verification_seconds')
        current['runtime_controls']['private_body'] = 'PRIVATE SOURCE CONTENT'
        rows = timing_summary(current)
        self.assertEqual(rows['verification']['status'], 'not_recorded')
        self.assertNotIn('PRIVATE SOURCE CONTENT', json.dumps(rows))
        current = measured_view()
        current['runtime_controls']['composition']['draft_calls'] = 3
        self.assertIsNone(timing_summary(current)['generation']['seconds'])
        current = measured_view()
        for attempt in current['runtime_controls']['composition']['attempts']:
            attempt['draft_seconds'] = 1e308
        self.assertIsNone(timing_summary(current)['generation']['seconds'])

    def test_delivery_requires_matching_operation_and_preserves_recovery_missingness(self):
        current = measured_view(); current['delivery'] = {'operation_id': 'c'*32}
        delivery = {'origin': 'UI_CLIENT_MONOTONIC', 'operation_id': 'c'*32,
                    'transport': 'sse', 'stream_complete': True, 'streaming_seconds': .25}
        self.assertEqual(timing_summary(current, delivery)['streaming']['seconds'], .25)
        self.assertEqual(timing_summary(current)['streaming']['status'], 'not_recorded')
        delivery['operation_id'] = 'd'*32
        self.assertIsNone(timing_summary(current, delivery)['streaming']['seconds'])
        delivery.update(operation_id='c'*32, stream_complete=False, streaming_elapsed_seconds=.4)
        interrupted = timing_summary(current, delivery)['streaming']
        self.assertEqual(interrupted['status'], 'interrupted')
        self.assertEqual(interrupted['seconds'], .4)


class ClientTimingTests(unittest.TestCase):
    def stream_client(self, frames):
        api = RiderAPI('https://example.com', 'synthetic-token')
        transport = Transport(result=b''.join(frames)); original = transport.open
        def streaming(request, timeout):
            result = original(request, timeout)
            result.headers.replace_header('Content-Type', 'text/event-stream')
            return result
        transport.open = streaming; api.opener = transport
        return api

    def test_complete_delivery_clock_is_separate_from_wait_and_exact_saved_view(self):
        current = view(); frames = accepted_frames(current); frozen = copy.deepcopy(current)
        api = self.stream_client(frames); seen = []; parts = []
        with patch('rider_ui.client.time.monotonic', side_effect=[10, 22, 22.25]):
            result = api.start('Synthetic question', 'c'*32, on_verified=seen.append, on_chunk=parts.append)
        self.assertEqual(result, frozen)
        self.assertEqual(current, frozen)
        self.assertEqual(seen, [frozen])
        self.assertEqual(''.join(parts), current['response']['natural_language'])
        self.assertEqual(response_hash(result), response_hash(frozen))
        self.assertEqual(api.last_delivery_timing['waiting_for_verified_seconds'], 12)
        self.assertEqual(api.last_delivery_timing['streaming_seconds'], .25)
        self.assertEqual(api.last_delivery_timing['request_seconds'], 12.25)
        self.assertTrue(api.last_delivery_timing['stream_complete'])
        self.assertNotIn('last_delivery_timing', result)

    def test_interrupted_stream_retains_verified_view_without_completed_duration_or_retry(self):
        current = view(); frames = accepted_frames(current); api = self.stream_client(frames[:6]); seen = []
        with patch('rider_ui.client.time.monotonic', side_effect=[10, 22, 23]):
            with self.assertRaises(APIError):
                api.start('Synthetic question', 'c'*32, on_verified=seen.append)
        self.assertEqual(seen, [current])
        self.assertEqual(api.opener.calls, 1)
        self.assertIsNone(api.last_delivery_timing['streaming_seconds'])
        self.assertEqual(api.last_delivery_timing['streaming_elapsed_seconds'], 1)
        self.assertFalse(api.last_delivery_timing['stream_complete'])

    def test_json_recovery_clears_previous_stream_measurement(self):
        current = view(); api = self.stream_client(accepted_frames(current))
        with patch('rider_ui.client.time.monotonic', side_effect=[10, 22, 22.25]):
            api.start('Synthetic question', 'c'*32)
        api.opener = Transport(result=json.dumps(current).encode())
        with patch('rider_ui.client.time.monotonic', side_effect=[30, 30.1]):
            self.assertEqual(api.recover_operation('c'*32), current)
        self.assertEqual(api.last_delivery_timing['transport'], 'json')
        self.assertIsNone(api.last_delivery_timing['streaming_seconds'])
        self.assertIsNone(api.last_delivery_timing['waiting_for_verified_seconds'])


if __name__ == '__main__':
    unittest.main()
