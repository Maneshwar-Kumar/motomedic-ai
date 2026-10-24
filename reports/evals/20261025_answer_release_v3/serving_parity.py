"""Usage (project root, needs NumPy): python reports/evals/20261025_answer_release_v3/serving_parity.py

Serving modules vs the v3 candidate on the real section index; zero model calls.

For each of the 30 questions: the serving assembly of the eval's retrieved chunk IDs must equal the
eval's model input byte for byte, the serving gate must give the same released/rejected outcome on
the saved drafts, and the real index must pass the serving identity check. Then one turn runs
through the real Questions pipeline (stored vectors as the dense query, a fake generation call).
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
EVAL = ROOT / 'reports/evals/20261025_answer_release_v3'
INDEX = ROOT / 'build/index-v3-sections'
from cloud.grounded_generation import section_assembly as sa, section_index as si, template_answer as ta
from cloud.grounded_generation import section_retrieval as sr
from cloud.grounded_generation.section_questions import ManualSource, Questions

identity = si.identity(INDEX)
si.verify(INDEX, identity)
index = sa.SectionIndex(INDEX)
cases = {c['case_id']: c for c in json.loads((ROOT / 'reports/evals/20261023_stage_replay_v1/cases.json').read_text(encoding='utf-8'))['cases']}
aliases = json.loads((ROOT / 'reports/evals/20261024_sonnet_generation_v1/alias_mapping.json').read_text())
rows = {}
for arm in ('haiku', 'haiku_high', 'sonnet'):
    expected = {r['alias']: r for r in json.loads((EVAL / f'gate_results_{arm}.json').read_text(encoding='utf-8'))['rows']}
    released = 0
    for alias, cid in sorted(aliases.items()):
        trace = json.loads((EVAL / 'retrieval' / f'{alias}.json').read_text(encoding='utf-8'))
        assembled = sa.assemble(index, trace['retrieval']['chunk_ids'])
        text = sa.model_input(cases[cid]['question'], assembled)
        assert text == (EVAL / 'inputs' / f'{alias}.txt').read_text(encoding='utf-8'), alias
        draft = json.loads((EVAL / f'drafts_{arm}' / f'{alias}.json').read_text(encoding='utf-8'))
        try:
            ta.gate(draft, assembled, cases[cid]['question'], 'mailto:support@royalenfield.com')
            outcome = 'RELEASED'
        except ta.ReleaseRejected as exc:
            outcome = exc.code
        released += outcome == 'RELEASED'
        assert outcome == (expected[alias]['rejection_code'] or 'RELEASED'), (arm, alias, outcome)
    rows[arm] = {'released': released}
SUMMARY = {'label': 'LOCAL_PROVIDER_FREE_PARITY_CHECK_ZERO_MODEL_CALLS', 'index_id': identity['index_id'], 'identity_verified': True,
           'inputs_identical': 30, 'gate_outcomes_identical': 90, 'gate_released': {arm: rows[arm]['released'] for arm in rows}}


class StoredVector:
    """Dense query = the stored vector of a chunk; exercises the real index without BGE-M3."""
    def __init__(self, retriever, chunk_id):
        import numpy as np
        self.vector = np.load(INDEX / 'embeddings.npy')[[c['id'] for c in retriever.chunks].index(chunk_id)]

    def encode(self, text, normalize_embeddings=True):
        return self.vector


class NoRerank:
    def predict(self, pairs):
        return [0.0] * len(pairs)


class Generate:
    from cloud.grounded_generation.haiku_answer import CONTRACT as contract
    last_trace = None

    def __call__(self, assembled, text, operation_id):
        self.last_trace = {'generation_calls': 1}
        label = next(l for l, o in assembled['objects'].items() if 'USB' in o['text'] or 'usb' in o['text'].lower())
        return {'route': 'SUPPORTED', 'coverage': 'COMPLETE',
                'answer': [{'text': 'The manual lists a USB charging port.', 'evidence_ids': [label]}],
                'watchout_review': [{'display_id': w, 'decision': 'NOT_APPLICABLE', 'reason': 'not asked'}
                                    for w in assembled['warnings']]}, self.last_trace


retriever = sr.SectionRetriever(INDEX, None, NoRerank())
usb = next(c['id'] for c in retriever.chunks if 'USB' in c['text'])
retriever.model = StoredVector(retriever, usb)
source = ManualSource.load(ROOT, identity)
q = Questions(source, index, retriever, Generate(), identity)
_s, view, _c = q.answer(q.new_session(), 'Where is the USB charging port?', operation_id='a' * 32)
SUMMARY['real_index_turn'] = ({'route': view['response']['type'], 'released': view['response']['release_gate_passed'],
                  'cited_pages': [c['pdf_page'] for c in view['response']['cited_pages']],
                  'sections_sent': view['runtime_controls']['assembly']['sections'],
                  'warnings_sent': view['runtime_controls']['assembly']['warnings'],
                  'reranked': view['runtime_controls']['retrieval']['reranked'],
                  'chunks_kept': len(view['runtime_controls']['retrieval']['chunk_ids'])})
(EVAL / 'serving_parity.json').write_bytes((json.dumps(SUMMARY, indent=1) + chr(10)).encode('utf-8'))
print(json.dumps(SUMMARY, indent=1))
