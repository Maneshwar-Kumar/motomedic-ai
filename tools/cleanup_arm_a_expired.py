"""Bounded cloud cleanup for expired MotoMedic records only; dry-run by default.

Generic `versions` TTL is deliberately not enabled. This tool filters nested
snapshots by exact Arm A parent path and rechecks expiry before deleting.
Running it once does not establish a continuous physical-deletion SLA.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROJECT = 'motomedic-ai-20261009'
BASE = 'https://firestore.googleapis.com/v1/projects/'+PROJECT+'/databases/(default)/documents'
GROUPS = ('arm_a_operations', 'arm_a_sessions', 'arm_a_usage', 'versions', 'arm_a_session_versions')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Redirect refused')


def allowed_path(name):
    prefix = 'projects/'+PROJECT+'/databases/(default)/documents/'
    if not name.startswith(prefix):
        return False
    path = name[len(prefix):]
    patterns = (r'arm_a_(?:operations|sessions|usage)/[A-Za-z0-9_-]{1,128}',
                r'arm_a_sessions/[A-Za-z0-9_-]{1,128}/(?:versions|arm_a_session_versions)/[0-9]{1,12}')
    return any(re.fullmatch(pattern, path) for pattern in patterns)


def expires(doc, now):
    value = doc.get('fields', {}).get('expires_at', {}).get('timestampValue')
    if type(value) is not str:
        return False
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')) <= now
    except (ValueError, TypeError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    gcloud = shutil.which('gcloud.cmd') or shutil.which('gcloud')
    token = subprocess.check_output([gcloud, 'auth', 'print-access-token', '--project='+PROJECT],
                                    text=True).strip()
    opener = build_opener(NoRedirect())

    def call(url, body=None, method=None):
        raw = json.dumps(body).encode() if body is not None else None
        headers = {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'}
        with opener.open(Request(url, raw, headers, method=method), timeout=30) as res:
            data = res.read(8*1024*1024+1)
            if len(data) > 8*1024*1024:
                raise ValueError('Cleanup response bound exceeded')
            return json.loads(data) if data else {}

    now = datetime.now(timezone.utc)
    candidates = {}
    group_counts = {}
    for group in GROUPS:
        body = {'structuredQuery': {
            'select': {'fields': [{'fieldPath': '__name__'}, {'fieldPath': 'expires_at'}]},
            'from': [{'collectionId': group, 'allDescendants': True}], 'limit': 1000}}
        rows = call(BASE+':runQuery', body)
        documents = [r['document'] for r in rows if 'document' in r]
        if len(documents) == 1000:
            raise ValueError('Cleanup batch bound reached; no deletion performed')
        scoped = [doc for doc in documents if allowed_path(doc['name'])]
        group_counts[group] = {
            'total_documents': len(documents),
            'motomedic_documents': len(scoped),
            'expired_motomedic_documents': sum(expires(doc, now) for doc in scoped),
            'motomedic_documents_without_expiry_timestamp': sum(
                type(doc.get('fields', {}).get('expires_at', {}).get('timestampValue')) is not str
                for doc in scoped),
        }
        for doc in documents:
            if allowed_path(doc['name']) and expires(doc, now):
                candidates[doc['name']] = doc
    # Inventory every group before mutation; stop if any scan failed.
    deleted, already_missing, retained = [], [], []
    if args.apply:
        for name in sorted(candidates):
            url = 'https://firestore.googleapis.com/v1/'+name
            try:
                current = call(url)
            except HTTPError as exc:
                if exc.code != 404:
                    raise
                already_missing.append(name)
                continue
            if not allowed_path(name) or not expires(current, datetime.now(timezone.utc)):
                retained.append(name)
                continue
            # Update-time precondition prevents deleting an extended/corrected record.
            from urllib.parse import urlencode
            query = urlencode({'currentDocument.updateTime': current['updateTime']})
            call(url+'?'+query, method='DELETE')
            deleted.append(name)
    receipt = {'schema_version': 'arm-a-scoped-expiry-cleanup-v1', 'project': PROJECT,
               'checked_at': now.isoformat(), 'apply': args.apply,
               'group_counts': group_counts,
               'candidate_count': len(candidates), 'candidate_paths': sorted(candidates),
               'deleted_paths': deleted, 'already_missing_paths': already_missing,
               'retained_changed_paths': retained, 'shared_versions_ttl_enabled': False,
               'continuous_24h_physical_deletion_sla_verified': False,
               'raw_rider_content_recorded': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in receipt.items() if not k.endswith('_paths')}, indent=2))


if __name__ == '__main__':
    main()
