"""Verifier-only replay of exact A deliveries from run 38122505406.

Never composes, retrieves, rewrites a source approval, or deploys a service.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from datetime import datetime, timezone
from dataclasses import asdict, replace

from architecture_benchmark import CHECK_POLICY, CHECK_SCHEMA, MODEL, sized_schema
from approved_registry import ApprovedEvidenceRegistry
from approved_text_journeys import require_live_preflight
from benchmark_pacing import Admission, AdmissionFailure, POLICY
from constrained_generator import citations, strict_schema, ValidationFailure
from generation_providers import GeminiJSONProvider, gemma_runtime_config, ProviderFailure

RUN = 'reports/architecture_run_38122505406/architecture_comparison.json'
RUN_SHA = 'bfd7603c1dccb84d99613c8de647de9475da4f9675d75ccdfb583c915583ac83'
IDS = ('GEN003', 'EXP003', 'GEN026')
PREFIX = 'reports/a_semantic_audit_v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def obj_sha(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False).encode()).hexdigest()


def audit_config():
    return replace(gemma_runtime_config(MODEL), max_output_tokens=400)


def recover(registry):
    if sha(RUN) != RUN_SHA:
        raise ValueError('Original run changed')
    run = json.loads(Path(RUN).read_text(encoding='utf-8'))
    if registry.lock != run['registry_lock']:
        raise ValueError('Original registry lock changed')
    if hashlib.sha256(CHECK_POLICY.encode()).hexdigest() != run['experimental_prompt_sha256']['verify']:
        raise ValueError('Original verifier policy changed')
    if (run['model'] != MODEL or any(run['runtime_config'].get(k) != v for k, v in asdict(audit_config()).items()) or
            run['manual_checksum'] != registry.checksum or run['index_id'] != registry.index_id):
        raise ValueError('Original runtime/source binding changed')
    bundles = []
    for rid in IDS:
        rows = [x for x in run['rows'] + run['cache_repeat_rows']
                if x['record_id'] == rid and x['architecture'] == 'A_COMPONENT_SELECTION']
        if len(rows) != 2 or [x['phase'] for x in rows] != ['INITIAL_EMPTY_CACHE', 'IMMEDIATE_REPEAT']:
            raise ValueError('Initial/repeat provenance missing')
        initial, repeat = rows
        if any(x['route'] != 'SUPPORTED' for x in rows):
            raise ValueError('Original delivery missing')
        sid = initial['step_id']
        if repeat['step_id'] != sid or not registry.step_ready(sid):
            raise ValueError('Exact step approval missing')
        step = registry.step(sid)
        attempts = [x for x in initial['provider_attempts'] if x['kind'] == 'SELECT_COMPONENTS']
        if len(attempts) != 1:
            raise ValueError('Selection provenance ambiguous')
        choices = attempts[0]['output_diagnostics']['choices']['integer_values']
        if len(choices) != len(step.claims):
            raise ValueError('Selection length changed')
        texts = []
        claims = []
        for c, index in zip(step.claims, choices):
            wording = [c['text'], *c.get('reviewed_wording_variants', [])]
            if type(index) is not int or not 0 <= index < len(wording):
                raise ValueError('Selection index invalid')
            text = wording[index]
            texts.append(text)
            claims.append({'proposed': text, 'required_meaning': wording[0],
                           'role': c['response_role'], 'source_evidence':
                           [registry.evidence[e]['raw_object'] for e in c['evidence_ids']]})
        delivered_sha = hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode()).hexdigest()
        refs = citations(registry, step)
        for row in rows:
            if (len(row['delivered_blocks']) != 1 or
                    row['delivered_blocks'][0]['claim_indices'] != list(range(len(texts))) or
                    row['delivered_blocks'][0]['content_sha256'] != delivered_sha or
                    row['citation_count'] != len(refs) or
                    row['citation_closure_complete'] is not True or
                    row['immutable_citations_valid'] is not True):
                raise ValueError('Exact delivery/citation mismatch')
        if repeat['provider_attempts'] or repeat['semantic_cache'] != 'EXACT_AUTHORITY_VALIDATED_CANDIDATE_HIT':
            raise ValueError('Repeat provenance changed')
        policy = CHECK_POLICY + ' Both arrays must have exactly ' + str(len(texts)) + ' boolean entries.'
        schema = sized_schema(sized_schema(CHECK_SCHEMA, 'supported', len(texts)), 'complete', len(texts))
        payload = {'claims': claims, 'selected_kind': step.kind}
        bundles.append({'record_id': rid, 'step_id': sid, 'choices': choices,
                        'claim_ids': [c['claim_id'] for c in step.claims],
                        'claim_evidence_ids': [c['evidence_ids'] for c in step.claims],
                        'texts': texts, 'delivery_sha256': delivered_sha, 'citations': refs,
                        'policy': policy, 'payload': payload, 'schema': schema,
                        'verifier_input_sha256': obj_sha([policy, payload, schema]),
                        'provenance': [{'phase': x['phase'], 'sample_order': x['sample_order'],
                                        'content_sha256': x['delivered_blocks'][0]['content_sha256'],
                                        'cache': x['semantic_cache']} for x in rows],
                        'repeat_reuse_basis': 'EXACT_TEXT_SOURCE_MEANING_POLICY_SCHEMA_IDENTITY'})
    return bundles


def classify(output, count):
    try:
        strict_schema(output, CHECK_SCHEMA)
        if len(output['supported']) != count or len(output['complete']) != count:
            raise ValidationFailure('ARRAY_LENGTH')
    except ValidationFailure:
        return 'MALFORMED_SCHEMA'
    return ('VALID_ACCEPTANCE' if output['supported'] == [True] * count and
            output['complete'] == [True] * count and output['unsupported_additions'] is False
            else 'VALID_REJECTION')


def run(index, output, live=False):
    registry = ApprovedEvidenceRegistry.load('.', index)
    bundles = recover(registry)
    report = {'schema_version': 'a-post-facto-semantic-audit-v1',
              'original_run_id': '38122505406', 'original_run_sha256': RUN_SHA,
              'registry_lock': registry.lock, 'model': MODEL, 'runtime_config': asdict(audit_config()),
              'generation_calls': 0,
              'maximum_provider_calls': 3, 'retries': 0, 'fallback': False,
              'unique_bundles': len(bundles), 'original_deliveries': 6,
              'scope': 'THREE_EXACT_A_DELIVERIES_ONLY_NOT_CORPUS_OR_DEPLOYMENT',
              'rows': [], 'finished_at_utc': None}
    if live:
        if not os.environ.get('GITHUB_ACTIONS') == 'true':
            raise ValueError('Provider calls must run hosted')
        approval = json.loads(Path(PREFIX + '_approval.json').read_text())
        review = json.loads(Path(PREFIX + '_review.json').read_text())
        if (review['decision'] != 'APPROVED_EXACT_ENGINEERING_AUDIT' or
                approval['decision'] != 'APPROVED_EXACT_VERIFIER_ONLY_AUDIT' or
                approval['review_sha256'] != sha(PREFIX + '_review.json') or
                approval['budget_sha256'] != sha(PREFIX + '_budget.json')):
            raise ValueError('Fresh audit approval binding missing')
        for path, expected in review['file_sha256'].items():
            if sha(path) != expected:
                raise ValueError('Reviewed runtime changed: ' + path)
        if [x['verifier_input_sha256'] for x in bundles] != review['verifier_input_sha256']:
            raise ValueError('Exact verifier inputs changed')
        budget = json.loads(Path(PREFIX + '_budget.json').read_text(encoding='utf-8-sig'))
        expected_budget = {'schema_version': 'a-verifier-only-budget-v1',
                           'allocation_id': 'owner-a-exact-output-post-facto-verifier-v1',
                           'maximum_provider_calls': 3, 'retries': 0, 'maximum_live_runs': 1,
                           'old_v4_allocation_reused': False}
        if any(type(budget.get(k)) is not type(v) or budget[k] != v
               for k, v in expected_budget.items()):
            raise ValueError('Wrong verifier-only budget allocation')
        report['review_sha256'] = sha(PREFIX + '_review.json')
        report['approval_sha256'] = sha(PREFIX + '_approval.json')
        report['budget_sha256'] = sha(PREFIX + '_budget.json')
        report['hosted_run_id'] = os.environ.get('GITHUB_RUN_ID')
        report['hosted_run_attempt'] = os.environ.get('GITHUB_RUN_ATTEMPT')
        report['preflight'] = require_live_preflight(MODEL)
        if report['preflight']['preflight_sha256'] != approval['budget_sha256']:
            raise ValueError('Wrong allocation')
        provider = GeminiJSONProvider(MODEL, audit_config(), enabled=True, authorized_calls=3)
        admission = Admission()
        begin = time.monotonic()
        time.sleep(60)
        report['pretrial_cooldown_seconds'] = time.monotonic() - begin
        report['pacing_policy'] = {**POLICY, 'maximum_requests_this_run': 3,
                                   'maximum_transient_retries_total': 0,
                                   'maximum_retries_per_nonstream_call': 0}
    for b in bundles:
        row = {k: v for k, v in b.items() if k not in ('policy', 'payload', 'schema')}
        row['classification'] = 'OFFLINE_RECOVERY_ONLY'
        if live:
            started = time.monotonic()
            row['provider_attempted'] = False
            try:
                row['admission'] = admission.admit(b['policy'], b['payload'], b['schema'])
                calls_before = provider.remaining_calls
                result = provider.complete(b['policy'], b['payload'], b['schema'])
                row['verifier_output'] = result.output
                row['classification'] = classify(result.output, len(b['claim_ids']))
                row['telemetry'] = result.telemetry
            except AdmissionFailure as e:
                row['classification'] = 'OPERATIONAL_FAILURE'
                row['failure_reason'] = str(e)
                row['failure_stage'] = 'ADMISSION_BEFORE_PROVIDER'
                row['telemetry'] = None
            except ProviderFailure as e:
                row['classification'] = 'OPERATIONAL_FAILURE'
                row['failure_reason'] = str(e)
                row['telemetry'] = e.telemetry
            if 'calls_before' in locals():
                row['provider_attempted'] = provider.remaining_calls < calls_before
                del calls_before
            row['admission_and_provider_wall_seconds'] = time.monotonic() - started
            report['actual_provider_attempts'] = 3 - provider.remaining_calls
        report['rows'].append(row)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    report['actual_provider_attempts'] = 3 - provider.remaining_calls if live else 0
    report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    Path(output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--index', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--live', action='store_true')
    a = p.parse_args()
    run(a.index, a.output, a.live)
