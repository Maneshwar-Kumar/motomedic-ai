"""Bounded rider presentation adapter; never supplies source approval or facts.

This is an integration component, not an installed hosted rider endpoint.
Choices bind server-side to an exact session version and pending proposition.
"""
from dataclasses import asdict
import hashlib
import json

from controller_contracts import Fact, Outcome, ResponseType

SCHEMA = 'motomedic-rider-api-v1'
VERSION = 'arm-a-rider-contract-policy-caveats-v2'


def choice_id(session, binding):
    body = {'policy': VERSION, 'session_id': session.session_id,
            'version': session.version, 'pending_step_id': session.pending_step_id,
            'pending_rule_id': session.pending_rule_id, 'binding': binding}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def issue_choices(registry, session, response):
    """Return public choices plus a private, version-bound immutable map.

    Generic boolean interpretation is deliberately absent. Only the exact
    independently source-checked EXP003 centred proposition is installed.
    """
    if response.type not in (ResponseType.AMBIGUOUS, ResponseType.SUPPORTED):
        return [], {}
    if session.status != 'OPEN':
        return [], {}
    if (response.type == ResponseType.SUPPORTED and not response.claim_evidence_map):
        return [], {}
    if not session.pending_step_id:
        return [], {}
    if session.pending_rule_id:
        rule = registry.rule(session.pending_rule_id)
        if (rule.rule_id != 'EXP003:rule:turn_switch_centred' or
                rule.predicate_type != 'BOOLEAN' or rule.operator != 'EQ' or
                rule.expected_value is not True or not rule.rider_resolvable or
                rule.review_status != 'APPROVED' or
                not all(registry.evidence_ready(e) for e in rule.clarification_evidence_ids)):
            return [], {}
        options = [('The turn switch is centred', Outcome.OBSERVED_NORMAL, Fact(True, 'BOOLEAN')),
                   ('The turn switch is not centred', Outcome.OBSERVED_ABNORMAL, Fact(False, 'BOOLEAN')),
                   ('I am not sure', Outcome.UNCLEAR, None)]
    elif registry.step(session.pending_step_id).kind == 'ACTION':
        options = [('I have not tried it', Outcome.NOT_TRIED, None),
                   ('I tried it; the symptom remains', Outcome.ACTION_COMPLETED_UNRESOLVED, None),
                   ('It does not apply to my bike', Outcome.NOT_APPLICABLE, None),
                   ('I am not sure', Outcome.UNCLEAR, None),
                   ('The symptom is resolved', Outcome.RESOLVED, None)]
    else:
        return [], {}
    public, private = [], {}
    for label, outcome, fact in options:
        binding = {'outcome': outcome.value, 'fact': asdict(fact) if fact else None,
                   'session_id': session.session_id, 'version': session.version,
                   'pending_step_id': session.pending_step_id,
                   'pending_rule_id': session.pending_rule_id}
        key = choice_id(session, binding)
        public.append({'id': key, 'label': label, 'outcome': outcome.value})
        private[key] = binding
    return public, private


def consume_choice(session, private, key, expected_version):
    """Validate only saved server bindings; client cannot send a typed fact."""
    if type(expected_version) is not int or session.version != expected_version:
        raise ValueError('STALE_SESSION_VERSION')
    if type(key) is not str or key not in private:
        raise ValueError('CHOICE_NOT_ISSUED')
    binding = private[key]
    if (binding['session_id'] != session.session_id or binding['version'] != session.version or
            binding['pending_step_id'] != session.pending_step_id or
            binding['pending_rule_id'] != session.pending_rule_id or
            choice_id(session, binding) != key):
        raise ValueError('CHOICE_BINDING_CHANGED')
    outcome = Outcome(binding['outcome'])
    fact = Fact(**binding['fact']) if binding['fact'] else None
    if outcome not in (Outcome.OBSERVED_NORMAL, Outcome.OBSERVED_ABNORMAL) and fact is not None:
        raise ValueError('OUTCOME_CANNOT_CREATE_FACT')
    return outcome, fact


def saved_view(registry, session, response):
    """Internal adapter after ReviewedController, never an eligibility authority.

    Recheck source-bound text/maps/citations. The controller must have applied
    session eligibility and retrieval gates; caller MUST commit before send.
    """
    technical = bool(response.claim_evidence_map)
    gated = ('ARM_A_EXACT_REVIEWED_CANONICAL_VALIDATED' in response.reason_codes)
    if technical:
        exact = False
        for sid, raw in registry.candidate['steps'].items():
            if not set(raw['symptom_tags']) & set(session.current_symptoms) or not registry.step_ready(sid):
                continue
            step = registry.step(sid)
            text = ' '.join(c['text'] for c in step.claims)
            support = (registry.source.get('oem_service_route') or {}).get('wording')
            if response.type == ResponseType.SAFETY_STOP and support and registry.support_uri() and support not in text:
                text += ' ' + support
            expected_claims = {c['claim_id']: set(c['evidence_ids']) for c in step.claims}
            actual_claims = {c['claim_id']: set(c['evidence_ids']) for c in response.claim_evidence_map}
            expected_policy = {c['claim_id']: set(c.get('policy_support_ids', []))
                               for c in step.claims if not c['evidence_ids']}
            actual_policy = {c['claim_id']: set(c.get('policy_support_ids', []))
                             for c in response.claim_evidence_map if not c['evidence_ids']}
            policy_valid = (expected_policy == actual_policy and
                            all(registry.approved_policy_caveat(sid, c) for c in step.claims if not c['evidence_ids']) and
                            all(not c.get('policy_support_ids') for c in response.claim_evidence_map if c['evidence_ids']))
            expected_pages = {(eid, p.get('page_no', p.get('pdf_page')))
                              for eid in step.required_evidence_ids
                              for p in registry.evidence[eid]['provenance']}
            valid_pages = all(c.get('manual_checksum') == registry.checksum and
                              c.get('index_id') == registry.index_id and
                              type(c.get('pdf_page')) is int and 1 <= c['pdf_page'] <= 149 and
                              type(c.get('pdf_page_index')) is int and
                              c['pdf_page_index'] == c['pdf_page']-1 for c in response.cited_pages)
            actual_pages = {(c.get('evidence_id'), c.get('pdf_page')) for c in response.cited_pages}
            if (text == response.natural_language and expected_claims == actual_claims and policy_valid and
                    len(actual_claims) == len(response.claim_evidence_map) and
                    valid_pages and expected_pages == actual_pages and registry.source_ready()):
                exact = True
                break
        if not exact:
            raise ValueError('RESPONSE_SOURCE_BINDINGS_CHANGED')
    if response.type == ResponseType.SAFETY_STOP:
        # Confirm the finite reviewed safety wording again at presentation.
        # A status or citation list alone cannot grant a release assertion.
        gated = False
        for sid, raw in registry.candidate['steps'].items():
            if raw['kind'] != 'SAFETY_STOP' or not set(raw['symptom_tags']) & set(session.current_symptoms):
                continue
            if not registry.verified_safety_claims(sid):
                continue
            step = registry.step(sid)
            text = ' '.join(c['text'] for c in step.claims)
            support = (registry.source.get('oem_service_route') or {}).get('wording')
            if support and registry.support_uri() and support not in text:
                text += ' ' + support
            claim_ids = {c['claim_id'] for c in response.claim_evidence_map}
            evidence_ids = {c['evidence_id'] for c in response.cited_pages}
            if (response.natural_language == text and
                    claim_ids == {c['claim_id'] for c in step.claims} and
                    set(step.required_evidence_ids) <= evidence_ids):
                gated = technical and bool(response.cited_pages)
                break
    if response.type == ResponseType.SUPPORTED and technical and not gated:
        raise ValueError('TECHNICAL_RESPONSE_NOT_VERIFIED')
    if response.type == ResponseType.SAFETY_STOP and technical and not gated:
        raise ValueError('SAFETY_RESPONSE_NOT_VERIFIED')
    permitted = {'evidence_id', 'pdf_page', 'pdf_page_index', 'printed_page_label',
                 'manual_checksum', 'index_id'}
    citations = [{k: v for k, v in c.items() if k in permitted} for c in response.cited_pages]
    choices, private = issue_choices(registry, session, response)
    history = []
    for attempt, superseded_by in session.history():
        if superseded_by or attempt.outcome_enum == Outcome.NOT_TRIED:
            continue
        if attempt.condition_id:
            # Describe the actual typed proposition; normal is not component health.
            facts = dict(attempt.observed_details)
            centred = facts.get('turn_switch_centred')
            if centred is not None:
                label = 'Turn switch reported ' + ('centred' if centred.value else 'not centred')
            else:
                label = 'Observation remains uncertain'
        else:
            label = {'ACTION_COMPLETED_UNRESOLVED': 'Action completed; symptom remains',
                     'NOT_APPLICABLE': 'Step reported not applicable', 'UNCLEAR': 'Outcome uncertain',
                     'RESOLVED': 'Customer reports symptom resolved'}.get(
                         attempt.outcome_enum.value, attempt.outcome_enum.value)
        history.append({'label': label})
    view = {'schema_version': SCHEMA, 'manual_checksum': registry.checksum,
            'index_id': registry.index_id, 'session_id': session.session_id,
            'version': session.version,
            'response': {'type': response.type.value, 'natural_language': response.natural_language,
                         'technical_content': technical, 'release_gate_passed': gated,
                         'cited_pages': citations, 'trace_id': response.trace_id},
            'choices': choices, 'history': history,
            'escalation_uri': response.escalation_uri,
            'runtime_policy': VERSION, 'provider_calls': 0}
    return view, private
