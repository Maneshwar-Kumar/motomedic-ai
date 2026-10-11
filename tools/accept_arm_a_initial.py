"""Authenticated live initial API acceptance; never prints credentials or text.

Runs against an already deployed private service. Model inference is hosted.
The receipt preserves hashes, timing, route, event and Firestore commit evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

PROJECT = 'motomedic-ai-20261009'
GCLOUD = shutil.which('gcloud.cmd') or shutil.which('gcloud')
EXPECTED_URL = 'https://motomedic-arm-a-279945185781.us-central1.run.app'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Redirect refused; credentials never forwarded')


OPENER = build_opener(NoRedirect())


def token(kind):
    return subprocess.check_output([GCLOUD, 'auth', 'print-' + kind + '-token',
                                    '--project=' + PROJECT], text=True).strip()


def request(url, identity, *, body=None, key=None, accept='application/json'):
    headers = {'Authorization': 'Bearer ' + identity, 'Accept': accept}
    if key:
        headers['Idempotency-Key'] = key
    raw = None if body is None else json.dumps(body).encode()
    if raw is not None:
        headers['Content-Type'] = 'application/json'
    started = time.perf_counter()
    try:
        response = OPENER.open(Request(url, raw, headers), timeout=190)
    except HTTPError as exc:
        response = exc
    with response:
        chunks, events, first = [], [], None
        if response.headers.get_content_type() == 'text/event-stream':
            name = None
            for raw_line in response:
                line = raw_line.decode().strip()
                if line.startswith('event: '):
                    name = line[7:]
                elif line.startswith('data: '):
                    data = json.loads(line[6:])
                    events.append((name, data))
                    if name == 'verified_block' and first is None:
                        first = time.perf_counter()-started
        else:
            chunks = response.read(262145)
            if len(chunks) > 262144:
                raise ValueError('Response bound exceeded')
        return response.code, events, json.loads(chunks) if chunks else None, {
            'first_verified_text_seconds': first,
            'completion_seconds': time.perf_counter()-started,
            'replay': response.headers.get('X-Operation-Replay') == 'true'}


def firestore_get(collection, document, access):
    url = ('https://firestore.googleapis.com/v1/projects/' + PROJECT +
           '/databases/(default)/documents/' + collection + '/' + document)
    with OPENER.open(Request(url, headers={'Authorization': 'Bearer ' + access}), timeout=30) as r:
        return json.load(r)['fields']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.url != EXPECTED_URL:
        parser.error('Only the exact authorized project/service HTTPS origin is supported')
    identity, access = token('identity'), token('access')
    status, _, catalogue, _ = request(args.url + '/v1/initial-catalogue', identity)
    assert status == 200 and len(catalogue['questions']) == 30
    body = {k: catalogue[k] for k in ('bike_variant', 'manual_checksum', 'index_id')}
    assert any(q['record_id'] == 'GEN007' for q in catalogue['questions'])
    body.update(record_id='GEN007', confirmed_himalayan_bs6=True)
    key = uuid.uuid4().hex
    status, events, _, timing = request(args.url + '/v1/initial-answer/stream', identity,
                                       body=body, key=key, accept='text/event-stream')
    assert status == 200 and [n for n, _ in events] == ['verified_block', 'complete']
    block, view = [data for _, data in events]
    assert block['natural_language'] == view['response']['natural_language']
    assert block['cited_pages'] == view['response']['cited_pages']
    assert view['response']['type'] == 'SUPPORTED' and view['response']['release_gate_passed']
    assert view['provider_calls'] == 0
    assert 'That does not establish approval for fuel above E20.' in block['natural_language']
    assert all(1 <= c['pdf_page'] <= 149 and c['manual_checksum'] == catalogue['manual_checksum']
               and c['index_id'] == catalogue['index_id'] for c in block['cited_pages'])
    claims = json.loads(__import__('base64').urlsafe_b64decode(identity.split('.')[1] + '==='))
    owner = hashlib.sha256(('motomedic-arm-a-initial-v1:' + claims['sub']).encode()).hexdigest()
    op_id = hashlib.sha256((owner + ':' + key).encode()).hexdigest()
    op = firestore_get('arm_a_operations', op_id, access)
    session = firestore_get('arm_a_sessions', view['session_id'], access)
    assert op['state']['stringValue'] == 'COMPLETE'
    assert session['owner']['stringValue'] == owner
    assert int(session['version']['integerValue']) == view['version']
    status, replay_events, _, replay = request(args.url + '/v1/initial-answer/stream', identity,
                                               body=body, key=key, accept='text/event-stream')
    assert status == 200 and replay['replay'] and replay_events == events
    status, _, recovered, recovery = request(args.url + '/v1/initial-operations/' + key, identity)
    assert status == 200 and recovered == view
    status, _, conflict, _ = request(args.url + '/v1/initial-answer', identity,
                                    body={**body, 'record_id': 'GEN014'}, key=key)
    assert status == 409 and not conflict['technical_content']
    rejected = []
    for change in ({'bike_variant': 'wrong'}, {'manual_checksum': '0'*64},
                   {'confirmed_himalayan_bs6': False}, {'record_id': 'unknown'}):
        status, events, error, t = request(args.url + '/v1/initial-answer/stream', identity,
            body={**body, **change}, key=uuid.uuid4().hex, accept='text/event-stream')
        assert status == 400 and not events and not error['technical_content']
        rejected.append({'changed_fields': list(change), 'status': status, 'route': error['type']})
    receipt = {'schema_version': 'arm-a-hosted-initial-acceptance-v1',
        'url': args.url, 'operation_id': key, 'session_id': view['session_id'],
        'manual_checksum': catalogue['manual_checksum'], 'index_id': catalogue['index_id'],
        'events': [name for name, _ in events], 'technical_events': 1,
        'response_sha256': hashlib.sha256(json.dumps(view, sort_keys=True).encode()).hexdigest(),
        'technical_text_sha256': hashlib.sha256(block['natural_language'].encode()).hexdigest(),
        'initial_timing': timing, 'replay_timing': replay, 'recovery_timing': recovery,
        'firestore_operation_complete': True, 'firestore_session_version': view['version'],
        'replay_exact': True, 'conflicting_replay_rejected': True, 'scope_rejections': rejected,
        'provider_calls': 0, 'p95_established': False, 'cold_path_classification': 'UNCLASSIFIED',
        'ttl_physical_deletion_verified': False, 'owner_isolation_second_principal_verified': False,
        'full_rider_api_acceptance': False}
    receipt['events'] = ['verified_block', 'complete']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
