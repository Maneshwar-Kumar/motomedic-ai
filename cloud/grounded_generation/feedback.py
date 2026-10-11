"""Source-bound answers to issued clarifications, never initial-query admission."""
import hashlib
import json
from pathlib import Path
from dataclasses import asdict
from controller_contracts import Fact, Outcome, ResponseType
from evidence_registry import content_hash
from cloud.arm_a.rider_contract import issue_choices as legacy_issue, consume_choice as legacy_consume, choice_id

PATH='reports/grounded_generation/prerequisite_review_v1/answer_bindings.json'
SHA='f198399fcaf1b43ddd6b7bbcf03514a11caaea987cc7eb6f28293c6e3c810a9a'

def binding_for(registry,session):
    if not session.pending_rule_id or not session.pending_step_id: return None
    data=(Path(__file__).resolve().parents[2]/PATH).read_bytes()
    if hashlib.sha256(data).hexdigest()!=SHA: raise ValueError('CLARIFICATION_REVIEW_CHANGED')
    manifest=json.loads(data)
    if manifest['manual_sha256']!=registry.checksum: raise ValueError('CLARIFICATION_SOURCE_CHANGED')
    row=next((b for b in manifest['bindings'] if b['rule_id']==session.pending_rule_id),None)
    if not row: return None
    rule=registry.rule(session.pending_rule_id)
    if (registry.candidate['steps'][session.pending_step_id]['canonical_record_id'] not in row['owners'] or not registry.step_ready(session.pending_step_id) or
        content_hash(registry.candidate['rules'][rule.rule_id])!=row['projected_rule_sha256'] or
        rule.clarification_question!=row['clarification_question'] or not rule.rider_resolvable or
        not all(registry.evidence_ready(e) for e in rule.clarification_evidence_ids)):
        return None
    return row

def issue_choices(registry,session,response):
    if response.type!=ResponseType.AMBIGUOUS or session.status!='OPEN':
        return legacy_issue(registry,session,response)
    row=binding_for(registry,session)
    if not row or response.natural_language!=row['clarification_question']:
        return legacy_issue(registry,session,response)
    public,private=[],{}
    for answer,outcome in [('yes',Outcome.OBSERVED_NORMAL),('no',Outcome.OBSERVED_ABNORMAL),('unsure',Outcome.UNCLEAR)]:
        value=row['answer_values'][answer]
        binding={'outcome':outcome.value,'fact':asdict(Fact(value,'BOOLEAN')) if value is not None else None,
            'session_id':session.session_id,'version':session.version,'pending_step_id':session.pending_step_id,
            'pending_rule_id':session.pending_rule_id,'clarification_review_sha256':SHA,'answer':answer}
        key=choice_id(session,binding)
        public.append({'id':key,'label':row['answer_labels'][answer],'outcome':outcome.value})
        private[key]=binding
    return public,private

def consume_choice(registry,session,private,key,version):
    binding=private.get(key,{})
    if binding.get('clarification_review_sha256'):
        row=binding_for(registry,session)
        if not row or binding['clarification_review_sha256']!=SHA: raise ValueError('CLARIFICATION_BINDING_CHANGED')
        value=row['answer_values'].get(binding.get('answer'))
        expected=asdict(Fact(value,'BOOLEAN')) if value is not None else None
        if binding.get('fact')!=expected: raise ValueError('CLARIFICATION_FACT_CHANGED')
    return legacy_consume(session,private,key,version)
