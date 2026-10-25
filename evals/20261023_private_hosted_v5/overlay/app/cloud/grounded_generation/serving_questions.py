"""Open-question production wiring for reviewed-object and history-aware retrieval."""
from cloud.grounded_generation.open_questions import Questions as FrozenQuestions
# v10.15 private candidate: reviewed structural_review_v2 authority (v4 subclass).
from cloud.grounded_generation.serving_source_authority_v5 import SourceAuthority
from cloud.grounded_generation.serving_retrieval import QUERY_CONTEXT
from copy import deepcopy
from dataclasses import replace
from constrained_generator import ValidationFailure
from cloud.grounded_generation.serving_safety import (select_known_safety,
    saved_safety_view, validate_saved_safety_view)

VERSION = 'history-aware-open-questions-exact-safety-v3'


class Questions(FrozenQuestions):
    def __init__(self, registry, retriever, composer, source_authority=None):
        source_authority = source_authority or SourceAuthority(registry, retriever.root)
        super().__init__(registry, retriever, composer, source_authority)
        retriever.source_authority = source_authority

    def answer(self, session, query, *, history=(), progress=None, operation_id=None):
        token = QUERY_CONTEXT.set(history)
        try:
            # No source hazard can be inferred from question wording, a policy
            # selector or an unresolved attempt. Normal Q&A retains draft/verify.
            if session.known_observations() and self.pipeline_lock.acquire(blocking=False):
                composer = self.controller.response_generator
                updated = replace(session, version=session.version+1,
                                  pending_step_id=None, pending_rule_id=None)
                try:
                    if updated.generation_lock != composer.config.lock:
                        raise ValidationFailure('GENERATION_VERSION_RECONFIRM_REQUIRED')
                    # Preserve the unchanged initial-response selector. The
                    # independent proof also rechecks its manual hazard gates.
                    known = self.known_safety(updated)
                    selected = select_known_safety(self.controller, updated) if known else None
                    if selected:
                        updated, sid, selection = selected
                        view, choices = saved_safety_view(self.controller, self.source_authority,
                            updated, sid, selection, query, history, operation_id, composer.config.lock)
                        composer.last_admitted = None
                        composer.last_source_admission = None
                        composer.last_trace = deepcopy(view['runtime_controls']['composition'])
                        return updated, view, choices
                except Exception as exc:
                    from cloud.grounded_generation.verified_qa import saved_view, SYSTEM_ERROR_TEXT
                    code = str(exc) if isinstance(exc, ValidationFailure) else 'EXACT_SAFETY_FAILURE'
                    response = self.controller.response('SYSTEM_ERROR', SYSTEM_ERROR_TEXT,
                        updated, reason_codes=(code,))
                    view, choices = saved_view(self.registry, updated, response, self.source_authority, None)
                    composer.last_admitted = None
                    composer.last_source_admission = None
                    composer.last_trace = {'provider_calls': 0, 'failure_code': code}
                    return updated, view, choices
                finally:
                    self.pipeline_lock.release()
            return super().answer(session, query, history=history, progress=progress,
                                  operation_id=operation_id)
        finally:
            QUERY_CONTEXT.reset(token)

    def check_saved_safety_view(self, view):
        return validate_saved_safety_view(self.registry, self.source_authority, view,
                                         self.controller.response_generator.config.lock)
