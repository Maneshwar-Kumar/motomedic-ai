"""Pinned Haiku call roles, native windows and permanent cost math.

Retired provider contracts below exist only for immutable historical receipts.
"""
from copy import deepcopy
from decimal import Decimal,ROUND_CEILING

GEMMA='gemma-4-26b-a4b-it'
FLASH='gemini-2.5-flash-lite'
HAIKU='claude-haiku-5-5'
OUTPUT_TOKENS=1800
OUTPUT_JSON_BYTES=16384
GEMMA_INPUT_TPM=16000
GEMMA_CONTEXT_TOKENS=256000
HAIKU_CONTEXT_TOKENS=1000000
ROUTING_THRESHOLD=8192
FLASH_INPUT_TOKENS=1048576
FLASH_INPUT_TPM=250000
VERSION='haiku-draft-finalized-verifier-v3'
SOURCES={'checked_date':'2026-10-12',
    'flash_lite_native_window':'https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite',
    'flash_lite_pricing':'https://ai.google.dev/gemini-api/docs/pricing',
    'gemma_native_window':'https://ai.google.dev/gemma/docs/core/model_card_4',
    'haiku_native_window_and_pricing':'https://platform.claude.com/docs/en/models/haiku-5-5/overview'}


def contract(model,role):
    if model not in (GEMMA,FLASH,HAIKU) or role not in ('private_draft','semantic_verifier'):
        raise ValueError('UNKNOWN_PINNED_MODEL_ROLE')
    result={'provider':'google-generative-language' if model in (GEMMA,FLASH) else 'anthropic',
        'model':model,'role':role,'version':VERSION,
        'context_window_tokens':FLASH_INPUT_TOKENS if model==FLASH else GEMMA_CONTEXT_TOKENS if model==GEMMA else HAIKU_CONTEXT_TOKENS,
        'input_tokens':FLASH_INPUT_TOKENS if model==FLASH else (GEMMA_CONTEXT_TOKENS if model==GEMMA else HAIKU_CONTEXT_TOKENS)-OUTPUT_TOKENS,
        'output_tokens':OUTPUT_TOKENS,'output_json_bytes':OUTPUT_JSON_BYTES,'request_bytes':None,'native_json_schema':True,
        'answer_cache':'DISABLED','fallback_role':False,
        'maximum_attempts_per_call':1 if model==HAIKU else 2,
        'prompt_cache':'EXPLICIT_POLICY_AND_EVIDENCE_PREFIX' if model==HAIKU else 'IMPLICIT_PROVIDER_USAGE_ONLY' if model==FLASH else 'UNSUPPORTED',
        'automatic_retries':0 if model==HAIKU else 1,'retry_rejections':[] if model==HAIKU else [429,503],
        'native_limit_sources':deepcopy(SOURCES)}
    if model==GEMMA:result['project_input_tpm_readback']=GEMMA_INPUT_TPM
    if model==FLASH:
        result.update(project_input_tpm_conservative=FLASH_INPUT_TPM,
            effective_account_quota_verified=False,thinking='disabled',
            thinking_budget=0,paid_primary=True,
            pricing={'usd_per_million':{'input':.10,'output':.40,'cached_input':.01}},
            primary_cost_bound='RETAINED_GLOBAL_999200_TOKEN_ALLOCATION_MAXIMUM_USD_0.39968')
    if model==HAIKU:
        result.update(cache_ttl='5m',minimum_cache_tokens=512,thinking='disabled',effort='medium',
            native_limit_sources={k:v for k,v in SOURCES.items() if k in ('checked_date','haiku_native_window_and_pricing')},
            pricing={'long_context_above_input_tokens':100000,
                'base_usd_per_million':{'input':.10,'output':.50,'cache_write':.125,'cache_read':.01},
                'long_usd_per_million':{'input':.50,'output':2.50,'cache_write':.625,'cache_read':.05}})
    return result


GEMMA_DRAFT=contract(GEMMA,'private_draft')
GEMMA_VERIFIER=contract(GEMMA,'semantic_verifier')
HAIKU_DRAFT=contract(HAIKU,'private_draft')
HAIKU_VERIFIER=contract(HAIKU,'semantic_verifier')
FLASH_DRAFT=contract(FLASH,'private_draft')
CONTRACT={'version':VERSION,'selection':'FIXED_HAIKU_SEPARATE_CALL_ROLES_NO_SIZE_FLIP',
    'roles':{'HAIKU_DRAFT_HAIKU_VERIFY':{'draft':HAIKU_DRAFT,'verifier':HAIKU_VERIFIER}},
    'same_model_is_not_cross_model_agreement':True,
    'route_after_semantic_quota_schema_integrity_or_availability_failure':False,
    'availability_fallback_enabled':False,
    'native_limit_sources':deepcopy(HAIKU_DRAFT['native_limit_sources'])}

# Retired in-memory engineering fixtures and immutable historic reservations
# retain their exact role contract. Serving's router never selects these pairs.
_legacy_sources={k:v for k,v in SOURCES.items() if not k.startswith('flash_lite')}
def _legacy_role(value):
    result=deepcopy(value)
    result['version']='native-context-distinct-role-router-v1'
    result['native_limit_sources']=deepcopy(_legacy_sources)
    return result
LEGACY_CONTRACT={'version':'native-context-distinct-role-router-v1',
    'routing_threshold_tokens':8192,'threshold_is_pre_generation_choice_not_context_rejection':True,
    'roles':{'GEMMA_DRAFT_HAIKU_VERIFY':{'draft':_legacy_role(GEMMA_DRAFT),'verifier':_legacy_role(HAIKU_VERIFIER)},
        'HAIKU_DRAFT_GEMMA_VERIFY':{'draft':_legacy_role(HAIKU_DRAFT),'verifier':_legacy_role(GEMMA_VERIFIER)}},
    'route_after_semantic_quota_schema_integrity_or_availability_failure':False,
    'availability_fallback_enabled':False,'native_limit_sources':deepcopy(_legacy_sources)}


def haiku_maximum_nanodollars(input_tokens,output_tokens=OUTPUT_TOKENS):
    if type(input_tokens)is not int or type(output_tokens)is not int or not 0<input_tokens<=HAIKU_CONTEXT_TOKENS-OUTPUT_TOKENS or not 0<output_tokens<=OUTPUT_TOKENS:
        raise ValueError('HAIKU_COST_INPUT_INVALID')
    write,out=(Decimal('.625'),Decimal('2.50')) if input_tokens>100000 else (Decimal('.125'),Decimal('.50'))
    return int(((Decimal(input_tokens)*write+Decimal(output_tokens)*out)*1000).to_integral_value(rounding=ROUND_CEILING))


def haiku_actual_cost(new,created,read,output):
    total=new+created+read
    rates=(.50,.625,.05,2.50) if total>100000 else (.10,.125,.01,.50)
    return (new*rates[0]+created*rates[1]+read*rates[2]+output*rates[3])/1000000
