"""Score the private hosted v10.15-candidate run against gold and the local v5 replay.

Usage (project root): python reports/answer_quality/20261023_private_hosted_v5/score_hosted.py <run_dir> <out.json>
"""
import json
import sys
from pathlib import Path

RUN, OUT = Path(sys.argv[1]), Path(sys.argv[2])
BASE = Path(__file__).resolve().parents[1] / '20261023_stage_replay_v1'
cases = {c['case_id']: c for c in json.loads((BASE / 'cases.json').read_text(encoding='utf-8'))['cases']}
local = {r['case_id']: r for r in json.loads((BASE / 'replay_v5.json').read_text(encoding='utf-8'))['results']}
pages_of = {}
for line in (Path(__file__).resolve().parents[3] / 'build/index-bge-final/evidence.jsonl').open(encoding='utf-8'):
    e = json.loads(line)
    pages_of[e['id']] = sorted({p['page_no'] for p in e['provenance']})

rows = []
for path in sorted(RUN.glob('case_*.json')):
    run = json.loads(path.read_text(encoding='utf-8'))
    cid = run['case_id']
    case, loc = cases[cid], local[cid]
    view = run.get('saved_view') or {}
    controls = view.get('runtime_controls') or {}
    admission = controls.get('source_admission') or {}
    composition = controls.get('composition') or {}
    response = view.get('response') or {}
    admitted = set(admission.get('admitted_evidence_ids') or [])
    gold_ev, gold_pages = set(case['gold_evidence_ids']), set(case['gold_pages'])
    cited = {e for claim in response.get('claim_evidence_map', []) for e in claim.get('evidence_ids', [])}
    verdicts = [a.get('verdict_summary') for a in composition.get('attempts', []) if a.get('verdict_summary')]
    if gold_ev:
        gold_admitted = len(gold_ev & admitted) == len(gold_ev)
        gold_cited = bool(gold_ev & cited)
    else:
        gold_admitted = bool({p for e in admitted for p in pages_of.get(e, [])} & gold_pages) if gold_pages else None
        gold_cited = bool({p for e in cited for p in pages_of.get(e, [])} & gold_pages) if gold_pages else None
    rows.append({
        'case_id': cid, 'group': case['group'], 'question': case['question'],
        'status': run.get('status'), 'error': run.get('error'), 'route': run.get('route'),
        'reason_codes': response.get('reason_codes'), 'failure_code': composition.get('failure_code'),
        'hosted_final_chunks_match_local_v5': admission.get('chunk_ids') == [h['chunk_id'] for h in loc['final_hits']] if admission else None,
        'hosted_admitted_match_local_v5': sorted(admitted) == sorted(loc['admitted_evidence_ids'] or []) if admission else None,
        'rerank_attempts': (admission.get('retrieval_policy') or {}).get('rerank_attempts'),
        'admitted_count': len(admitted), 'gold_admitted_in_deployed_candidate': gold_admitted if admission else None,
        'provider_calls': composition.get('provider_calls'), 'verdicts': verdicts,
        'cited_evidence_count': len(cited), 'gold_cited_in_released_answer': gold_cited if cited else (False if response else None),
        'release_gate_passed': response.get('release_gate_passed'),
        'answer_text': response.get('natural_language'), 'exact_saved_stream': run.get('exact_saved_stream'),
        'exact_recovered_view': run.get('exact_recovered_view'), 'elapsed_seconds': run.get('elapsed_seconds')})
OUT.write_text(json.dumps({'schema': 'motomedic-private-hosted-v5-scores-v1', 'rows': rows}, indent=1, ensure_ascii=False) + '\n',
               encoding='utf-8')
for r in rows:
    print(f"{r['group'][:7]:7s} {r['case_id']:7s} {str(r['route']):12s} adm_gold={r['gold_admitted_in_deployed_candidate']} "
          f"cited_gold={r['gold_cited_in_released_answer']} match_local={r['hosted_final_chunks_match_local_v5']}/{r['hosted_admitted_match_local_v5']} "
          f"calls={r['provider_calls']} {r['error'] or ''} {r['failure_code'] or ''}")
