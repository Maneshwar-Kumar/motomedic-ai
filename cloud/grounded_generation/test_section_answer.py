"""Provider-free checks of the answer path on a synthetic section index.

Index regrouping, top-5 retrieval and conditional reranking, plain-text assembly, the answer
schema, the deterministic gate, the single Haiku call (fake transport and ledger) and the
questions pipeline. No model, network, cloud store or manual content is used.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from cloud.common import ProviderFailure
from cloud.grounded_generation import haiku_answer as ha
from cloud.grounded_generation import section_assembly as sa
from cloud.grounded_generation import section_index as si
from cloud.grounded_generation import section_retrieval as sr
from cloud.grounded_generation import template_answer as ta
from cloud.grounded_generation.section_questions import ManualSource, Questions, SYSTEM_ERROR_TEXT
from cloud.grounded_generation.delivery import bind_view
from cloud.grounded_generation.test_section_fixture import (CrossEncoder, Embedder, SOURCE_MANIFEST, build)

SUPPORT = 'mailto:support@royalenfield.com'
RUNNING_IN = 'At 300 km, does this manual allow full throttle?'


def fixture():
    root = Path(tempfile.mkdtemp(prefix='motomedic-section-fixture-'))
    return build(root)


def raw_chunk(cid, heading, page, text='Line.'):
    return {'id': cid, 'section_path': [heading], 'evidence_ids': ['ev_' + cid], 'citations': [{'pdf_page': page}],
            'source_sha256': 'f' * 64, 'retrieval_window': False, 'requires_full_source_context': False,
            'index_text': heading + '\n' + text, 'text': text}


class IndexTests(unittest.TestCase):
    def test_boxes_join_the_section_they_follow_and_running_headers_continue(self):
        chunks = [raw_chunk('c1', 'CHARGER PORT', 64), raw_chunk('c2', 'WARNING', 64, 'Not in rain.'),
                  raw_chunk('c3', 'NOTE', 64), raw_chunk('c4', 'INSTRUMENT CLUSTER', 49),
                  raw_chunk('c5', 'SETTINGS', 50), raw_chunk('c6', 'INSTRUMENT CLUSTER', 51),
                  raw_chunk('c7', 'SERVICE', 52)]
        out, sections, stats = si.regroup(chunks, {'INSTRUMENT CLUSTER': [49, 51, 53]})
        self.assertEqual([(s['heading'], s['chunk_ids']) for s in sections],
                         [('CHARGER PORT', ['c1', 'c2', 'c3']), ('INSTRUMENT CLUSTER', ['c4']),
                          ('SETTINGS', ['c5', 'c6']), ('SERVICE', ['c7'])])
        self.assertEqual(sections[0]['box_of'], {'ev_c1': None, 'ev_c2': 'WARNING', 'ev_c3': 'NOTE'})
        self.assertEqual(out[1]['index_text'], 'CHARGER PORT\nWARNING\nNot in rain.')
        self.assertEqual(out[5]['section_heading'], 'SETTINGS')
        self.assertEqual((stats['box_chunks'], stats['box_chunks_attached'], stats['page_break_continuations']), (2, 2, 1))

    def test_running_headers_are_repeated_top_band_section_headers_only(self):
        def item(text, page, top):
            return {'label': 'section_header', 'text': text,
                    'prov': [{'page_no': page, 'bbox': {'t': top, 'coord_origin': 'TOPLEFT'}}]}
        doc = {'pages': {str(p): {'size': {'height': 800}} for p in (1, 2, 3)},
               'texts': [item('INSTRUMENT CLUSTER', p, 20) for p in (1, 2, 3)] + [item('WARNING', p, 20) for p in (1, 2, 3)]
               + [item('MIXED', 1, 20), item('MIXED', 2, 20), item('MIXED', 3, 500), item('SETTINGS', 2, 400)]}
        self.assertEqual(si.running_headers(doc), {'INSTRUMENT CLUSTER': [1, 2, 3]})

    def test_a_split_off_subsection_inherits_its_parents_warnings_only(self):
        def section(sid, heading, pages, boxes):
            return {'id': sid, 'heading': heading, 'pdf_pages': pages, 'evidence_ids': list(boxes), 'box_of': dict(boxes)}
        sections = [section('a', 'ACCESSORIES AND LUGGAGE', [14, 15], {'w1': 'WARNING', 't1': None}),
                    section('b', 'LUGGAGE CATEGORIES', [15], {'t2': None}),
                    section('c', 'CLUTCH CABLE FREE PLAY', [101, 102], {'w2': 'CAUTION'}),
                    section('d', 'DRIVE CHAIN TENSION (FREE PLAY)', [102], {'t3': None}),
                    section('e', 'FUEL TANK CAP', [27], {'w3': 'WARNING'}),
                    section('f', 'FUEL FILLING LEVEL', [30], {'t4': None})]
        self.assertEqual(si.link_related_warnings(sections), 1)
        self.assertEqual((sections[1]['related_warnings'], sections[1]['related_section']), (['w1'], 'a'))
        # "drive" is not in the clutch heading; page 30 is too far from page 27.
        self.assertEqual([s['related_warnings'] for s in sections[2:]], [[], [], [], []])

    def test_serving_verifies_the_pinned_identity_and_every_file(self):
        root = fixture()
        expected = si.identity(root)
        self.assertEqual(si.verify(root, expected), expected)
        with self.assertRaisesRegex(ValueError, 'IDENTITY_MISMATCH'):
            si.verify(root, dict(expected, chunks=7))
        (root / 'bm25.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'SECTION_INDEX_FILE_CHANGED:bm25.json'):
            si.verify(root, expected)
        (root / 'manifest.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'MANIFEST_CHANGED'):
            si.verify(root, expected)


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.root = fixture()
        self.cross = CrossEncoder({'CHARGER PORT': 2.0, 'RUNNING IN': 1.0})

    def retriever(self, forced=None, cross=None):
        return sr.SectionRetriever(self.root, Embedder(forced), cross or self.cross)

    def test_only_the_fused_top_five_are_kept(self):
        found = self.retriever().search('Where is the charger port?')
        self.assertEqual(len(found['chunk_ids']), sr.TOP_K)
        self.assertEqual(len(set(found['chunk_ids'])), sr.TOP_K)

    def test_agreeing_top_sections_are_scored_for_relevance_but_not_reordered(self):
        found = self.retriever().search('compression ratio')
        self.assertFalse(found['sections_disagree'])
        self.assertFalse(found['reranked'])
        self.assertEqual(len(self.cross.calls), 1)
        self.assertEqual(found['chunk_ids'][0], 'chunk_synthetic_2_0')
        self.assertEqual((found['max_cross_score'], found['below_relevance_floor']), (2.0, False))

    def test_best_score_below_the_floor_marks_the_turn_as_nothing_found(self):
        headings = ('RUNNING IN', 'CHARGER PORT', 'SPECIFICATIONS', 'FUEL TANK CAP', 'FUEL FILLING LEVEL')
        found = self.retriever(cross=CrossEncoder({h: sr.RELEVANCE_FLOOR - 1 for h in headings})).search('Bluetooth pairing')
        self.assertTrue(found['below_relevance_floor'])
        edge = CrossEncoder({h: sr.RELEVANCE_FLOOR for h in headings})
        self.assertFalse(self.retriever(cross=edge).search('Bluetooth pairing')['below_relevance_floor'])

    def test_disagreement_reorders_the_same_five_chunks(self):
        query = 'charger port'
        plain = self.retriever(forced={query: [1, 0, 0, 0]}, cross=CrossEncoder({'RUNNING IN': 0.0})).search(query)
        found = self.retriever(forced={query: [1, 0, 0, 0]}).search(query)
        self.assertTrue(found['sections_disagree'])
        self.assertTrue(found['reranked'])
        self.assertEqual(len(self.cross.calls), 1)
        self.assertEqual(set(found['chunk_ids']), set(plain['chunk_ids']))
        self.assertTrue(found['chunk_ids'][0].startswith('chunk_synthetic_1_'))

    def test_long_query_skips_rerank_without_failing(self):
        cross = CrossEncoder()
        cross.tokenizer = type('T', (), {'encode': lambda self, q, add_special_tokens=False: [0] * 200})()
        query = 'charger port'
        found = self.retriever(forced={query: [1, 0, 0, 0]}, cross=cross).search(query)
        self.assertEqual((found['reranked'], found['rerank_skip_reason']), (False, 'QUERY_EXCEEDS_RERANK_LIMIT'))
        self.assertEqual(cross.calls, [])

    def test_follow_up_keeps_the_prior_rider_topic(self):
        history = [{'question': 'Where is the charger port?', 'response': 'On the handlebar.'}]
        self.assertIn('Where is the charger port?', sr.retrieval_query('Can I use it in rain?', history))
        self.assertEqual(sr.retrieval_query('Different question: what is the bore?', history),
                         'Different question: what is the bore?')

    def test_hosted_dense_response_is_bound_to_index_source_and_known_chunks(self):
        ids = ['a', 'b']
        sent = []
        def send(response):
            def call(path, payload, headers):
                sent.append((path, payload, headers))
                return response
            return call
        good = {'index_id': 'idx', 'candidate_evidence_only': True, 'result': {'points': [
            {'payload': {'chunk_id': 'a', 'source_sha256': 'm'}, 'score': 0.2},
            {'payload': {'chunk_id': 'b', 'source_sha256': 'm'}, 'score': 0.9}]}}
        dense = sr.QdrantDense('https://qdrant.example', 'idx', 'm', ids, send=send(good), token=lambda: 'tok')
        self.assertEqual(dense.top([0.1, 0.2], 2), [(1, 0.9), (0, 0.2)])
        self.assertEqual(sent[0][1], {'vector': [0.1, 0.2], 'limit': 2, 'source_sha256': 'm', 'index_id': 'idx'})
        self.assertEqual(sent[0][2]['Authorization'], 'Bearer tok')
        bad = [dict(good, index_id='other'), dict(good, candidate_evidence_only=False),
               {**good, 'result': {'points': [{'payload': {'chunk_id': 'zzz', 'source_sha256': 'm'}, 'score': 1}]}},
               {**good, 'result': {'points': [{'payload': {'chunk_id': 'a', 'source_sha256': 'x'}, 'score': 1}]}},
               {**good, 'result': {'points': good['result']['points'] * 2}}]
        for response in bad:
            with self.subTest(response=response), self.assertRaises(sr.RetrievalError):
                sr.QdrantDense('https://qdrant.example', 'idx', 'm', ids, send=send(response), token=lambda: 'tok').top([0.1], 2)
        with self.assertRaisesRegex(sr.RetrievalError, 'IDENTITY_UNAVAILABLE'):
            sr.QdrantDense('https://qdrant.example', 'idx', 'm', ids, send=send(good), token=lambda: 'a\nb').top([0.1], 2)
        with self.assertRaisesRegex(sr.RetrievalError, 'HTTPS_REQUIRED'):
            sr.QdrantDense('http://qdrant.example', 'idx', 'm', ids)


class AssemblyAndGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = sa.SectionIndex(fixture())

    def sent(self, *chunk_ids):
        return sa.assemble(self.index, list(chunk_ids))

    def label(self, assembled, phrase):
        return next(label for label, obj in assembled['objects'].items() if phrase in obj['text'])

    def draft(self, label, text, assembled, **overrides):
        value = {'route': 'SUPPORTED', 'coverage': 'COMPLETE', 'answer': [{'text': text, 'evidence_ids': [label]}],
                 'watchout_review': [{'display_id': w, 'decision': 'NOT_APPLICABLE', 'reason': 'not asked'}
                                     for w in assembled['warnings']]}
        value.update(overrides)
        return value

    def rejected(self, draft, assembled, question=RUNNING_IN):
        with self.assertRaises(ta.ReleaseRejected) as ctx:
            ta.gate(draft, assembled, question, SUPPORT)
        return ctx.exception.code

    def test_whole_section_is_sent_with_its_boxes_and_only_warnings_to_decide(self):
        assembled = self.sent('chunk_synthetic_1_0')
        self.assertEqual(len(assembled['sections']), 1)
        self.assertEqual(len(assembled['objects']), 3)
        self.assertIn('(WARNING) Do not use the charger port in rain', assembled['text'])
        self.assertIn('(NOTE) Close the charger port cap', assembled['text'])
        self.assertEqual(assembled['warnings'], [self.label(assembled, 'in rain')])
        self.assertTrue(assembled['text'].startswith('## CHARGER PORT (page 64)'))

    def test_related_warnings_follow_the_subsection_and_are_listed_for_a_decision(self):
        assembled = self.sent('chunk_synthetic_4_0')
        self.assertIn('(WARNING, from FUEL TANK CAP) Do not overfill the fuel tank.', assembled['text'])
        label = self.label(assembled, 'overfill')
        self.assertEqual(assembled['warnings'], [label])
        self.assertEqual(assembled['objects'][label]['section'], 'FUEL TANK CAP')
        both = self.sent('chunk_synthetic_3_0', 'chunk_synthetic_4_0')
        self.assertEqual(sum('overfill' in o['text'] for o in both['objects'].values()), 1)
        self.assertNotIn('from FUEL TANK CAP', both['text'])

    def test_sections_are_deduplicated_in_retrieval_order_and_tables_are_rows(self):
        assembled = self.sent('chunk_synthetic_2_0', 'chunk_synthetic_0_1', 'chunk_synthetic_0_0')
        self.assertEqual(len(assembled['sections']), 2)
        self.assertIn('Item: Compression ratio; Value: 11.5:1', assembled['text'])
        self.assertLess(assembled['text'].index('SPECIFICATIONS'), assembled['text'].index('RUNNING IN'))

    def test_model_input_is_plain_text_without_ids_hashes_or_json(self):
        assembled = self.sent('chunk_synthetic_1_0')
        text = sa.model_input('Where is the charger port?', assembled, ['Rider: earlier question'])
        for marker in ('evidence_', 'sha256', 'section_synthetic', '{"', 'review'):
            self.assertNotIn(marker, text)
        self.assertIn('WARNINGS TO DECIDE: ' + assembled['warnings'][0], text)
        self.assertIn('EARLIER CONVERSATION: - Rider: earlier question', text)

    def test_schema_limits_citations_to_sent_labels_and_requires_review_only_with_warnings(self):
        assembled = self.sent('chunk_synthetic_1_0')
        schema = ta.answer_schema(assembled)
        self.assertEqual(schema['required'], ['route', 'coverage', 'watchout_review'])
        cite = schema['properties']['answer']['items']['properties']['evidence_ids']['items']['enum']
        self.assertEqual(cite, ['E1', 'E2', 'E3'])
        self.assertEqual(schema['properties']['watchout_review']['items']['properties']['display_id']['enum'],
                         assembled['warnings'])
        quiet = ta.answer_schema(self.sent('chunk_synthetic_0_0'))
        self.assertNotIn('watchout_review', quiet['properties'])
        def walk(node):
            if isinstance(node, dict):
                if node.get('type') == 'object':
                    self.assertIs(node['additionalProperties'], False)
                self.assertFalse({'minItems', 'maxItems', 'minLength', 'maxLength'} & set(node))
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(schema)

    def test_numbers_must_come_from_the_cited_line_or_the_question(self):
        assembled = self.sent('chunk_synthetic_0_0')
        label = self.label(assembled, 'first 500 km')
        ok = self.draft(label, 'No. At 300 km you are in the first 500 km: stay below 6000 rpm, no full throttle.', assembled)
        self.assertEqual(ta.gate(ok, assembled, RUNNING_IN)['route'], 'SUPPORTED')
        self.assertEqual(self.rejected(self.draft(label, 'Keep below 9000 rpm.', assembled), assembled),
                         'NUMBER_NOT_IN_CITED_OBJECT_OR_QUESTION')

    def test_citations_must_be_sent_labels(self):
        assembled = self.sent('chunk_synthetic_0_0')
        label = self.label(assembled, 'first 500 km')
        for ids, code in (([], 'UNCITED_TECHNICAL_ITEM'), (['E999'], 'CITATION_NOT_SENT')):
            draft = self.draft(label, 'No full throttle.', assembled,
                               answer=[{'text': 'No full throttle.', 'evidence_ids': ids}])
            self.assertEqual(self.rejected(draft, assembled), code)
        released = ta.gate(self.draft(label, 'No full throttle.', assembled), assembled, RUNNING_IN)
        self.assertEqual(released['citations'], [{'label': label, 'evidence_id': 'evidence_synthetic_0_0', 'pages': [40]}])

    def test_every_sent_warning_needs_a_decision(self):
        assembled = self.sent('chunk_synthetic_1_0')
        label, warning = self.label(assembled, 'located'), assembled['warnings'][0]
        q = 'Where is the charger port?'
        draft = self.draft(label, 'It is on the centre of the handlebar.', assembled)
        self.assertTrue(ta.gate(draft, assembled, q)['text'])
        self.assertEqual(self.rejected(dict(draft, watchout_review=[]), assembled, q), 'WATCHOUT_NOT_CONSIDERED')
        included = dict(draft, watchout_review=[{'display_id': warning, 'decision': 'INCLUDED', 'reason': ''}])
        self.assertEqual(self.rejected(included, assembled, q), 'INCLUDED_WATCHOUT_MISSING')
        included['watchouts'] = [{'text': 'Do not use it in the rain.', 'evidence_ids': [warning]}]
        self.assertIn('Watch out: Do not use it in the rain.', ta.gate(included, assembled, q)['text'])
        blank = dict(draft, watchout_review=[{'display_id': warning, 'decision': 'NOT_APPLICABLE', 'reason': ' '}])
        self.assertEqual(self.rejected(blank, assembled, q), 'EXCLUSION_WITHOUT_REASON')

    def test_unsupported_shows_cited_facts_then_the_fixed_fallback(self):
        assembled = self.sent('chunk_synthetic_2_0')
        label = self.label(assembled, 'Compression ratio')
        q = 'What compression pressure should a test show?'
        draft = self.draft(label, 'The manual lists a compression ratio of 11.5:1, which is not a test pressure.', assembled,
                           route='UNSUPPORTED', coverage='NONE', disclaimers=[{'text': 'No test pressure is given.'}])
        released = ta.gate(draft, assembled, q, SUPPORT)
        self.assertTrue(released['text'].endswith(ta.FALLBACK_TEXT))
        self.assertEqual((released['escalation_uri'], released['suppressed_disclaimers']), (SUPPORT, 1))
        nothing = ta.no_evidence_release(SUPPORT)
        self.assertEqual((nothing['text'], nothing['provider_calls'], nothing['route']), (ta.FALLBACK_TEXT, 0, 'UNSUPPORTED'))

    def test_repeated_sentences_are_left_out_but_extensions_and_list_items_stay(self):
        assembled = self.sent('chunk_synthetic_1_0')
        label, warning = self.label(assembled, 'located'), assembled['warnings'][0]
        draft = self.draft(label, 'The charger port is on the centre of the handlebar.', assembled,
            policy=[{'text': 'The manual says the charger port is located on the centre of the handlebar.',
                     'evidence_ids': [label]}],
            watchouts=[{'text': 'Do not use the charger port in rain, to avoid damaging the phone and the charger.',
                        'evidence_ids': [warning]}],
            watchout_review=[{'display_id': warning, 'decision': 'INCLUDED', 'reason': 'rain'}])
        released = ta.gate(draft, assembled, 'Where is the charger port?')
        self.assertEqual(released['suppressed_duplicates'], 1)
        self.assertNotIn('The manual says the charger port is located', released['text'])
        self.assertIn('Watch out: Do not use the charger port in rain', released['text'])
        self.assertEqual({c['label'] for c in released['citations']}, {label, warning})
        self.assertFalse(ta.near_duplicate('ECO + Rear ABS OFF.', ['Performance + Rear ABS OFF.']))
        # Answer steps that share their words but reverse the order are both shown.
        steps = ['When removing the battery, disconnect the black negative terminal first, then the red positive terminal.',
                 'When refitting the battery, connect the red positive terminal first, then the black negative terminal.']
        ordered = self.draft(label, steps[0], assembled, answer=[{'text': s, 'evidence_ids': [label]} for s in steps])
        released = ta.gate(ordered, assembled, 'Which battery terminal goes first?')
        self.assertEqual((released['text'].count('battery'), released['suppressed_duplicates']), (2, 0))
        self.assertFalse(ta.near_duplicate('Do not switch the ignition OFF while riding; it can cause an accident and serious injury.',
                                           ['Do not switch the ignition OFF while riding.']))

    def test_meta_phrases_are_rewritten_and_leaked_labels_fail_closed(self):
        assembled = self.sent('chunk_synthetic_1_0')
        label = self.label(assembled, 'located')
        partial = self.draft(label, 'The charger port is on the centre of the handlebar.', assembled, coverage='PARTIAL',
                             disclaimers=[{'text': 'The supplied sections do not give a power rating.'}])
        released = ta.gate(partial, assembled, 'Where is the charger port and how strong is it?')
        self.assertIn('The parts of the manual I checked do not give a power rating.', released['text'])
        self.assertEqual(released['rewritten_phrases'], ['The supplied sections'])
        self.assertEqual(ta.rider_wording('It is not given in the sections shown.')[0],
                         'It is not given in the parts of the manual I checked.')
        for leak in (f'See [{label}].', 'This comes from line E2 of the manual.', 'Every warning needs a display_id.'):
            with self.subTest(leak=leak):
                self.assertEqual(self.rejected(self.draft(label, leak, assembled), assembled), 'INTERNAL_LABEL_IN_RIDER_TEXT')
        self.assertEqual(ta.gate(self.draft(label, 'Use E20 fuel or lower.', assembled), assembled, 'Can I use E20?')['route'],
                         'SUPPORTED')

    def test_disclaimers_pages_partial_clarification_and_caps(self):
        assembled = self.sent('chunk_synthetic_0_0')
        label = self.label(assembled, 'first 500 km')
        for text in ('Another table says 9000 rpm.', 'Page 116 says otherwise.'):
            draft = self.draft(label, 'No full throttle.', assembled, disclaimers=[{'text': text}])
            self.assertEqual(self.rejected(draft, assembled), 'UNCITED_DISCLAIMER_STATES_VALUE_OR_PAGE')
        self.assertEqual(self.rejected(self.draft(label, 'No full throttle (page 12).', assembled), assembled),
                         'PAGE_NOT_OF_CITED_OBJECT')
        self.assertEqual(self.rejected(self.draft(label, 'Below 6000 rpm.', assembled, coverage='PARTIAL'), assembled),
                         'UNDISCLOSED_PARTIAL_ANSWER')
        over = self.draft(label, 'x', assembled, answer=[{'text': 'No full throttle.', 'evidence_ids': [label]}] * 7)
        self.assertEqual(self.rejected(over, assembled), 'TEMPLATE_SECTION_INVALID_OR_OVER_CAP')
        self.assertEqual(self.rejected({'route': 'AMBIGUOUS', 'coverage': 'NONE'}, assembled), 'CLARIFICATION_ROUTE_MISMATCH')
        asked = ta.gate({'route': 'AMBIGUOUS', 'coverage': 'NONE', 'clarification_question': 'Which kilometre reading?'},
                        assembled, 'Can I go full throttle?')
        self.assertEqual(asked['clarification_question'], 'Which kilometre reading?')
        self.assertEqual(self.rejected({'route': 'SUPPORTED', 'coverage': 'COMPLETE', 'extra': 1}, assembled), 'TEMPLATE_SCHEMA')


class FakeAdmission:
    def __init__(self, fail_permit=False):
        self.events, self.fail_permit, self.slot = [], fail_permit, None

    def begin_turn(self, operation_id, plan=None):
        self.events.append(('begin', operation_id, deepcopy(plan)))
        self.slot = dict(plan['slots'][0], tokens=plan['slots'][0]['input_tokens'] + plan['slots'][0]['output_tokens'])
        return {'reservation_mode': 'SINGLE_GENERATION_CALL', 'reserved_tokens': self.slot['tokens'],
                'reserved_nanodollars': self.slot['maximum_nanodollars'], 'sealing_status': 'ACTIVE_RESERVATIONS_RETAINED',
                'sealed_unused_slots': 0}

    def for_model(self, model, *, role=None):
        def permit(tokens, kind):
            self.events.append(('permit', model, role, tokens, kind))
            if self.fail_permit:
                raise ProviderFailure('PROVIDER_WHOLE_TURN_ALLOCATION_LIMIT')
            return deepcopy(self.slot)
        return permit

    def end_turn(self):
        self.events.append(('end',))
        return {'reservation_mode': 'SINGLE_GENERATION_CALL', 'sealing_status': 'SEALED_UNUSED_CONFIRMED'}


class FakeTransport:
    def __init__(self, draft=None, count=1500, **result):
        text = json.dumps(draft if draft is not None else {'route': 'UNSUPPORTED', 'coverage': 'NONE'})
        self.count, self.calls = count, []
        self.result = {'model': ha.MODEL, 'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': text}],
                       'usage': {'input_tokens': 300, 'output_tokens': 120, 'cache_creation_input_tokens': 1200,
                                 'cache_read_input_tokens': 0,
                                 'cache_creation': {'ephemeral_5m_input_tokens': 1200, 'ephemeral_1h_input_tokens': 0}}}
        self.result.update(result)

    def __call__(self, method, path, body, key):
        self.calls.append((path, deepcopy(body)))
        if path == 'messages/count_tokens':
            return {'input_tokens': self.count}
        return deepcopy(self.result)


class HaikuAnswerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assembled = sa.assemble(sa.SectionIndex(fixture()), ['chunk_synthetic_1_0'])

    def call(self, transport, admission=None, key='synthetic-key'):
        generate = ha.HaikuAnswer(admission or FakeAdmission(), transport=transport, key=key)
        return generate, generate(self.assembled, 'RIDER QUESTION: synthetic', 'op-1')

    def test_one_call_at_high_effort_with_cached_system_prompt_and_exact_schema(self):
        transport, admission = FakeTransport(), FakeAdmission()
        _generate, (draft, trace) = self.call(transport, admission)
        self.assertEqual(draft, {'route': 'UNSUPPORTED', 'coverage': 'NONE'})
        self.assertEqual([path for path, _ in transport.calls], ['messages/count_tokens', 'messages'])
        counted, body = transport.calls[0][1], transport.calls[1][1]
        self.assertNotIn('max_tokens', counted)
        self.assertEqual(body['model'], 'claude-haiku-5-5')
        self.assertEqual(body['thinking'], {'type': 'disabled'})
        self.assertEqual(body['output_config']['effort'], 'high')
        self.assertEqual(body['output_config']['format'], {'type': 'json_schema', 'schema': ta.answer_schema(self.assembled)})
        self.assertEqual(body['system'], [{'type': 'text', 'text': ta.SYSTEM_PROMPT,
                                           'cache_control': {'type': 'ephemeral', 'ttl': '5m'}}])
        self.assertNotIn('cache_control', body['messages'][0]['content'][0])
        reserved = 1500 + ha.COUNTER_HEADROOM_TOKENS
        begin = admission.events[0][2]
        self.assertEqual(begin['slots'], [{'model': ha.MODEL, 'stage': 'generate', 'input_tokens': reserved,
            'output_tokens': 1800, 'attempt': 1, 'maximum_nanodollars': ha.maximum_nanodollars(reserved)}])
        self.assertEqual(admission.events[1], ('permit', ha.MODEL, 'generation', reserved + 1800, 'generation'))
        self.assertEqual(admission.events[-1], ('end',))
        self.assertEqual((trace['generation_calls'], trace['cache_creation_input_tokens'], trace['raw_content_logged']),
                         (1, 1200, False))
        self.assertAlmostEqual(trace['estimated_cost_usd'], ha.actual_cost(300, 1200, 0, 120))

    def test_cost_bounds_use_the_cache_write_and_long_context_tiers(self):
        self.assertEqual(ha.maximum_nanodollars(20000), 20000 * 125 + 1800 * 500)
        self.assertEqual(ha.maximum_nanodollars(120000), 120000 * 625 + 1800 * 2500)
        with self.assertRaises(ValueError):
            ha.maximum_nanodollars(ha.INPUT_TOKENS + 1)

    def test_incomplete_oversized_or_malformed_output_fails_closed_and_still_ends_the_turn(self):
        cases = [({'stop_reason': 'max_tokens'}, 'PROVIDER_INCOMPLETE_OR_REFUSED'),
                 ({'model': 'claude-sonnet-5-5'}, 'PROVIDER_MODEL_MISMATCH'),
                 ({'usage': {'input_tokens': 5000, 'output_tokens': 1, 'cache_creation_input_tokens': 0,
                             'cache_read_input_tokens': 0}}, 'PROVIDER_TOKEN_BOUND'),
                 ({'content': [{'type': 'text', 'text': '{"route":"A","route":"B"}'}]}, 'PROVIDER_INVALID_JSON'),
                 ({'content': [{'type': 'text', 'text': '[]'}]}, 'PROVIDER_INVALID_JSON'),
                 ({'content': [{'type': 'text', 'text': '{}'}, {'type': 'text', 'text': '{}'}]}, 'PROVIDER_INVALID_PARTS')]
        for result, code in cases:
            with self.subTest(code=code):
                admission = FakeAdmission()
                with self.assertRaisesRegex(ProviderFailure, code):
                    self.call(FakeTransport(**result), admission)
                self.assertEqual(admission.events[-1], ('end',))

    def test_no_key_oversized_context_or_refused_ledger_never_sends_the_paid_call(self):
        transport = FakeTransport()
        with self.assertRaisesRegex(ProviderFailure, 'CLAUDE_UNCONFIGURED'):
            ha.HaikuAnswer(FakeAdmission(), transport=transport, key='')(self.assembled, 'x', 'op')
        with self.assertRaisesRegex(ProviderFailure, 'TOKEN_BOUND_NO_TRUNCATION'):
            self.call(FakeTransport(count=ha.INPUT_TOKENS))
        transport, admission = FakeTransport(), FakeAdmission(fail_permit=True)
        with self.assertRaisesRegex(ProviderFailure, 'ALLOCATION_LIMIT'):
            self.call(transport, admission)
        self.assertEqual([path for path, _ in transport.calls], ['messages/count_tokens'])
        self.assertEqual(admission.events[-1], ('end',))


class FakeGenerate:
    contract = ha.CONTRACT

    def __init__(self, draft=None, failure=None):
        self.draft, self.failure, self.calls, self.last_trace = draft, failure, [], None

    def __call__(self, assembled, text, operation_id):
        self.calls.append((assembled, text, operation_id))
        self.last_trace = {'generation_calls': 1, 'admission': {'reservation_mode': 'SINGLE_GENERATION_CALL', 'events': ['x']}}
        if self.failure:
            raise ProviderFailure(self.failure)
        return deepcopy(self.draft(assembled) if callable(self.draft) else self.draft), self.last_trace


class EmptyRetriever:
    def __init__(self, manifest):
        self.manifest = manifest

    def search(self, query):
        return {'version': sr.VERSION, 'index_id': self.manifest['index_id'], 'chunk_ids': [],
                'sections_disagree': False, 'reranked': False, 'rerank_skip_reason': None,
                'max_cross_score': None, 'below_relevance_floor': False}


def located(assembled):
    label = next(l for l, o in assembled['objects'].items() if 'located' in o['text'])
    return {'route': 'SUPPORTED', 'coverage': 'COMPLETE',
            'answer': [{'text': 'The charger port is on the centre of the handlebar.', 'evidence_ids': [label]}],
            'watchout_review': [{'display_id': w, 'decision': 'NOT_APPLICABLE', 'reason': 'not asked'}
                                for w in assembled['warnings']]}


class QuestionsTests(unittest.TestCase):
    def setUp(self):
        self.root = fixture()
        self.identity = si.identity(self.root)
        self.source = ManualSource(SOURCE_MANIFEST, self.identity)
        self.index = sa.SectionIndex(self.root)

    def questions(self, generate, retriever=None):
        retriever = retriever or sr.SectionRetriever(self.root, Embedder(), CrossEncoder())
        return Questions(self.source, self.index, retriever, generate, self.identity)

    def test_released_answer_is_a_bound_private_buffer_with_server_page_citations(self):
        generate = FakeGenerate(located)
        q = self.questions(generate)
        session = q.new_session()
        stages = []
        updated, view, choices = q.answer(session, 'Where is the charger port?', progress=stages.append, operation_id='a' * 32)
        self.assertEqual((updated.version, choices, stages), (1, {}, ['retrieving', 'drafting', 'checking']))
        response = view['response']
        self.assertEqual((response['type'], response['release_gate_passed'], response['technical_content']),
                         ('SUPPORTED', True, True))
        self.assertEqual(response['natural_language'], 'The charger port is on the centre of the handlebar.')
        self.assertEqual(response['cited_pages'], [{'evidence_id': 'evidence_synthetic_1_0', 'pdf_page': 64,
            'pdf_page_index': 63, 'manual_checksum': self.source.checksum, 'index_id': self.source.index_id}])
        self.assertEqual(view['provider_calls'], 1)
        self.assertEqual(view['runtime_controls']['generation']['admission'],
                         {'reservation_mode': 'SINGLE_GENERATION_CALL', 'reserved_tokens': None,
                          'reserved_nanodollars': None, 'sealing_status': None, 'sealed_unused_slots': None})
        self.assertNotIn('watchout_review', json.dumps(view))
        bound = bind_view(view, 'a' * 32, q.runtime_lock)
        self.assertEqual(q.validate_saved(bound), bound)
        for change in (lambda v: v['response'].update(natural_language='Changed advice.'),
                       lambda v: v['release_delivery'].update(runtime_lock='0' * 64),
                       lambda v: v['delivery'].update(release_binding_sha256='0' * 64),
                       lambda v: v.update(runtime_policy='open-manual-haiku-draft-verify-v10_13')):
            changed = deepcopy(bound)
            change(changed)
            with self.subTest(change=change), self.assertRaises(ValueError):
                q.validate_saved(changed)
        with self.assertRaisesRegex(ValueError, 'RELEASED_OPERATION_BINDING_CHANGED'):
            bind_view(view, 'b' * 32, q.runtime_lock)

    def test_nothing_retrieved_returns_fixed_fallback_and_support_with_no_call(self):
        generate = FakeGenerate(located)
        q = self.questions(generate, EmptyRetriever(self.index.manifest))
        _s, view, _c = q.answer(q.new_session(), 'Anything?', operation_id='a' * 32)
        self.assertEqual(generate.calls, [])
        self.assertEqual((view['response']['type'], view['response']['natural_language'], view['escalation_uri']),
                         ('UNSUPPORTED', ta.FALLBACK_TEXT, SUPPORT))
        self.assertEqual((view['provider_calls'], view['response']['release_gate_passed']), (0, False))
        self.assertEqual(view['response']['reason_codes'], ['NOTHING_RETRIEVED'])

    def test_a_best_score_below_the_floor_sends_the_fallback_with_no_call(self):
        generate = FakeGenerate(located)
        low = CrossEncoder({h: sr.RELEVANCE_FLOOR - 1 for h in ('RUNNING IN', 'CHARGER PORT', 'SPECIFICATIONS',
                                                                 'FUEL TANK CAP', 'FUEL FILLING LEVEL')})
        q = self.questions(generate, sr.SectionRetriever(self.root, Embedder(), low))
        _s, view, _c = q.answer(q.new_session(), 'How do I pair a Bluetooth intercom?', operation_id='a' * 32)
        self.assertEqual(generate.calls, [])
        self.assertEqual((view['response']['type'], view['response']['natural_language'], view['provider_calls']),
                         ('UNSUPPORTED', ta.FALLBACK_TEXT, 0))
        self.assertEqual(view['response']['reason_codes'], ['BELOW_RELEVANCE_FLOOR'])
        self.assertTrue(view['runtime_controls']['retrieval']['below_relevance_floor'])

    def test_gate_rejection_and_provider_failure_are_system_errors(self):
        bad = FakeGenerate(lambda a: dict(located(a), answer=[{'text': 'Somewhere.', 'evidence_ids': ['E99']}]))
        _s, view, _c = self.questions(bad).answer(self.questions(bad).new_session(), 'Where is the charger port?')
        self.assertEqual((view['response']['type'], view['response']['natural_language']), ('SYSTEM_ERROR', SYSTEM_ERROR_TEXT))
        self.assertEqual(view['response']['reason_codes'], ['GATE_CITATION_NOT_SENT'])
        self.assertEqual((view['provider_calls'], view['response']['technical_content']), (1, False))
        failing = FakeGenerate(failure='CLAUDE_HTTP_429')
        _s, view, _c = self.questions(failing).answer(self.questions(failing).new_session(), 'Where is the charger port?')
        self.assertEqual(view['response']['reason_codes'], ['CLAUDE_HTTP_429'])

    def test_changed_runtime_session_never_reaches_retrieval_or_generation(self):
        generate = FakeGenerate(located)
        q = self.questions(generate)
        from dataclasses import replace
        stale = replace(q.new_session(), generation_lock='0' * 64)
        stages = []
        _s, view, _c = q.answer(stale, 'Where is the charger port?', progress=stages.append)
        self.assertEqual((view['response']['reason_codes'], stages, generate.calls), (['SESSION_RUNTIME_CHANGED'], [], []))

    def test_follow_up_sends_prior_turns_as_data_and_keeps_retrieval_topic(self):
        generate = FakeGenerate(located)
        history = [{'question': 'Where is the charger port?', 'response': 'On the handlebar.', 'route': 'SUPPORTED'}]
        self.questions(generate).answer(self.questions(generate).new_session(), 'Can I use it in rain?', history=history)
        text = generate.calls[0][1]
        self.assertIn('EARLIER CONVERSATION: - Rider: Where is the charger port?\n- MotoMedic: On the handlebar.', text)
        self.assertIn('RIDER QUESTION: Can I use it in rain?', text)

    def test_concurrent_turn_on_the_same_worker_fails_closed(self):
        q = self.questions(FakeGenerate(located))
        q.pipeline_lock.acquire()
        try:
            _s, view, _c = q.answer(q.new_session(), 'Where is the charger port?')
        finally:
            q.pipeline_lock.release()
        self.assertEqual(view['response']['reason_codes'], ['PIPELINE_CONCURRENCY_LIMIT'])

    def test_source_manifest_must_match_the_index_and_have_a_verified_route(self):
        with self.assertRaisesRegex(ValueError, 'MANUAL_INDEX_SOURCE_MISMATCH'):
            ManualSource(dict(SOURCE_MANIFEST, sha256='0' * 64), self.identity)
        route = dict(SOURCE_MANIFEST['oem_service_route'], verified=False)
        with self.assertRaisesRegex(ValueError, 'SUPPORT_ROUTE_UNVERIFIED'):
            ManualSource(dict(SOURCE_MANIFEST, oem_service_route=route), self.identity)


if __name__ == '__main__':
    unittest.main()
