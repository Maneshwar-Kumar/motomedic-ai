"""Exact Gemma API token counting, bounded transport and provider cache capability.

Never logs request/response text or credentials. No semantic-verifier request.
All attempts reserve their maximum token allowance before transmission.
"""
from copy import deepcopy
import hashlib
import json
import os
import threading
import time
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from generation_providers import ProviderFailure, ProviderResult

MODEL = 'gemma-4-26b-a4b-it'
INPUT_TOKENS = 8192
OUTPUT_TOKENS = 1800
REQUEST_BYTES = 65536

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def unique(pairs):
    obj = {}
    for k,v in pairs:
        if k in obj: raise ValueError('DUPLICATE_JSON_KEY')
        obj[k] = v
    return obj

class HTTP:
    def __call__(self, method, path, body, key):
        raw = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False,separators=(',',':')).encode()
        request = Request('https://generativelanguage.googleapis.com/v1beta/'+path,
            data=raw, method=method, headers={'Content-Type':'application/json','x-goog-api-key':key})
        try:
            with build_opener(NoRedirect).open(request, timeout=25) as response:
                data=response.read(131073)
                if len(data)>131072: raise ProviderFailure('PROVIDER_OUTPUT_BYTE_BOUND')
                return json.loads(data, object_pairs_hook=unique,
                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except HTTPError as exc:
            # No provider error body: it can contain echoed rider/source data.
            raise ProviderFailure('PROVIDER_HTTP_'+str(exc.code)) from None
        except ProviderFailure: raise
        except Exception: raise ProviderFailure('PROVIDER_TRANSPORT_OR_SCHEMA_FAILURE') from None

class GemmaProvider:
    def __init__(self, reserve, *, transport=None, key=None, cache_capability='unsupported', clock=time.monotonic):
        self.reserve=reserve
        self.transport=transport or HTTP()
        self.key=key or os.environ.get('MOTOMEDIC_GEMINI_API_KEY')
        self.cache_capability=cache_capability
        if cache_capability not in ('unsupported','explicit'): raise ValueError('CACHE_CAPABILITY')
        self.clock=clock
        self.cache={}
        self.lock=threading.Lock()
        self.last_trace=None

    def count(self, body):
        if not self.key: raise ProviderFailure('PROVIDER_UNCONFIGURED')
        result=self.transport('POST','models/'+MODEL+':countTokens',
            {'generateContentRequest':{'model':'models/'+MODEL,**body}},self.key)
        n=result.get('totalTokens')
        if type(n) is not int or n<1: raise ProviderFailure('EXACT_TOKEN_COUNT_UNAVAILABLE')
        return n

    def begin_turn(self, operation_id, *, availability_fallback=False):
        begin=getattr(self.reserve,'begin_turn',None)
        if not callable(begin):
            raise ProviderFailure('WHOLE_TURN_ADMISSION_UNCONFIGURED')
        return begin(operation_id,attempts=12 if availability_fallback else 8)

    def end_turn(self):
        end=getattr(self.reserve,'end_turn',None)
        if callable(end):end()

    def context(self,policy,evidence,dynamic,schema):
        body={'systemInstruction':{'parts':[{'text':policy}]},
            'contents':[{'role':'user','parts':[{'text':json.dumps(evidence,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))}]},
                {'role':'user','parts':[{'text':json.dumps(dynamic,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))}]}],
            'generationConfig':{'maxOutputTokens':OUTPUT_TOKENS,'temperature':0,
                'responseMimeType':'application/json','responseJsonSchema':deepcopy(schema),
                'thinkingConfig':{'thinkingLevel':'minimal'}}}
        if len(json.dumps(body,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode())>REQUEST_BYTES:
            raise ProviderFailure('COMPLETE_CONTEXT_BYTE_BOUND_NO_TRUNCATION')
        count=self.count(body)
        if count>INPUT_TOKENS: raise ProviderFailure('COMPLETE_CONTEXT_TOKEN_BOUND_NO_TRUNCATION')
        return body,count

    def complete(self, policy, evidence, dynamic, schema):
        trace={'model':MODEL,'generation_calls':0,'verifier_calls':0,'retry_count':0,
            'provider_cache':'UNSUPPORTED_EXACT_MODEL','cached_tokens':0,
            'raw_content_logged':False,'token_counter':'PROVIDER_COUNT_TOKENS'}
        self.last_trace=trace
        if not self.key: raise ProviderFailure('PROVIDER_UNCONFIGURED')
        if not self.lock.acquire(blocking=False): raise ProviderFailure('PROVIDER_CONCURRENCY_LIMIT')
        try:
            body,count=self.context(policy,evidence,dynamic,schema)
            system=body['systemInstruction'];stable,varying=body['contents']
            trace['input_tokens_counted']=count
            if count>INPUT_TOKENS: raise ProviderFailure('COMPLETE_CONTEXT_TOKEN_BOUND_NO_TRUNCATION')
            cache_key=hashlib.sha256(json.dumps({'model':MODEL,'system':system,'stable':stable,'schema':schema},sort_keys=True).encode()).hexdigest()
            if self.cache_capability=='explicit':
                entry=self.cache.get(cache_key)
                if entry and entry[1]<=self.clock(): entry=None; self.cache.pop(cache_key,None)
                if not entry:
                    # Actual support is confirmed out of band; no padding to meet minimum.
                    stable_tokens=self.count({'systemInstruction':system,'contents':[stable]})
                    self.reserve(stable_tokens,'prompt_cache')
                    try:
                        created=self.transport('POST','cachedContents',{'model':'models/'+MODEL,
                            'systemInstruction':system,'contents':[stable],'ttl':'300s'},self.key)
                        name=created['name']
                        if not isinstance(name,str) or not name.startswith('cachedContents/'): raise ValueError()
                        entry=(name,self.clock()+240)
                        if len(self.cache)>=64: self.cache.pop(next(iter(self.cache)))
                        self.cache[cache_key]=entry
                    except Exception:
                        trace['provider_cache']='CACHE_CREATE_MISS_NO_PADDING'
                if entry:
                    body.pop('systemInstruction')
                    body['contents']=[varying]
                    body['cachedContent']=entry[0]
                    trace['provider_cache']='EXPLICIT_VERSIONED_CONTEXT'
            started=time.monotonic()
            for attempt in range(2):
                self.reserve(count+OUTPUT_TOKENS,'generation')
                trace['generation_calls']+=1
                try:
                    response=self.transport('POST','models/'+MODEL+':generateContent',body,self.key)
                    break
                except ProviderFailure as exc:
                    # Retry only an explicit rejection, never uncertain timeout/delivery.
                    if attempt==0 and str(exc) in ('PROVIDER_HTTP_429','PROVIDER_HTTP_503'):
                        trace['retry_count']=1
                        continue
                    raise
            trace['provider_seconds']=time.monotonic()-started
            trace['model_version_matches']=response.get('modelVersion')==MODEL
            if response.get('modelVersion')!=MODEL: raise ProviderFailure('PROVIDER_MODEL_MISMATCH')
            candidates=response.get('candidates',[])
            trace['candidate_count']=len(candidates)
            if candidates:
                finish=candidates[0].get('finishReason')
                trace['finish_reason']=finish if finish in ('STOP','MAX_TOKENS','SAFETY','RECITATION','OTHER') else 'UNRECOGNIZED'
            if len(candidates)!=1 or candidates[0].get('finishReason')!='STOP':
                raise ProviderFailure('PROVIDER_INCOMPLETE_OR_REFUSED')
            parts=candidates[0].get('content',{}).get('parts',[])
            # Gemma's confirmed empty thought marker carries no reasoning or
            # answer text. Match this exact shape only; real thought content fails.
            def empty_marker(p):
                return type(p) is dict and set(p)=={'text','thought'} and p['text']=='' and p['thought'] is True
            markers=sum(empty_marker(p) for p in parts)
            parts=[p for p in parts if not empty_marker(p)]
            trace['empty_thought_markers']=markers
            if not parts or any(type(p.get('text')) is not str or p.get('thought') or
                ('thought' in p and type(p['thought']) is not bool) or
                set(p)-{'text','thought'} for p in parts): raise ProviderFailure('PROVIDER_INVALID_PARTS')
            usage=response.get('usageMetadata',{})
            for field in ('promptTokenCount','candidatesTokenCount','totalTokenCount'):
                if type(usage.get(field)) is not int or usage[field]<0: raise ProviderFailure('PROVIDER_USAGE_MISSING')
            if usage.get('thoughtsTokenCount',0)!=0: raise ProviderFailure('PROVIDER_UNBOUNDED_THINKING')
            if usage['promptTokenCount']>INPUT_TOKENS or usage['candidatesTokenCount']>OUTPUT_TOKENS:
                raise ProviderFailure('PROVIDER_TOKEN_BOUND')
            cached=usage.get('cachedContentTokenCount',0)
            if type(cached) is not int or cached<0: raise ProviderFailure('PROVIDER_CACHE_USAGE_INVALID')
            trace.update(input_tokens=usage['promptTokenCount'],output_tokens=usage['candidatesTokenCount'],cached_tokens=cached)
            output=json.loads(''.join(p['text'] for p in parts),object_pairs_hook=unique,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            return ProviderResult(output,usage['promptTokenCount'],usage['candidatesTokenCount'],None,deepcopy(trace))
        except ProviderFailure: raise
        except Exception: raise ProviderFailure('PROVIDER_INVALID_JSON') from None
        finally: self.lock.release()
