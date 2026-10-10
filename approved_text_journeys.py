"""Persistent approved text journeys; simulations and grounded provider runs distinct.

SQLite is an engineering harness store only. No manual ingestion/embedding runs here.
Live mode needs fresh root-owned budget evidence and finite two-call allocations for
composer and verifier. Scripted rider answers are explicit evaluation observations,
never facts imported from golden case fixtures or verified mechanical outcomes.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

from approved_runner import build_approved_runner
from approved_registry import ApprovedEvidenceRegistry, RELEASE_SHA
from constrained_generator import ConstrainedGenerator, SemanticSupportAdapter
from controller_contracts import Fact, Outcome, ResponseType
from diagnose import ReviewedService
from generation_providers import ProviderResult
from online_retrieve import Retriever
from reviewed_controller import ReviewedController
from session_store import SQLiteSessionStore


class SimulatedProvider:
    """Exact-wording software double; its verifier is NOT a semantic evaluation."""
    def __init__(self, judge=False):
        self.judge, self.calls = judge, 0

    def complete(self, policy, payload, schema):
        self.calls += 1
        if self.judge:
            output = {'claims': [{'claim_id': c['claim_id'], 'supported': True}
                                 for c in payload['claims']], 'unsupported_additions': False}
        else:
            output = {k: deepcopy(payload[k]) for k in
                      ('schema_version', 'route', 'step_id', 'kind', 'citations')}
            output['claims'] = [{'claim_id': c['claim_id'], 'text': c['wording'][0],
                                 'evidence_ids': c['evidence_ids']} for c in payload['claims']]
        return ProviderResult(output, 0, 0, None,
                              telemetry={'execution': 'SOFTWARE_SIMULATION_NO_PROVIDER'})


class SimulatedRetrieval:
    """Explicit complete bundle double using exact approved mandatory IDs."""
    def __init__(self, index):
        self.manifest = json.loads((Path(index) / 'manifest.json').read_text(encoding='utf-8'))
        self.calls = 0

    def reviewed_controller(self, registry, semantic_verifier=None):
        return ReviewedController(registry, self, semantic_verifier)

    def search(self, query, **kwargs):
        self.calls += 1
        sid = kwargs['step_id']
        required = kwargs['dependency_manifest']['steps'][sid]['required_evidence_ids']
        return {'index_id': self.manifest['index_id'],
                'manual_checksum': self.manifest['source_sha256'].lower(),
                'required_evidence_ids': list(required), 'attached_evidence_ids': list(required),
                'missing_evidence_ids': [], 'coverage_established': True,
                'retrieval_action': 'CONTINUE_GATES',
                'retrieval_policy': {'execution': 'SOFTWARE_SIMULATION_NO_RETRIEVAL',
                                     'required_evidence_ids': list(required),
                                     'attached_evidence_ids': list(required),
                                     'missing_evidence_ids': [], 'coverage_established': True}}


def require_live_preflight():
    """No provider call is permitted merely because --live was supplied."""
    if os.environ.get('MOTOMEDIC_GROUNDED_LIVE_AUTHORIZED') != '1':
        raise ValueError('Grounded live allocation not authorized')
    path = os.environ.get('MOTOMEDIC_BUDGET_PREFLIGHT_FILE')
    if not path:
        raise ValueError('Fresh budget preflight missing')
    proof = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    expected = {'project_id': 'motomedic-ai-20261009', 'live_calls_authorized': True,
                'main_billing_enabled': True, 'inference_billing_enabled': False,
                'billing_stop_guard_ready': True}
    if any(type(proof.get(k)) is not type(v) or proof[k] != v for k, v in expected.items()):
        raise ValueError('Budget/account preflight does not authorize this free-only allocation')
    checked = datetime.fromisoformat(proof['checked_at_utc'].replace('Z', '+00:00'))
    if checked.tzinfo is None:
        raise ValueError('Budget preflight lacks UTC offset')
    age = (datetime.now(timezone.utc) - checked).total_seconds()
    if not 0 <= age <= 1800:
        raise ValueError('Budget preflight is stale')
    return {'preflight_file': Path(path).name,
            'preflight_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'project_id': proof['project_id'], 'checked_at_utc': proof['checked_at_utc'],
            'main_billing_enabled': True, 'inference_billing_enabled': False,
            'billing_stop_guard_ready': True, 'calls_per_adapter': 2}


def _citation_check(registry, record_id, response):
    sid = registry._consumer.routes[record_id].get('step_id')
    required = set(registry.step(sid).required_evidence_ids) if sid else set()
    cited = {c['evidence_id'] for c in response.cited_pages}
    valid = all(c.get('manual_checksum') == registry.checksum and
                c.get('index_id') == registry.index_id and
                c.get('pdf_page_index') == c.get('pdf_page', 0) - 1 and
                any(p.get('page_no', p.get('pdf_page')) == c.get('pdf_page')
                    for p in registry.evidence.get(c['evidence_id'], {}).get('provenance', []))
                and 'evidence_uri' not in c for c in response.cited_pages)
    return {'immutable_citations_valid': bool(response.cited_pages) and valid,
            'citation_closure_complete': bool(required) and required <= cited,
            'required_evidence_ids': sorted(required), 'cited_evidence_ids': sorted(cited)}


def evaluate(index, output, live=False):
    root = Path(__file__).resolve().parent
    index, output = Path(index).resolve(), Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    preflight = require_live_preflight() if live else None
    traces, rows, checks = [], [], []
    started = time.perf_counter()
    if live:
        controller = build_approved_runner(index, root=root, live=True, calls_per_adapter=2)
        registry, retrieval, pipeline = (controller.registry, controller.retriever,
                                         controller.response_generator)
    else:
        registry = ApprovedEvidenceRegistry.load(root, index)
        retrieval = SimulatedRetrieval(index)
        pipeline = ConstrainedGenerator(SimulatedProvider(), SemanticSupportAdapter(SimulatedProvider(judge=True)))
    # Preserve the snapshots so another process can inspect typed engineering state.
    store_path = output.with_suffix('.sessions.sqlite')
    store = SQLiteSessionStore(str(store_path))
    service = ReviewedService(registry, retrieval, store, response_generator=pipeline,
                              trace_sink=lambda t: traces.append(deepcopy(t)))
    warm_started = time.perf_counter()

    def check(name, passed):
        checks.append({'check': name, 'passed': bool(passed)})

    def turn(session, record_id, query, expected, **kwargs):
        begin = time.perf_counter()
        updated, response, _ = service.turn(session.session_id, query, **kwargs)
        row = {'record_id': record_id, 'expected_route': expected, 'route': response.type.value,
               'route_correct': response.type.value == expected,
               'reason_codes': list(response.reason_codes),
               'suggested_step_id': response.suggested_step_id,
               'session_version': updated.version if updated is not None else None,
               'citation_metadata': list(response.cited_pages),
               'validated_claim_ids': [c['claim_id'] for c in response.claim_evidence_map],
               'verified_service_uri': response.escalation_uri,
               'confirmed_input_to_releasable_response_seconds': time.perf_counter() - begin,
               'technical_text_published_only_after_validation_and_session_save': True,
               'raw_rider_input_recorded': False}
        if response.type == ResponseType.SUPPORTED and response.claim_evidence_map:
            row.update(_citation_check(registry, record_id, response))
        rows.append(row)
        check(record_id + ':' + str(len(rows)) + ':route', row['route_correct'])
        return updated, response

    try:
        lookup = service.start('GEN003', registry.source['variant'])
        lookup, direct = turn(lookup, 'GEN003',
                              'Cars in my mirrors look farther away than they really are. Is that described?',
                              'SUPPORTED')
        check('GEN003 immutable citations and full mandatory closure',
              rows[-1].get('immutable_citations_valid') and rows[-1].get('citation_closure_complete'))
        check('GEN003 persisted reload', lookup is not None and store.load(lookup.session_id) == lookup)

        signal = service.start('EXP003', registry.source['variant'])
        signal, clarify = turn(signal, 'EXP003', 'How do I cancel the turn signal?', 'AMBIGUOUS')
        check('EXP003 unknown emits one source-derived question',
              bool(clarify.clarification_question) and not clarify.claim_evidence_map and
              not clarify.suggested_step_id)
        clarification_generation = deepcopy(service.last_trace.get('generation_validation')) if service.last_trace else None
        check('EXP003 unknown has zero composer/verifier requests',
              clarification_generation is None or clarification_generation.get('generation_calls', 0) == 0)
        # Explicit scripted rider reply, not imported from the golden fixture.
        signal = service.feedback(signal.session_id, Outcome.OBSERVED_NORMAL, 'scripted-rider-centred',
                                  fact=Fact(True, 'BOOLEAN'))
        signal, action = turn(signal, 'EXP003', 'I can see that the turn switch has returned to centre.', 'SUPPORTED')
        check('EXP003 immutable citations and full mandatory closure',
              rows[-1].get('immutable_citations_valid') and rows[-1].get('citation_closure_complete'))
        issued_action = action.suggested_step_id
        if issued_action:
            signal = service.feedback(signal.session_id, Outcome.ACTION_COMPLETED_UNRESOLVED,
                                      'scripted-rider-tried-unresolved')
            # Close/reopen the engineering database to prove persistence across handles.
            store.close()
            store = SQLiteSessionStore(str(store_path))
            service.store = store
            restored = store.load(signal.session_id)
            check('EXP003 persisted typed unresolved action', restored == signal and any(
                a.step_id == issued_action and a.outcome_enum == Outcome.ACTION_COMPLETED_UNRESOLVED and
                not a.observed_details for a in restored.active_attempts()))
            check('Unresolved action cannot create a normal fact',
                  all(not a.observed_details for a in restored.active_attempts()
                      if a.outcome_enum == Outcome.ACTION_COMPLETED_UNRESOLVED))
            signal, escalation = turn(restored, 'EXP003', 'I pushed it inward, but the signal still remains on.', 'UNSUPPORTED')
            check('EXP003 verified support with no approved successor',
                  escalation.escalation_uri == registry.support_uri() and bool(escalation.escalation_uri) and
                  'NO_APPROVED_NEXT_STEP_AFTER_UNRESOLVED_ACTION' in escalation.reason_codes)
            signal, repeated = turn(signal, 'EXP003', 'The same problem remains.', 'UNSUPPORTED')
            check('No repeated action after unresolved', not repeated.suggested_step_id and not repeated.claim_evidence_map)
        else:
            check('EXP003 action issued before feedback', False)
        unsupported = service.start('GEN003', registry.source['variant'])
        unsupported, response = turn(unsupported, 'GEN003', 'Show an undocumented electrical bypass.',
                                     'UNSUPPORTED', unsupported_request=True)
        check('Unsupported request releases no technical steps', not response.claim_evidence_map and not response.suggested_step_id)
    except Exception as exc:
        # Preserve controlled failure evidence without raw provider errors or inputs.
        checks.append({'check': 'journey boundary', 'passed': False, 'error_class': type(exc).__name__})
    finally:
        store.close()

    grounded = [r for r in rows if r['expected_route'] == 'SUPPORTED']
    grounded_successes = [r for r in grounded if r['route'] == 'SUPPORTED' and r.get('immutable_citations_valid') and r.get('citation_closure_complete')]
    report = {'schema_version': 'approved-text-journeys-v1',
              'execution': 'GROUNDED_EXTERNAL_PROVIDER_WITH_SCRIPTED_RIDER' if live else 'SOFTWARE_SIMULATION',
              'approval_manifest_sha256': RELEASE_SHA, 'index_id': registry.index_id,
              'manual_checksum': registry.checksum, 'registry_lock': registry.lock,
              'runtime_versions': pipeline.config.versions(), 'runtime_lock': pipeline.config.lock,
              'rider_answers': 'EXPLICIT_SCRIPTED_EVALUATION_OBSERVATIONS_NOT_FIXTURE_FACTS',
              'storage': {'backend': 'SQLite', 'scope': 'ENGINEERING_HARNESS_ONLY',
                          'file': store_path.name, 'hosted_durable_store_claimed': False},
              'preflight': preflight, 'rows': rows, 'checks': checks, 'traces': traces,
              'passed': bool(checks) and all(c['passed'] for c in checks),
              'grounded_external_composer_attempts': (2 - pipeline.provider.remaining_calls) if live else 0,
              'grounded_external_verifier_attempts': (2 - pipeline.verifier.provider.remaining_calls) if live else 0,
              'grounded_external_provider_attempts': ((2 - pipeline.provider.remaining_calls) +
                  (2 - pipeline.verifier.provider.remaining_calls)) if live else 0,
              'composer_gate_invocations': sum(t.get('generation_validation', {}).get('generation_calls', 0)
                  for t in traces if isinstance(t.get('generation_validation'), dict)),
              'grounded_external_provider_verified_answers': len(grounded_successes) if live else 0,
              'simulated_verified_answers': len(grounded_successes) if not live else 0,
              'complete_evidence_gate_passes': len(grounded_successes),
              'answerable_provider_requests': len(grounded),
              'first_request_in_process_cold': True,
              'startup_seconds': warm_started - started,
              'total_seconds': time.perf_counter() - started,
              'representative_grounded_warm_cold_p95': 'NOT_ESTABLISHED_TWO_ANSWER_SAMPLE',
              'semantic_quality': 'PROVIDER_VERIFIER_GATED_NOT_INDEPENDENT_HELD_OUT_EVALUATION' if live else 'NOT_MEASURED_SYNTHETIC_JUDGE',
              'provider_cost_usd': None if live else 0,
              'provider_cost_status': 'NOT_VERIFIED_PRICING_OR_BILLING' if live else 'NO_EXTERNAL_CALLS',
              'mechanical_repairs_verified': 0, 'manual_reparsed_or_reembedded': False,
              'raw_rider_media_or_queries_recorded': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'passed': report['passed'],
                      'execution': report['execution'],
                      'external_verified_answers': report['grounded_external_provider_verified_answers']}))
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    result = evaluate(args.index, args.output, args.live)
    raise SystemExit(0 if result['passed'] else 1)
