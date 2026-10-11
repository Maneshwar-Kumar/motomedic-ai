"""Open manual Q&A. Source authority is independent of authored actions.

Legacy controller is used for selected-manual identity, typed history and
source-verified safety predicates only. Every technical release is verified.
"""
from copy import deepcopy
from dataclasses import replace
import threading
import time
from constrained_generator import ValidationFailure
from cloud.grounded_generation.generic_runtime import Questions as SafetyQuestions
from cloud.arm_a.runtime_controls import diagnostic_projection


class Questions(SafetyQuestions):
    open_verification = True

    def __init__(self, registry, retriever, composer, source_authority=None):
        super().__init__(registry, retriever, composer, source_authority)
        self.pipeline_lock = threading.Lock()

    def _view(self, session, response):
        from cloud.grounded_generation.verified_qa import saved_view
        composer = self.controller.response_generator
        view, choices = saved_view(self.registry, session, response,
                                   self.source_authority, composer.last_admitted)
        view['runtime_controls'] = {'composition': deepcopy(composer.last_trace),
            'retrieval': deepcopy(getattr(self.retriever, 'last_cache_trace', None)),
            'source_admission': deepcopy(composer.last_source_admission)}
        view['provider_calls'] = (composer.last_trace or {}).get('provider_calls', 0)
        return session, view, choices

    def answer(self, session, query, *, history=(), progress=None, operation_id=None):
        c, r = self.controller, self.registry
        composer = c.response_generator
        session = replace(session, version=session.version+1,
                          pending_step_id=None, pending_rule_id=None)
        if not self.pipeline_lock.acquire(blocking=False):
            # No shared composer metadata can be consulted on this path.
            from cloud.grounded_generation.verified_qa import saved_view
            response = c.response('SYSTEM_ERROR', 'I couldn’t check the answer right now. Please try again shortly.',
                                  session, reason_codes=('PIPELINE_CONCURRENCY_LIMIT',))
            view, choices = saved_view(r, session, response, self.source_authority, None)
            return session, view, choices
        composer.last_trace = None
        composer.last_admitted = None
        composer.last_source_admission = None
        try:
            if not r.source_ready():
                raise ValidationFailure('SOURCE_IDENTITY_CHANGED')
            if c.scope_status(session) != 'CONFIRMED':
                raise ValidationFailure('SCOPE_NOT_CONFIRMED')
            if session.generation_lock != composer.config.lock:
                raise ValidationFailure('GENERATION_VERSION_RECONFIRM_REQUIRED')
            if progress:
                progress('retrieving')
            started = time.monotonic()
            bundle = self.retriever.search(query, limit=6, scope=self.scope(),
                                           applicability_status='CONFIRMED')
            if bundle.get('manual_checksum') != r.checksum or bundle.get('index_id') != r.index_id:
                raise ValidationFailure('INVALID_BUNDLE_IDENTITY')
            # Known safety authority is exact and precedence-bound, but its
            # complete proposed rider wording still goes through online verify.
            known = self.known_safety(session)
            from cloud.grounded_generation.fuse_refusal import detect_refusal
            refusal = detect_refusal(r, query)
            required_safety_ids = set()
            if known:
                session, stop = known
                required_safety_ids.update(e for claim in stop.claim_evidence_map
                                           for e in claim.get('evidence_ids', ()))
            if refusal:
                required_safety_ids.update(e for claim in refusal['claims']
                                           for e in claim['evidence_ids'])
            if required_safety_ids:
                existing = {h['id'] for h in bundle.get('hits', ())}
                # Only genuine immutable chunks are attached; no synthetic
                # scope or prewritten answer becomes factual authority.
                for chunk in self.source_authority.chunks.values():
                    if required_safety_ids & set(chunk['evidence_ids']) and chunk['id'] not in existing:
                        bundle.setdefault('hits', []).append({'id': chunk['id'],
                            'evidence_ids': list(chunk['evidence_ids']),
                            'parent_section_id': chunk['parent_section_id']})
                        existing.add(chunk['id'])
            admitted = self.source_authority.assemble(bundle)
            if required_safety_ids - set(admitted['evidence']):
                raise ValidationFailure('SAFETY_SOURCE_CONTEXT_UNAVAILABLE')
            composer.last_source_admission = {'authority_lock': self.source_authority.lock,
                'chunk_ids': [h['id'] for h in bundle.get('hits', ())],
                'admitted_evidence_ids': admitted['required_evidence_ids'],
                'gaps': deepcopy(admitted['gaps']),
                'retrieval_assembly_seconds': time.monotonic()-started}
            context = {'conversation': deepcopy(list(history)),
                       'typed_outcomes': diagnostic_projection(session),
                       'required_route': 'SAFETY_STOP' if required_safety_ids else None,
                       'required_safety_evidence_ids': sorted(required_safety_ids),
                       'source_conflicts': deepcopy(bundle.get('conflicts', [])),
                       'operation_id': operation_id}
            response = composer.compose_open(c, session, admitted, query, context, progress=progress)
            return self._view(session, response)
        except Exception as exc:
            code = str(exc) if isinstance(exc, ValidationFailure) else 'OPEN_QA_FAILURE'
            composer.last_trace = deepcopy(composer.last_trace or {'provider_calls': 0})
            composer.last_trace['failure_code'] = code
            composer.last_admitted = None
            response = c.response('SYSTEM_ERROR',
                'I couldn’t check the answer right now. Please try again shortly.',
                session, reason_codes=(code,))
            return self._view(session, response)
        finally:
            self.pipeline_lock.release()

    def feedback(self, session, query, *, history=(), progress=None, operation_id=None):
        # Optional existing typed feedback remains history; it is never
        # interpreted as normality or an eligibility allowlist for open Q&A.
        return self.answer(session, query, history=history, progress=progress, operation_id=operation_id)
