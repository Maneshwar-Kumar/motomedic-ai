"""Development measurements for this round, on the 30 v3 questions; no model calls.

1. Warnings outside the sent sections (suggestion 4): the pinned cross-encoder scores each question
   against every WARNING/CAUTION line in the manual. The three best-scoring warnings are listed with
   whether the v3 run sent them, for reading by a person.
2. "Not found" floor (suggestion 6): the cross-encoder's best score over the 5 retrieved chunks,
   for answerable and unanswerable questions.

Usage (project root, needs sentence-transformers): python evals/20261025_quality_round_v1/measure_dev.py
"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
INDEX = ROOT / 'build/index-v3-sections'
V3 = ROOT / 'evals/20261025_answer_release_v3'
PUA = re.compile('[-]')


def main():
    from sentence_transformers import CrossEncoder
    from cloud.grounded_generation import section_assembly as sa
    cross = CrossEncoder(str(INDEX / 'reranker_model'), device='cpu', local_files_only=True)
    index = sa.SectionIndex(INDEX)
    warnings = []
    for section in index.sections.values():
        for eid in section['evidence_ids']:
            if section['box_of'].get(eid) in ('WARNING', 'CAUTION'):
                text = sa.render(index.evidence[eid])
                if text:
                    warnings.append({'evidence_id': eid, 'section_id': section['id'], 'section': section['heading'],
                                     'pages': section['pdf_pages'], 'text': PUA.sub('', text)})
    cases = {c['case_id']: c for c in json.loads((ROOT / 'evals/20261023_stage_replay_v1/cases.json').read_text(encoding='utf-8'))['cases']}
    aliases = json.loads((ROOT / 'evals/20261024_sonnet_generation_v1/alias_mapping.json').read_text())
    rows = []
    for alias, cid in sorted(aliases.items()):
        case = cases[cid]
        trace = json.loads((V3 / 'retrieval' / f'{alias}.json').read_text(encoding='utf-8'))
        chunk_ids = trace['retrieval']['chunk_ids']
        sent_sections = set(trace['assembled']['sections'])
        chunk_text = [index.chunks[c]['index_text'] for c in chunk_ids]
        top = cross.predict([(case['question'], t) for t in chunk_text])
        scores = cross.predict([(case['question'], w['section'] + '\n' + w['text']) for w in warnings])
        ranked = sorted(zip(scores, warnings), key=lambda r: -float(r[0]))[:3]
        rows.append({'alias': alias, 'case_id': cid, 'group': case['group'], 'question': case['question'],
                     'answerable': bool(case['gold_evidence_ids']),
                     'retrieved_max_cross_score': round(float(max(top)), 3),
                     'top_warnings': [{'score': round(float(s), 3), 'sent': w['section_id'] in sent_sections,
                                       'section': w['section'], 'pages': w['pages'], 'text': w['text'][:220]}
                                      for s, w in ranked]})
    answerable = sorted(r['retrieved_max_cross_score'] for r in rows if r['answerable'])
    unanswerable = sorted(r['retrieved_max_cross_score'] for r in rows if not r['answerable'])
    summary = {'label': 'LOCAL_DEVELOPMENT_MEASUREMENT_NO_MODEL_CALLS', 'questions': len(rows),
               'warning_lines_in_manual': len(warnings),
               'top3_warnings_not_sent': sum(not w['sent'] for r in rows for w in r['top_warnings']),
               'questions_whose_best_warning_was_not_sent': sum(not r['top_warnings'][0]['sent'] for r in rows),
               'retrieved_max_cross_score': {'answerable': answerable, 'unanswerable': unanswerable},
               'rows': rows}
    (HERE / 'dev_measurements.json').write_bytes((json.dumps(summary, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}, indent=1))


if __name__ == '__main__':
    main()
