"""Prepare a measured proposal or apply separately recorded exact owner authority.

Preparing is local/provider-free. Applying requires an explicitly marked hosted
maintenance job, fresh exact owner evidence and the private original ledgers.
It cannot change attempt/USD1/INR controls, billing, events or reserved counters.
"""
import argparse
from datetime import datetime
import base64
from hashlib import sha256
import json
import os
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cloud.grounded_generation.token_ceiling import (
    ALLOCATION, GRANT_DOCUMENT, HAIKU_ALLOCATION, make_proposal,
    grant_from_owner_evidence, apply_authorized_grant, resolve_token_ceiling)
from evidence_registry import content_hash


def audit_value(value):
    """Lossless typed normalization for hashing every Firestore audit field."""
    if isinstance(value, datetime):
        precise = value.rfc3339() if callable(getattr(value, 'rfc3339', None)) else value.isoformat()
        return {'firestore_type': 'timestamp', 'value': precise}
    if type(value) is dict:
        if any(type(key) is not str for key in value):raise ValueError('FIRESTORE_AUDIT_MAP_KEY_INVALID')
        return {key: audit_value(item) for key, item in value.items()}
    if type(value) is list:return [audit_value(item) for item in value]
    if type(value) is bytes:return {'firestore_type': 'bytes', 'base64': base64.b64encode(value).decode('ascii')}
    if type(value) is float and not math.isfinite(value):
        return {'firestore_type': 'float', 'value': 'NaN' if math.isnan(value) else 'Infinity' if value > 0 else '-Infinity'}
    if type(value) in (str, int, float, bool, type(None)):return value
    # Other supported Firestore value kinds are hashed with complete identities.
    if type(value).__name__ == 'GeoPoint' and hasattr(value, 'latitude') and hasattr(value, 'longitude'):
        return {'firestore_type': 'geopoint', 'latitude': value.latitude, 'longitude': value.longitude}
    if type(value).__name__ == 'DocumentReference' and hasattr(value, 'path'):
        return {'firestore_type': 'reference', 'path': value.path,
            'project': value._client.project, 'database': value._client._database}
    raise ValueError('FIRESTORE_AUDIT_VALUE_UNSUPPORTED')


def document_audit(value, scalar_fields):
    normalized = audit_value(value)
    events = value.get('events', [])
    return {'scalars': {key: audit_value(value[key]) for key in scalar_fields if key in value},
        'complete_document_sha256': content_hash(normalized),
        'event_count': len(events), 'complete_events_sha256': content_hash(audit_value(events)),
        'all_document_fields_in_digest': True, 'raw_events_or_unrelated_metadata_saved': False}


def write_receipt(path, value):
    encoded = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as target:target.write(encoded)


def read(path):
    return json.loads(Path(path).read_bytes())


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='action', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--budget', required=True)
    prepare.add_argument('--ledgers', required=True)
    prepare.add_argument('--conditional-strategy', choices=(
        'ONE_LARGEST_CONDITIONAL_PHASE', 'ALL_CONDITIONAL_PHASES'), default='ONE_LARGEST_CONDITIONAL_PHASE')
    prepare.add_argument('--output', required=True)
    apply = commands.add_parser('apply-owner-approved')
    apply.add_argument('--proposal', required=True)
    apply.add_argument('--owner-evidence', required=True)
    apply.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():raise RuntimeError('NEVER_OVERWRITE_TOKEN_CEILING_RECEIPT')
    if args.action == 'prepare':
        result = make_proposal(read(args.budget), read(args.ledgers), conditional_strategy=args.conditional_strategy)
    else:
        if os.environ.get('MOTOMEDIC_HOSTED_TOKEN_LIMIT_MAINTENANCE') != 'true':
            raise RuntimeError('OWNER_APPROVED_APPLICATION_REQUIRES_EXPLICIT_HOSTED_MAINTENANCE_JOB')
        owner_path = Path(args.owner_evidence).resolve()
        relative = owner_path.relative_to(ROOT).as_posix()
        raw = owner_path.read_bytes()
        grant = grant_from_owner_evidence(read(args.proposal), owner_evidence_raw=raw, evidence_path=relative)
        pending = output.with_name(output.stem + '_application_pending' + output.suffix)
        if pending.exists():raise RuntimeError('APPLICATION_ALREADY_JOURNALED_REQUIRE_EXACT_READBACK')
        write_receipt(pending, {'schema': 'motomedic-owner-token-ceiling-application-pending-v1',
            'grant_scope_sha256': grant['scope_sha256'], 'approval_evidence_sha256': sha256(raw).hexdigest(),
            'intended_maximum_tokens': grant['maximum_tokens'],
            'application_result': 'UNKNOWN_UNTIL_TRANSACTION_AND_READBACK',
            'billing_or_other_budget_change_authorized': False})
        from google.cloud import firestore
        client = firestore.Client(project='motomedic-ai-20261009')
        result = apply_authorized_grant(client, grant, owner_evidence_raw=raw)
        collection = client.collection('arm_a_usage')
        primary = collection.document(ALLOCATION).get().to_dict()
        current_grant = collection.document(GRANT_DOCUMENT).get().to_dict()
        money = collection.document(HAIKU_ALLOCATION).get().to_dict()
        usage = collection.document('grounded-provider-global-v1').get().to_dict()
        maximum, binding = resolve_token_ceiling(primary, current_grant)
        if maximum != grant['maximum_tokens'] or binding != result['authorization']:
            raise RuntimeError('EXACT_TOKEN_CEILING_GRANT_READBACK_FAILED')
        result.update(schema='motomedic-owner-token-ceiling-application-receipt-v1', owner_approved=True,
            grant=grant, owner_evidence_sha256=sha256(raw).hexdigest(),
            application_pending_receipt_sha256=sha256(pending.read_bytes()).hexdigest(),
            primary_readback=document_audit(primary, ('version', 'maximum_tokens', 'maximum_attempts',
                'reserved_tokens', 'reserved_attempts', 'token_ceiling_authorization')),
            shared_haiku_readback=document_audit(money, ('version', 'model', 'maximum_nanodollars',
                'reserved_nanodollars', 'reservation_count')),
            rolling_usage_readback=document_audit(usage, ('controls_version',)),
            events_written=0, reserved_counters_reset_or_refunded=False,
            maximum_attempts_changed=False, shared_haiku_limit_changed=False,
            inr_guard_changed=False, billing_changed=False, provider_calls=0)
    write_receipt(output, result)
    print(json.dumps({'receipt': str(output.resolve()), 'owner_approved': result.get('owner_approved', False),
        'provider_calls': 0, 'counter_writes': result.get('writes', 0)}))


if __name__ == '__main__':main()
