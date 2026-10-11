"""Matched hosted A/B benchmark: 30 frozen cases, no cache or retry."""
from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
import time
import architecture_benchmark as base
from approved_registry import ApprovedEvidenceRegistry, RELEASE_SHA
from approved_text_journeys import require_live_preflight
from online_retrieve import Retriever
from session_store import SQLiteSessionStore
from architecture_measurement import measured_sse_turn

ROOT = Path(__file__).resolve().parent
MAX_CALLS = 90
ALLOCATION = 'owner-ab30-initial-matched-v2'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def validate_authority():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('HOSTED_ONLY')
    proofpath = Path(os.environ['MOTOMEDIC_BUDGET_PREFLIGHT_FILE'])
    proof = read(proofpath)
    preflight = require_live_preflight(base.MODEL)
    reviewpath = ROOT / 'reports/ab30_v2_review.json'
    review = read(reviewpath)
    approval = read(ROOT / 'reports/ab30_v2_approval.json')
    if (review['decision'] != 'APPROVED_EXACT_AB30_ENGINEERING_RUN' or
        approval['review_sha256'] != sha(reviewpath) or
        approval['budget_sha256'] != sha(proofpath) or
        approval['decision'] != 'APPROVED_ONE_BOUNDED_AB30_RUN'):
        raise ValueError('EXACT_REVIEW_REQUIRED')
    if (proof.get('maximum_provider_calls') != MAX_CALLS or
        proof.get('allocation_id') != ALLOCATION or
        proof.get('maximum_live_runs') != 1 or proof.get('retries') != 0):
        raise ValueError('FRESH90CALL_ALLOCATION_REQUIRED')
    for group in ('code_sha256', 'source_sha256'):
        for name, expected in review[group].items():
            if sha(ROOT / name) != expected:
                raise ValueError('REVIEWED_BYTES_CHANGED:' + name)
    preflight.pop('calls_per_adapter', None)
    preflight['maximum_total_provider_calls'] = MAX_CALLS
    return preflight, review, approval

def evaluate(index, output):
    preflight, review, approval = validate_authority()
    cases = read(ROOT / 'reports/ab30_v1_cases.json')['cases']
    if len(cases) != 30 or len({c['record_id'] for c in cases}) != 30:
        raise ValueError('30_DISTINCT_REQUIRED')
    started = time.perf_counter()
    registry = ApprovedEvidenceRegistry.load(ROOT, index)
    registered = time.perf_counter()
    retriever = Retriever(index, rerank=False)
    loaded = time.perf_counter()
    retriever._load_reranker()
    config = replace(base.gemma_runtime_config(base.MODEL), max_output_tokens=400)
    capture = base.Capture(config)
    controller = base.ReviewedController(registry, retriever, response_generator=capture)
    controller.audience = 'end_user'
    session = replace(base.start_session(registry, [cases[0]['record_id']], registry.source['variant']), generation_lock=config.lock)
    controller.next(session, cases[0]['query'])
    if capture.allowed is None:
        raise ValueError('WARMUP_GATE_FAILED')
    warmed = time.perf_counter()
    base.MAX_CALLS = MAX_CALLS
    allocation = base.Allocation(paced=True)
    allocation.retry_used = 2  # Exhaust original retry permission before run: zero actual retries.
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    dbpath = output.with_suffix('.sessions.sqlite')
    report = {'schema_version': 'ab30-matched-result-v1', 'model': base.MODEL,
        'runtime_config': config.versions(), 'manual_checksum': registry.checksum,
        'index_id': registry.index_id, 'release_manifest_sha256': RELEASE_SHA,
        'registry_lock': registry.lock, 'review_sha256': sha(ROOT/'reports/ab30_v2_review.json'),
        'approval_sha256': sha(ROOT/'reports/ab30_v2_approval.json'),
        'cases_sha256': sha(ROOT/'reports/ab30_v1_cases.json'), 'budget_preflight': preflight,
        'maximum_provider_calls': 90, 'retries': 0, 'cache': 'BYPASS_EVERY_TURN',
        'architectures': ['A_COMPONENT_SELECTION', 'B_SHORT_GENERATION'],
        'warmup_seconds_excluded': warmed-started,
        'startup_stages_seconds': {'registry': registered-started, 'model_index_load': loaded-registered, 'reranker_and_first_query': warmed-loaded},
        'rows': [], 'scope': '30 reviewed initial LOOKUP cases; preselected intents; not held-out/general/vision/adaptive',
        'timing_boundary': 'HOSTED_WARM_QUERY_WORKER_ACTUAL_LOOPBACK_HTTP_SSE_NOT_PUBLIC_CLOUD_RUN_APP',
        'private_engineering_output_text_retained': True, 'public_source_delivery': False,
        'cloud_run_qdrant_setting_is_separate': True,
        'library_versions': {name: version(name) for name in ('torch','numpy','sentence-transformers','pypdfium2')},
        'started_at_utc': datetime.now(timezone.utc).isoformat()}
    def save():
        report['external_provider_attempts'] = allocation.calls
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    cooldown = time.perf_counter()
    time.sleep(60)
    report['pretrial_cooldown_seconds_excluded'] = time.perf_counter()-cooldown
    try:
        for n, case in enumerate(cases):
            order = report['architectures'] if n % 2 == 0 else list(reversed(report['architectures']))
            for architecture in order:
                received = []
                def produce(stream):
                    store = SQLiteSessionStore(dbpath)
                    store.db.execute('CREATE TABLE IF NOT EXISTS benchmark_deliveries (session_id TEXT, block INTEGER, session_version INTEGER, content_sha256 TEXT, evidence_ids TEXT, PRIMARY KEY(session_id,block))')
                    original = stream.deliver
                    def capture_delivery(unit):
                        original(unit)
                        received.append(json.loads(json.dumps(unit)))
                    stream.deliver = capture_delivery
                    try:
                        return base.run_sample(registry, retriever, config, allocation, store,
                            case['record_id'], case['query'], architecture, delivery_stream=stream, cache_bypass=True)
                    finally:
                        store.close()
                before = allocation.calls
                try:
                    row = measured_sse_turn(produce)
                except Exception as exc:
                    row = {'route': 'SYSTEM_ERROR', 'failure_class': type(exc).__name__,
                        'provider_attempts': [r for r in allocation.records if r['call'] > before],
                        'loopback_client_delivery': {'first_verified_output_seconds': None, 'complete_response_seconds': None}}
                row.update(record_id=case['record_id'], stratum=case['stratum'], architecture=architecture,
                    sample_order=len(report['rows'])+1, phase='INITIAL_EMPTY_CACHE', engineering_delivered_units=received)
                row['provider_requests_this_turn'] = allocation.calls-before
                report['rows'].append(row)
                save()
                print(json.dumps({'record_id': case['record_id'], 'architecture': architecture,
                    'route': row['route'], 'calls': allocation.calls,
                    'client_seconds': row['loopback_client_delivery']['complete_response_seconds']}), flush=True)
    finally:
        save()
    return report

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.index, args.output)
    raise SystemExit(0 if len(result['rows']) == 60 else 1)
