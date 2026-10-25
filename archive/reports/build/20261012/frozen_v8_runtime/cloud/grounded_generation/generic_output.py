"""Deterministic generation checks; citation validity is not entailment proof."""
from constrained_generator import ValidationFailure

VERSION = 'generic-evidence-output-v1'

def check_output(draft, admitted_ids, actions, clarifications, safety):
    if type(draft) is not dict or set(draft) != {'route','step_id','clarification_id','claims'}:
        raise ValidationFailure('OUTPUT_SCHEMA')
    route=draft['route']
    if (route not in ('SUPPORTED','AMBIGUOUS','UNSUPPORTED','SAFETY_STOP') or
        type(draft['step_id']) is not str or type(draft['clarification_id']) is not str or
        type(draft['claims']) is not list): raise ValidationFailure('OUTPUT_SCHEMA')
    if route=='SAFETY_STOP':
        if draft['claims'] or draft['clarification_id'] or draft['step_id'] not in safety:
            raise ValidationFailure('UNADMITTED_SAFETY_STOP')
        return draft
    if route!='SUPPORTED':
        if draft['claims'] or draft['step_id']: raise ValidationFailure('NON_SUPPORTED_TECHNICAL_CONTENT')
        if route=='AMBIGUOUS':
            if draft['clarification_id'] not in clarifications: raise ValidationFailure('UNADMITTED_CLARIFICATION')
        elif draft['clarification_id']: raise ValidationFailure('OUTPUT_SCHEMA')
        return draft
    if draft['clarification_id'] or not 1<=len(draft['claims'])<=12:
        raise ValidationFailure('OUTPUT_SCHEMA')
    sid=draft['step_id']
    if sid and sid not in actions: raise ValidationFailure('UNPERMITTED_STEP')
    for claim in draft['claims']:
        if type(claim) is not dict or set(claim)!={'text','role','evidence_ids'}:
            raise ValidationFailure('OUTPUT_SCHEMA')
        text,role,ids=claim['text'],claim['role'],claim['evidence_ids']
        if (type(text) is not str or not text.strip() or len(text)>2400 or '?' in text or
            type(ids) is not list or not ids or any(type(e) is not str for e in ids) or
            len(ids)!=len(set(ids)) or not set(ids)<=set(admitted_ids)):
            raise ValidationFailure('INVALID_CLAIM_CITATION')
        if role not in ('FACT','ACTION'): raise ValidationFailure('UNPERMITTED_ROLE')
        if role=='ACTION' and (not sid or not set(ids)&set(actions[sid]['permitted_action_evidence_ids'])):
            raise ValidationFailure('UNPERMITTED_STEP')
    if sum(c['role']=='ACTION' for c in draft['claims'])!=(1 if sid else 0):
        raise ValidationFailure('ONE_STEP_DISCIPLINE')
    return draft
