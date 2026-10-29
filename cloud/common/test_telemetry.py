"""Telemetry keeps rider text out, correlates by trace and never fails a turn; no network or cloud."""
import json
import unittest

from cloud.common import telemetry as tm


class TelemetryTests(unittest.TestCase):
    def capture(self):
        lines = []
        return tm.Telemetry(sink=lines.append), lines

    def test_only_allowlisted_fields_with_token_values_are_written(self):
        telemetry, lines = self.capture()
        telemetry.emit('answer_turn', trace_id='a' * 32, span_id='b' * 16, route='SUPPORTED', chunk_ids=['chunk_1'],
                       stage_ms={'retrieval': 12.5}, query='brakes', reason_codes=['Where is the charger port?'],
                       citations=3)
        record = json.loads(lines[0])
        self.assertEqual(record['logging.googleapis.com/trace'], 'projects/%s/traces/%s' % (tm.PROJECT, 'a' * 32))
        self.assertEqual((record['severity'], record['message'], record['route'], record['citations']),
                         ('INFO', 'answer_turn', 'SUPPORTED', 3))
        self.assertEqual(record['redacted_fields'], ['query', 'reason_codes'])
        self.assertNotIn('brakes', lines[0])
        self.assertNotIn('charger port', lines[0])

    def test_trace_ids_come_only_from_well_formed_headers(self):
        trace = '4bf92f3577b34da6a3ce929d0e0e4736'
        self.assertEqual(tm.trace_from_headers({'traceparent': '00-%s-00f067aa0ba902b7-01' % trace}), trace)
        self.assertEqual(tm.trace_from_headers({'X-Cloud-Trace-Context': trace + '/123;o=1'}), trace)
        for junk in ({'traceparent': '00-' + '0' * 32 + '-00f067aa0ba902b7-01'}, {'traceparent': 'question text'},
                     {'X-Cloud-Trace-Context': 'not-a-trace'}, {}):
            with self.subTest(junk=junk):
                value = tm.trace_from_headers(junk)
                self.assertRegex(value, r'^[0-9a-f]{32}$')
                self.assertNotEqual(value, '0' * 32)

    def test_a_question_is_described_by_shape_and_an_optional_keyed_hash(self):
        shape = tm.question_shape('Where is the charger port?', key='')
        self.assertEqual(shape, {'question_chars': 26, 'question_words': 5})
        keyed = tm.question_shape('Where is the charger port?', key='secret')
        self.assertRegex(keyed['question_hmac'], r'^[0-9a-f]{32}$')
        self.assertNotEqual(keyed['question_hmac'], tm.question_shape('Where is the fuse box?', key='secret')['question_hmac'])

    def test_a_failing_sink_never_raises(self):
        def broken(_line):
            raise OSError('disk full')
        tm.Telemetry(sink=broken).emit('answer_turn', route='SUPPORTED')
        tm.Telemetry(sink=broken).span('retrieval', 'a' * 32, duration_ms=1.0)


class AnswerTurnTelemetryTests(unittest.TestCase):
    def test_a_turn_emits_hits_gate_outcome_and_spans_without_rider_or_manual_text(self):
        from pathlib import Path
        import tempfile
        from cloud.grounded_generation import section_assembly as sa, section_index as si, section_retrieval as sr
        from cloud.grounded_generation.section_questions import ManualSource, Questions
        from cloud.grounded_generation.test_section_answer import FakeGenerate, located
        from cloud.grounded_generation.test_section_fixture import CrossEncoder, Embedder, SOURCE_MANIFEST, build
        root = build(Path(tempfile.mkdtemp(prefix='motomedic-telemetry-')))
        identity = si.identity(root)
        lines = []
        questions = Questions(ManualSource(SOURCE_MANIFEST, identity), sa.SectionIndex(root),
                              sr.SectionRetriever(root, Embedder(), CrossEncoder()), FakeGenerate(located), identity,
                              telemetry=tm.Telemetry(sink=lines.append))
        trace = 'c' * 32
        _s, view, _c = questions.answer(questions.new_session(), 'Where is the charger port?', operation_id='a' * 32,
                                        trace_id=trace)
        records = [json.loads(line) for line in lines]
        turn = next(r for r in records if r['event'] == 'answer_turn')
        self.assertEqual((turn['route'], turn['operation_id'], turn['question_words']), ('SUPPORTED', 'a' * 32, 5))
        self.assertIn(64, turn['pages_sent'])
        self.assertTrue(turn['chunk_ids'] and turn['citations'] == 1)
        self.assertEqual(set(turn['stage_ms']), {'retrieval', 'assembly', 'generation', 'gate'})
        spans = [r for r in records if r['event'] == 'span']
        self.assertEqual([s['span_name'] for s in spans], ['retrieval', 'assembly', 'generation', 'gate', 'answer_turn'])
        self.assertTrue(all(r['logging.googleapis.com/trace'].endswith(trace) for r in records))
        self.assertEqual({s['parent_span_id'] for s in spans[:-1]}, {spans[-1]['logging.googleapis.com/spanId']})
        joined = '\n'.join(lines)
        for private in ('charger port', view['response']['natural_language'], 'handlebar'):
            self.assertNotIn(private.lower(), joined.lower())
        self.assertNotIn('redacted_fields', joined)

    def test_every_api_request_but_the_startup_probe_is_one_event(self):
        from cloud.arm_a.app import create_app
        source = type('S', (), {'checksum': 'm', 'index_id': 'i'})()
        lines = []
        app = create_app(source, telemetry=tm.Telemetry(sink=lines.append))
        client = app.test_client()
        client.get('/healthz')
        self.assertEqual(lines, [])
        response = client.get('/v1/health', headers={'traceparent': '00-%s-00f067aa0ba902b7-01' % ('d' * 32)})
        record = json.loads(lines[-1])
        self.assertEqual((record['event'], record['path'], record['http_status'], record['error_code']),
                         ('http_request', '/v1/health', response.status_code, 'AUTH_REQUIRED'))
        self.assertTrue(record['logging.googleapis.com/trace'].endswith('d' * 32))


if __name__ == '__main__':
    unittest.main()
