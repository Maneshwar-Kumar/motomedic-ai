"""One bounded availability fallback, never a second opinion on rejected content."""
from copy import deepcopy
import threading
from generation_providers import ProviderFailure, ProviderResult
from cloud.grounded_generation.provider import MODEL as PRIMARY_MODEL
from cloud.grounded_generation.claude_provider import CONTRACT as CLAUDE_CONTRACT

AVAILABILITY_FAILURES=frozenset(('PROVIDER_HTTP_500','PROVIDER_HTTP_502','PROVIDER_HTTP_503',
    'PROVIDER_HTTP_504','PROVIDER_UNCONFIGURED'))
CONTRACT={'version':'gemma-haiku-availability-fallback-v1','primary_model':PRIMARY_MODEL,
    'fallback':CLAUDE_CONTRACT,'eligible_failures':sorted(AVAILABILITY_FAILURES),
    'fallback_attempts_per_call':1,'fallback_after_semantic_rejection':False,
    'fallback_after_quota_schema_integrity_or_source_failure':False}

class FallbackProvider:
    cache_capability='unsupported'
    contract=CONTRACT
    def __init__(self,primary,fallback):
        self.primary=primary;self.fallback=fallback;self.last_trace=None;self.lock=threading.Lock()
    def begin_turn(self, operation_id):
        reservation=self.primary.begin_turn(operation_id,availability_fallback=True)
        try:self.fallback.begin_turn()
        except Exception:
            self.primary.end_turn()
            raise
        return reservation
    def end_turn(self):
        self.primary.end_turn();self.fallback.end_turn()
    def count(self,body):
        try:return self.primary.count(body)
        except ProviderFailure as exc:
            if str(exc)not in AVAILABILITY_FAILURES:raise
            return self.fallback.count(body)
    def context(self,policy,evidence,dynamic,schema):
        try:return self.primary.context(policy,evidence,dynamic,schema)
        except ProviderFailure as exc:
            if str(exc)not in AVAILABILITY_FAILURES:raise
            return self.fallback.context(policy,evidence,dynamic,schema)
    def complete(self,policy,evidence,dynamic,schema):
        if not self.lock.acquire(blocking=False):raise ProviderFailure('PROVIDER_CONCURRENCY_LIMIT')
        trace={'model':PRIMARY_MODEL,'generation_calls':0,'fallback_used':False,'attempts':[]}
        self.last_trace=trace
        try:
            try:
                value=self.primary.complete(policy,evidence,dynamic,schema)
                trace.update(deepcopy(value.telemetry or {}));return value
            except ProviderFailure as exc:
                primary=deepcopy(self.primary.last_trace or {})
                trace['attempts'].append({'provider':'gemma','failure_code':str(exc),'trace':primary})
                trace['generation_calls']=primary.get('generation_calls',0)
                if str(exc)not in AVAILABILITY_FAILURES:raise
                trace['fallback_used']=True
            try:
                value=self.fallback.complete(policy,evidence,dynamic,schema)
            except ProviderFailure as exc:
                failed=deepcopy(self.fallback.last_trace or {})
                trace['attempts'].append({'provider':'anthropic','failure_code':str(exc),'trace':failed})
                trace['generation_calls']+=failed.get('generation_calls',0)
                raise
            detail=deepcopy(value.telemetry or {})
            trace['attempts'].append({'provider':'anthropic','trace':detail})
            trace['generation_calls']+=detail.get('generation_calls',0)
            trace['model']=detail.get('model');trace['successful_provider']='anthropic'
            return ProviderResult(value.output,value.input_tokens,value.output_tokens,value.cost_usd,deepcopy(trace))
        finally:self.lock.release()
