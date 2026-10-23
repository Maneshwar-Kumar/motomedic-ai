"""Attach the main agent's per-case judgments to gate_results.json (agent judgment, not human review).

Every cited answer/policy/watchout item was read against the semantic text of each object it
cites; 'matches_canonical' compares the released text with the approved package's canonical answer.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTERNAL = re.compile(r'admitted|evidence|retriev|passage|reviewed|source context|available (?:here|to me)', re.I)
# case_id: (matches_canonical, issues)
JUDGED = {
    'GEN007': (True, []), 'GEN012': (True, []), 'GEN022': (True, []), 'GEN025': (True, []),
    'GEN035': (True, []), 'GEN044': (True, []), 'EXP027': (True, []), 'EXP034': (True, []),
    'EXP037': (True, []), 'EXP038': (True, []), 'GEN004': (True, []), 'GEN041': (True, []),
    'GEN047': (True, []), 'GEN048': (True, []),
    'GEN011': (None, ['NOT_RELEASED: draft omitted the empty clarification_question field; content was correct']),
    'GEN014': (True, ['an "approximate values" note was put in the policy section',
                      'wrong-grade oil caution excluded by the model with a reason']),
    'GEN017': (True, ['engine-running condition excluded by the model with a reason']),
    'GEN030': (True, ['coverage PARTIAL with a disclaimer that describes the pipeline, though all six languages were given',
                      'three unasked menu-navigation sentences']),
    'EXP040': (False, ['p116/p117 conflict is disclosed, but the disclaimer leans to the 3rd notch and coverage is COMPLETE; '
                       'canonical says it cannot be verified and to confirm with authorised service',
                       'the uncited disclaimer carries page numbers and a setting that the gate does not check']),
    'EXP044': (True, ['long: 9 items and 1,483 characters (five watchouts, at the cap)', 'one unasked starting-step sentence']),
    'N09': (True, ['tells the rider to check the owner\'s manual directly']),
    'N10': (True, ['disclaimer tells the rider that source context was not fully reviewed']),
}
for case in ('N01', 'N02', 'N03', 'N04', 'N05', 'N06', 'N07', 'N08'):
    JUDGED.setdefault(case, (True, []))

data = json.loads((HERE / 'gate_results.json').read_text(encoding='utf-8'))
out = []
for r in data['rows']:
    ok, issues = JUDGED[r['case_id']]
    items = sum(len(r['sections'][s] or []) for s in ('answer', 'policy', 'watchouts'))
    jargon = sorted({m.group().lower() for m in INTERNAL.finditer(r['released_text'] or '')})
    out.append({'case_id': r['case_id'], 'group': r['group'], 'gate': r['gate'], 'route': r['draft_route'],
                'coverage': r['draft_coverage'], 'cited_items': items, 'cited_items_unfaithful': 0,
                'matches_canonical': ok, 'internal_wording_shown_to_rider': jargon, 'issues': issues,
                'released_characters': len(r['released_text'] or '')})
released = [o for o in out if o['gate'] == 'RELEASED']
summary = {'released': len(released), 'system_error': len(out) - len(released),
           'released_matching_canonical': sum(o['matches_canonical'] is True for o in released),
           'released_weaker_than_canonical': sum(o['matches_canonical'] is False for o in released),
           'cited_items_checked': sum(o['cited_items'] for o in released), 'cited_items_unfaithful': 0,
           'no_answer_cases_answered_with_invented_fact': 0,
           'released_with_internal_wording': sum(bool(o['internal_wording_shown_to_rider']) for o in released)}
(HERE / 'scored.json').write_text(json.dumps({'schema': 'motomedic-verifier-free-release-score-v1',
    'label': 'MAIN_AGENT_JUDGMENT_NOT_HUMAN_REVIEW_NOT_ACCEPTANCE', 'summary': summary, 'rows': out},
    indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps(summary, indent=1))
