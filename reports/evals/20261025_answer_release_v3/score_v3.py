"""Combine the gate results with the main agent's judgments (judgments_<arm>.json) and compare to v2.

Usage (project root): python score_v3.py <arm> [<arm> ...]
Judgment per case: {"correct": true|false|null, "unfaithful": [item texts], "issues": [...]}.
correct is null when the gate did not release. Agent judgment, not human review.
"""
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
V2 = json.loads((HERE.parent / '20261024_answer_release_v1/scored_v2.json').read_text(encoding='utf-8'))
INTERNAL = re.compile(r'\b(?:admitted|evidence|retriev\w*|passages?|reviewed|source context|labels?)\b|\[E\d+\]|'
                      r'\b(?:these|supplied|provided) sections\b|\bsections (?:supplied|provided|shown|sent)\b', re.I)
summaries = {'v2_sonnet_reviewed_admission': V2['summary']}
for arm in sys.argv[1:]:
    gate = json.loads((HERE / f'gate_results_{arm}.json').read_text(encoding='utf-8'))['rows']
    judged = json.loads((HERE / f'judgments_{arm}.json').read_text(encoding='utf-8'))
    rows = []
    for r in gate:
        j = judged[r['case_id']]
        objects = json.loads((HERE / 'retrieval' / f"{r['alias']}.json").read_text(encoding='utf-8'))['assembled']['objects']
        gold_warnings = {o['evidence_id'] for o in objects.values()
                         if o['box'] in ('WARNING', 'CAUTION') and o['evidence_id'] in set(r['gold_evidence_ids'])}
        watch = {objects[l]['evidence_id'] for i in (r['sections'].get('watchouts') or []) for l in i['evidence_ids'] if l in objects}
        text = r['released_text'] or ''
        rows.append({'case_id': r['case_id'], 'group': r['group'], 'gate': r['gate'], 'route': r['released_route'],
                     'rejection_code': r['rejection_code'], 'provider_calls': r['provider_calls'],
                     'correct': j['correct'], 'unfaithful': j['unfaithful'], 'issues': j['issues'],
                     'cited_items': sum(len(r['sections'].get(s) or []) for s in ('answer', 'policy', 'watchouts')),
                     'internal_wording': sorted({m.group().lower() for m in INTERNAL.finditer(text)}),
                     'released_characters': len(text),
                     'gold_warnings': len(gold_warnings), 'gold_warnings_shown': len(gold_warnings & watch)})
    released = [x for x in rows if x['gate'] == 'RELEASED']
    summary = {'released': len(released), 'system_error': len(rows) - len(released),
               'released_matching_canonical': sum(x['correct'] is True for x in released),
               'released_wrong_or_weaker': sum(x['correct'] is False for x in released),
               'cited_items_checked': sum(x['cited_items'] for x in released),
               'unfaithful_cited_items': sum(len(x['unfaithful']) for x in released),
               'released_with_internal_wording': sum(bool(x['internal_wording']) for x in released),
               'released_characters_median': sorted(x['released_characters'] for x in released)[len(released) // 2] if released else 0,
               'gold_warnings_shown': f"{sum(x['gold_warnings_shown'] for x in rows)}/{sum(x['gold_warnings'] for x in rows)}",
               'provider_calls': sum(x['provider_calls'] for x in rows)}
    summaries[arm] = summary
    (HERE / f'scored_{arm}.json').write_text(json.dumps({'schema': 'motomedic-template-release-score-v3', 'arm': arm,
        'label': 'MAIN_AGENT_JUDGMENT_NOT_HUMAN_REVIEW_NOT_ACCEPTANCE', 'summary': summary, 'rows': rows},
        indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
(HERE / 'comparison.json').write_text(json.dumps(summaries, indent=1) + '\n', encoding='utf-8')
print(json.dumps(summaries, indent=1))
