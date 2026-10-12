"""Pinned paid Flash-Lite drafting; complete native counting, no role fallback."""
from copy import deepcopy
from generation_providers import ProviderFailure,ProviderResult
from cloud.grounded_generation.provider import GemmaProvider
from cloud.grounded_generation.role_contracts import FLASH,FLASH_DRAFT,FLASH_INPUT_TOKENS,FLASH_INPUT_TPM

MODEL=FLASH


class FlashLiteProvider(GemmaProvider):
    model=MODEL
    input_tokens=FLASH_INPUT_TOKENS
    thinking={'thinkingBudget':0}
    contract=FLASH_DRAFT

    def __init__(self,reserve,*,transport=None,key=None,pre_reserved=False):
        super().__init__(reserve,transport=transport,key=key,cache_capability='unsupported')
        self.central_admission=pre_reserved
        self.contract=deepcopy(FLASH_DRAFT)

    @classmethod
    def _new_trace(cls):
        trace=super()._new_trace()
        trace.update(role='private_draft',provider_cache='IMPLICIT_PROVIDER_USAGE_ONLY',
                     paid_primary=True,cache_hit_observed=False)
        return trace

    def context(self,policy,evidence,dynamic,schema,*,_trace=None,_sizing=False):
        from cloud.grounded_generation.verified_qa import DRAFT_POLICY,DRAFT_SCHEMA
        if (policy,schema)!=(DRAFT_POLICY,DRAFT_SCHEMA):raise ProviderFailure('PRIMARY_MODEL_ROLE_MISMATCH')
        body,count=super().context(policy,evidence,dynamic,schema,_trace=_trace)
        if not _sizing and count>FLASH_INPUT_TPM:
            self.last_trace['failure_code']='PRIMARY_PROJECT_INPUT_TPM_LIMIT'
            raise ProviderFailure('PRIMARY_PROJECT_INPUT_TPM_LIMIT')
        return body,count

    def complete(self,policy,evidence,dynamic,schema):
        result=super().complete(policy,evidence,dynamic,schema)
        cached=result.telemetry.get('cached_tokens',0)
        cost=((result.input_tokens-cached)*.10+cached*.01+result.output_tokens*.40)/1000000
        trace=deepcopy(result.telemetry)
        trace.update(estimated_cost_usd=cost,cache_hit_observed=cached>0,
                     primary_cost_bound='RETAINED_GLOBAL_999200_TOKEN_ALLOCATION_MAXIMUM_USD_0.39968')
        self.last_trace=deepcopy(trace)
        return ProviderResult(result.output,result.input_tokens,result.output_tokens,cost,trace)
