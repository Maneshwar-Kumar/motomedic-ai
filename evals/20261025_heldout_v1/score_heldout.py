"""Unblind the judge's verdicts and combine them with the gate results into comparison.json.

Usage (project root): python evals/20261025_heldout_v1/score_heldout.py
Inputs: gate_results_<arm>.json (run_heldout.py), judgments.json (the blinded judge, keyed by
question then A/B) and judge_key.json. Agent judgment, not human review.
"""
from collections import Counter
import json
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
ARMS = ('haiku_high', 'haiku_default')
VERDICTS = ('CORRECT', 'PARTIAL', 'WRONG', 'REFUSED', 'NOT_RELEASED')


def main():
    key = json.loads((HERE / 'judge_key.json').read_text(encoding='utf-8'))
    judged = json.loads((HERE / 'judgments.json').read_text(encoding='utf-8'))
    questions = {q['id']: q for q in json.loads((HERE / 'questions.json').read_text(encoding='utf-8'))['questions']}
    out = {'label': 'LOCAL_CLAUDE_CODE_SUBAGENT_RUN_AGENT_JUDGED_NOT_HOSTED_NOT_HUMAN_ACCEPTANCE', 'arms': {}, 'rows': []}
    for arm in ARMS:
        gate = json.loads((HERE / f'gate_results_{arm}.json').read_text(encoding='utf-8'))
        rows = []
        for g in gate['rows']:
            alias = next(a for a, name in key[g['id']].items() if name == arm)
            j = judged[g['id']][alias]
            if g['route'] == 'SYSTEM_ERROR' and j['verdict'] != 'NOT_RELEASED':
                raise SystemExit('Judge verdict for an unreleased answer: ' + g['id'])
            required = questions[g['id']]['required_warnings']
            rows.append({'arm': arm, 'id': g['id'], 'category': g['category'], 'expected_route': g['expected_route'],
                         'route': g['route'], 'route_matches': g['route'] == g['expected_route'],
                         'verdict': j['verdict'], 'missing': j['missing'], 'unfaithful_items': j['unfaithful_items'],
                         'required_warnings': len(required), 'required_warnings_shown': sum(map(bool, j['required_warnings_shown'])),
                         'restatement': j['restatement'], 'internal_wording': j['internal_wording'], 'notes': j['notes'],
                         'reason': g['reason'], 'schema_errors': g['schema_errors'], 'below_relevance_floor': g['below_relevance_floor'],
                         'max_cross_score': g['max_cross_score'], 'suppressed_duplicates': g['suppressed_duplicates'],
                         'rewritten_phrases': g['rewritten_phrases'], 'reference_pages': g['reference_pages'],
                         'reference_pages_sent': g['reference_pages_sent'], 'model_input_chars': g['model_input_chars'],
                         'released_characters': len(g['text'])})
        verdicts = Counter(r['verdict'] for r in rows)
        answerable = [r for r in rows if r['expected_route'] != 'UNSUPPORTED']
        out['arms'][arm] = {
            'questions': len(rows), **{v.lower(): verdicts[v] for v in VERDICTS},
            'by_category': {c: dict(Counter(r['verdict'] for r in rows if r['category'] == c))
                            for c in dict.fromkeys(r['category'] for r in rows)},
            'route_matches': sum(r['route_matches'] for r in rows),
            'system_errors': [r['id'] + ':' + r['reason'] for r in rows if r['route'] == 'SYSTEM_ERROR'],
            'system_errors_with_schema_slips': [r['id'] for r in rows if r['route'] == 'SYSTEM_ERROR' and r['schema_errors']],
            'unfaithful_cited_items': sum(len(r['unfaithful_items']) for r in rows),
            'required_warnings_shown': f"{sum(r['required_warnings_shown'] for r in rows)}/{sum(r['required_warnings'] for r in rows)}",
            'answers_with_restatement': sum(bool(r['restatement']) for r in rows),
            'answers_with_internal_wording': sum(bool(r['internal_wording']) for r in rows),
            'dropped_duplicates': sum(r['suppressed_duplicates'] or 0 for r in rows),
            'rewritten_phrases': sum(len(r['rewritten_phrases'] or []) for r in rows),
            'floor_refusals': [r['id'] for r in rows if r['below_relevance_floor']],
            'floor_false_refusals': [r['id'] for r in answerable if r['below_relevance_floor']],
            'unanswerable_released_with_a_fact': [r['id'] for r in rows if r['expected_route'] == 'UNSUPPORTED'
                                                  and r['verdict'] == 'WRONG'],
            'answerable_with_all_reference_pages_sent': sum(r['reference_pages_sent'] == r['reference_pages'] for r in answerable),
            'answerable_with_any_reference_page_sent': sum(bool(r['reference_pages_sent']) for r in answerable),
            'answerable': len(answerable),
            'median_model_input_chars': median(r['model_input_chars'] for r in rows),
            'median_released_chars': median(r['released_characters'] for r in rows)}
        out['rows'] += rows
    (HERE / 'comparison.json').write_bytes((json.dumps(out, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    print(json.dumps(out['arms'], indent=1))


if __name__ == '__main__':
    main()
