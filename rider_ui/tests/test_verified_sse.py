import copy
import json
import unittest

from rider_ui.client import APIError
from rider_ui.tests.test_client import view
from rider_ui.verified_sse import read_verified_stream


def frame(event, data):
    return ('event: '+event+'\ndata: '+json.dumps(data, ensure_ascii=False)+'\n\n').encode()


class VerifiedStreamTests(unittest.TestCase):
    def test_whole_unit_only_under_single_byte_utf8_and_crlf_splits(self):
        v = view(); v['response']['natural_language'] = 'Synthetic warning — keep complete.'
        raw = (frame('verified_block', {'view': v})+frame('complete', v)).replace(b'\n', b'\r\n')
        released = []
        result = read_verified_stream((raw[i:i+1] for i in range(len(raw))), released.append)
        self.assertEqual(released, [v])
        self.assertEqual(result, v)

    def test_partial_warning_and_raw_tokens_never_publish(self):
        v = view()
        released = []
        raw = frame('verified_block', {'view': v})[:-2]
        with self.assertRaises(APIError):
            read_verified_stream([raw], released.append)
        self.assertFalse(released)
        for event in ('token', 'delta', 'selection'):
            with self.assertRaises(APIError):
                read_verified_stream([frame(event, {'text': 'unverified'})], released.append)
        self.assertFalse(released)

    def test_disconnect_after_verified_unit_requires_recovery(self):
        v = view(); released = []
        with self.assertRaises(APIError):
            read_verified_stream([frame('verified_block', {'view': v})], released.append)
        self.assertEqual(released, [v])

    def test_complete_must_match_saved_unit(self):
        v = view(); changed = copy.deepcopy(v); changed['version'] += 1
        with self.assertRaises(APIError):
            read_verified_stream([frame('verified_block', {'view': v}), frame('complete', changed)])
        with self.assertRaises(APIError):
            read_verified_stream([frame('complete', v)])

    def test_unverified_or_wrong_source_block_withheld(self):
        for mutation in ('gate', 'source', 'metadata'):
            v = view(); released = []
            if mutation == 'gate': v['response']['release_gate_passed'] = False
            elif mutation == 'source': v['manual_checksum'] = 'wrong'
            else: v['response']['cited_pages'][0]['excerpt'] = 'prohibited'
            with self.assertRaises(APIError):
                read_verified_stream([frame('verified_block', {'view': v})], released.append)
            self.assertFalse(released)

    def test_error_and_duplicate_events_fail_without_retry(self):
        v = view()
        with self.assertRaises(APIError):
            read_verified_stream([frame('error', {'code': 'STORE_ERROR'})])
        for last in (frame('verified_block', {'view': v}),
                     frame('complete', v)+frame('complete', v)):
            with self.assertRaises(APIError):
                read_verified_stream([frame('verified_block', {'view': v}), last])

    def test_nontechnical_and_stopped_complete_routes_preserved(self):
        for state in ('SUPPORTED', 'AMBIGUOUS', 'UNSUPPORTED', 'SYSTEM_ERROR', 'SAFETY_STOP'):
            v = view(); v['response']['type'] = state
            v['response']['technical_content'] = False
            v['response']['release_gate_passed'] = False
            v['response']['cited_pages'] = []
            self.assertEqual(read_verified_stream([frame('complete', v)])['response']['type'], state)

    def test_invalid_utf8_and_stream_bound_fail(self):
        for chunks in ([b'\xff'], [b'a'*(256*1024+1)], [b'']):
            with self.assertRaises(APIError):
                read_verified_stream(chunks)


if __name__ == '__main__':
    unittest.main()
