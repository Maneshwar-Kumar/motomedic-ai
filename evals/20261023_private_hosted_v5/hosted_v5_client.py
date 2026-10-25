"""Private hosted run of the 30-question experiment against the tagged v10.15 candidate API.

Runs only inside one allocated Cloud Build job (backend image, backend service
account). One POST per question, never retried; every saved view is validated
and compared with its stream and recovery, exactly as the existing engineering
client does. The candidate revision receives 0% public traffic. No provider
credential is handled here; the deployed worker uses its managed secret.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
TAGGED_API = re.compile(r'https://v15cand---motomedic-arm-a-279945185781\.us-central1\.run\.app')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as target:
        json.dump(value, target, indent=2, sort_keys=True, ensure_ascii=False)
        target.write('\n')


def main(args):
    if ROOT != Path('/workspace') or os.environ.get('MOTOMEDIC_HOSTED_PROVIDER_VALIDATION') != 'true':
        raise ValueError('HOSTED_ONLY_RUN_REQUIRED')
    job = os.environ.get('MOTOMEDIC_CLOUD_BUILD_ID')
    if not re.fullmatch(r'[0-9a-f-]{36}', job or '') or job != args.allocated_job_id:
        raise ValueError('EXACT_ALLOCATED_JOB_REQUIRED')
    if not TAGGED_API.fullmatch(args.api_url):
        raise ValueError('ONLY_THE_PRIVATE_TAGGED_CANDIDATE_API_ALLOWED')
    cases = json.loads((ROOT / args.cases).read_bytes())['cases']
    if args.only:
        wanted = set(args.only.split(','))
        cases = [c for c in cases if c['case_id'] in wanted]
        if {c['case_id'] for c in cases} != wanted:
            raise ValueError('UNKNOWN_CASE_SELECTION')
    order = {'GOLDEN': 0, 'PARTIAL': 1, 'NO_ANSWER': 2}
    cases = sorted((c for c in cases if c['group'] in order), key=lambda c: (order[c['group']], c['case_id']))
    sys.path[:] = ['/app'] + [p for p in sys.path if p != '/app']
    spec = importlib.util.spec_from_file_location('engineering_client',
        ROOT / 'tmp/public_evaluator/hosted_client_v10_13_v2.py')
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    sys.path[:] = ['/app'] + [p for p in sys.path if p != '/app']
    from rider_ui.client import validate_view, RUNTIME_POLICY
    from rider_ui.verified_sse import read_verified_stream, response_hash
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if list(output.iterdir()):
        raise ValueError('NEVER_OVERWRITE_RUN_OUTPUT')
    before = client.ledger('motomedic-ai-20261009')
    backend = client.Backend(args.api_url, os.environ['MOTOMEDIC_VISITOR_SECRET'])
    health = backend.request('GET', '/v1/health')
    if health.get('ready') is not True or health.get('answer_provider') != 'claude-haiku-5-5':
        raise ValueError('CANDIDATE_RUNTIME_NOT_READY')
    results = []
    try:
        for at, case in enumerate(cases):
            if at and args.min_interval_seconds:
                # Stay under the per-principal 6-turns-per-minute application cap.
                time.sleep(float(args.min_interval_seconds))
            key = uuid.uuid4().hex
            row = {'case_id': case['case_id'], 'group': case['group'], 'question': case['question'],
                   'operation_id': key, 'post_retries': 0, 'status': 'NOT_POSTED'}
            started = time.monotonic()
            try:
                payload = {'query': case['question'], 'bike_variant': 'Himalayan BS6', 'confirmed_himalayan_bs6': True,
                           'manual_checksum': 'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89',
                           'index_id': 'index_a3282c4d98cf54595e4ba168', 'cache_mode': 'bypass'}
                row['status'] = 'ONE_POST_DISPATCHED'
                value = backend.request('POST', '/v1/sessions', body=payload, operation=key)
                deadline = time.monotonic() + 1250
                while value.get('status') == 'RUNNING':
                    if value.get('operation_id') != key or time.monotonic() >= deadline:
                        raise ValueError('OPERATION_WAIT_EXHAUSTED_NO_POST_RETRY')
                    time.sleep(5)
                    value = backend.request('GET', '/v1/operations/' + key)
                view = validate_view(value, expected_policy=RUNTIME_POLICY)
                row.update(status='SAVED', saved_view=view, route=view['response']['type'])
                stream = backend.request('GET', '/v1/operations/' + key, sse=True)
                chunks = []
                try:
                    streamed = read_verified_stream(stream.iter_content(4096), operation_id=key,
                        on_chunk=chunks.append, expected_policy=RUNTIME_POLICY)
                finally:
                    stream.close()
                recovered = validate_view(backend.request('GET', '/v1/operations/' + key), expected_policy=RUNTIME_POLICY)
                row.update(exact_saved_stream=streamed == view, exact_recovered_view=recovered == view,
                           streamed_text=''.join(chunks), response_sha256=response_hash(view))
                if streamed == view and recovered == view:
                    row['status'] = 'SAVED_STREAMED_RECOVERED'
            except Exception as exc:
                row['error'] = client.safe_code(str(exc), 'LIVE_API_OR_DELIVERY_FAILURE')
                row['failure_class'] = type(exc).__name__
            row['elapsed_seconds'] = round(time.monotonic() - started, 2)
            save(output / ('case_' + case['case_id'] + '.json'), row)
            results.append({k: row.get(k) for k in ('case_id', 'group', 'status', 'route', 'error', 'elapsed_seconds')})
            print(json.dumps(results[-1]), flush=True)
    finally:
        backend.http.close()
        after = client.ledger('motomedic-ai-20261009')
        for doc, fields in (('grounded-primary-nonrecurring-v1', ('reserved_attempts', 'reserved_tokens')),
                            ('owner-haiku-fallback-20261011-validation-v1', ('reserved_nanodollars', 'reservation_count'))):
            if any(after[doc].get(f, 0) < before[doc].get(f, 0) for f in fields):
                raise ValueError('HISTORICAL_CHARGES_DECREASED')
        save(output / 'receipt.json', {'schema': 'motomedic-private-hosted-v5-run-receipt-v1', 'cloud_build_id': job,
            'api_url': args.api_url, 'health': health, 'cases_file_sha256': sha(ROOT / args.cases),
            'client_sha256': sha(__file__), 'results': results, 'ledger_before': before, 'ledger_after': after,
            'public_traffic_percent': 0, 'post_retries': 0, 'allocation_reset': False, 'allocation_refund': False,
            'raw_provider_bodies_logged': False, 'independent_factual_quality_acceptance': False})
        save(output / 'exit_status.json', {'cloud_build_id': job, 'cases_attempted': len(results)})
        client.upload_artifacts(args)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('--cases', '--api-url', '--output', '--allocated-job-id', '--artifact-uri'):
        parser.add_argument(name, required=True)
    parser.add_argument('--only', default='')
    parser.add_argument('--min-interval-seconds', default='0')
    try:
        sys.exit(main(parser.parse_args()))
    except Exception as exc:
        print(json.dumps({'failure_code': 'PRIVATE_HOSTED_V5_RUN_FAILED_NO_REPLAY', 'class': type(exc).__name__}), flush=True)
        sys.exit(1)
