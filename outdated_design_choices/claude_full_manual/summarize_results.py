"""Recompute comparable timing and spend from the frozen hosted artifact."""
from collections import Counter
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def distribution(values):
    return {'n': len(values), 'median_seconds': statistics.median(values) if values else None,
            'min_seconds': min(values) if values else None,
            'max_seconds': max(values) if values else None}


def main():
    result = json.loads((HERE / 'experiment_results.json').read_text(encoding='utf-8'))
    calls = result['request_ledger']
    keys = ['input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens']
    assert len(result['rows']) == 40 and len(calls) == result['dispatched_requests'] == 28
    assert result['unknown_charge_upper_usd'] == 0
    assert all(all(k in c['usage'] for k in keys) and c['stop_reason'] == 'end_turn' for c in calls)
    total = sum(c['estimated_cost_usd'] for c in calls)
    assert abs(total - result['confirmed_usage_cost_usd']) < 1e-10
    # Same observed outputs, every observed input billed at the uncached input
    # rate. A cost counterfactual only, not an uncached latency experiment.
    no_cache = sum((sum(c['usage'][k] for k in keys[:3]) * .1 + c['usage']['output_tokens'] * .5) / 1e6 for c in calls)
    report = {'model': result['model'], 'cost_basis': 'PROVIDER_REPORTED_TOKENS_TIMES_PUBLISHED_RATES_NOT_BILLING_RECONCILIATION',
              'total_estimated_cost_usd': total, 'same_usage_no_cache_cost_counterfactual_usd': no_cache,
              'cost_reduction_against_same_usage_counterfactual_percent': 100 * (1 - total / no_cache),
              'cache_states': dict(Counter(c['cache_state'] for c in calls)),
              'token_totals': {k: sum(c['usage'][k] for c in calls) for k in keys}, 'arms': []}
    for arm in ['A', 'B']:
        rows = [r for r in result['rows'] if r['arm'].startswith(arm + '_')]
        generated = [r for r in rows if r['provider_request_count'] > 0]
        warm = [r for r in generated if all(c['cache_state'] == 'HIT' for c in r['provider_calls'])]
        cold = [r for r in generated if any(c['cache_state'] == 'MISS' for c in r['provider_calls'])]
        gated = [r for r in rows if r['provider_request_count'] == 0]
        ac = [c for c in calls if c['arm'] == arm]
        report['arms'].append({'arm': arm, 'rider_turns': len(rows), 'route_matches': sum(r['route_match'] for r in rows),
            'provider_requests': len(ac), 'estimated_cost_usd': sum(c['estimated_cost_usd'] for c in ac),
            'all_model_generated_complete_response': distribution([r['rider_visible_total_seconds'] for r in generated]),
            'warm_model_generated_complete_response': distribution([r['rider_visible_total_seconds'] for r in warm]),
            'cold_model_generated_complete_response': distribution([r['rider_visible_total_seconds'] for r in cold]),
            'zero_call_response': distribution([r['rider_visible_total_seconds'] for r in gated]),
            'warm_provider_ttft': distribution([c['ttft_seconds'] for c in ac if c['cache_state'] == 'HIT'])})
    report['latency_limits'] = ['Complete response includes free token-count request overhead.',
        'No partial unvalidated output is displayed; provider TTFT is separate.',
        'A generated turns include composer and verifier; B has one request.',
        'Only one cold rider response per arm; no causal latency improvement or stable p95 is established.',
        'No uncached latency control was run.']
    (HERE / 'comparison_metrics.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
