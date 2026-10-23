"""Fail closed at the boundary between initial scopes and adaptive transitions.

This guard is not an answer authorization gate. The caller checks known hazards
first and must still enforce eligibility, evidence, and non-repeat requirements.
Initial-scope approval cannot establish next-step authority. A future registry
may supply unresolved_transition_ready(prior_id, next_id), backed by separately
reviewed transition records; authored question text and symptom tags never do.
"""
from constrained_generator import ValidationFailure
from controller_contracts import Outcome

VERSION = 'unresolved-source-transition-guard-v1'


def exhausted_after_unresolved(registry, session):
    """Whether unresolved action feedback must stop the documented path.

    Historical completion is retained across superseding corrections: a rider
    correction cannot grant new source transition authority. The caller handles
    reported resolution as a status response, without issuing another action.
    Binding failures raise ValidationFailure (SYSTEM_ERROR at the caller).
    True is evidence exhaustion (UNSUPPORTED), never a normal observation.
    False only lets the caller continue its ordinary deterministic gates. When
    explicit edges exist, it must restrict candidates to those reviewed targets.
    """
    attempts = [a for a in session.attempted_steps
                if a.outcome_enum == Outcome.ACTION_COMPLETED_UNRESOLVED]
    if not attempts:
        return False
    if (not registry.source_ready() or session.version_lock != registry.lock or
            session.manual_checksum != registry.checksum or
            session.manual_id != registry.source.get('manual_id')):
        raise ValidationFailure('UNRESOLVED_TRANSITION_SOURCE_BINDING')
    priors = []
    for attempt in attempts:
        try:
            prior = registry.step(attempt.step_id)
            ready = registry.step_ready(attempt.step_id)
        except (KeyError, ValueError, TypeError):
            raise ValidationFailure('UNRESOLVED_TRANSITION_STEP_BINDING') from None
        if (not ready or prior.kind != 'ACTION' or attempt.condition_id is not None
                or attempt.observed_details or prior.manual_checksum != registry.checksum):
            raise ValidationFailure('UNRESOLVED_TRANSITION_STEP_BINDING')
        priors.append((attempt, prior))
    for attempt, prior in priors:
        if prior.unresolved_route.startswith('ESCALATE'):
            return True
        if not getattr(registry, 'terminal_initial_scope_only', False):
            # A general adaptive registry retains its ordinary controller contract.
            continue
        targets = tuple(prior.next_step_ids)
        links = tuple(prior.next_step_evidence_ids)
        reviewed = getattr(registry, 'unresolved_transition_ready', None)
        if not targets or not links or not callable(reviewed):
            return True
        if (len(set(targets)) != len(targets) or attempt.step_id in targets or
                not set(links) <= set(prior.required_evidence_ids) or
                not all(registry.evidence_ready(eid) for eid in links)):
            raise ValidationFailure('UNRESOLVED_TRANSITION_EDGE_BINDING')
        for target in targets:
            try:
                target_step = registry.step(target)
                target_ready = registry.step_ready(target)
            except (KeyError, ValueError, TypeError):
                raise ValidationFailure('UNRESOLVED_TRANSITION_EDGE_BINDING') from None
            if not target_ready or target_step.manual_checksum != registry.checksum:
                raise ValidationFailure('UNRESOLVED_TRANSITION_EDGE_BINDING')
            if reviewed(attempt.step_id, target) is not True:
                return True
    return False