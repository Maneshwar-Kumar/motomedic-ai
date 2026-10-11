"""Retrieved-evidence Haiku adapter. No full-manual mode or direct delivery."""
from copy import deepcopy
import json, os, threading, time
from urllib.request import Request, build_opener
from urllib.error import HTTPError
from generation_providers import ProviderFailure, ProviderResult
from cloud.grounded_generation.provider import NoRedirect, unique, INPUT_TOKENS, OUTPUT_TOKENS, REQUEST_BYTES

MODEL = 'claude-haiku-5-5'
CONTRACT = {'provider':'anthropic', 'model':MODEL, 'version':'haiku-evidence-json-v1',
    'input_tokens':INPUT_TOKENS, 'output_tokens':OUTPUT_TOKENS, 'request_bytes':REQUEST_BYTES,
    'native_json_schema':True, 'thinking':'disabled', 'automatic_retries':0,
    'input_usd_per_million':0.10, 'output_usd_per_million':0.50,
    'pricing_checked_date':'2026-10-11', 'prompt_cache':'DISABLED'}
# Reserve the complete permitted request, not an optimistic usage prediction.
MAX_CALL_USD = (INPUT_TOKENS * 0.10 + OUTPUT_TOKENS * 0.50) / 1_000_000

class HTTP:
    def __call__(self, method, path, body, key):
        raw=json.dumps(body,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
        request=Request('https://api.anthropic.com/v1/'+path,data=raw,method=method,
            headers={'Content-Type':'application/json','x-api-key':key,'anthropic-version':'2023-06-01'})
        try:
            with build_opener(NoRedirect).open(request,timeout=25) as response:
                data=response.read(131073)
                if len(data)>131072:raise ProviderFailure('PROVIDER_OUTPUT_BYTE_BOUND')
                return json.loads(data,object_pairs_hook=unique,
                    parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
        except HTTPError as exc:
            raise ProviderFailure('CLAUDE_HTTP_'+str(exc.code)) from None
        except ProviderFailure:raise
        except Exception:raise ProviderFailure('CLAUDE_TRANSPORT_OR_SCHEMA_FAILURE') from None

class ClaudeProvider:
    cache_capability='unsupported'
    contract=CONTRACT
    def __init__(self,reserve,*,reserve_cost,transport=None,key=None):
        self.reserve=reserve;self.reserve_cost=reserve_cost
        self.transport=transport or HTTP();self.key=key or os.environ.get('ANTHROPIC_API_KEY')
        self.lock=threading.Lock();self.last_trace=None
        self.turn=threading.local()
    def begin_turn(self):
        if not callable(self.reserve_cost):raise ProviderFailure('CLAUDE_SPEND_GUARD_UNCONFIGURED')
        self.reserve_cost(4*MAX_CALL_USD,MODEL)
        self.turn.remaining=4
    def end_turn(self):
        self.turn.remaining=None
    def _count(self,body):
        if not self.key:raise ProviderFailure('CLAUDE_UNCONFIGURED')
        counted={k:deepcopy(v) for k,v in body.items() if k not in ('max_tokens','stream')}
        result=self.transport('POST','messages/count_tokens',counted,self.key)
        value=result.get('input_tokens')
        if type(value)is not int or value<1:raise ProviderFailure('EXACT_TOKEN_COUNT_UNAVAILABLE')
        return value
    def count(self,body):
        # Composer counts its finalized presentation using the historical wire shape.
        messages=[{'role':'user','content':[{'type':'text','text':p['text']} for c in body.get('contents',[]) for p in c.get('parts',[])]}]
        return self._count({'model':MODEL,'messages':messages,'thinking':{'type':'disabled'}})
    def context(self,policy,evidence,dynamic,schema):
        body={'model':MODEL,'max_tokens':OUTPUT_TOKENS,'system':policy,
            'messages':[{'role':'user','content':json.dumps({'assembled_evidence':evidence,'request':dynamic},
                sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))}],
            'thinking':{'type':'disabled'},'output_config':{'format':{'type':'json_schema','schema':deepcopy(schema)}}}
        if len(json.dumps(body,ensure_ascii=False,separators=(',',':')).encode())>REQUEST_BYTES:
            raise ProviderFailure('COMPLETE_CONTEXT_BYTE_BOUND_NO_TRUNCATION')
        count=self._count(body)
        if count>INPUT_TOKENS:raise ProviderFailure('COMPLETE_CONTEXT_TOKEN_BOUND_NO_TRUNCATION')
        return body,count
    def complete(self,policy,evidence,dynamic,schema):
        trace={'model':MODEL,'provider':'anthropic','generation_calls':0,'retry_count':0,
            'cached_tokens':0,'provider_cache':'DISABLED','raw_content_logged':False,
            'token_counter':'ANTHROPIC_COUNT_TOKENS','token_counter_is_estimate':True}
        self.last_trace=trace
        if not self.key:raise ProviderFailure('CLAUDE_UNCONFIGURED')
        if not callable(self.reserve_cost):raise ProviderFailure('CLAUDE_SPEND_GUARD_UNCONFIGURED')
        if not self.lock.acquire(blocking=False):raise ProviderFailure('PROVIDER_CONCURRENCY_LIMIT')
        try:
            body,count=self.context(policy,evidence,dynamic,schema)
            trace['input_tokens_counted']=count
            remaining=getattr(self.turn,'remaining',None)
            if remaining is None:self.reserve_cost(MAX_CALL_USD,MODEL)
            elif remaining<=0:raise ProviderFailure('CLAUDE_UNRESERVED_ATTEMPT')
            else:self.turn.remaining=remaining-1
            self.reserve(count+OUTPUT_TOKENS,'generation')
            trace['reserved_maximum_cost_usd']=MAX_CALL_USD
            started=time.monotonic();trace['generation_calls']=1
            result=self.transport('POST','messages',body,self.key)
            trace['provider_seconds']=time.monotonic()-started
            if result.get('model')!=MODEL:raise ProviderFailure('PROVIDER_MODEL_MISMATCH')
            if result.get('stop_reason')!='end_turn':raise ProviderFailure('PROVIDER_INCOMPLETE_OR_REFUSED')
            blocks=result.get('content')
            if type(blocks)is not list or len(blocks)!=1 or blocks[0].get('type')!='text' or type(blocks[0].get('text'))is not str:
                raise ProviderFailure('PROVIDER_INVALID_PARTS')
            usage=result.get('usage',{})
            for field in ('input_tokens','output_tokens'):
                if type(usage.get(field))is not int or usage[field]<0:raise ProviderFailure('PROVIDER_USAGE_MISSING')
            if usage['input_tokens']>INPUT_TOKENS or usage['output_tokens']>OUTPUT_TOKENS:
                raise ProviderFailure('PROVIDER_TOKEN_BOUND')
            if any(usage.get(k,0)!=0 for k in ('cache_creation_input_tokens','cache_read_input_tokens')):
                raise ProviderFailure('PROVIDER_UNEXPECTED_CACHE_USAGE')
            output=json.loads(blocks[0]['text'],object_pairs_hook=unique,
                parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
            cost=(usage['input_tokens']*.10+usage['output_tokens']*.50)/1_000_000
            trace.update(input_tokens=usage['input_tokens'],output_tokens=usage['output_tokens'],estimated_cost_usd=cost)
            return ProviderResult(output,usage['input_tokens'],usage['output_tokens'],cost,deepcopy(trace))
        except ProviderFailure:raise
        except Exception:raise ProviderFailure('PROVIDER_INVALID_JSON') from None
        finally:self.lock.release()
