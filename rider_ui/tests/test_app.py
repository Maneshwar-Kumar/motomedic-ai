"""UI-only engineering tests. These do not satisfy the hosted acceptance gate."""
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from rider_ui.tests.fixture_api import serve, requests, operations, sessions, Handler

class AppTests(unittest.TestCase):
    def test_preview_disables_input_without_checkbox_and_creates_no_operation(self):
        server=serve(0)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        requests.clear();sessions.clear();operations.clear()
        env={'MOTOMEDIC_RIDER_API_URL':'http://127.0.0.1:'+str(server.server_port),
            'MOTOMEDIC_RIDER_API_TOKEN':'ui-test-only','MOTOMEDIC_UI_ENGINEERING_LOOPBACK':'1',
            'MOTOMEDIC_RIDER_ANSWERS_ENABLED':'false'}
        try:
            with patch.dict(os.environ,env):
                at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
                self.assertFalse(at.exception)
                self.assertFalse(at.checkbox)
                self.assertTrue(at.chat_input[0].disabled)
                self.assertIn('Answering is paused while we finish checking the demo.',[item.value for item in at.info])
                # Force a widget return independently of the browser's disabled
                # control to exercise the server dispatch guard as well.
                import streamlit
                real_chat_input=streamlit.chat_input
                sent=[False]
                def forged(*args,**kwargs):
                    value=real_chat_input(*args,**kwargs)
                    if not sent[0]:
                        sent[0]=True
                        return 'Forged disabled-widget question'
                    return value
                with patch('streamlit.chat_input',side_effect=forged):at.run()
                self.assertFalse(at.exception)
                self.assertEqual(requests,[]);self.assertEqual(operations,{})
                self.assertIsNone(at.session_state['pending'])
        finally:
            server.shutdown();server.server_close()

    def show_saved_notice_fixture(self, *, state='SUPPORTED', composition=None, source_admission=None, reasons=None, verified=True):
        """Render only a saved synthetic view; no request or model call."""
        with patch.dict(os.environ, {'MOTOMEDIC_RIDER_API_URL': '', 'MOTOMEDIC_RIDER_API_TOKEN': ''}):
            at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
            response = {'type': state, 'natural_language': 'Exact synthetic saved answer.',
                'technical_content': False, 'cited_pages': [], 'reason_codes': reasons or [],
                'release_gate_passed': verified, 'semantic_verification_passed': verified}
            view = {'session_id': 'e' * 32, 'version': 1, 'response': response,
                'choices': [], 'history': [], 'runtime_controls': {'composition': composition or {},
                    'source_admission': source_admission or {}}}
            at.session_state['messages'] = [('rider', 'Synthetic question'), ('assistant', view)]
            at.session_state['view'] = view
            at.run()
            self.assertFalse(at.exception)
            return at, view

    def test_recorded_timings_are_separate_from_saved_answer_and_missing_stream_is_honest(self):
        # Scalar projection from the real private v14 Service Reminder receipt;
        # rendering this fixture performs no retrieval or provider request.
        at, view = self.show_saved_notice_fixture(
            source_admission={'retrieval_assembly_seconds': 2.3623035379998782,
                'retrieval_policy': {'rerank_attempts': 1, 'stages_seconds': {
                    'dense_query_embedding_and_qdrant_rpc': 0.5988896799999566,
                    'bm25_scoring': 0.0007435039999563742,
                    'reranking': 1.6348707170000125}}},
            composition={'draft_calls': 1, 'verifier_calls': 1,
                'attempts': [{'draft_seconds': 22.88393380399998,
                'verification_seconds': 60.75883190799982}]})
        self.assertIn('Timings · Retrieval: 2.36 s · Ranking: 1.63 s · '
            'Generation: 22.88 s · Verification: 60.76 s · Streaming: Not recorded',
            [item.value for item in at.caption])
        self.assertIn('Exact synthetic saved answer.', [item.value for item in at.text])
        self.assertEqual(at.session_state['view'], view)
        self.assertNotIn('delivery_timings', view)
        at.run()
        self.assertEqual(at.session_state['view'], view)

    def test_invalid_or_absent_timings_are_not_shown_as_zero_or_private_metadata(self):
        at, view = self.show_saved_notice_fixture(
            source_admission={'retrieval_assembly_seconds': float('nan'),
                'retrieval_policy': {'stages_seconds': {'reranking': -1}}},
            composition={'attempts': [{'draft_seconds': True,
                'verification_seconds': float('inf'), 'private_draft': 'NEVER DISPLAY THIS'}]})
        self.assertIn('Timings · Retrieval: Not recorded · Ranking: Not recorded · '
            'Generation: Not recorded · Verification: Not recorded · Streaming: Not recorded',
            [item.value for item in at.caption])
        self.assertNotIn('NEVER DISPLAY THIS', '\n'.join(item.value for item in at.caption))
        self.assertEqual(at.session_state['view'], view)

    def test_delivery_timing_is_detached_and_bound_to_the_saved_operation(self):
        at, view = self.show_saved_notice_fixture()
        view['delivery'] = {'operation_id': 'a' * 32}
        at.session_state['view'] = view
        at.session_state['messages'] = [('rider', 'Synthetic question'), ('assistant', view)]
        measured = {'operation_id': 'a' * 32, 'origin': 'UI_CLIENT_MONOTONIC',
                    'transport': 'sse', 'stream_complete': True, 'streaming_seconds': 0.041}
        at.session_state['delivery_timings'] = {1: measured}
        at.run()
        self.assertFalse(at.exception)
        self.assertTrue(any(item.value.endswith('Streaming: 0.04 s') for item in at.caption))
        self.assertEqual(at.session_state['view'], view)
        self.assertNotIn('streaming_seconds', view['delivery'])
        at.session_state['delivery_timings'] = {1: {**measured, 'operation_id': 'b' * 32}}
        at.run()
        self.assertTrue(any(item.value.endswith('Streaming: Not recorded') for item in at.caption))
        self.assertEqual(at.session_state['view'], view)

    def test_large_verified_context_notice_is_separate_and_reset_requires_user_action(self):
        at, view = self.show_saved_notice_fixture(composition={'start_new_conversation_required': True})
        self.assertEqual([item.value for item in at.info],
            ['This chat used a large amount of context. Start a new conversation before your next question.'])
        self.assertIn('Exact synthetic saved answer.', [item.value for item in at.text])
        self.assertEqual(at.session_state['view'], view)
        at.run()
        self.assertEqual(at.session_state['view'], view)
        next(button for button in at.button if button.label == 'Start a new conversation').click().run()
        self.assertFalse(at.exception)
        self.assertIsNone(at.session_state['view'])
        self.assertEqual(at.session_state['messages'], [])
        self.assertFalse(at.info)

    def test_only_proven_native_input_overflow_suggests_a_new_conversation(self):
        at, view = self.show_saved_notice_fixture(state='SYSTEM_ERROR', verified=False,
            reasons=['COMPLETE_CONTEXT_TOKEN_BOUND_NO_TRUNCATION'])
        self.assertEqual([item.value for item in at.info],
            ['This chat is too large to process. Start a new conversation for your next question.'])
        self.assertEqual(at.session_state['view'], view)
        self.assertIsNone(at.session_state['pending'])

    def test_quota_budget_outage_and_output_bound_errors_do_not_suggest_a_new_chat(self):
        for code in ('PROVIDER_HTTP_429', 'PROVIDER_WHOLE_TURN_ALLOCATION_LIMIT',
                     'CLAUDE_SPEND_LIMIT', 'PROVIDER_ADMISSION_STORE_UNAVAILABLE',
                     'FINAL_PRESENTATION_TOKEN_BOUND_NO_TRUNCATION'):
            with self.subTest(code=code):
                at, _ = self.show_saved_notice_fixture(state='SYSTEM_ERROR', verified=False,
                    reasons=[code], composition={'start_new_conversation_required': True})
                self.assertFalse(at.info)

    def test_post_answer_notice_requires_true_server_flag_and_verified_release(self):
        for composition, verified in (({}, True),
                ({'start_new_conversation_required': 'true'}, True),
                ({'start_new_conversation_required': 1}, True),
                ({'start_new_conversation_required': True}, False)):
            with self.subTest(composition=composition, verified=verified):
                at, _ = self.show_saved_notice_fixture(composition=composition, verified=verified)
                self.assertFalse(at.info)

    def test_disconnected_has_no_advice_input(self):
        with patch.dict(os.environ,{'MOTOMEDIC_RIDER_API_URL':'','MOTOMEDIC_RIDER_API_TOKEN':''}):
            at=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
            self.assertFalse(at.exception)
            self.assertTrue(at.chat_input[0].disabled)
            self.assertFalse(any('not connected' in x.value for x in at.info))
    def test_immediate_question_feedback_and_no_duplicate_rerun(self):
        server=serve(0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        requests.clear();sessions.clear();operations.clear()
        env={'MOTOMEDIC_RIDER_API_URL':'http://127.0.0.1:'+str(server.server_port),
             'MOTOMEDIC_RIDER_API_TOKEN':'ui-test-only','MOTOMEDIC_UI_ENGINEERING_LOOPBACK':'1'}
        try:
            with patch.dict(os.environ,env):
                at=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
                self.assertFalse(at.exception)
                self.assertFalse(at.checkbox)
                self.assertFalse(at.chat_input[0].disabled)
                self.assertEqual(at.selectbox[0].value,'Royal Enfield Himalayan 450')
                self.assertTrue(at.selectbox[0].disabled)
                self.assertIn('RAM00818/A · 4 November 2025',[item.value for item in at.caption])
                at.chat_input[0].set_value('Engineering test only').run()
                self.assertFalse(at.exception)
                self.assertTrue(any(x.label=='Yes' for x in at.button))
                next(x for x in at.button if x.label=='Yes').click().run()
                self.assertFalse(at.exception)
                self.assertTrue(any(x.label=='Tried, not fixed' for x in at.button))
                next(x for x in at.button if x.label=='Tried, not fixed').click().run()
                self.assertFalse(at.exception)
                self.assertEqual(at.session_state['view']['response']['type'],'UNSUPPORTED')
                self.assertIn('ACTION_COMPLETED_UNRESOLVED',at.session_state['view']['history'][0]['label'])
                count=len(requests);at.run();self.assertEqual(len(requests),count)
                self.assertEqual(count,3)
        finally:
            server.shutdown();server.server_close()
    def test_reset_detaches_chat_and_diagnostic_context(self):
        server=serve(0)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        env={'MOTOMEDIC_RIDER_API_URL':'http://127.0.0.1:'+str(server.server_port),
             'MOTOMEDIC_RIDER_API_TOKEN':'ui-test-only','MOTOMEDIC_UI_ENGINEERING_LOOPBACK':'1'}
        try:
            with patch.dict(os.environ,env):
                at=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'),default_timeout=15).run()
                at.chat_input[0].set_value('Engineering reset test').run()
                old_id=at.session_state['view']['session_id']
                next(x for x in at.button if x.label=='Start a new conversation').click().run()
                self.assertFalse(at.exception)
                self.assertIsNone(at.session_state['view'])
                self.assertEqual(at.session_state['messages'],[])
                self.assertIsNone(at.session_state['pending'])
                self.assertIsNone(at.session_state['connection_error'])
                self.assertEqual(at.session_state['delivery_timings'], {})
                self.assertIn(old_id,sessions)
                self.assertFalse(at.checkbox)
                self.assertFalse(at.chat_input[0].disabled)
        finally:
            server.shutdown();server.server_close()

    def test_chat_input_remains_available_for_arbitrary_followup_questions(self):
        server=serve(0)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        requests.clear();sessions.clear();operations.clear()
        env={'MOTOMEDIC_RIDER_API_URL':'http://127.0.0.1:'+str(server.server_port),
             'MOTOMEDIC_RIDER_API_TOKEN':'ui-test-only','MOTOMEDIC_UI_ENGINEERING_LOOPBACK':'1'}
        try:
            with patch.dict(os.environ,env):
                at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
                at.chat_input[0].set_value('First engineering question').run()
                self.assertFalse(at.exception)
                self.assertFalse(at.chat_input[0].disabled)
                sid=at.session_state['view']['session_id']
                at.chat_input[0].set_value('Another unrelated engineering question').run()
                self.assertFalse(at.exception)
                self.assertEqual(requests[-1]['path'],'/v1/sessions/'+sid+'/questions')
                self.assertEqual(requests[-1]['payload']['query'],'Another unrelated engineering question')
                self.assertNotIn('intent_mode',requests[-1]['payload'])
        finally:
            server.shutdown();server.server_close()

    def test_failed_delivery_recovers_saved_operation_without_resending(self):
        server=serve(0)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        requests.clear();sessions.clear();operations.clear()
        env={'MOTOMEDIC_RIDER_API_URL':'http://127.0.0.1:'+str(server.server_port),
             'MOTOMEDIC_RIDER_API_TOKEN':'ui-test-only','MOTOMEDIC_UI_ENGINEERING_LOOPBACK':'1'}
        try:
            with patch.dict(os.environ,env):
                at=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'),default_timeout=15).run()
                Handler.fail_next_response=True
                at.chat_input[0].set_value('Engineering timeout recovery').run()
                self.assertFalse(at.exception)
                self.assertIsNotNone(at.session_state['pending'])
                self.assertTrue(at.chat_input[0].disabled)
                self.assertTrue(next(x for x in at.button if x.label=='Start a new conversation').disabled)
                next(x for x in at.button if x.label=='Reconnect and retrieve result').click().run()
                self.assertFalse(at.exception)
                self.assertIsNone(at.session_state['pending'])
                self.assertEqual(at.session_state['view']['response']['type'],'AMBIGUOUS')
                self.assertEqual(len(requests),1)
        finally:
            Handler.fail_next_response=False
            server.shutdown();server.server_close()

if __name__=='__main__': unittest.main()

