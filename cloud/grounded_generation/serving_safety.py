"""Finite coordinator-approved safety buffers, independent of provider availability.

Only an existing manual-backed, confirmed typed hazard and exact controller
eligibility can select a record. This is scoped source review, not an online
semantic verdict or an answer-cache path. Generated safety remains draft/verify.
"""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from approved_registry import MANIFEST
from constrained_generator import ValidationFailure
from controller_contracts import ResponseType, Truth
from evidence_registry import content_hash
from human_review.agent_release_161.approval_consumer import RELEASE_SHA
from reviewed_controller import ReviewedController, compare
from session_store import decode
from cloud.arm_a.rider_contract import saved_view as legacy_view
from cloud.grounded_generation.delivery import response_hash
from cloud.grounded_generation.verified_qa import response_wire, VERSION as RUNTIME_VERSION

VERSION = 'exact-approved-safety-buffer-v1'
METHOD = 'COORDINATOR_APPROVED_EXACT_SAFETY_INITIAL_SCOPE'
REASON = 'EXACT_APPROVED_SAFETY_PRECEDENCE'


def _require(ok, code):
    if not ok:
        raise ValidationFailure(code)


def _record(registry, authority, sid):
    """Re-read approval identity; mutable projections cannot create authority."""
    authority.check()
    _require(getattr(registry, 'coordinator_scoped_authority', False) and
             getattr(registry, 'terminal_initial_scope_only', False),
             'EXACT_SAFETY_AUTHORITY_UNAVAILABLE')
    raw = (Path(authority.root) / MANIFEST).read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == RELEASE_SHA,
             'EXACT_SAFETY_RELEASE_CHANGED')
    manifest = json.loads(raw)
    rid = registry.candidate['steps'][sid]['canonical_record_id']
    records = [r for r in manifest['records'] if r['record_id'] == rid]
    _require(len(records) == 1, 'EXACT_SAFETY_RECORD_UNAVAILABLE')
    record = records[0]
    _require(record == registry._consumer.records[rid] and
             record['artifact_bindings'] == registry._bound[rid] and
             registry._scope_intact(rid) and registry.verified_safety_claims(sid),
             'EXACT_SAFETY_SCOPE_CHANGED')
    _require({'SOURCE_CONTENT', 'INITIAL_ROUTE'} <= set(record['approved_scopes']),
             'EXACT_SAFETY_SCOPE_UNAPPROVED')
    step = registry.step(sid)
    _require(step.kind == 'SAFETY_STOP' and not step.next_step_ids,
             'EXACT_SAFETY_INITIAL_SCOPE_ONLY')
    evidence = {}
    for eid in step.required_evidence_ids:
        _require(authority.evidence_ready(eid), 'EXACT_SAFETY_SOURCE_UNAVAILABLE')
        obj = registry.evidence[eid]
        evidence[eid] = {'raw_object_sha256': content_hash(obj['raw_object']),
            'provenance_sha256': content_hash(obj['provenance']),
            'approved_source_sha256': content_hash(registry.approved_sources[eid])}
    # Policy caveats remain separately source-bound; no policy object is cited
    # as a manual page or substituted for the hazard observation.
    return {'step_id': sid, 'record_id': rid, 'release_manifest_sha256': RELEASE_SHA,
        'record_sha256': content_hash(record),
        'scope_binding_sha256': content_hash(registry._bound[rid]),
        'required_evidence_ids': sorted(step.required_evidence_ids),
        'source_objects': evidence,
        'step_sha256': content_hash(registry.candidate['steps'][sid]),
        'dependency_sha256': content_hash(registry.candidate['dependencies'][sid])}


def select_known_safety(controller, session):
    """Return an exact record only for an already reviewed typed hazard rule."""
    registry = controller.registry
    _require(controller.scope_status(session) == 'CONFIRMED', 'SCOPE_NOT_CONFIRMED')
    facts = session.known_observations()
    if not facts:
        return None
    for sid, raw in sorted(registry.candidate['steps'].items()):
        if raw['kind'] != 'SAFETY_STOP':
            continue
        rid = raw.get('canonical_record_id')
        if rid in getattr(registry, '_bound', {}):
            _require(registry._scope_intact(rid), 'SAFETY_AUTHORITY_CHANGED')
        if not registry.verified_safety_claims(sid):
            continue
        step = registry.step(sid)
        hazards = []
        for rule_id in step.applicability_rule_ids:
            rule = registry.rule(rule_id)
            manual = [eid for eid in rule.source_evidence_ids
                if registry.approved_sources.get(eid, {}).get('authority')
                in ('OEM_MANUAL', 'OEM_ORIGINAL_PDF_CANDIDATE')]
            if (manual and rule.origin == 'MANUAL' and rule.fact_key in facts
                    and compare(rule, facts[rule.fact_key]) == Truth.TRUE):
                hazards.append({'rule_id': rule_id, 'fact_key': rule.fact_key,
                    'result': 'TRUE', 'source_evidence_ids': sorted(manual)})
        scoped = replace(session, current_symptoms=tuple(step.symptom_tags))
        decision = controller.eligible(scoped, sid)
        if hazards and decision.eligibility_status == Truth.TRUE:
            return scoped, sid, {'hazard_predicates': hazards,
                'eligibility': json.loads(json.dumps(asdict(decision), allow_nan=False))}
    return None


def _render(controller, session, sid):
    # Use engineering claim metadata internally, then remove private locations.
    audience = controller.audience
    try:
        controller.audience = 'engineering'
        response = controller.render(session, sid, safety=True)
    finally:
        controller.audience = audience
    _require(response.type == ResponseType.SAFETY_STOP and response.claim_evidence_map,
             'EXACT_SAFETY_RENDER_FAILED')
    citations = tuple({k: deepcopy(v) for k, v in page.items()
        if k in ('evidence_id', 'pdf_page', 'pdf_page_index', 'printed_page_label',
                 'manual_checksum', 'index_id')}
        for page in response.cited_pages)
    return replace(response, cited_pages=citations, reason_codes=(REASON,))


def saved_safety_view(controller, authority, session, sid, selection, query,
                      history, operation_id, runtime_lock):
    """Build a separately identified exact scoped-review buffer for durable save."""
    _require(type(operation_id) is str and bool(operation_id), 'EXACT_SAFETY_OPERATION_REQUIRED')
    _require(session.generation_lock == runtime_lock, 'GENERATION_VERSION_RECONFIRM_REQUIRED')
    selected = select_known_safety(controller, session)
    _require(selected is not None and selected[0] == session and selected[1] == sid
             and selected[2] == selection, 'EXACT_SAFETY_ELIGIBILITY_CHANGED')
    record = _record(controller.registry, authority, sid)
    response = _render(controller, session, sid)
    final = response_wire(response)
    snapshot = json.loads(json.dumps(asdict(session), ensure_ascii=False, allow_nan=False))
    proof = {'version': VERSION, 'verification_method': METHOD,
        'exact_scope': record, 'selection': deepcopy(selection),
        'session_snapshot': snapshot, 'session_sha256': content_hash(snapshot),
        'question_sha256': content_hash(query), 'history_sha256': content_hash(list(history)),
        'manual_checksum': controller.registry.checksum, 'index_id': controller.registry.index_id,
        'registry_lock': controller.registry.lock, 'source_authority_lock': authority.lock,
        'runtime_lock': runtime_lock, 'operation_id': operation_id,
        'response_sha256': content_hash(final), 'trace_id': response.trace_id}
    proof['evidence_payload_sha256'] = content_hash(record)
    binding_sha256 = content_hash(proof)
    neutral = replace(response, type=ResponseType.UNSUPPORTED, claim_evidence_map=(), cited_pages=())
    view, _ = legacy_view(controller.registry, session, neutral)
    view.update(runtime_policy=RUNTIME_VERSION, choices=[], provider_calls=0)
    view['response'] = {'type': 'SAFETY_STOP', 'natural_language': response.natural_language,
        'technical_content': True, 'release_gate_passed': True,
        'source_scope_verification_passed': True, 'semantic_verification_passed': False,
        'semantic_support_proven': False, 'verification_method': METHOD,
        'cited_pages': deepcopy(final['citations']), 'claim_evidence_map': deepcopy(final['claims']),
        'trace_id': response.trace_id, 'reason_codes': [REASON],
        'clarification_question': None, 'escalation_uri': response.escalation_uri}
    view['source_scope_verification'] = proof
    view['verified_delivery'] = {'response_sha256': proof['response_sha256'],
        'text_sha256': hashlib.sha256(response.natural_language.encode()).hexdigest(),
        'binding_sha256': binding_sha256, 'evidence_payload_sha256': proof['evidence_payload_sha256'],
        'manual_checksum': controller.registry.checksum, 'index_id': controller.registry.index_id,
        'source_authority_lock': authority.lock, 'runtime_lock': runtime_lock,
        'operation_id': operation_id, 'verification_method': METHOD,
        'presentation_sha256': response_hash(view)}
    view['runtime_controls'] = {'composition': {'version': VERSION, 'provider_calls': 0,
        'generation_calls': 0, 'verification_calls': 0, 'answer_cache': 'DISABLED',
        'verification_method': METHOD, 'verified_buffer_ready': True},
        'retrieval': {'skipped': 'CONFIRMED_EXACT_SOURCE_SAFETY_PRECEDENCE'}}
    validate_saved_safety_view(controller.registry, authority, view, runtime_lock)
    return view, {}


def validate_saved_safety_view(registry, authority, view, runtime_lock):
    """Revalidate source approval, typed eligibility and exact bytes on recovery."""
    try:
        proof, delivery, body = (view['source_scope_verification'],
                                view['verified_delivery'], view['response'])
        _require(set(proof) == {'version', 'verification_method', 'exact_scope',
            'selection', 'session_snapshot', 'session_sha256', 'question_sha256',
            'history_sha256', 'manual_checksum', 'index_id', 'registry_lock',
            'source_authority_lock', 'runtime_lock', 'operation_id', 'response_sha256',
            'trace_id', 'evidence_payload_sha256'} and view['runtime_policy'] == RUNTIME_VERSION,
            'EXACT_SAFETY_PROOF_SCHEMA_CHANGED')
        for field in ('session_sha256', 'question_sha256', 'history_sha256',
                      'response_sha256', 'evidence_payload_sha256'):
            value = proof[field]
            _require(type(value) is str and len(value) == 64 and
                     all(char in '0123456789abcdef' for char in value),
                     'EXACT_SAFETY_HASH_SCHEMA_CHANGED')
        _require(type(proof['operation_id']) is str and bool(proof['operation_id'])
                 and type(proof['trace_id']) is str and bool(proof['trace_id']),
                 'EXACT_SAFETY_OPERATION_SCHEMA_CHANGED')
        _require(proof['version'] == VERSION and proof['verification_method'] == METHOD
                 and body['verification_method'] == METHOD
                 and delivery['verification_method'] == METHOD,
                 'EXACT_SAFETY_VERIFICATION_METHOD_CHANGED')
        _require(body['type'] == 'SAFETY_STOP' and body['technical_content'] is True
                 and body['release_gate_passed'] is True
                 and body['source_scope_verification_passed'] is True
                 and body['semantic_verification_passed'] is False
                 and body['semantic_support_proven'] is False
                 and body['reason_codes'] == [REASON], 'EXACT_SAFETY_RELEASE_FLAGS_CHANGED')
        _require(proof['runtime_lock'] == delivery['runtime_lock'] == runtime_lock
                 and proof['registry_lock'] == registry.lock
                 and proof['source_authority_lock'] == delivery['source_authority_lock'] == authority.lock
                 and proof['manual_checksum'] == delivery['manual_checksum'] == view['manual_checksum'] == registry.checksum
                 and proof['index_id'] == delivery['index_id'] == view['index_id'] == registry.index_id
                 and proof['operation_id'] == delivery['operation_id'] and bool(proof['operation_id']),
                 'EXACT_SAFETY_RUNTIME_BINDING_CHANGED')
        _require(content_hash(proof) == delivery['binding_sha256']
                 and response_hash(view) == delivery['presentation_sha256']
                 and hashlib.sha256(body['natural_language'].encode()).hexdigest() == delivery['text_sha256'],
                 'EXACT_SAFETY_BUFFER_CHANGED')
        session = decode(json.dumps(proof['session_snapshot'], ensure_ascii=False, allow_nan=False))
        _require(content_hash(asdict(session)) == proof['session_sha256']
                 and session.session_id == view['session_id'] and session.version == view['version']
                 and session.generation_lock == runtime_lock, 'EXACT_SAFETY_SESSION_CHANGED')
        controller = ReviewedController(registry, SimpleNamespace(manifest={
            'index_id': registry.index_id, 'source_sha256': registry.checksum}))
        selected = select_known_safety(controller, session)
        sid = proof['exact_scope']['step_id']
        _require(selected is not None and selected[0] == session and selected[1] == sid
                 and selected[2] == proof['selection'], 'EXACT_SAFETY_ELIGIBILITY_CHANGED')
        record = _record(registry, authority, sid)
        _require(record == proof['exact_scope'] and content_hash(record) ==
                 proof['evidence_payload_sha256'] == delivery['evidence_payload_sha256'],
                 'EXACT_SAFETY_SOURCE_BINDING_CHANGED')
        response = replace(_render(controller, session, sid), trace_id=proof['trace_id'])
        final = response_wire(response)
        _require(content_hash(final) == proof['response_sha256'] == delivery['response_sha256']
                 and final['text'] == body['natural_language']
                 and final['claims'] == body['claim_evidence_map']
                 and final['citations'] == body['cited_pages']
                 and final['trace_id'] == body['trace_id']
                 and final['clarification_question'] == body['clarification_question']
                 and final['escalation_uri'] == body['escalation_uri'],
                 'EXACT_SAFETY_APPROVED_WORDING_CHANGED')
        return view
    except ValidationFailure:
        raise
    except Exception:
        raise ValidationFailure('EXACT_SAFETY_PROOF_INVALID') from None
