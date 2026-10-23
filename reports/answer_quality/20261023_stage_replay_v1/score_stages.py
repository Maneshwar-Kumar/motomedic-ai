"""Score the local stage replay: where did the gold evidence survive or get lost?

Usage: python score_stages.py <replay.json> <cases.json> <out_scored.json>
"""
import json
import sys

replay = json.load(open(sys.argv[1], encoding='utf-8'))
cases = {c['case_id']: c for c in json.load(open(sys.argv[2], encoding='utf-8'))['cases']}


def hit(row, gold_ev, gold_pages):
    if gold_ev:
        return bool(set(row['evidence_ids']) & gold_ev)
    return bool(set(row['pages']) & gold_pages)


def first_rank(rows, gold_ev, gold_pages):
    for at, row in enumerate(rows or [], 1):
        if hit(row, gold_ev, gold_pages):
            return at
    return None


def covered(rows, gold_ev):
    return sorted({e for r in rows or [] for e in r['evidence_ids']} & gold_ev)


scored = []
for r in replay['results']:
    case = cases[r['case_id']]
    gold_ev, gold_pages = set(r['gold_evidence_ids']), set(r['gold_pages'])
    admitted = set(r['admitted_evidence_ids'] or [])
    reviewed_gold = sorted(e for e, ok in r['gold_evidence_reviewed'].items() if ok)
    s = {'case_id': r['case_id'], 'group': r['group'], 'question': r['question'], 'error': r['error'],
         'gold_basis': 'evidence' if gold_ev else ('pages' if gold_pages else 'none'),
         'gold_evidence_count': len(gold_ev), 'gold_reviewed_count': len(reviewed_gold)}
    stages = [('dense_top20', r['dense_top20']), ('bm25_top20', r['bm25_top20']),
              ('rrf_top20', r['rrf_top20']), ('initial_top5', r['initial_primary_top5']),
              ('final_hits', r['final_hits'])]
    for name, rows in stages:
        s[name + '_rank'] = first_rank(rows, gold_ev, gold_pages)
        if gold_ev:
            s[name + '_gold_covered'] = len(covered(rows, gold_ev))
    s['rerank_fired'] = r['rerank_fired']
    s['rerank_skip_reason'] = r['rerank_skip_reason']
    s['rerank_top10_rank'] = first_rank(r['rerank_order_top10'], gold_ev, gold_pages) if r['rerank_order_top10'] else None
    s['final_action'] = r['final_action']
    s['admitted_count'] = len(admitted)
    s['admitted_pages'] = r['admitted_pages']
    if gold_ev:
        s['gold_admitted'] = len(admitted & gold_ev)
    else:
        s['gold_admitted'] = None
    s['gold_page_admitted'] = bool(set(r['admitted_pages']) & gold_pages) if gold_pages else None
    gap_ev = {e for g in r['gaps'] for e in g['evidence_ids']}
    s['gold_blocked_as_gap'] = len(gap_ev & gold_ev) if gold_ev else None
    s['top_dense'] = r['dense_top20'][0]['dense'] if r['dense_top20'] else None
    s['top_bm25'] = r['bm25_top20'][0]['bm25'] if r['bm25_top20'] else None
    s['top_ce'] = r['rerank_order_top10'][0]['ce'] if r['rerank_order_top10'] else None

    # Where is the gold lost? (answerable groups) / what does the generator see? (no-answer)
    if r['error']:
        verdict = 'SYSTEM_ERROR'
    elif r['group'] == 'NO_ANSWER':
        verdict = ('GENERATOR_SEES_NO_EVIDENCE (route forced to UNSUPPORTED)' if not admitted else
                   'GENERATOR_SEES_UNRELATED_APPROVED_EVIDENCE (must abstain; false-support risk)')
    else:
        any_admitted = (s['gold_admitted'] or 0) > 0 if gold_ev else bool(s['gold_page_admitted'])
        full_admitted = (s['gold_admitted'] == len(gold_ev)) if gold_ev else bool(s['gold_page_admitted'])
        in_final = s['final_hits_rank'] is not None or (s['gold_admitted'] or 0) > 0
        if full_admitted:
            verdict = 'GOLD_REACHES_GENERATOR'
        elif any_admitted:
            verdict = 'GOLD_PARTLY_REACHES_GENERATOR'
        elif gold_ev and not reviewed_gold:
            verdict = ('LOST_AT_ADMISSION: gold retrieved but never reviewed' if in_final
                       else 'LOST_AT_RETRIEVAL (gold also unreviewed, so admission would block it)')
        elif in_final:
            verdict = 'LOST_AT_ADMISSION: gold retrieved, blocked by review gate'
        elif s['initial_top5_rank'] is not None:
            verdict = 'LOST_AT_RERANK: in initial top-5, dropped by reranking'
        elif s['rrf_top20_rank'] is not None:
            verdict = 'LOST_AT_RANKING_CUTOFF: in RRF top-20, outside top-5'
        elif s['dense_top20_rank'] is not None or s['bm25_top20_rank'] is not None:
            verdict = 'LOST_AT_FUSION: in one backend top-20, not RRF top-20'
        else:
            verdict = 'LOST_AT_RETRIEVAL: gold in neither dense nor BM25 top-20'
    s['verdict'] = verdict
    if r['group'] == 'CONTROL':
        exp = case['hosted_expected']
        s['fidelity'] = {
            'final_chunk_ids_match': [h['chunk_id'] for h in r['final_hits']] == exp['chunk_ids'],
            'admitted_match': sorted(r['admitted_evidence_ids'] or []) == sorted(exp['admitted_evidence_ids']),
            'dense_top3_parents_match': r['rank_signals']['dense_top_distinct_parent_ids'] == exp['dense_top_distinct_parent_ids'],
            'sparse_top3_parents_match': r['rank_signals']['sparse_top_distinct_parent_ids'] == exp['sparse_top_distinct_parent_ids'],
            'rerank_match': int(r['rerank_fired']) == exp['rerank_attempts'],
            'preserved_anchor_match': r['preserved_anchor_chunk_ids'] == exp['preserved_initial_anchor_chunk_ids'],
            'final_action_match': r['final_action'] == exp['final_action'],
            'gap_count_match': len(r['gaps']) == exp['gap_count']}
    scored.append(s)

json.dump({'schema': 'motomedic-stage-scores-v1', 'label': replay['label'], 'scores': scored},
          open(sys.argv[3], 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
for s in scored:
    print(f"{s['group'][:7]:7s} {s['case_id']:16s} dense={s['dense_top20_rank']} bm25={s['bm25_top20_rank']} "
          f"rrf={s['rrf_top20_rank']} top5={s['initial_top5_rank']} rerank={'Y' if s['rerank_fired'] else 'n'} "
          f"final={s['final_hits_rank']} adm={s['gold_admitted']}/{s['gold_evidence_count']} rev={s['gold_reviewed_count']} "
          f"nadm={s['admitted_count']} -> {s['verdict']}")
    if 'fidelity' in s:
        print('   FIDELITY', s['fidelity'])
