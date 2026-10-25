"""Private engineering observation around an unchanged frozen Haiku transport.

No model invocation, ledger write, retry, response parsing or release is provided
by this module. A coordinator may install it only in a fresh hosted diagnostic
operation using the frozen router and existing whole-turn/durable worker path.
"""
from copy import deepcopy
import hashlib
import math

from evidence_registry import content_hash
from cloud.grounded_generation.role_contracts import HAIKU,HAIKU_DRAFT,HAIKU_VERIFIER,OUTPUT_TOKENS,haiku_actual_cost

STOP_REASONS=frozenset(('end_turn','max_tokens','stop_sequence','tool_use','pause_turn','refusal','model_context_window_exceeded'))
REFERENCE='https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons'


def bounded_usage(result,trace):
    """Validate the same scalar token/cache/cost bounds before completeness."""
    if result.get('model')!=HAIKU:return None,['PROVIDER_MODEL_NOT_PINNED']
    errors=[];usage=result.get('usage')
    fields=('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens')
    if type(usage)is not dict or any(type(usage.get(key))is not int or usage[key]<0 for key in fields):
        return None,['USAGE_FIELDS_MISSING_OR_INVALID']
    new,output,created,read=(usage[key] for key in fields);total=new+created+read
    ceiling=trace.get('reserved_input_token_ceiling');maximum=trace.get('reserved_maximum_cost_usd')
    if type(ceiling)is not int or ceiling<1 or type(maximum)not in (int,float) or not math.isfinite(maximum) or maximum<=0:
        errors.append('COMMITTED_PERMIT_BOUNDS_MISSING_OR_INVALID')
    else:
        if not 1<=total<=ceiling or output>OUTPUT_TOKENS:errors.append('USAGE_EXCEEDS_COMMITTED_TOKEN_ENVELOPE')
        elif haiku_actual_cost(new,created,read,output)>maximum:errors.append('USAGE_EXCEEDS_COMMITTED_COST_ENVELOPE')
    if 'cache_creation' in usage:
        detail=usage['cache_creation']
        if (type(detail)is not dict or set(detail)!={'ephemeral_5m_input_tokens','ephemeral_1h_input_tokens'} or
                any(type(value)is not int or value<0 for value in detail.values()) or
                detail.get('ephemeral_1h_input_tokens')!=0 or detail.get('ephemeral_5m_input_tokens')!=created):
            errors.append('CACHE_USAGE_DETAILS_INCONSISTENT')
    if errors:return None,errors
    return {'input_tokens':total,'uncached_input_tokens':new,'output_tokens':output,
        'cache_creation_input_tokens':created,'cache_read_input_tokens':read,
        'estimated_cost_usd':haiku_actual_cost(new,created,read,output)},[]


class SanitizedRoleTransport:
    """Forward each original request/result once and retain only safe scalars."""
    def __init__(self,provider):
        role=getattr(provider,'contract',{}).get('role')
        expected={'private_draft':HAIKU_DRAFT,'semantic_verifier':HAIKU_VERIFIER}.get(role)
        if expected is None or provider.contract!=expected:raise ValueError('EXACT_CURRENT_HAIKU_ROLE_REQUIRED')
        if isinstance(provider.transport,SanitizedRoleTransport):raise ValueError('DIAGNOSTIC_OBSERVER_ALREADY_INSTALLED')
        self.provider=provider;self.original=provider.transport;self.role=role
        self.observations=[];self.counter_calls=0

    def __call__(self,method,path,body,key):
        if method!='POST' or path not in ('messages','messages/count_tokens'):
            raise ValueError('ONLY_EXISTING_NATIVE_ROLE_TRANSPORT_PATHS_ALLOWED')
        if path=='messages/count_tokens':
            self.counter_calls+=1
            return self.original(method,path,body,key)
        trace=deepcopy(self.provider.last_trace or {})
        event={'schema':'motomedic-haiku-scalar-transport-observation-v1','role':self.role,'model':HAIKU,
            'role_contract_sha256':content_hash(self.provider.contract),'request_sha256':content_hash(body),
            'native_role_schema_sha256':content_hash(body['output_config']['format']['schema']),
            'role_policy_sha256':hashlib.sha256(body['system'][0]['text'].encode()).hexdigest(),
            'reserved_input_token_ceiling':trace.get('reserved_input_token_ceiling'),
            'reserved_maximum_cost_usd':trace.get('reserved_maximum_cost_usd'),
            'raw_response_text_logged':False,'raw_request_or_credentials_logged':False,'transport_calls':1,
            'response_observed':False,'adapter_validation_not_bypassed':True,'automatic_retries':0}
        try:result=self.original(method,path,body,key)
        except Exception:
            event['transport_error_observed']=True;self.observations.append(event)
            raise
        event['response_observed']=True
        if type(result)is dict:
            reason=result.get('stop_reason')
            event['provider_model_matches_pin']=result.get('model')==HAIKU
            event['native_stop_reason']=reason if type(reason)is str and reason in STOP_REASONS else 'MISSING_OR_UNRECOGNIZED'
            event['native_stop_reason_recognized']=type(reason)is str and reason in STOP_REASONS
            usage,errors=bounded_usage(result,trace)
            event.update(usage_validation_status='VALID' if usage is not None else 'INVALID',
                         validated_scalar_usage=usage,usage_invalid_predicates=errors)
        else:event.update(native_stop_reason='MISSING_OR_UNRECOGNIZED',usage_validation_status='INVALID',
                          validated_scalar_usage=None,usage_invalid_predicates=['RESPONSE_NOT_OBJECT'])
        self.observations.append(event)
        return result  # Exact object, including incomplete result, reaches original strict guard.


def install_frozen_role_observers(router,release,runtime_lock):
    """Provider-free setup only; frozen source/role identities must match first."""
    from pathlib import Path
    import importlib.util
    path=Path(__file__).with_name('audit_hosted_delivery_cache_v3.py')
    spec=importlib.util.spec_from_file_location('diagnostic_frozen_policy_audit',path)
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    audit.frozen_role_policies(release,runtime_lock)
    if router.contract!=release['model_routing_contract']:raise ValueError('FROZEN_ROUTER_CONTRACT_CHANGED')
    providers=(router.draft,router.verifier)
    if providers[0] is providers[1]:raise ValueError('SEPARATE_DRAFT_AND_VERIFIER_INSTANCES_REQUIRED')
    observers=[SanitizedRoleTransport(provider) for provider in providers]
    for provider,observer in zip(providers,observers):provider.transport=observer
    return observers
