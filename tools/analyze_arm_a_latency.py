"""Offline additive decomposition of the frozen hosted Arm A measurements."""
import csv, hashlib, json, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'MotoMedic_AB30_20261011'
OUT = ROOT / 'reports/arm_a/20261011_latency'
OUT.mkdir(parents=True, exist_ok=True)
source = PACKAGE / 'raw_result.json'
raw = json.loads(source.read_text(encoding='utf-8'))
all_a = [r for r in raw['rows'] if r['architecture'] == 'A_COMPONENT_SELECTION']
rows = [r for r in all_a if r['route'] == 'SUPPORTED']

def q(values, p):
    values = sorted(values)
    position = (len(values)-1)*p
    lo = int(position)
    hi = min(lo+1, len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(position-lo)

def stats(values):
    return {'n': len(values), 'mean': statistics.mean(values),
            'p50': q(values, .5), 'p95': q(values, .95), 'sum': sum(values)}

records = []
for r in rows:
    t = r['timing_measurement']
    stages = r['retrieval_trace']['stages_seconds']
    total = r['loopback_client_delivery']['complete_response_seconds']
    retrieval = r['controller_retrieval_assembly_seconds']
    pacing = t['pacing_idle_only_seconds']
    provider = t['provider_active_union_seconds']
    residual = total-retrieval-pacing-provider
    assert residual >= -1e-8
    records.append({'record_id': r['record_id'], 'client_complete': total,
        'provider_idle_pacing': pacing, 'retrieval_and_gates': retrieval,
        'provider_active': provider, 'remaining_setup_validation_save_delivery': residual,
        'session_save_subset_of_remaining': r['session_and_delivery_commit_seconds'],
        'client_answer_start_offset_subset_of_remaining': r['loopback_client_delivery']['answer_turn_started_at_client_seconds'],
        'first_dense_bm25_retrieval_subset': stages['first_retrieval'],
        'dense_embedding_scoring_subset_of_first_retrieval': stages['dense_embedding_and_scoring'],
        'bm25_subset_of_first_retrieval': stages['bm25_scoring'],
        'reranking_subset_of_retrieval': stages.get('reranking', 0),
        'dependency_recovery_subset_of_retrieval': stages.get('dependency_recovery', 0),
        'rerank_attempts': r['retrieval_trace']['rerank_attempts'],
        'recovery_attempts': r['retrieval_trace']['recovery_attempts'],
        'client_complete_minus_pacing_arithmetic': total-pacing,
        'server_complete_minus_pacing_arithmetic': t['full_excluding_idle_pacing_seconds']})
fields = [k for k in records[0] if k not in ('record_id', 'rerank_attempts', 'recovery_attempts')]
summary = {k: stats([r[k] for r in records]) for k in fields}
partition = ['provider_idle_pacing', 'retrieval_and_gates', 'provider_active', 'remaining_setup_validation_save_delivery']
for field in partition:
    summary[field]['fraction_of_total_client_seconds'] = summary[field]['sum']/summary['client_complete']['sum']
assert abs(sum(summary[k]['sum'] for k in partition)-summary['client_complete']['sum']) < 1e-6
attempts = [a for r in rows for a in r['provider_attempts']]
reservation = sum(a['reserved_input_tokens_estimate'] for a in attempts)
reported_tokens = sum(a.get('input_tokens', 0) or 0 for a in attempts)
result = {'schema_version': 'arm-a-latency-offline-v1', 'run_id': 38128714743,
    'raw_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'decision': 'Owner selected Arm A on11October2026; B retained as historical comparator, C excluded.',
    'attempted': len(all_a), 'successful_denominator': len(rows),
    'failed_denominator': len(all_a)-len(rows), 'summary': summary,
    'additive_partition': partition,
    'share_basis': 'Sum of stage seconds divided by sum of client completion seconds over the same23 successful turns; means add, medians/p95 do not.',
    'rerank_turn_count': sum(r['rerank_attempts'] > 0 for r in records),
    'recovery_turn_count': sum(r['recovery_attempts'] > 0 for r in records),
    'startup_excluded': raw['startup_stages_seconds'],
    'cooldown_excluded': raw['pretrial_cooldown_seconds_excluded'],
    'successful_selection_reservation_bytes': reservation,
    'successful_reported_selection_input_tokens': reported_tokens,
    'reservation_bytes_per_reported_token': reservation/reported_tokens,
    'median_complete_case': sorted(records, key=lambda r:r['client_complete'])[len(records)//2],
    'three_slowest': sorted(records, key=lambda r:r['client_complete'], reverse=True)[:3],
    'rows': records,
    'limitations': ['Hosted worker actual loopbackHTTP/SSE, not public app.',
        'A and B shared limiter; cannot infer A-only latency from this alternating batch.',
        'No-pacing values are arithmetic, not observed unpaced speed.',
        'Provider active includes transport and parsing; not isolated GPU inference.',
        'Nested retrieval metrics overlap; do not add them to top-level retrieval.',
        'Failed turns are retained in raw and accuracy denominators; latency table only successful turns.',
        'No new provider requests, runtime change, deployment or billing change.']}
registry_path = ROOT/'human_review/agent_release_161/coordinator/approved_package_v3/candidate_registry.json'
registry = json.loads(registry_path.read_text(encoding='utf-8'))
result['approved_candidate_registry_sha256'] = hashlib.sha256(registry_path.read_bytes()).hexdigest()
steps = registry['steps']
steps = steps if isinstance(steps, dict) else {s['step_id']:s for s in steps}
claim_options = []
for r in rows:
    step = steps[r['step_id']]
    counts = [1+len(c.get('reviewed_wording_variants', [])) for c in step['claims']]
    claim_options.append({'record_id':r['record_id'], 'option_counts':counts,
        'all_singleton':all(n == 1 for n in counts)})
result['wording_options'] = claim_options
result['successful_turns_with_only_one_reviewed_option_per_claim'] = sum(r['all_singleton'] for r in claim_options)
parity = []
for r in rows:
    step = steps[r['step_id']]
    expected = [c['text'] for c in step['claims']]
    actual = [t for u in r['engineering_delivered_units'] for t in u['texts']]
    parity.append({'record_id':r['record_id'], 'exact_text_and_order_match':expected == actual})
assert all(x['exact_text_and_order_match'] for x in parity)
result['singleton_zero_choice_offline_wording_parity'] = parity
result['client_minus_pacing_and_provider_arithmetic_not_measured_fast_path'] = stats([
    r['client_complete']-r['provider_idle_pacing']-r['provider_active'] for r in records])
for target in (OUT/'measurements.json', PACKAGE/'ARM_A_LATENCY.json'):
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
with (OUT/'case_timings.csv').open('w', newline='', encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
print(json.dumps({k:v for k,v in result.items() if k not in ('rows','wording_options')}, indent=2))
