"""Gate every arm's blind drafts against the exact sections sent, then unblind for scoring.

Usage (project root): python run_gate_v3.py <arm> [<arm> ...]   e.g. haiku haiku_high sonnet
Reads drafts_<arm>/Qnn.json and retrieval/Qnn.json; writes gate_results_<arm>.json.
"""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EVALS = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE / 'candidate'))
import template_answer as ta  # noqa: E402

SUPPORT = json.loads((ROOT / 'source_manifest.json').read_text(encoding='utf-8-sig'))['oem_service_route']['url']
mapping = json.loads((EVALS / '20261024_sonnet_generation_v1/alias_mapping.json').read_text())
cases = {c['case_id']: c for c in json.loads((EVALS / '20261023_stage_replay_v1/cases.json').read_text(encoding='utf-8'))['cases']}

for arm in sys.argv[1:]:
    rows = []
    for alias, cid in sorted(mapping.items(), key=lambda kv: (cases[kv[1]]['group'], kv[1])):
        case = cases[cid]
        assembled = json.loads((HERE / 'retrieval' / f'{alias}.json').read_text(encoding='utf-8'))['assembled']
        path = HERE / f'drafts_{arm}' / f'{alias}.json'
        draft, code, detail, released = None, None, None, None
        if not assembled['objects']:
            released = ta.no_evidence_release(SUPPORT)
        else:
            try:
                draft = json.loads(path.read_text(encoding='utf-8'))
                released = ta.gate(draft, assembled, case['question'], SUPPORT)
            except ta.ReleaseRejected as exc:
                code, detail = exc.code, exc.detail
            except (OSError, ValueError) as exc:
                code, detail = 'MALFORMED_OR_MISSING_OUTPUT', type(exc).__name__
        draft = draft if isinstance(draft, dict) else {}
        rows.append({'alias': alias, 'case_id': cid, 'group': case['group'], 'question': case['question'],
                     'gold_evidence_ids': case['gold_evidence_ids'],
                     'draft_route': draft.get('route'), 'draft_coverage': draft.get('coverage'),
                     'gate': 'RELEASED' if released else 'SYSTEM_ERROR', 'rejection_code': code, 'rejection_detail': detail,
                     'released_route': released and released['route'], 'released_text': released and released['text'],
                     'escalation_uri': released and released['escalation_uri'],
                     'provider_calls': released['provider_calls'] if released else 1,
                     'citations': released and released['citations'],
                     'cited_evidence_ids': sorted({c['evidence_id'] for c in (released or {}).get('citations', [])}),
                     'watchouts_included': released and [r['display_id'] for r in released['watchout_review'] if r['decision'] == 'INCLUDED'],
                     'warnings_sent': len(assembled['warnings']),
                     'sections': {s: draft.get(s) for s in ta.CAPS},
                     'clarification_question': draft.get('clarification_question'),
                     'canonical_answer': case.get('canonical_answer'), 'absence_check': case.get('absence_check')})
    out = HERE / f'gate_results_{arm}.json'
    out.write_text(json.dumps({'schema': 'motomedic-template-release-diagnostic-v3', 'gate_version': ta.VERSION, 'arm': arm,
                               'label': 'LOCAL_DIAGNOSTIC_CLAUDE_CODE_SUBAGENT_GENERATOR_NOT_HOSTED_NOT_ACCEPTANCE',
                               'rows': rows}, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    released = sum(r['gate'] == 'RELEASED' for r in rows)
    print(arm, 'released', released, '/', len(rows))
    for r in rows:
        if r['gate'] != 'RELEASED':
            print('  ', r['case_id'], r['rejection_code'], r['rejection_detail'])
