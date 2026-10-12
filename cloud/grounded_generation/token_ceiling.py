"""Separate owner authority for one legacy token-ceiling increase.

Default limits remain unchanged. Serving only reads a private grant committed
with the existing allocation; it never creates or applies an authorization.
The dormant maintainer function requires exact owner evidence and fresh counted
proposal bindings. No attempt, monetary, billing, event or counter reset exists.
"""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import re
import uuid

from evidence_registry import content_hash
from generation_providers import ProviderFailure
from cloud.grounded_generation.claude_budget import (
    ALLOCATION as HAIKU_ALLOCATION, validate_ledger as validate_haiku_ledger)

ALLOCATION = 'grounded-primary-nonrecurring-v1'
ALLOCATION_VERSION = 'whole-turn-capacity-v1'
DEFAULT_TOKEN_CEILING = 999200
MAX_TOKEN_CEILING = 3000000
MAX_ATTEMPTS = 100
GRANT_DOCUMENT = ALLOCATION + '-owner-token-ceiling-grant-v1'
GRANT_SCHEMA = 'motomedic-primary-token-ceiling-owner-grant-v1'
PROPOSAL_SCHEMA = 'motomedic-measured-primary-token-ceiling-proposal-v1'
OWNER_SCHEMA = 'motomedic-direct-owner-primary-token-ceiling-approval-v1'
OWNER_FIELDS = {'schema', 'authority', 'owner_approved', 'exact_owner_instruction', 'approved_at_utc',
    'proposal_sha256', 'maximum_tokens', 'only_primary_token_ceiling_change',
    'other_budgets_and_historical_charges_unchanged', 'billing_restart_authorized', 'refund_or_reset_authorized'}
MODEL_SCOPE_SHA = '65755e0a6b79f2df542c1c4b5f4f2e382a6857f7ee5ff5803d64988204e5ad0f'
PRIMARY_FIELDS = ('version', 'maximum_attempts', 'maximum_tokens', 'reserved_attempts', 'reserved_tokens')
HAIKU_FIELDS = ('version', 'maximum_nanodollars', 'reserved_nanodollars', 'reservation_count')
MEASURED_FIELDS = {'count_build_id', 'count_receipt_sha256', 'phase_budget_sha256',
    'serving_manifest_sha256', 'runtime_lock', 'required_token_ceiling',
    'required_attempts', 'required_haiku_nanodollars', 'conditional_strategy'}
GRANT_FIELDS = {'schema', 'authority', 'owner_approved', 'exact_owner_instruction',
    'approved_at_utc', 'approval_evidence', 'allocation_id', 'allocation_version',
    'previous_maximum_tokens', 'maximum_tokens', 'maximum_attempts',
    'haiku_maximum_nanodollars', 'project_lifetime_inr', 'billing_disconnect_inr',
    'billing_restart_authorized', 'refund_or_reset_authorized', 'model_scope_sha256',
    'measured', 'ledger_before', 'proposal_sha256', 'scope_sha256'}


def fail(code):
    raise ProviderFailure('PRIMARY_TOKEN_CEILING_' + code)


def _integer(value, low=0, high=MAX_TOKEN_CEILING):
    return type(value) is int and low <= value <= high


def _hex(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _owner_evidence(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:raise ValueError('duplicate owner field')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if type(value) is not dict:fail('OWNER_EVIDENCE_INVALID')
        return value
    except ProviderFailure:
        raise
    except Exception:
        fail('OWNER_EVIDENCE_INVALID')


def _ledger_snapshot(ledgers):
    if type(ledgers) is not dict or not {ALLOCATION, HAIKU_ALLOCATION} <= set(ledgers):
        fail('LEDGER_SNAPSHOT_INVALID')
    primary, haiku = ledgers[ALLOCATION], ledgers[HAIKU_ALLOCATION]
    if (type(primary) is not dict or primary.get('version') != ALLOCATION_VERSION or
            primary.get('maximum_attempts') != MAX_ATTEMPTS or
            primary.get('maximum_tokens') != DEFAULT_TOKEN_CEILING or
            not _integer(primary.get('reserved_attempts'), high=MAX_ATTEMPTS) or
            not _integer(primary.get('reserved_tokens'), high=DEFAULT_TOKEN_CEILING)):
        fail('LEDGER_SNAPSHOT_INVALID')
    validate_haiku_ledger(haiku)
    if type(haiku.get('maximum_nanodollars')) is not int:
        fail('LEDGER_SNAPSHOT_INVALID')
    return {ALLOCATION: {key: primary.get(key) for key in PRIMARY_FIELDS},
        HAIKU_ALLOCATION: {key: haiku.get(key, 0) for key in HAIKU_FIELDS}}


def make_proposal(budget, ledgers, *, conditional_strategy='ONE_LARGEST_CONDITIONAL_PHASE'):
    """Pure measured calculation; this object is explicitly not an approval."""
    before = _ledger_snapshot(ledgers)
    if (type(budget) is not dict or budget.get('schema') != 'motomedic-measured-initial-phase-capacity-v2' or
            budget.get('owner_model_scope_sha256') != MODEL_SCOPE_SHA or
            budget.get('allocation_reservations_refunded_or_reset') is not False or
            conditional_strategy not in ('ONE_LARGEST_CONDITIONAL_PHASE', 'ALL_CONDITIONAL_PHASES') or
            not all(_hex(budget.get(key)) for key in ('count_receipt_sha256', 'serving_manifest_sha256', 'runtime_lock'))):
        fail('MEASURED_PROPOSAL_INVALID')
    try:
        if str(uuid.UUID(budget['count_build_id'])) != budget['count_build_id']:
            fail('MEASURED_PROPOSAL_INVALID')
        rows = budget['case_forecasts']
        floor = budget['retained_floor']['required']
        if type(rows) is not list or len(rows) != 6:
            fail('MEASURED_PROPOSAL_INVALID')
        keys = ('attempts', 'tokens', 'haiku_nanodollars')
        values = [row[stage] for row in rows for stage in ('initial_totals', 'conditional_totals')] + [floor]
        if any(type(row) is not dict or set(row) != set(keys) or any(
                not _integer(row[key], high=1000000000) for key in keys) for row in values):
            fail('MEASURED_PROPOSAL_INVALID')
        initial = {key: sum(row['initial_totals'][key] for row in rows) for key in keys}
        conditional = {key: (sum(row['conditional_totals'][key] for row in rows)
            if conditional_strategy == 'ALL_CONDITIONAL_PHASES' else
            max(row['conditional_totals'][key] for row in rows)) for key in keys}
        required = {key: initial[key] + conditional[key] + floor[key] for key in keys}
    except (KeyError, TypeError, ValueError):
        fail('MEASURED_PROPOSAL_INVALID')
    minimum = before[ALLOCATION]['reserved_tokens'] + required['tokens']
    measured = {'count_build_id': budget['count_build_id'],
        'count_receipt_sha256': budget['count_receipt_sha256'], 'phase_budget_sha256': content_hash(budget),
        'serving_manifest_sha256': budget['serving_manifest_sha256'], 'runtime_lock': budget['runtime_lock'],
        'required_token_ceiling': minimum, 'required_attempts': required['attempts'],
        'required_haiku_nanodollars': required['haiku_nanodollars'], 'conditional_strategy': conditional_strategy}
    result = {'schema': PROPOSAL_SCHEMA, 'owner_approved': False, 'allocation_id': ALLOCATION,
        'previous_maximum_tokens': DEFAULT_TOKEN_CEILING, 'proposed_maximum_tokens': max(DEFAULT_TOKEN_CEILING, minimum),
        'compiled_maximum_tokens': MAX_TOKEN_CEILING, 'measured': measured, 'ledger_before': before,
        'initial_totals': initial, 'conditional_totals': conditional, 'retained_floor': deepcopy(floor),
        'attempts_and_money_eligible': before[ALLOCATION]['reserved_attempts'] + required['attempts'] <= MAX_ATTEMPTS and
            before[HAIKU_ALLOCATION]['reserved_nanodollars'] + required['haiku_nanodollars'] <= 1000000000,
        'within_compiled_token_ceiling': minimum <= MAX_TOKEN_CEILING,
        'provider_calls': 0, 'counter_writes': 0, 'billing_changes': 0}
    result['proposal_sha256'] = content_hash(result)
    return result


def validate_grant(grant):
    if type(grant) is not dict or set(grant) != GRANT_FIELDS:
        fail('GRANT_SCHEMA_INVALID')
    measured = grant['measured']
    if (grant['schema'] != GRANT_SCHEMA or grant['authority'] != 'DIRECT_OWNER_INSTRUCTION' or
            grant['owner_approved'] is not True or type(grant['exact_owner_instruction']) is not str or
            not 1 <= len(grant['exact_owner_instruction']) <= 4000 or
            grant['allocation_id'] != ALLOCATION or grant['allocation_version'] != ALLOCATION_VERSION or
            type(grant['previous_maximum_tokens']) is not int or grant['previous_maximum_tokens'] != DEFAULT_TOKEN_CEILING or
            not _integer(grant['maximum_tokens'], DEFAULT_TOKEN_CEILING + 1) or
            type(grant['maximum_attempts']) is not int or grant['maximum_attempts'] != MAX_ATTEMPTS or
            type(grant['haiku_maximum_nanodollars']) is not int or grant['haiku_maximum_nanodollars'] != 1000000000 or
            type(grant['project_lifetime_inr']) is not int or grant['project_lifetime_inr'] != 2700 or
            type(grant['billing_disconnect_inr']) is not int or grant['billing_disconnect_inr'] != 2540 or
            grant['billing_restart_authorized'] is not False or grant['refund_or_reset_authorized'] is not False or
            grant['model_scope_sha256'] != MODEL_SCOPE_SHA or not _hex(grant['proposal_sha256']) or
            not _hex(grant['scope_sha256']) or grant['scope_sha256'] != content_hash(
                {key: value for key, value in grant.items() if key != 'scope_sha256'}) or
            type(measured) is not dict or set(measured) != MEASURED_FIELDS or
            not all(_hex(measured.get(key)) for key in ('count_receipt_sha256', 'phase_budget_sha256',
                'serving_manifest_sha256', 'runtime_lock')) or
            not _integer(measured.get('required_token_ceiling'), DEFAULT_TOKEN_CEILING + 1) or
            measured['required_token_ceiling'] > grant['maximum_tokens'] or
            not _integer(measured.get('required_attempts'), high=MAX_ATTEMPTS) or
            not _integer(measured.get('required_haiku_nanodollars'), high=1000000000) or
            measured.get('conditional_strategy') not in ('ONE_LARGEST_CONDITIONAL_PHASE', 'ALL_CONDITIONAL_PHASES')):
        fail('GRANT_AUTHORITY_OR_BINDING_INVALID')
    try:
        approved = datetime.fromisoformat(grant['approved_at_utc'].replace('Z', '+00:00'))
        if approved.tzinfo is None or str(uuid.UUID(measured['count_build_id'])) != measured['count_build_id']:
            fail('GRANT_AUTHORITY_OR_BINDING_INVALID')
    except (ValueError, TypeError, AttributeError, KeyError):
        fail('GRANT_AUTHORITY_OR_BINDING_INVALID')
    evidence = grant['approval_evidence']
    if (type(evidence) is not dict or set(evidence) != {'path', 'sha256'} or not _hex(evidence['sha256']) or
            type(evidence['path']) is not str or not re.fullmatch(
                r'reports/public_evaluator/20261012/[a-zA-Z0-9_/-]+\.json', evidence['path']) or
            '..' in evidence['path']):
        fail('OWNER_EVIDENCE_INVALID')
    before = _ledger_snapshot(grant['ledger_before'])
    if (before != grant['ledger_before'] or
            before[ALLOCATION]['reserved_attempts'] + measured['required_attempts'] > MAX_ATTEMPTS or
            before[HAIKU_ALLOCATION]['reserved_nanodollars'] + measured['required_haiku_nanodollars'] > 1000000000):
        fail('NON_TOKEN_GUARD_EXCEEDED')
    return {'document_id': GRANT_DOCUMENT, 'schema': GRANT_SCHEMA, 'scope_sha256': grant['scope_sha256'],
        'previous_maximum_tokens': DEFAULT_TOKEN_CEILING, 'maximum_tokens': grant['maximum_tokens'],
        'approval_evidence_sha256': evidence['sha256'],
        'measured_count_receipt_sha256': measured['count_receipt_sha256']}


def resolve_token_ceiling(allocation, grant=None):
    """Read-only fail-closed consumption; never changes a ledger or Config lock."""
    if type(allocation) is not dict:
        fail('ALLOCATION_INVALID')
    maximum = allocation.get('maximum_tokens', DEFAULT_TOKEN_CEILING)
    if maximum == DEFAULT_TOKEN_CEILING and type(maximum) is int:
        if grant is not None or allocation.get('token_ceiling_authorization') is not None:
            fail('UNAPPLIED_OR_CHANGED_GRANT')
        return maximum, None
    binding = validate_grant(grant)
    if (type(maximum) is not int or maximum != binding['maximum_tokens'] or
            content_hash(allocation.get('token_ceiling_authorization')) != content_hash(binding)):
        fail('ALLOCATION_GRANT_BINDING_CHANGED')
    return maximum, binding


def grant_from_owner_evidence(proposal, *, owner_evidence_raw, evidence_path):
    """Construct an applicable grant only from exact explicit owner approval."""
    if (type(proposal) is not dict or proposal.get('schema') != PROPOSAL_SCHEMA or
            proposal.get('owner_approved') is not False or
            proposal.get('proposal_sha256') != content_hash({key: value for key, value in proposal.items()
                if key != 'proposal_sha256'}) or proposal.get('attempts_and_money_eligible') is not True or
            proposal.get('within_compiled_token_ceiling') is not True or type(owner_evidence_raw) is not bytes):
        fail('PROPOSAL_OR_OWNER_EVIDENCE_REQUIRED')
    owner = _owner_evidence(owner_evidence_raw)
    if (type(owner) is not dict or set(owner) != OWNER_FIELDS or owner['schema'] != OWNER_SCHEMA or
            owner['authority'] != 'DIRECT_OWNER_INSTRUCTION' or owner['owner_approved'] is not True or
            owner['proposal_sha256'] != proposal['proposal_sha256'] or
            owner['only_primary_token_ceiling_change'] is not True or
            owner['other_budgets_and_historical_charges_unchanged'] is not True or
            owner['billing_restart_authorized'] is not False or owner['refund_or_reset_authorized'] is not False or
            not _integer(owner['maximum_tokens'], proposal['proposed_maximum_tokens'])):
        fail('EXACT_OWNER_APPROVAL_REQUIRED')
    grant = {'schema': GRANT_SCHEMA, 'authority': owner['authority'], 'owner_approved': True,
        'exact_owner_instruction': owner['exact_owner_instruction'], 'approved_at_utc': owner['approved_at_utc'],
        'approval_evidence': {'path': evidence_path, 'sha256': sha256(owner_evidence_raw).hexdigest()},
        'allocation_id': ALLOCATION, 'allocation_version': ALLOCATION_VERSION,
        'previous_maximum_tokens': DEFAULT_TOKEN_CEILING, 'maximum_tokens': owner['maximum_tokens'],
        'maximum_attempts': MAX_ATTEMPTS, 'haiku_maximum_nanodollars': 1000000000,
        'project_lifetime_inr': 2700, 'billing_disconnect_inr': 2540,
        'billing_restart_authorized': False, 'refund_or_reset_authorized': False,
        'model_scope_sha256': MODEL_SCOPE_SHA, 'measured': deepcopy(proposal['measured']),
        'ledger_before': deepcopy(proposal['ledger_before']), 'proposal_sha256': proposal['proposal_sha256']}
    grant['scope_sha256'] = content_hash(grant)
    validate_grant(grant)
    return grant


def apply_authorized_grant(client, grant, *, owner_evidence_raw):
    """Dormant maintainer action. No caller may substitute authorization evidence."""
    binding = validate_grant(grant)
    if (type(owner_evidence_raw) is not bytes or
            sha256(owner_evidence_raw).hexdigest() != binding['approval_evidence_sha256']):
        fail('EXACT_OWNER_EVIDENCE_REQUIRED')
    # Revalidate exact approval fields, not only a hash-shaped reference.
    owner = _owner_evidence(owner_evidence_raw)
    if (set(owner) != OWNER_FIELDS or owner.get('schema') != OWNER_SCHEMA or owner.get('authority') != 'DIRECT_OWNER_INSTRUCTION' or
            owner.get('owner_approved') is not True or owner.get('maximum_tokens') != grant['maximum_tokens'] or
            owner.get('proposal_sha256') != grant['proposal_sha256'] or
            owner.get('exact_owner_instruction') != grant['exact_owner_instruction'] or
            owner.get('approved_at_utc') != grant['approved_at_utc'] or
            owner.get('only_primary_token_ceiling_change') is not True or
            owner.get('other_budgets_and_historical_charges_unchanged') is not True or
            owner.get('billing_restart_authorized') is not False or owner.get('refund_or_reset_authorized') is not False):
        fail('EXACT_OWNER_APPROVAL_REQUIRED')
    from google.cloud import firestore
    primary_ref = client.collection('arm_a_usage').document(ALLOCATION)
    grant_ref = client.collection('arm_a_usage').document(GRANT_DOCUMENT)
    money_ref = client.collection('arm_a_usage').document(HAIKU_ALLOCATION)

    @firestore.transactional
    def apply(tx):
        primary_snap, grant_snap, money_snap = (ref.get(transaction=tx) for ref in (primary_ref, grant_ref, money_ref))
        if not primary_snap.exists or not money_snap.exists:
            fail('EXISTING_LEDGER_REQUIRED')
        primary, money = primary_snap.to_dict(), money_snap.to_dict()
        validate_haiku_ledger(money)
        if grant_snap.exists:
            existing = grant_snap.to_dict()
            if content_hash(existing) != content_hash(grant):
                fail('GRANT_ALREADY_EXISTS_NO_REPLACEMENT')
            resolve_token_ceiling(primary, existing)
            return {'already_applied': True, 'writes': 0, 'authorization': binding}
        before = grant['ledger_before']
        if any(primary.get(key) != before[ALLOCATION][key] for key in PRIMARY_FIELDS) or any(
                money.get(key, 0) != before[HAIKU_ALLOCATION][key] for key in HAIKU_FIELDS):
            fail('FRESH_LEDGER_SNAPSHOT_CHANGED')
        resolve_token_ceiling(primary)
        updated = {**deepcopy(primary), 'maximum_tokens': binding['maximum_tokens'],
            'token_ceiling_authorization': deepcopy(binding)}
        tx.set(grant_ref, deepcopy(grant))
        tx.set(primary_ref, updated)
        return {'already_applied': False, 'writes': 2, 'authorization': binding,
            'primary_counters_retained': {key: updated[key] for key in ('reserved_attempts', 'reserved_tokens')}}

    try:
        return apply(client.transaction())
    except ProviderFailure:
        raise
    except Exception:
        fail('STORE_UNAVAILABLE_UNCERTAIN_NO_RESET')
