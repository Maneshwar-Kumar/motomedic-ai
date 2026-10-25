"""Run the verifier-free release gate on blind Sonnet template drafts and unblind for scoring.

Run from the project root with PYTHONPATH=. (venv): python run_gate.py <run_dir> <out.json>
<run_dir> holds inputs/ and drafts/ (Qnn.json). Payloads are rebuilt with the v5 authority from
the local replay's final hits, so the gate checks against the exact admitted objects. When
nothing is admitted the gate sends the fixed fallback and no draft is used (no model call).
gate_results_v1.json was produced by the v1 gate at commit f95f22d.
"""
import json
import sys
from pathlib import Path

E, OUT = Path(sys.argv[1]), Path(sys.argv[2])
HERE = Path(__file__).resolve().parent
EVALS = HERE.parent
sys.path.insert(0, '.')
sys.path.insert(0, 'reports/grounded_generation/structural_review_v2/candidate')
sys.path.insert(0, str(HERE / 'candidate'))
import answer_release as ar
import serving_source_authority_v5 as v5
from approved_registry import ApprovedEvidenceRegistry

idx = Path('build/index-bge-final').resolve()
registry = ApprovedEvidenceRegistry.load(Path('.').resolve(), idx)
sa = v5.SourceAuthority(registry, idx)
support = registry.support_uri()
paths = {e: p['section_path'] for p in map(json.loads, (idx / 'parents.jsonl').open(encoding='utf-8'))
         for e in p['evidence_ids']}
mapping = json.loads((EVALS / '20261024_sonnet_generation_v1/alias_mapping.json').read_text())
cases = {c['case_id']: c for c in json.loads((EVALS / '20261023_stage_replay_v1/cases.json').read_text(encoding='utf-8'))['cases']}
rep = {r['case_id']: r for r in json.loads((EVALS / '20261023_stage_replay_v1/replay_v5.json').read_text(encoding='utf-8'))['results']}
rows = []
for q, cid in sorted(mapping.items(), key=lambda kv: (cases[kv[1]]['group'], kv[1])):
    case = cases[cid]
    hits = [{'id': h['chunk_id'], 'evidence_ids': sa.chunks[h['chunk_id']]['evidence_ids'],
             'parent_section_id': sa.chunks[h['chunk_id']]['parent_section_id']} for h in rep[cid]['final_hits']]
    payload = sa.assemble({'index_id': sa.index_id, 'manual_checksum': sa.checksum, 'hits': hits})
    candidates = ar.watchout_candidates(payload, paths)
    shown = json.loads((E / 'inputs' / (q + '.json')).read_text(encoding='utf-8'))
    assert shown['question'] == case['question'], q
    assert sorted(shown['assembled_evidence']['evidence']) == sorted(payload['evidence']), q
    assert [c['display_id'] for c in shown['watchout_candidates']] == [c['display_id'] for c in candidates], q
    draft = json.loads((E / 'drafts' / (q + '.json')).read_text(encoding='utf-8'))
    code = detail = None
    if not payload['evidence']:
        released = ar.no_evidence_release(support)
    else:
        try:
            released = ar.gate(draft, payload, case['question'], candidates, support)
        except ar.ReleaseRejected as exc:
            released, code, detail = None, exc.code, exc.detail
    rows.append({'alias': q, 'case_id': cid, 'group': case['group'], 'question': case['question'],
                 'gold_evidence_ids': case['gold_evidence_ids'],
                 'admitted_objects': len(payload['evidence']), 'watchout_candidates': len(candidates),
                 'draft_route': draft.get('route'), 'draft_coverage': draft.get('coverage'),
                 'draft_used': bool(payload['evidence']),
                 'gate': 'RELEASED' if released else 'SYSTEM_ERROR', 'rejection_code': code, 'rejection_detail': detail,
                 'released_route': released and released['route'],
                 'released_text': released and released['text'],
                 'escalation_uri': released and released['escalation_uri'],
                 'provider_calls': released['provider_calls'] if released else 1,
                 'cited_evidence_ids': sorted({e for s in ar.CAPS for i in draft.get(s, []) if isinstance(i, dict)
                                               for e in i.get('evidence_ids') or []}),
                 'cited_pages': released and released['cited_pages'],
                 'watchouts_included': released and [r['display_id'] for r in released['watchout_review'] if r['decision'] == 'INCLUDED'],
                 'watchouts_excluded': released and len(released['excluded_watchouts']),
                 'sections': {s: draft.get(s) for s in ar.CAPS},
                 'clarification_question': draft.get('clarification_question'),
                 'canonical_answer': case.get('canonical_answer'), 'absence_check': case.get('absence_check')})
OUT.write_text(json.dumps({'schema': 'motomedic-verifier-free-release-diagnostic-v1', 'gate_version': ar.VERSION,
                           'label': 'LOCAL_DIAGNOSTIC_SONNET_SUBAGENT_GENERATOR_NOT_HOSTED_NOT_ACCEPTANCE',
                           'drafts': 'GENERATED_WITH_ANSWER_INSTRUCTIONS_v1',
                           'source_authority_lock': sa.lock, 'provider_calls_by_gate': 0, 'rows': rows},
                          indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
for r in rows:
    print(f"{r['group'][:7]:7s} {r['case_id']:7s} {r['draft_route']}/{r['draft_coverage']} -> {r['gate']} "
          f"{r['released_route'] or ''} calls={r['provider_calls']} {r['rejection_code'] or ''} {r['rejection_detail'] or ''}")
