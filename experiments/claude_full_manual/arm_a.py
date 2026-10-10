"""Isolated actual-controller architecture adapter; no golden evaluator imports.

Arm A additionally has bound registry metadata and approved authored wording.
Consequently this compares complete architectures, not the isolated effect of
a controller. Semantic provider evidence uses only common Markdown page text.
Known conversion-association gaps fail closed. No BGE, BM25, embedding, or manual
ingestion runs here.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import time

from approved_registry import ApprovedEvidenceRegistry
from constrained_generator import ConstrainedGenerator, SemanticSupportAdapter
from controller_contracts import Fact, Outcome
from diagnose import ReviewedService
from generation_contracts import RuntimeConfig
from generation_contracts import VERIFICATION_POLICY, VERIFIER_SCHEMA
from constrained_generator import strict_schema, ValidationFailure
from generation_providers import ProviderFailure, ProviderResult
from reviewed_controller import ReviewedController, append_attempt, compare
from controller_contracts import Truth
from session_store import SQLiteSessionStore


ROOT = Path(__file__).resolve().parents[2]
MANUAL = Path(__file__).with_name('royal-enfield-himalayan-450-owner-manual.md')
ARCHITECTURE = 'CASE_SELECTED_APPROVED_RESPONSE_COMPOSITION_WITH_ACTUAL_CONTROLLER'


class CachedClaudeProvider:
    """Translate the common experiment transport to the unchanged provider API."""
    def __init__(self, transport, role, pass_id):
        self.transport, self.role, self.pass_id = transport, role, pass_id
        self.calls = []

    def complete(self, policy, payload, schema):
        try:
            result = self.transport.complete_json(
                policy, payload, schema, max_tokens=1800,
                tag=f'A:{self.pass_id}:{self.role}:{len(self.calls) + 1}')
        except Exception:
            # Transport owns safe error/usage accounting. Do not expose bodies.
            self.calls.append({'output': None, 'usage': {}, 'total_seconds': None,
                               'ttft_seconds': None, 'estimated_cost_usd': None,
                               'transport_failed': True,
                               'provider_attempt_count': 1})
            raise ProviderFailure('PROVIDER_REQUEST_FAILED') from None
        self.calls.append(deepcopy(result))
        usage = result.get('usage') or {}
        input_tokens = sum(usage.get(k, 0) for k in
                           ('input_tokens', 'cache_creation_input_tokens',
                            'cache_read_input_tokens'))
        telemetry = {k: deepcopy(result.get(k)) for k in
                     ('usage', 'total_seconds', 'ttft_seconds', 'estimated_cost_usd')}
        telemetry['experiment_role'] = self.role
        return ProviderResult(result['output'], input_tokens,
                              usage.get('output_tokens'),
                              result.get('estimated_cost_usd'), telemetry)


class BoundManualAssembly:
    """Complete-manual presence plus exact registry authority; not similarity."""
    def __init__(self, registry, index, markdown):
        self.registry = registry
        self.manifest = json.loads((index / 'manifest.json').read_text(encoding='utf-8'))
        self.pages = {int(n) for n in re.findall(r'<!-- PDF_PAGE:(\d+) -->', markdown)}
        self.evidence = registry.reviewed_evidence()
        self.reviewed_scope = registry.source
        self.calls = 0
        qa = json.loads(MANUAL.with_name('case_conversion_review.json').read_text(encoding='utf-8'))
        if qa['markdown_sha256'] != hashlib.sha256(MANUAL.read_bytes()).hexdigest():
            raise ValueError('Markdown conversion review binding changed')
        self.case_reviews = {c['record_id']: c for c in qa['cases']}

    def reviewed_controller(self, registry, semantic_verifier=None):
        return ConversionGatedController(registry, self, semantic_verifier)

    def conversion_ready(self, record_id):
        return self.case_reviews.get(record_id, {}).get('verdict') in (
            'REQUIRED_PASSAGES_CLEAR', 'REQUIRED_PASSAGES_CLEAR_WITH_FOOTER_INTERRUPTION',
            'REQUIRED_SAFETY_PASSAGES_CLEAR_ON_PAGE_66')

    def search(self, query, **kwargs):
        self.calls += 1
        sid = kwargs['step_id']
        step = self.registry.step(sid)
        manifest = kwargs['dependency_manifest']
        declared = manifest['steps'][sid]['required_evidence_ids']
        required = list(step.required_evidence_ids)
        # Page presence alone NEVER establishes reviewed dependency sufficiency.
        approved = (self.registry.source_ready() and self.registry.step_ready(sid)
                    and set(declared) == set(required) and bool(required))
        record_id = self.registry.candidate['steps'][sid]['canonical_record_id']
        review = self.case_reviews.get(record_id, {})
        qa_complete = self.conversion_ready(record_id)
        approved = approved and qa_complete
        attached = []
        for eid in required:
            evidence = self.registry.evidence.get(eid, {})
            pages = [p.get('page_no', p.get('pdf_page'))
                     for p in evidence.get('provenance', [])]
            if (approved and self.registry.evidence_ready(eid) and pages
                    and all(p in self.pages for p in pages)):
                attached.append(eid)
        missing = sorted(set(required) - set(attached))
        complete = approved and not missing
        policy = {'execution': 'EXACT_BOUND_SOURCE_ASSEMBLY_NO_EMBEDDINGS',
                  'authority': 'SCOPED_REGISTRY_PLUS_CASE_MARKDOWN_QA_NOT_PAGE_PRESENCE',
                  'required_evidence_ids': required, 'attached_evidence_ids': attached,
                  'missing_evidence_ids': missing, 'coverage_established': complete,
                  'full_manual_page_presence_checked': True,
                  'markdown_only_semantic_completeness_claimed': False,
                  'conversion_review_verdict': review.get('verdict', 'MISSING_REVIEW'),
                  'source_review_required': not qa_complete,
                  'source_gap_rider_resolvable': False}
        return {**policy, 'index_id': self.registry.index_id,
                'manual_checksum': self.registry.checksum,
                'retrieval_action': 'CONTINUE_GATES' if complete else 'ABSTAIN',
                'retrieval_policy': policy}


class ConversionGatedController(ReviewedController):
    """Source conversion gaps are internal abstentions, never rider questions."""
    def next(self, session, query, **kwargs):
        if any(not self.retriever.conversion_ready(rid)
               for rid in session.current_symptoms):
            self.last_retrieval_trace = {'execution': 'MARKDOWN_CONVERSION_SOURCE_GATE',
                                        'coverage_established': False,
                                        'source_gap_rider_resolvable': False}
            self.response_generator.last_trace = None
            return session, self.response(
                'UNSUPPORTED', 'The converted source has unresolved evidence associations; '
                'I cannot verify a documented answer from this input.', session,
                reason_codes=('MARKDOWN_CONVERSION_SOURCE_GAP',)), []
        return super().next(session, query, **kwargs)


class MarkdownSupportAdapter(SemanticSupportAdapter):
    """Same verifier contract, but source text is raw common Markdown only."""
    def __init__(self, provider, markdown):
        super().__init__(provider)
        parts = re.split(r'<!-- PDF_PAGE:(\d+) -->', markdown)
        self.pages = {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}

    def verify(self, draft, allowed, evidence):
        self.last_usage = None
        objects = {}
        for eid, obj in evidence.items():
            pages = sorted({p.get('page_no', p.get('pdf_page'))
                            for p in obj.get('provenance', [])})
            objects[eid] = {'type': 'markitdown_page_context',
                            'raw_object': {'text': '\n'.join(self.pages[p] for p in pages)},
                            'provenance': [{'page_no': p} for p in pages]}
        payload = {'claims': draft['claims'], 'evidence': objects,
                   'selected_kind': allowed['kind'], 'audience': allowed['audience']}
        result = self.provider.complete(VERIFICATION_POLICY, payload, VERIFIER_SCHEMA)
        self.last_usage = result
        strict_schema(result.output, VERIFIER_SCHEMA)
        rows = result.output['claims']
        if ([c['claim_id'] for c in rows] != [c['claim_id'] for c in draft['claims']]
                or any(c['supported'] is not True for c in rows)
                or result.output['unsupported_additions'] is not False):
            raise ValidationFailure('SEMANTIC_SUPPORT_REJECTED')
        return result


def apply_reported_facts(service, session, facts, turn_id):
    """Bind explicit rider facts only to this selected record's approved rules.

    Unbound observations remain audit inputs; they create no eligibility rule.
    For example EXP048 has no ABS predicate in its exact approved definition.
    """
    registry = service.controller.registry
    candidate_rules = {}
    for rid in session.current_symptoms:
        sid = registry._consumer.routes[rid].get('step_id')
        if sid:
            step = registry.step(sid)
            for rule_id in step.applicability_rule_ids + step.safety_rule_ids:
                rule = registry.rule(rule_id)
                if rule.origin == 'MANUAL':
                    candidate_rules[rule.fact_key] = (sid, rule)
    updated, unbound = session, []
    for key, value in facts.items():
        value = dict(value)
        outcome = Outcome(value.pop('outcome', 'OBSERVED_ABNORMAL'))
        fact = Fact(**value)
        if not fact.confirmed or outcome not in (Outcome.OBSERVED_NORMAL, Outcome.OBSERVED_ABNORMAL):
            raise ValueError('Initial observation must be explicit confirmed typed rider input')
        if key not in candidate_rules:
            unbound.append(key)
            continue
        sid, rule = candidate_rules[key]
        if compare(rule, fact) == Truth.UNKNOWN:
            raise ValueError('Reported fact does not match the approved predicate type/unit')
        updated = append_attempt(updated, sid, outcome, turn_id + ':' + key,
                                 condition_id=rule.rule_id, facts=((key, fact),))
    if updated != session:
        service.store.save(updated, expected_version=session.version)
    return updated, unbound


def run_cases(transport, cases, pass_id):
    """Return actual released outputs, attempts and provider usage per rider turn.

    Only record_id and user_turns are consumed from case records. Expected routes
    or evaluator facts are deliberately not read. Typed fact/outcome input is an
    explicit scripted rider observation, not extracted from a golden fixture.
    """
    index = Path(os.environ.get('MOTOMEDIC_TEST_INDEX', ROOT / 'build/index-bge-final'))
    registry = ApprovedEvidenceRegistry.load(ROOT, index)
    markdown = MANUAL.read_text(encoding='utf-8')
    assembly = BoundManualAssembly(registry, index, markdown)
    composer = CachedClaudeProvider(transport, 'composer', pass_id)
    verifier = CachedClaudeProvider(transport, 'verifier', pass_id)
    model = getattr(transport, 'model', 'experiment-selected-claude')
    config = RuntimeConfig(generator_provider='anthropic', generator_model=model,
                           verifier_provider='anthropic', verifier_model=model,
                           provider_revision='claude-cached-manual-experiment-v1',
                           max_output_tokens=1800, timeout_seconds=30)
    pipeline = ConstrainedGenerator(composer, MarkdownSupportAdapter(verifier, markdown), config)
    store = SQLiteSessionStore(':memory:')
    service = ReviewedService(registry, assembly, store, response_generator=pipeline)
    rows = []
    try:
        for case in cases:
            record_id = case['record_id']
            try:
                session = service.start(record_id, registry.source['variant'])
            except Exception:
                session = None
            for turn_index, turn in enumerate(case['user_turns']):
                started = time.perf_counter()
                prior_composer, prior_verifier = len(composer.calls), len(verifier.calls)
                unbound_facts, feedback_not_applied, controlled_error = [], None, None
                try:
                    if session is None:
                        raise ValueError('Session unavailable')
                    session, unbound_facts = apply_reported_facts(
                        service, session, turn.get('facts', {}),
                        f'{pass_id}:{record_id}:{turn_index}:initial-observation')
                    if turn.get('outcome'):
                        outcome = Outcome(turn['outcome'])
                        observed = outcome in (Outcome.OBSERVED_NORMAL, Outcome.OBSERVED_ABNORMAL)
                        if (not session.pending_step_id or
                                (observed and not session.pending_rule_id) or
                                (not observed and session.pending_rule_id and outcome != Outcome.UNCLEAR)):
                            feedback_not_applied = 'SCENARIO_NOT_PROGRESSED_NO_MATCHING_PENDING_STEP'
                        else:
                            fact = Fact(**turn['fact']) if turn.get('fact') is not None else None
                            session = service.feedback(session.session_id, outcome,
                                                       f'{pass_id}:{record_id}:{turn_index}:rider', fact=fact)
                    session, response, decisions = service.turn(session.session_id, turn['text'])
                except Exception as exc:
                    controlled_error = type(exc).__name__
                    # Only controlled code/class names; never exception messages.
                    session, response, decisions = service.operational_failure(
                        'EXPERIMENT_CASE_BOUNDARY_FAILURE', session)
                elapsed = time.perf_counter() - started
                new_calls = composer.calls[prior_composer:] + verifier.calls[prior_verifier:]
                rows.append({'arm': 'A_DETERMINISTIC_CONTROLLER', 'pass_id': pass_id,
                             'record_id': record_id, 'turn_index': turn_index,
                             'architecture': ARCHITECTURE,
                             'model': model, 'output': asdict(response),
                             'user_input': turn['text'],
                             'explicit_scripted_rider_facts': deepcopy(turn.get('facts', {})),
                             'facts_without_same_record_rule_not_applied_to_eligibility': unbound_facts,
                             'scripted_feedback_not_applied': feedback_not_applied,
                             'controlled_error_class': controlled_error,
                             'session': asdict(session) if session else None,
                             'controller_trace': deepcopy(service.last_trace),
                             'provider_calls': new_calls,
                             'provider_request_count': len(new_calls),
                             'rider_visible_total_seconds': elapsed,
                             'rider_visible_ttft_seconds': elapsed,
                             'rider_visible_streaming': False,
                             'provider_ttft_seconds': [c.get('ttft_seconds') for c in new_calls],
                             'markdown_sha256': hashlib.sha256(MANUAL.read_bytes()).hexdigest(),
                             'registry_lock': registry.lock,
                             'runtime_lock': config.lock,
                             'scripted_intent_selection': True,
                             'autonomous_intent_accuracy_measured': False,
                             'additional_arm_a_context': ['BOUND_APPROVED_REGISTRY_METADATA',
                                                         'APPROVED_AUTHORED_CLAIM_WORDING'],
                             'isolated_controller_effect_claimed': False,
                             'golden_evaluator_expectations_used_in_prompts': False})
    finally:
        store.close()
    return rows


def provider_payload_templates(cases, model='experiment-selected-claude'):
    """Collect exact successful-path request shapes with NO external provider.

    This software double is token-budget preparation only, never accuracy or
    semantic evaluation. Real model wording failures can shorten the schedule.
    """
    templates = []

    class CaptureTransport:
        def __init__(self):
            self.model = model

        def complete_json(self, policy, payload, schema, **kwargs):
            templates.append({'policy': policy, 'payload': deepcopy(payload),
                              'schema': deepcopy(schema),
                              'max_tokens': kwargs.get('max_tokens', 1800),
                              'tag': kwargs.get('tag'),
                              'execution': 'SOFTWARE_TEMPLATE_CAPTURE_NOT_EVALUATION'})
            if 'wording' in payload.get('claims', [{}])[0]:
                output = {k: deepcopy(payload[k]) for k in
                          ('schema_version', 'route', 'step_id', 'kind', 'citations')}
                output['claims'] = [{'claim_id': c['claim_id'], 'text': c['wording'][0],
                                     'evidence_ids': c['evidence_ids']} for c in payload['claims']]
            else:
                output = {'claims': [{'claim_id': c['claim_id'], 'supported': True}
                                     for c in payload['claims']], 'unsupported_additions': False}
            return {'output': output, 'usage': {'input_tokens': 0, 'output_tokens': 0},
                    'total_seconds': 0, 'ttft_seconds': 0, 'estimated_cost_usd': 0,
                    'raw_text': 'SOFTWARE_TEMPLATE_CAPTURE_NOT_EVALUATION'}

    run_cases(CaptureTransport(), cases, 'budget-template-only')
    return templates
