"""Approved canonical records used only as exact cache entries, never admission.

The original signed approval package and bound planner bytes supply authority.
Generated misses are never inserted; prompt/runtime changes produce new bindings.
"""
import hashlib,json
from copy import deepcopy
from cloud.grounded_generation.policy import VERSION, POLICY_SHA256
from evidence_registry import content_hash

class ReviewedResponses:
    def __init__(self,registry,runtime_lock):
        self.registry=registry;self.runtime_lock=runtime_lock;self.entries={}
        for sid,raw in registry.candidate['steps'].items():
            if raw['kind'] not in ('LOOKUP','ACTION') or not registry.step_ready(sid): continue
            rid=raw['canonical_record_id']
            if rid not in registry._consumer.records:continue
            binding=registry._consumer.records[rid]
            path=registry._consumer.root/binding['planner_file']
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=binding['planner_file_sha256']: raise ValueError('CACHE_SOURCE_BINDING')
            case=json.loads(data)['candidate_case']
            question=case.get('branch_context',{}).get('producer',{}).get('question') or case.get('question')
            if isinstance(question,str): self.entries.setdefault(question,[]).append((sid,binding['planner_file_sha256']))

    def get(self,query,session,scopes,lock):
        # Any typed outcomes, pending fact, correction or exclusion misses. Never
        # interpret state using chat similarity or a semantic lookup.
        if (lock!=self.runtime_lock or session.generation_lock!=lock or session.active_attempts() or
            session.pending_rule_id or session.pending_step_id or session.excluded_branches or
            session.status!='OPEN' or session.scope_reconfirmation_required): return None
        rows=[row for row in self.entries.get(query,[]) if row[0] in scopes]
        if len(rows)!=1:return None
        sid,binding=rows[0]
        if not self.registry.step_ready(sid):return None
        step=self.registry.step(sid)
        claims=[{'text':c['text'],'role':c['response_role'],'evidence_ids':list(c['evidence_ids'])}
            for c in step.claims if c['evidence_ids'] and c['response_role'] in ('FACT','ACTION')]
        if not claims:return None
        return {'output':{'route':'SUPPORTED','scope_ids':[sid],
            'step_id':sid if step.kind=='ACTION' else '', 'clarification_id':'','claims':deepcopy(claims)},
            'authority_binding':content_hash({'version':VERSION,'runtime_lock':lock,
                'policy_sha256':POLICY_SHA256,'source':self.registry.checksum,'index':self.registry.index_id,
                'registry':self.registry.lock,'scope':scopes[sid],'planner_sha256':binding,
                'typed_state':'EMPTY_ACTIVE_STATE_ONLY'})}
