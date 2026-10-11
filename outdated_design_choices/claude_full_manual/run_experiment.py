"""Private hosted architecture comparison; reference answers are evaluator-only."""
from collections import Counter
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from claude_transport import ClaudeTransport, preflight
import arm_a
import arm_b


def encode(obj):
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    raise TypeError(type(obj).__name__)


def persist(report):
    (HERE / 'experiment_results.json').write_text(json.dumps(report, indent=2, default=encode) + '\n', encoding='utf-8')


def main():
    os.environ['MOTOMEDIC_TEST_INDEX'] = str(HERE / 'registry_index')
    budget = preflight()
    cases = json.loads((HERE / 'rider_inputs.json').read_text(encoding='utf-8'))['cases']
    transport = ClaudeTransport(budget['selected_model'])
    transport.maximum_requests = budget['maximum_requests']
    transport.input_token_ceiling = budget['input_token_ceiling']
    report = {'schema_version': 'claude-cached-manual-eight-case-experiment-v1',
              'model': transport.model, 'rows': [], 'status': 'IN_PROGRESS',
              'manual_sha256': transport.manifest['source_sha256'],
              'markdown_sha256': transport.manifest['markdown_sha256'],
              'source_input': 'UNREPAIRED_MARKITDOWN_WITH_RECORDED_EXTRACTION_GAPS',
              'cache_policy': '5_MINUTE_TWO_NEUTRAL_ARM_PARTITIONS',
              'ceiling_usd': 4, 'inference_retries': 0,
              'eight_case_scope': 'REGRESSION_SMOKE_NOT_RELEASE_OR_HELD_OUT_ACCURACY',
              'comparison_limits': [
                  'Arm A has actual approved authored registry wording and scripted intent selection.',
                  'Arm B manages dialogue and facts autonomously from the same raw Markdown and policy.',
                  'This is a full architecture comparison, not attribution solely to controller presence.',
                  'Source conversion and existing controller gates may abstain on PDF-answerable cases.',
                  'Both return complete JSON before rider display; provider TTFT is reported separately.',
                  'Cache namespaces isolate independent cold source writes while preserving source and policy.',
              ]}
    persist(report)
    try:
        # Alternate architecture order on the repeat pass. Continuous requests keep
        # cache entries warm; actual usage counters determine cold/warm labels.
        for pass_id, order in [('first', ['A', 'B']), ('repeat', ['B', 'A'])]:
            for arm in order:
                transport.active_arm = arm
                rows = (arm_a if arm == 'A' else arm_b).run_cases(transport, cases, pass_id)
                report['rows'].extend(rows)
                persist(report)
        report['status'] = 'COMPLETED'
    except Exception as exc:
        report['status'] = 'SYSTEM_ERROR'
        report['controlled_error_class'] = type(exc).__name__
    report['request_ledger'] = transport.calls
    report['confirmed_usage_cost_usd'] = sum(c['estimated_cost_usd'] for c in transport.calls)
    report['request_count'] = len(transport.calls)
    report['dispatched_requests'] = transport.dispatched
    report['unknown_charge_upper_usd'] = transport.unknown_charge_upper_usd
    if transport.halted:
        report['status'] = 'SYSTEM_ERROR_INCOMPLETE_CHARGED_USAGE'
    # Evaluation reads goldens only AFTER all runtime calls are completed.
    references = json.loads((HERE / 'evaluator_goldens.json').read_text(encoding='utf-8'))['records']
    expected = {r['record_id']: r['expected_routes'] for r in references}
    for row in report['rows']:
        output = row['output'] or {}
        route = output.get('type')
        if isinstance(route, Enum):
            route = route.value
        row['expected_route'] = expected[row['record_id']][row['turn_index']]
        row['route_match'] = route == row['expected_route']
    summaries = []
    for arm in ['A_DETERMINISTIC_CONTROLLER', 'B_CLAUDE_MANAGED']:
        rows = [r for r in report['rows'] if r['arm'] == arm]
        times = [r['rider_visible_total_seconds'] for r in rows]
        summaries.append({'arm': arm, 'rider_turns': len(rows),
                          'route_matches': sum(r['route_match'] for r in rows),
                          'routes': dict(Counter(getattr((r['output'] or {}).get('type'), 'value', (r['output'] or {}).get('type')) for r in rows)),
                          'median_complete_response_seconds': statistics.median(times) if times else None,
                          'mean_complete_response_seconds': statistics.mean(times) if times else None,
                          'semantic_accuracy_status': 'PENDING_INDEPENDENT_SOURCE_ADJUDICATION'})
    report['summaries'] = summaries
    persist(report)
    print(json.dumps({'status': report['status'], 'model': report['model'],
                      'request_count': report['request_count'],
                      'confirmed_usage_cost_usd': report['confirmed_usage_cost_usd'], 'summaries': summaries}))


if __name__ == '__main__':
    main()
