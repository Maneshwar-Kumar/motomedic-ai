"""Unblind and compile the Sonnet draft->finalize->verify run for scoring."""
import json
import sys
from pathlib import Path

E = Path(sys.argv[1]); OUT = Path(sys.argv[2])
cases = {c['case_id']: c for c in json.loads(Path('reports/evals/20261023_stage_replay_v1/cases.json').read_text(encoding='utf-8'))['cases']}
mapping = json.loads((E / 'alias_mapping_PRIVATE.json').read_text())
rows = []
for q, cid in sorted(mapping.items(), key=lambda kv: (cases[kv[1]]['group'], kv[1])):
    fin = json.loads((E / 'finalized' / (q + '.json')).read_text(encoding='utf-8'))
    ver_path = E / 'verdicts' / (q + '.json')
    ver = json.loads(ver_path.read_text(encoding='utf-8')) if ver_path.exists() else None
    if fin['draft_validation'] != 'VALID':
        outcome, shown = 'SYSTEM_ERROR', None
    elif ver and ver.get('decision', '').startswith('RELEASE') and ver.get('release_eligible'):
        outcome = fin['route'] if fin['route'] != 'SUPPORTED' else ('SUPPORTED_' + ver['decision'].split('_', 1)[1])
        shown = ' '.join(c['text'] for c in fin['claims'])
    else:
        outcome, shown = 'FALLBACK_UNSUPPORTED', None
    unsupported = [p for p in (ver or {}).get('per_claim_support', []) if not p.get('supported')]
    rows.append({'alias': q, 'case_id': cid, 'group': cases[cid]['group'], 'question': cases[cid]['question'],
                 'draft_route': fin['route'], 'draft_coverage': fin['question_coverage'],
                 'draft_validation': fin['draft_validation'], 'draft_rejection_code': fin['draft_rejection_code'],
                 'verifier_decision': (ver or {}).get('decision'), 'verifier_coverage': (ver or {}).get('question_coverage'),
                 'unsupported_claims': [{'index': p.get('claim_index'), 'note': p.get('note')} for p in unsupported],
                 'omissions': (ver or {}).get('omissions'), 'conflicts': (ver or {}).get('conflicts'),
                 'outcome': outcome, 'shown_answer': shown,
                 'draft_answer': ' '.join(c['text'] for c in fin['claims'] if c.get('origin') == 'DRAFT') or None,
                 'canonical_answer': cases[cid].get('canonical_answer'), 'absence_check': cases[cid].get('absence_check')})
OUT.write_text(json.dumps({'schema': 'motomedic-sonnet-generation-diagnostic-v1', 'rows': rows}, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
for r in rows:
    print(f"{r['group'][:7]:7s} {r['case_id']:7s} draft={r['draft_route']}/{r['draft_validation']} verifier={r['verifier_decision']} -> {r['outcome']}")
