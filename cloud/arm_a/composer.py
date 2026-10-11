"""Exact approved canonical wording, without a model or benchmark admission."""
from copy import deepcopy
from dataclasses import dataclass
import json
import time

from constrained_generator import envelope, validate_output, ValidationFailure
from evidence_registry import content_hash


@dataclass(frozen=True)
class ArmAConfig:
    max_input_bytes: int = 24000

    def __post_init__(self):
        if type(self.max_input_bytes) is not int or not 1 <= self.max_input_bytes <= 48000:
            raise ValueError('Invalid Arm A byte bound')

    def versions(self):
        return {'architecture': 'A_DETERMINISTIC_CANONICAL',
                'generator_version': 'arm-a-canonical-policy-caveats-v2',
                'selection': 'FIRST_EXACT_REVIEWED_CANONICAL_WORDING',
                'verifier': 'EXACT_APPROVED_SCOPE_BINDINGS_AND_DETERMINISTIC_GATES',
                'max_input_bytes': self.max_input_bytes, 'provider_calls': 0,
                'benchmark_pacing': False, 'cache': 'DISABLED', 'policy_caveat_validation': 'EXACT_RECORD_BOUND_PRODUCT_POLICY_V1'}

    @property
    def lock(self):
        return content_hash(self.versions())


class ArmAComposer:
    def __init__(self, config=None):
        self.config = config or ArmAConfig()
        self.last_trace = None

    def compose(self, controller, session, sid, *, cache_draft=None):
        started = time.perf_counter()
        trace = {'architecture': 'A_DETERMINISTIC_CANONICAL',
                 'runtime_lock': self.config.lock, 'generation_calls': 0,
                 'verifier_calls': 0, 'provider_wait_seconds': 0,
                 'estimated_cost_usd': 0, 'cost_status': 'NO_PROVIDER_CALL',
                 'cache': 'DISABLED', 'source_or_user_text_recorded': False}
        self.last_trace = trace
        try:
            if not getattr(controller.registry, 'coordinator_scoped_authority', False):
                raise ValidationFailure('SOURCE_REVIEW_REQUIRED')
            if session.generation_lock != self.config.lock:
                raise ValidationFailure('GENERATION_VERSION_RECONFIRM_REQUIRED')
            if cache_draft is not None:
                raise ValidationFailure('ARM_A_CACHE_NOT_ENABLED')
            allowed = envelope(controller, session, sid, allow_approved_policy_caveats=True)
            if len(json.dumps(allowed, allow_nan=False, ensure_ascii=False).encode('utf-8')) > self.config.max_input_bytes:
                raise ValidationFailure('CONTEXT_BOUND_NO_TRUNCATION')
            draft = {key: deepcopy(allowed[key]) for key in
                     ('schema_version', 'route', 'step_id', 'kind', 'citations')}
            draft['claims'] = [{'claim_id': c['claim_id'], 'text': c['wording'][0],
                                'evidence_ids': deepcopy(c['evidence_ids'])}
                               for c in allowed['claims']]
            validate_output(draft, allowed)
            # Re-read authority, eligibility, conditions, warnings and citations.
            current = envelope(controller, session, sid, allow_approved_policy_caveats=True)
            if current != allowed:
                raise ValidationFailure('ARM_A_ENVELOPE_CHANGED')
            validate_output(draft, current)
            step = controller.registry.step(sid)
            claim_map = tuple({**claim, 'presentation_mode': step.claims[i].get('presentation_mode'),
                                **({'policy_support_ids': list(step.claims[i]['policy_support_ids'])} if not claim['evidence_ids'] else {})}
                              for i, claim in enumerate(draft['claims']))
            pages = tuple({**page, 'manual_checksum': controller.registry.checksum,
                           'index_id': controller.registry.index_id,
                           'pdf_page_index': page['pdf_page']-1} for page in draft['citations'])
            response = controller.response('SUPPORTED', ' '.join(c['text'] for c in draft['claims']),
                session, claim_evidence_map=claim_map, cited_pages=pages,
                suggested_step_id=sid if step.kind == 'ACTION' else None,
                reason_codes=('ARM_A_EXACT_REVIEWED_CANONICAL_VALIDATED',))
            response = controller.for_end_user(response) if controller.audience == 'end_user' else response
            trace.update(reason_codes=response.reason_codes,
                         total_ms=(time.perf_counter()-started)*1000)
            return response
        except ValidationFailure as exc:
            known = {'SOURCE_REVIEW_REQUIRED', 'STEP_NOT_ELIGIBLE', 'CLAIM_BOUND_OR_EMPTY',
                     'INVALID_REVIEWED_WORDING', 'END_USER_EXCERPT_DISPLAY_PROHIBITED',
                     'CLAIM_ROLE_REVIEW_REQUIRED', 'UNEXPECTED_TECHNICAL_QUESTION',
                     'DUPLICATE_CLAIM_ID', 'ONE_STEP_DISCIPLINE', 'INVALID_CLAIM_CITATION',
                     'MANDATORY_WARNING_OR_CONDITION_OMITTED', 'INVALID_SOURCE_PAGE',
                     'MISSING_SOURCE_PROVENANCE', 'FIGURE_SEMANTIC_ADAPTER_UNAVAILABLE',
                     'GENERATION_VERSION_RECONFIRM_REQUIRED', 'CONTEXT_BOUND_NO_TRUNCATION',
                     'ARM_A_ENVELOPE_CHANGED', 'ARM_A_CACHE_NOT_ENABLED'}
            code = str(exc) if str(exc) in known else 'ARM_A_VALIDATION_FAILURE'
        except Exception:
            code = 'ARM_A_VALIDATION_FAILURE'
        trace.update(reason_codes=(code,), total_ms=(time.perf_counter()-started)*1000)
        source_gap = code in {'SOURCE_REVIEW_REQUIRED', 'END_USER_EXCERPT_DISPLAY_PROHIBITED',
                             'CLAIM_ROLE_REVIEW_REQUIRED'}
        return controller.response('UNSUPPORTED' if source_gap else 'SYSTEM_ERROR',
            'I could not verify an approved answer for display.' if source_gap else
            'I am temporarily unable to validate the response.', session, reason_codes=(code,))
