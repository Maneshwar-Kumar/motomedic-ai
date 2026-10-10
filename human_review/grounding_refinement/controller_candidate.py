"""Isolated engineering candidate; delegates every technical gate to ReviewedController.

No source records, review decisions, model config or deployment defaults are changed.
Issue IDs and typed feedback must come from trusted application state, not model text.
"""
from dataclasses import dataclass, replace
from controller_contracts import Outcome, ResponseType, Truth
from reviewed_controller import ReviewedController, update_symptoms

VERSION = 'isolated-issue-controller-v1'

class ControllerCandidate(ReviewedController):
    def next(self, session, query, **kwargs):
        updated, response, decisions = super().next(session, query, **kwargs)
        policy = self.registry.source.get('applicability_policy', {})
        if (response.type == ResponseType.AMBIGUOUS and
                response.reason_codes == ('CONFIRM_VARIANT',) and
                policy.get('version') == 'owner-himalayan-bs6-v1' and
                policy.get('rider_edition_selection_required') is False):
            question = 'Is your motorcycle a Himalayan BS6?'
            response = replace(response, natural_language=question, clarification_question=question)
        return updated, response, decisions

@dataclass(frozen=True)
class IssueState:
    issues: tuple  # (trusted issue_id, DiagnosticSession)
    selected_issue: str
    candidate_version: str = VERSION

    def __post_init__(self):
        ids=[key for key,_ in self.issues]
        sessions=[session.session_id for _,session in self.issues]
        if (not ids or len(set(ids))!=len(ids) or self.selected_issue not in ids
                or len(set(sessions))!=len(sessions) or self.candidate_version!=VERSION):
            raise ValueError('Invalid or stale issue state')

    def session(self, issue_id=None):
        return dict(self.issues)[issue_id or self.selected_issue]

    def updated(self, issue_id, session):
        if issue_id not in dict(self.issues):
            raise ValueError('Unknown issue')
        return replace(self, issues=tuple((key, session if key==issue_id else old)
                                        for key, old in self.issues))

class IssueController:
    """Explicit per-issue sessions prevent global resolution from erasing another issue."""
    def __init__(self, controller):
        self.controller = controller

    def next(self, state, query, **kwargs):
        # Known reviewed stops in ANY open issue precede selected-issue closure.
        # Never run other issues' ordinary next() paths or optional provider calls.
        for issue_id, session in state.issues:
            if session.status == 'CUSTOMER_REPORTED_RESOLVED':
                continue
            for sid in sorted(self.controller.registry.candidate['steps']):
                step = self.controller.registry.step(sid)
                if step.kind != 'SAFETY_STOP':
                    continue
                decision = self.controller.eligible(session, sid)
                if decision.eligibility_status == Truth.TRUE:
                    response = self.controller.render(session, sid, safety=True)
                    if response.type == ResponseType.SAFETY_STOP:
                        return state, response
        session, response, _ = self.controller.next(state.session(), query, **kwargs)
        state = state.updated(state.selected_issue, session)
        open_others = [key for key, value in state.issues if key != state.selected_issue
                       and value.status != 'CUSTOMER_REPORTED_RESOLVED']
        if session.status == 'CUSTOMER_REPORTED_RESOLVED' and response.type == ResponseType.SUPPORTED and open_others:
            response = replace(response, natural_language='You reported this symptom resolved. Other reported symptoms remain open. The repair and cause have not been mechanically verified.',
                               session_status='OTHER_ISSUES_OPEN', reason_codes=response.reason_codes+('OTHER_ISSUES_OPEN',))
        return state, response

    def feedback(self, state, outcome, turn_id, **kwargs):
        updated = self.controller.feedback(state.session(), outcome, turn_id, **kwargs)
        return state.updated(state.selected_issue, updated)

    def reopen(self, state, issue_id, symptoms):
        if not symptoms:
            raise ValueError('Recurrence requires an explicit symptom')
        session = state.session(issue_id)
        # Recurrence is an explicit trusted event, not a health inference or retry.
        # Preserve all immutable attempts even if the symptom set is unchanged.
        updated = update_symptoms(session, symptoms)
        if updated == session:
            updated = replace(session, version=session.version+1, status='OPEN',
                              pending_step_id=None, pending_rule_id=None)
        return replace(state.updated(issue_id, updated), selected_issue=issue_id)
