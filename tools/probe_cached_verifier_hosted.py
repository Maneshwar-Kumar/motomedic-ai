"""Cloud Build-only exact verifier/schema/cache probe with persistent reservations.

Uses one already approved source anchor and a fixed nontechnical engineering ping.
No held-out question, source tuning, rider answer or raw provider content is logged.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import hashlib
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from constrained_generator import ValidationFailure
from evidence_registry import content_hash
from generation_providers import ProviderFailure
from cloud.grounded_generation.cached_verifier import CachedVerifier, CONTRACT, DRAFT_CONTRACT
from cloud.grounded_generation.verified_qa import (
    VERSION, VERIFY_POLICY, VERIFY_SCHEMA, FALLBACK_TEXT, compact_source_evidence, validate_verdict,
)

ANCHOR = 'evidence_13ff401422c8fc0d784d7e92'
QUESTION = 'Engineering-only verifier schema and prompt-cache ping; no technical rider answer is requested.'


def source_prefix(release_path, cache):
    from cloud.serving_artifacts import load_index
    from approved_registry import ApprovedEvidenceRegistry
    from cloud.grounded_generation.serving_source_authority import SourceAuthority
    release = json.loads(Path(release_path).read_bytes())
    index = load_index(release, cache)
    registry = ApprovedEvidenceRegistry.load(ROOT, index)
    authority = SourceAuthority(registry, index)
    authority.check()
    chunk = next((row for row in authority.chunks.values() if ANCHOR in row['evidence_ids']), None)
    if chunk is None:
        raise ValidationFailure('CAPABILITY_PROBE_APPROVED_ANCHOR_MISSING')
    assembled = authority.assemble({'index_id': authority.index_id,
        'manual_checksum': authority.checksum, 'hits': [deepcopy(chunk)]})
    admitted = authority.select(assembled, {ANCHOR})
    authority.validate(admitted)
    stable = {
        'runtime_contract': {'version': VERSION,
            'probe': 'fixed-nontechnical-schema-cache-v1',
            'draft_model_contract': deepcopy(DRAFT_CONTRACT),
            'verifier_contract': deepcopy(CONTRACT)},
        'full_evidence_payload_sha256': admitted['payload_sha256'],
        'source_projection': 'lossless-identical-orig-reference-v1',
        'manual_checksum': registry.checksum, 'index_id': registry.index_id,
        'source_authority_lock': admitted['authority_lock'],
        'evidence': compact_source_evidence(admitted['evidence']),
        'required_source_display': deepcopy(admitted['required_display']),
        'source_gaps': deepcopy(admitted['gaps']),
        'verified_oem_support': deepcopy(registry.source.get('oem_service_route')),
    }
    return stable


def ping(stable, operation_id, number):
    final = {'route': 'UNSUPPORTED', 'text': FALLBACK_TEXT,
             'claims': [{'claim_id': 'probe:neutral', 'text': FALLBACK_TEXT,
                         'role': 'LIMITATION', 'evidence_ids': []}],
             'citations': [], 'clarification_question': None,
             'escalation_uri': None, 'trace_id': None, 'session_status': 'OPEN'}
    binding = {'version': VERSION, 'operation_sha256': content_hash(operation_id),
               'probe_call': number, 'question_sha256': content_hash(QUESTION),
               'response_sha256': content_hash(final),
               'evidence_payload_sha256': stable['full_evidence_payload_sha256'],
               'source_authority_lock': stable['source_authority_lock'],
               'manual_checksum': stable['manual_checksum'], 'index_id': stable['index_id'],
               'draft_model_contract_sha256': content_hash(DRAFT_CONTRACT),
               'verifier_contract_sha256': content_hash(CONTRACT)}
    dynamic = {'question': QUESTION, 'history': {}, 'complete_proposed_response': final,
               'declared_question_coverage': 'NONE', 'unanswered_parts': [],
               'binding': binding, 'binding_sha256': content_hash(binding)}
    return dynamic


def run_probe(provider, admission, stable, operation_id):
    """Injected synthetic doubles may exercise this function; main is hosted-only."""
    calls = []
    receipt = {'schema_version': 'hosted-cached-verifier-capability-v1',
               'model': CONTRACT['model'], 'model_contract_sha256': content_hash(CONTRACT),
               'draft_model_contract_sha256': content_hash(DRAFT_CONTRACT),
               'runtime_version': VERSION,
               'code_sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                   for name in ('cloud/grounded_generation/cached_verifier.py',
                                'cloud/grounded_generation/verified_qa.py',
                                'tools/probe_cached_verifier_hosted.py')},
               'verify_policy_sha256': hashlib.sha256(VERIFY_POLICY.encode()).hexdigest(),
               'verify_schema_sha256': content_hash(VERIFY_SCHEMA),
               'evidence_payload_sha256': stable['full_evidence_payload_sha256'],
               'source_authority_lock': stable['source_authority_lock'],
               'operation_sha256': content_hash(operation_id),
               'manual_checksum': stable['manual_checksum'], 'index_id': stable['index_id'],
               'provider_calls': 0, 'cache_hit_proven': False,
               'quality_acceptance': False, 'rider_answer_released': False,
               'fallback_activated': False, 'allocation_reset': False, 'calls': calls}
    try:
        provider.context(VERIFY_POLICY, stable, ping(stable, operation_id, 1), VERIFY_SCHEMA)
        provider.begin_turn()  # Both worst-case writes reserved before generation.
        admission.begin_turn(content_hash({'scope': receipt['schema_version'],
                                          'operation_id': operation_id}), attempts=8)
        for number in (1, 2):
            dynamic = ping(stable, operation_id, number)
            value = provider.complete(VERIFY_POLICY, stable, dynamic, VERIFY_SCHEMA)
            receipt['provider_calls'] += 1
            accepted = validate_verdict(value.output, dynamic['binding'],
                dynamic['complete_proposed_response'], {'route':'UNSUPPORTED','coverage':'NONE'})
            if accepted or value.output['decision'] != 'SHOW_FALLBACK':
                raise ProviderFailure('CAPABILITY_PROBE_EXPECTED_NEUTRAL_VERDICT')
            trace = value.telemetry or {}
            if trace.get('model') != CONTRACT['model']:
                raise ProviderFailure('CAPABILITY_PROBE_MODEL_MISMATCH')
            # Scalars only; no verdict reasons, source bodies or raw result text.
            calls.append({k: deepcopy(trace[k]) for k in (
                'model', 'role', 'generation_calls', 'retry_count', 'input_tokens_counted',
                'input_tokens', 'uncached_input_tokens', 'cache_creation_input_tokens',
                'cache_read_input_tokens', 'cached_tokens', 'cache_hit_observed',
                'cached_prefix_sha256', 'output_tokens', 'estimated_cost_usd',
                'reserved_maximum_cost_usd', 'provider_seconds') if k in trace})
            calls[-1].update(binding_sha256=dynamic['binding_sha256'],
                             verdict_sha256=content_hash(value.output),
                             decision=value.output['decision'],
                             released=False)
        if (calls[0].get('cache_creation_input_tokens', 0) <= 0 or
                calls[1].get('cache_read_input_tokens', 0) <= 0 or
                calls[0].get('cached_prefix_sha256') != calls[1].get('cached_prefix_sha256')):
            raise ProviderFailure('CAPABILITY_PROBE_CACHE_HIT_NOT_DEMONSTRATED')
        receipt.update(cache_hit_proven=True, status='PASS',
                       total_estimated_cost_usd=sum(c['estimated_cost_usd'] for c in calls))
        return receipt
    except (ProviderFailure, ValidationFailure) as exc:
        receipt.update(status='FAIL', failure_code=str(exc))
        # Preserve uncertain-call count without exposing its request/response.
        trace = getattr(provider, 'last_trace', None) or {}
        receipt['provider_calls'] = max(receipt['provider_calls'],
            len(calls) + (trace.get('generation_calls', 0) if len(calls) < 2 else 0))
        return receipt
    finally:
        provider.end_turn()
        admission.end_turn()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--operation-id', required=True)
    parser.add_argument('--release', type=Path,
        default=ROOT/'reports/build/20261012/serving_manifest_v9_1.json')
    parser.add_argument('--output', type=Path, default=ROOT/'build/cached-verifier-capability.json')
    args = parser.parse_args()
    if (os.environ.get('MOTOMEDIC_HOSTED_PROVIDER_VALIDATION') != 'true' or
            not re.fullmatch(r'[0-9a-f-]{36}', os.environ.get('MOTOMEDIC_CLOUD_BUILD_ID', '')) or
            not ROOT.as_posix().startswith('/workspace')):
        raise RuntimeError('HOSTED_CLOUD_BUILD_EXECUTION_REQUIRED')
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,180}', args.operation_id):
        raise RuntimeError('CAPABILITY_PROBE_OPERATION_ID_INVALID')
    from google.cloud import firestore
    from cloud.grounded_generation.claude_budget import ClaudeBudget
    from cloud.grounded_generation.whole_turn_admission import WholeTurnAdmission, operation_deadline
    stable = source_prefix(args.release, ROOT/'build/provider-probe-index')
    client = firestore.Client(project=args.project)
    admission = WholeTurnAdmission(client)
    provider = CachedVerifier(admission, reserve_cost=ClaudeBudget(client))
    with operation_deadline(datetime.now(timezone.utc)+timedelta(seconds=1200)):
        receipt = run_probe(provider, admission, stable, args.operation_id)
    receipt['cloud_build_id'] = os.environ['MOTOMEDIC_CLOUD_BUILD_ID']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
