"""UI-only engineering tests. These do not satisfy the hosted acceptance gate."""
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from rider_ui.tests.fixture_api import serve, requests, operations, sessions, Handler

class AppTests(unittest.TestCase):
    def test_disconnected_has_no_advice_input(self):
        with patch.dict(os.environ,{'MOTOMEDIC_RIDER_API_URL':'','MOTOMEDIC_RIDER_API_TOKEN':''}):
            at=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
            self.assertFalse(at.exception)
            self.assertTrue(at.chat_input[0].disabled)
            self.assertFalse(any('not connected' in x.value for x in at.info))
    def test_confirmation_feedback_and_no_duplicate_rerun(self):
        server=serve(0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        requests.clear();sessions.clear();operations.clear()
        env={'MOTOMEDIC_RIDER_API_URL':'http://127.0.0.1:'+str(server.server_port),
             'MOTOMEDIC_RIDER_API_TOKEN':'ui-test-only','MOTOMEDIC_UI_ENGINEERING_LOOPBACK':'1'}
        try:
            with patch.dict(os.environ,env):
                at=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
                self.assertFalse(at.exception)
                self.assertTrue(at.chat_input[0].disabled)
                at.checkbox[0].check().run()
                at.selectbox[0].select_index(0).run()
                self.assertFalse(at.chat_input[0].disabled)
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
    def test_failed_delivery_recovers_saved_operation_without_resending(self):
        server=serve(0)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        requests.clear();sessions.clear();operations.clear()
        env={'MOTOMEDIC_RIDER_API_URL':'http://127.0.0.1:'+str(server.server_port),
             'MOTOMEDIC_RIDER_API_TOKEN':'ui-test-only','MOTOMEDIC_UI_ENGINEERING_LOOPBACK':'1'}
        try:
            with patch.dict(os.environ,env):
                at=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'),default_timeout=15).run()
                at.checkbox[0].check().run()
                at.selectbox[0].select_index(0).run()
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

