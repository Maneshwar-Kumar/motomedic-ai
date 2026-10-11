"""Real local HTTP checks and interval accounting; zero external provider calls."""
from copy import deepcopy
import time
import unittest
from unittest.mock import patch
from architecture_measurement import summarize, measured_sse_turn


class TimingContracts(unittest.TestCase):
    def row(self):
        return {'provider_attempts':[
            {'kind':'GENERATE_SHORT','call':1,'started_at_seconds':2.,'finished_at_seconds':4.,
             'admission_started_at_seconds':0.,'transport':{'provider_transport_started_at_seconds':2.1,'first_visible_token_seconds':.5}},
            {'kind':'VERIFY','call':2,'started_at_seconds':6.,'finished_at_seconds':8.,'admission_started_at_seconds':4.},
            {'kind':'VERIFY','call':3,'started_at_seconds':7.,'finished_at_seconds':9.,'admission_started_at_seconds':4.}],
            'controller_retrieval_assembly_seconds':.1,'first_stream_event_seconds':8.2,'complete_response_seconds':10.}

    def test_overlapping_waits_remove_only_idle_intervals(self):
        out=summarize(self.row())
        self.assertEqual(out['provider_pacing_wait_union_seconds'],5.)
        self.assertEqual(out['pacing_idle_only_seconds'],4.)
        self.assertEqual(out['provider_active_union_seconds'],5.)
        self.assertAlmostEqual(out['ttft_from_turn_start_seconds'],2.6)
        self.assertAlmostEqual(out['ttft_excluding_idle_pacing_seconds'],.6)
        self.assertAlmostEqual(out['ttfo_excluding_idle_pacing_seconds'],4.2)
        self.assertEqual(out['full_excluding_idle_pacing_seconds'],6.)

    def test_cache_hit_has_no_generation_ttft(self):
        row=self.row()
        row['provider_attempts']=row['provider_attempts'][1:]
        out=summarize(row)
        self.assertIsNone(out['generator_provider_ttft_seconds'])
        self.assertIsNone(out['ttft_from_turn_start_seconds'])

    def test_client_ttft_mapping_includes_producer_database_setup(self):
        def producer(stream):
            time.sleep(.02)  # Simulated pre-run SQLite setup.
            answer_started=time.perf_counter()
            row={'route':'SUPPORTED','server_request_setup_seconds':.001,
                'answer_turn_started_monotonic_seconds':answer_started,
                'complete_response_seconds':.02,'provider_attempts':[{'kind':'SELECT_COMPONENTS','call':1,
                'started_at_seconds':.002,'finished_at_seconds':.01,'admission_started_at_seconds':0.,
                'transport':{'provider_transport_started_at_seconds':.003,'first_visible_token_seconds':.004}}]}
            stream.finish(row)
            return row
        row=measured_sse_turn(producer)
        client=row['loopback_client_delivery']
        self.assertGreater(client['answer_turn_started_at_client_seconds']-client['engine_started_at_client_seconds'],.015)
        self.assertAlmostEqual(row['timing_measurement']['ttft_from_client_request_seconds'],
            client['answer_turn_started_at_client_seconds']+.007)

    def test_retry_and_unsent_admission_waits_preserved(self):
        row=self.row()
        row['provider_attempts'][0].update(retry_backoff_started_at_seconds=4.,retry_backoff_finished_at_seconds=5.)
        row['admission_failures']=[{'admission_started_at_seconds':9.,'admission_finished_at_seconds':10.}]
        self.assertEqual(summarize(row)['pacing_idle_only_seconds'],5.)

    def test_local_http_receives_ordered_verified_blocks_then_terminal(self):
        def producer(stream):
            started=time.perf_counter()
            for index in range(2):
                stream.deliver({'session_id':'test','session_version':1,'block':index,
                    'texts':['test fixture'],'citations':[{'id':'test'}],'content_sha256':'test','architecture':'C'})
                time.sleep(.02)
            row={'provider_attempts':[],'controller_retrieval_assembly_seconds':0.,
                 'server_request_setup_seconds':0.,'first_stream_event_seconds':.001,
                 'complete_response_seconds':time.perf_counter()-started,'route':'SUPPORTED'}
            stream.finish(row)
            return row
        row=measured_sse_turn(producer)
        client=row['loopback_client_delivery']
        self.assertEqual(client['received_verified_blocks'],2)
        self.assertEqual([e['event'] for e in client['events']],['verified_block','verified_block','complete'])
        self.assertLess(client['first_verified_output_seconds'],client['complete_response_seconds'])
        self.assertFalse(client['raw_content_logged'])
        self.assertNotIn('test fixture',str(client))

    def test_failed_http_turn_cannot_be_reported_as_completed_answer(self):
        def producer(stream):
            row={'route':'SYSTEM_ERROR','provider_attempts':[],'failed_attempt_seconds':.01,
                 'server_request_setup_seconds':0.,'complete_response_seconds':None}
            stream.finish(row)
            return row
        row=measured_sse_turn(producer)
        self.assertIsNone(row['loopback_client_delivery']['complete_response_seconds'])
        self.assertIsNone(row['loopback_client_delivery']['first_verified_output_seconds'])
        self.assertEqual(row['loopback_client_delivery']['terminal_event'],'error')

    def test_receiver_start_failure_is_retained_without_reexecuting_producer(self):
        calls=[]
        with patch('architecture_measurement.build_opener',side_effect=OSError('sensitive body')):
            row=measured_sse_turn(lambda stream:calls.append(True))
        self.assertEqual(calls,[])
        self.assertEqual(row['route'],'SYSTEM_ERROR')
        self.assertEqual(row['loopback_client_delivery']['terminal_event'],'receiver_error')
        self.assertIsNone(row['complete_response_seconds'])
        self.assertGreaterEqual(row['failed_attempt_seconds'],0)
        self.assertNotIn('sensitive body',str(row))

    def test_producer_exception_is_retained_without_raw_error(self):
        def broken(stream): raise RuntimeError('sensitive source')
        row=measured_sse_turn(broken)
        self.assertEqual(row['route'],'SYSTEM_ERROR')
        self.assertEqual(row['failure_class'],'RuntimeError')
        self.assertIsNone(row['loopback_client_delivery']['complete_response_seconds'])
        self.assertNotIn('sensitive source',str(row))

    def test_receiver_disconnect_retains_completed_engine_and_spent_attempt(self):
        from urllib.request import build_opener as real_opener
        class Interrupted:
            def __init__(self,response): self.response=response
            def __enter__(self): return self
            def __exit__(self,*args): self.response.close()
            def __iter__(self):
                for raw in self.response:
                    yield raw
                    if raw in (b'\n',b'\r\n'): raise OSError('private receiver detail')
        class Opener:
            def open(self,*args,**kwargs): return Interrupted(real_opener().open(*args,**kwargs))
        def producer(stream):
            stream.deliver({'session_id':'test','session_version':1,'block':0,'texts':['fixture'],
                'citations':[{'id':'test'}],'content_sha256':'test','architecture':'A'})
            row={'route':'SUPPORTED','provider_attempts':[{'kind':'SELECT_COMPONENTS','call':1,
                'started_at_seconds':0.,'finished_at_seconds':.001,'admission_started_at_seconds':0.}],
                'server_request_setup_seconds':0.,'complete_response_seconds':.01,'stream_event_count':1}
            stream.finish(row)
            return row
        with patch('architecture_measurement.build_opener',return_value=Opener()):
            row=measured_sse_turn(producer)
        self.assertEqual(row['route'],'SYSTEM_ERROR')
        self.assertEqual(row['engine_route_before_receiver_failure'],'SUPPORTED')
        self.assertEqual(row['engine_complete_response_seconds_before_receiver_failure'],.01)
        self.assertIsNone(row['complete_response_seconds'])
        self.assertEqual(len(row['provider_attempts']),1)
        self.assertEqual(row['loopback_client_delivery']['received_verified_blocks'],1)
        self.assertNotIn('private receiver detail',str(row))


if __name__=='__main__': unittest.main()
