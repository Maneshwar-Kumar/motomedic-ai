"""Bind separate pinned Haiku call roles before generation; no model switching.

Future request forecasts are conservative admission ceilings, not assertions
about an unknown final answer. Every actual complete request is counted again.
"""
from copy import deepcopy
from dataclasses import dataclass,asdict,is_dataclass
import re
import threading
from evidence_registry import content_hash
from generation_providers import ProviderFailure
from cloud.grounded_generation.provider import GemmaProvider
from cloud.grounded_generation.cached_verifier import CachedDraft,CachedVerifier
from cloud.grounded_generation.role_contracts import (CONTRACT as ROUTING_CONTRACT,
    GEMMA,FLASH,HAIKU,GEMMA_DRAFT,GEMMA_VERIFIER,HAIKU_DRAFT,HAIKU_VERIFIER,
    OUTPUT_TOKENS,OUTPUT_JSON_BYTES,GEMMA_INPUT_TPM,ROUTING_THRESHOLD,
    FLASH_INPUT_TOKENS,FLASH_INPUT_TPM,HAIKU_CONTEXT_TOKENS,haiku_maximum_nanodollars)


class GemmaRole(GemmaProvider):
    """Exact policy/schema role over the existing pinned Gemma transport."""
    def __init__(self,reserve,*,role,transport=None,key=None,pre_reserved=False):
        if role not in ('private_draft','semantic_verifier'):raise ValueError('GEMMA_ROLE')
        super().__init__(reserve,transport=transport,key=key,cache_capability='unsupported')
        self.contract=deepcopy(GEMMA_DRAFT if role=='private_draft' else GEMMA_VERIFIER)
        self.central_admission=pre_reserved

    def _new_trace(self):
        trace=super()._new_trace();trace['role']=self.contract['role'];return trace

    def context(self,policy,evidence,dynamic,schema,*,_trace=None,_sizing=False):
        from cloud.grounded_generation.verified_qa import DRAFT_POLICY,DRAFT_SCHEMA,VERIFY_POLICY,VERIFY_SCHEMA
        expected=(DRAFT_POLICY,DRAFT_SCHEMA) if self.contract['role']=='private_draft' else (VERIFY_POLICY,VERIFY_SCHEMA)
        if (policy,schema)!=expected:raise ProviderFailure('GEMMA_MODEL_ROLE_MISMATCH')
        value=super().context(policy,evidence,dynamic,schema,_trace=_trace,_native_window=not _sizing)
        if not _sizing and value[1]>GEMMA_INPUT_TPM:
            self.last_trace['failure_code']='GEMMA_PROJECT_INPUT_TPM_LIMIT'
            raise ProviderFailure('GEMMA_PROJECT_INPUT_TPM_LIMIT')
        return value


@dataclass(frozen=True)
class RolePlan:
    name:str
    routing_count:int
    initial_input_tokens:int
    initial_request_sha256:str
    stable_sha256:str
    draft:object
    verifier:object
    draft_contract_sha256:str
    verifier_contract_sha256:str

    def binding(self):
        return {'version':ROUTING_CONTRACT['version'],'route':self.name,
            'routing_contract_sha256':content_hash(ROUTING_CONTRACT),
            'primary_input_tokens_counted':self.routing_count,
            'selected_draft_input_tokens':self.initial_input_tokens,
            'initial_draft_request_sha256':self.initial_request_sha256,
            'stable_context_sha256':self.stable_sha256,
            'draft_model_contract_sha256':self.draft_contract_sha256,
            'verifier_contract_sha256':self.verifier_contract_sha256}


class RoleRouter:
    contract=ROUTING_CONTRACT
    def __init__(self,draft,verifier,admission):
        self.draft,self.verifier=draft,verifier
        self.haiku_draft,self.haiku_verifier=draft,verifier
        self.admission=admission
        for provider,expected in ((draft,HAIKU_DRAFT),(verifier,HAIKU_VERIFIER)):
            if getattr(provider,'contract',None)!=expected:raise ProviderFailure('ROUTER_MODEL_ROLE_CONTRACT_CHANGED')
        self.last_plan=None
        self.last_count_provider=None
        self.local=threading.local()

    def validate(self,plan):
        if (plan.draft is plan.verifier or plan.draft is not self.draft or plan.verifier is not self.verifier or
            content_hash(plan.draft.contract)!=plan.draft_contract_sha256 or
            content_hash(plan.verifier.contract)!=plan.verifier_contract_sha256 or self.contract!=ROUTING_CONTRACT):
            raise ProviderFailure('ROUTER_SELECTED_ROLE_BINDING_CHANGED')
        validate_role_plan_binding(plan.binding())

    def select(self,stable,dynamic):
        from cloud.grounded_generation.verified_qa import DRAFT_POLICY,DRAFT_SCHEMA
        encoded=deepcopy(dynamic)
        name='HAIKU_DRAFT_HAIKU_VERIFY'
        draft,verifier=self.draft,self.verifier
        chosen=deepcopy(stable)
        chosen['runtime_contract']['draft_model_contract']=deepcopy(draft.contract)
        chosen['runtime_contract']['verifier_contract']=deepcopy(verifier.contract)
        self.last_count_provider=draft
        body,selected_count=draft.context(DRAFT_POLICY,chosen,encoded,DRAFT_SCHEMA)
        plan=RolePlan(name,selected_count,selected_count,content_hash(body),content_hash(chosen),draft,verifier,
                      content_hash(draft.contract),content_hash(verifier.contract))
        self.validate(plan);self.last_plan=plan
        return plan,chosen

    def reservation_plan(self,plan,stable,dynamic,admitted,session):
        """Count fixed future scaffolds, then reserve bounded unknown outputs.

        These placeholders are engineering admission inputs, never answers or
        generation seeds. Actual contexts must fit the reserved hard ceiling.
        """
        from cloud.grounded_generation.verified_qa import (VERSION,DRAFT_POLICY,DRAFT_SCHEMA,
            VERIFY_POLICY,VERIFY_SCHEMA)
        claims=[{'claim_id':'draft:'+str(i),'text':'','role':'PREREQUISITE',
            'evidence_ids':[],'presentation_mode':'VERIFIED_GENERATED_PARAPHRASE','origin':'DRAFT'} for i in range(12)]
        claims += [{'claim_id':'source:'+row['claim_id'],'text':row['text'],'role':row['response_role'],
            'evidence_ids':deepcopy(row['evidence_ids']),'presentation_mode':'VERIFIED_SOURCE_PARAPHRASE',
            'origin':'SOURCE_REQUIRED_DISPLAY'} for row in admitted['required_display']]
        citations=[{'evidence_id':row['evidence_id'],'pdf_page':row['pdf_page'],
            'pdf_page_index':row['pdf_page']-1,'manual_checksum':stable['manual_checksum'],
            'index_id':stable['index_id']} for row in admitted['citation_mapping']]
        final={'route':'SAFETY_STOP','text':'','claims':claims,'citations':citations,
            'clarification_question':'','escalation_uri':None,'trace_id':'0'*32,'session_status':session.status}
        binding={'version':VERSION,'runtime_lock':stable['runtime_contract']['runtime_lock'],
            'draft_model_contract_sha256':plan.draft_contract_sha256,'verifier_contract_sha256':plan.verifier_contract_sha256,
            'question_sha256':content_hash(dynamic['question']),'history_sha256':content_hash(dynamic['history']),
            'session_sha256':content_hash(asdict(session) if is_dataclass(session) else session.__dict__),'response_sha256':'0'*64,
            'evidence_payload_sha256':admitted['payload_sha256'],'source_authority_lock':admitted['authority_lock'],
            'manual_checksum':stable['manual_checksum'],'index_id':stable['index_id'],
            'operation_id':dynamic['history'].get('operation_id'),'role_plan':plan.binding()}
        verification={**dynamic,'complete_proposed_response':final,'declared_question_coverage':'COMPLETE',
            'unanswered_parts':[],'binding':binding,'binding_sha256':'0'*64}
        def counted(provider,policy,payload,schema,*,sizing=False):
            self.last_count_provider=provider
            return provider.context(policy,stable,deepcopy(payload),schema)[1]
        verify_fixed=counted(plan.verifier,VERIFY_POLICY,verification,VERIFY_SCHEMA,sizing=True)
        base_verification=deepcopy(verification)
        base_verification['complete_proposed_response'].update(claims=[],citations=[],text='')
        # Only this full-source/actual-history unavoidable prefix can establish
        # pre-generation quota eligibility. Maximal selected warnings are a
        # forecast, not a claim about the unknown actual finalized response.
        verify_base=counted(plan.verifier,VERIFY_POLICY,base_verification,VERIFY_SCHEMA)
        verdict={'binding_sha256':'0'*64,'decision':'RELEASE_CLARIFICATION','question_coverage':'NEEDS_CLARIFICATION',
            'per_claim_support':[{'claim_id':r['claim_id'],'supported':False,'supported_evidence_ids':[],
                'reason':''} for r in claims],'omissions':[],'conflicts':[],'coverage_limitation_clear':False,
            'clarification_is_rider_resolvable':False,'release_eligible':False,'correction_possible':True}
        correction_fixed=counted(plan.draft,DRAFT_POLICY,{**dynamic,
            'correction_feedback':{'rejected_response':final,'verdict':verdict}},DRAFT_SCHEMA,sizing=True)
        # Each private draft/verdict has a hard JSON byte ceiling. Fixed source
        # display/citation/field scaffolds above are counted, not discarded.
        unknown_verify=2*OUTPUT_JSON_BYTES+512
        unknown_correction=3*OUTPUT_JSON_BYTES+512
        def future(provider,fixed,unknown):
            value=fixed+unknown
            if value>HAIKU_CONTEXT_TOKENS-OUTPUT_TOKENS:
                raise ProviderFailure('ROLE_FUTURE_FORECAST_EXCEEDS_NATIVE_WINDOW')
            return value
        initial_limit=min(HAIKU_CONTEXT_TOKENS-OUTPUT_TOKENS,plan.initial_input_tokens+512)
        limits={'draft':initial_limit,'verify':future(plan.verifier,verify_fixed,unknown_verify),
                'correction':future(plan.draft,correction_fixed,unknown_correction),
                'reverify':future(plan.verifier,verify_fixed,unknown_verify)}
        slots=[]
        for stage,provider in [('draft',plan.draft),('verify',plan.verifier),
                               ('correction',plan.draft),('reverify',plan.verifier)]:
            for attempt in range(1,provider.contract['maximum_attempts_per_call']+1):
                row={'model':provider.contract['model'],'stage':stage,'input_tokens':limits[stage],
                     'output_tokens':OUTPUT_TOKENS,'attempt':attempt}
                if row['model']==HAIKU:row['maximum_nanodollars']=haiku_maximum_nanodollars(row['input_tokens'])
                slots.append(row)
        return {'slots':slots,'role_plan':plan.binding(),'forecast_method':'NATIVE_FIXED_SCAFFOLD_PLUS_BOUNDED_PRIVATE_OUTPUT_BYTES',
            'forecast_is_not_unknown_final_answer_guarantee':True,
            'fixed_verifier_native_tokens':verify_fixed,'fixed_correction_native_tokens':correction_fixed,
            'known_verifier_prefix_native_tokens':verify_base,
            'unknown_verifier_byte_allowance':unknown_verify,'unknown_correction_byte_allowance':unknown_correction,
            'initial_haiku_counter_headroom_tokens':initial_limit-plan.initial_input_tokens,
            'initial_primary_counter_headroom_tokens':0}

    def begin(self,operation_id,plan,stable,dynamic,admitted,session):
        self.validate(plan)
        if content_hash(stable)!=plan.stable_sha256:raise ProviderFailure('ROUTER_STABLE_CONTEXT_CHANGED')
        reservation=self.reservation_plan(plan,stable,dynamic,admitted,session)
        # The ledger retains the audited slot, role and scaffold bindings.
        initial=deepcopy(reservation);initial['slots']=[row for row in initial['slots'] if row['stage'] in ('draft','verify')]
        receipt=self.admission.begin_turn(operation_id,plan=initial)
        self.local.operation_id=operation_id;self.local.initial_forecast=deepcopy(reservation)
        receipt['model_routing']=deepcopy(reservation)
        expected=getattr(plan.draft,'expect_initial_context',None)
        if not callable(expected):raise ProviderFailure('ROUTER_INITIAL_REQUEST_GUARD_REQUIRED')
        expected(plan.initial_request_sha256)
        return receipt

    def begin_correction(self,operation_id,plan,stable,dynamic,admitted,session,feedback,rejected_binding):
        from cloud.grounded_generation.verified_qa import DRAFT_POLICY,DRAFT_SCHEMA
        self.validate(plan)
        initial=getattr(self.local,'initial_forecast',None)
        if (getattr(self.local,'operation_id',None)!=operation_id or not initial or
            initial['role_plan']!=plan.binding()):raise ProviderFailure('ROUTER_CORRECTION_OPERATION_CHANGED')
        if content_hash(stable)!=plan.stable_sha256:raise ProviderFailure('ROUTER_STABLE_CONTEXT_CHANGED')
        self.last_count_provider=plan.draft
        body,count=plan.draft.context(DRAFT_POLICY,stable,deepcopy({**dynamic,
            'correction_feedback':feedback}),DRAFT_SCHEMA)
        reservation=self.reservation_plan(plan,stable,dynamic,admitted,session)
        for key in ('initial_haiku_counter_headroom_tokens','initial_primary_counter_headroom_tokens','known_verifier_prefix_native_tokens'):
            reservation[key]=initial[key]
        reservation['slots']=[row for row in reservation['slots'] if row['stage'] in ('correction','reverify')]
        for slot in reservation['slots']:
            if slot['stage']=='correction':
                slot['input_tokens']=min(HAIKU_CONTEXT_TOKENS-OUTPUT_TOKENS,count+512)
                if slot['model']==HAIKU:slot['maximum_nanodollars']=haiku_maximum_nanodollars(slot['input_tokens'])
        reservation.update(correction_request_sha256=content_hash(body),
            rejected_binding_sha256=content_hash(rejected_binding),verdict_sha256=content_hash(feedback['verdict']))
        receipt=self.admission.reserve_correction(operation_id,plan=reservation)
        plan.draft.expect_initial_context(content_hash(body))
        return receipt

    def end(self):
        self.admission.end_turn()
        self.local.initial_forecast=None;self.local.operation_id=None
        for provider in (self.draft,self.verifier):
            provider.expect_initial_context(None)


def production_router(admission):
    return RoleRouter(CachedDraft(admission.for_model(HAIKU,role='private_draft'),pre_reserved=True),
        CachedVerifier(admission.for_model(HAIKU,role='semantic_verifier'),pre_reserved=True),admission)


def validate_role_plan_binding(value):
    keys={'version','route','routing_contract_sha256','primary_input_tokens_counted',
          'selected_draft_input_tokens','initial_draft_request_sha256','stable_context_sha256',
          'draft_model_contract_sha256','verifier_contract_sha256'}
    if type(value)is not dict or set(value)!=keys:raise ProviderFailure('ROUTER_ROLE_PLAN_SCHEMA_CHANGED')
    pair=ROUTING_CONTRACT['roles'].get(value['route'])
    if (not pair or value['version']!=ROUTING_CONTRACT['version'] or
        value['routing_contract_sha256']!=content_hash(ROUTING_CONTRACT) or
        type(value['primary_input_tokens_counted'])is not int or value['primary_input_tokens_counted']<1 or
        type(value['selected_draft_input_tokens'])is not int or value['selected_draft_input_tokens']<1 or
        any(type(value[k])is not str or not re.fullmatch('[0-9a-f]{64}',value[k]) for k in keys if k.endswith('sha256')) or
        value['draft_model_contract_sha256']!=content_hash(pair['draft']) or
        value['verifier_contract_sha256']!=content_hash(pair['verifier']) or
        value['route']!='HAIKU_DRAFT_HAIKU_VERIFY' or
        value['primary_input_tokens_counted']!=value['selected_draft_input_tokens'] or
        value['selected_draft_input_tokens']>pair['draft']['input_tokens']):
        raise ProviderFailure('ROUTER_SELECTED_ROLE_BINDING_CHANGED')
    return pair
