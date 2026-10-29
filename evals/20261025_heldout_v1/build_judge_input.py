"""Write the blinded judge input: each question with both arms' released answers as A and B.

For every question the judge sees the reference answer, the facts and warnings it must show, and
each arm's released rider text with every cited item next to the exact manual line it cites. The
arm behind A and B is drawn per question from a fixed seed and kept in judge_key.json, which the
judge is not given. Usage (project root): python evals/20261025_heldout_v1/build_judge_input.py
"""
import json
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
ARMS = ('haiku_high', 'haiku_default')
SEED = 20261025


def answer(arm, qid):
    out = HERE / 'runs' / arm / qid
    result = json.loads((out / 'release.json').read_text(encoding='utf-8'))
    objects = json.loads((out / 'retrieval.json').read_text(encoding='utf-8'))['assembled']['objects']
    items = []
    for section, rows in (result.get('sections') or {}).items():
        for row in rows:
            items.append({'section': section, 'text': row['text'],
                          'cites': [{'page': objects[l]['pages'], 'box': objects[l].get('box'), 'line': objects[l]['text']}
                                    for l in row.get('evidence_ids', [])]})
    return {'route': result['route'], 'released_text': result['text'], 'items': items,
            'warnings_excluded': [{'line': objects[r['display_id']]['text'], 'reason': r['reason']}
                                  for r in result.get('watchout_review', []) if r['decision'] == 'NOT_APPLICABLE']}


def main():
    rng = random.Random(SEED)
    questions = json.loads((HERE / 'questions.json').read_text(encoding='utf-8'))['questions']
    by_id = {q['id']: q for q in questions}
    cases, key = [], {}
    for q in questions:
        order = list(ARMS)
        rng.shuffle(order)
        key[q['id']] = dict(zip('AB', order))
        cases.append({'id': q['id'], 'question': q['question'],
                      'earlier_question': by_id[q['follow_up_of']]['question'] if q['follow_up_of'] else None,
                      'expected_route': q['expected_route'], 'expected_coverage': q['coverage'],
                      'reference_answer': q['reference_answer'], 'must_include': q['must_include'],
                      'required_warnings': q['required_warnings'],
                      'answers': {alias: answer(arm, q['id']) for alias, arm in key[q['id']].items()}})
    (HERE / 'judge_input.json').write_bytes((json.dumps({'cases': cases}, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    (HERE / 'judge_key.json').write_bytes((json.dumps(key, indent=1) + '\n').encode('utf-8'))
    print(len(cases), 'cases')


if __name__ == '__main__':
    main()
