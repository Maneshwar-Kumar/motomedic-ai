"""Localhost SSE receiver and interval audit for engineering timing only.

No public API/browser, raw source or rider text is retained. Producer owns the
SQLite connection in its thread; SSE contains already verified delivery packets.
"""
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import time
from urllib.request import build_opener, ProxyHandler
import uuid

from verified_delivery_stream import VerifiedDeliveryStream


def union(intervals):
    merged=[]
    for a,b in sorted((a,b) for a,b in intervals if b>a):
        if merged and a<=merged[-1][1]: merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else: merged.append((a,b))
    return merged


def duration(intervals, end):
    return sum(b-a for a,b in union([(max(0,a),min(end,b)) for a,b in intervals]))


def summarize(row):
    calls=row['provider_attempts']
    active=[(c['started_at_seconds'],c['finished_at_seconds']) for c in calls]
    waits=[(c.get('admission_started_at_seconds',c['started_at_seconds']-c.get('admission_wait_seconds',0)),
            c['started_at_seconds']) for c in calls]
    waits += [(c['retry_backoff_started_at_seconds'],c['retry_backoff_finished_at_seconds'])
              for c in calls if 'retry_backoff_started_at_seconds' in c]
    waits += [(c['admission_started_at_seconds'],c['admission_finished_at_seconds'])
              for c in row.get('admission_failures',[]) if 'admission_started_at_seconds' in c]
    # Remove only waiting with no provider work occurring anywhere in this turn.
    idle=[]
    for a,b in union(waits):
        parts=[(a,b)]
        for c,d in union(active):
            next_parts=[]
            for x,y in parts:
                if d<=x or c>=y: next_parts.append((x,y))
                else:
                    if x<c: next_parts.append((x,c))
                    if d<y: next_parts.append((d,y))
            parts=next_parts
        idle.extend(parts)
    generation=[c for c in calls if c['kind']!='VERIFY']
    tokens=[]
    for c in generation:
        trace=c.get('transport') or {}
        first=trace.get('first_visible_token_seconds')
        base=trace.get('provider_transport_started_at_seconds')
        if first is not None and base is not None: tokens.append((base+first,first,c['call']))
    first=min(tokens,default=None)
    end=row.get('complete_response_seconds') or row.get('failed_attempt_seconds',0)
    out={'retrieval_wall_seconds':row.get('controller_retrieval_assembly_seconds'),
         'ttft_from_turn_start_seconds':first[0] if first else None,
         'generator_provider_ttft_seconds':first[1] if first else None,
         'ttft_provider_call':first[2] if first else None,
         'ttfo_verified_sink_seconds':row.get('first_stream_event_seconds'),
         'full_response_seconds':row.get('complete_response_seconds'),
         'failed_turn_seconds':row.get('failed_attempt_seconds'),
         'provider_pacing_wait_union_seconds':duration(waits,end),
         'provider_active_union_seconds':duration(active,end),
         'pacing_idle_only_seconds':duration(idle,end),
         'pacing_included_in_observed_times':True,
         'adjusted_times_are_arithmetic_not_observed_unpaced':True}
    for name,value in (('ttft',out['ttft_from_turn_start_seconds']),
                       ('ttfo',out['ttfo_verified_sink_seconds']),('full',row.get('complete_response_seconds'))):
        out[name+'_excluding_idle_pacing_seconds']=None if value is None else value-duration(idle,value)
    return out


def measured_sse_turn(producer):
    """Call producer(stream) once; receive flushed SSE over real loopback HTTP.

    The supplied producer creates/closes its SQLite store in its own thread.
    Shared perf_counter maps engine and receiver intervals in one process.
    """
    stream=VerifiedDeliveryStream()
    path='/'+uuid.uuid4().hex
    holder={}
    pool=ThreadPoolExecutor(max_workers=1)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            if self.path!=path:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            def produce():
                holder['engine_started_at_client_seconds']=time.perf_counter()-holder['request_started']
                try: return producer(stream)
                except Exception:
                    if not stream.closed: stream.finish({'route':'SYSTEM_ERROR'})
                    raise
            holder['future']=pool.submit(produce)
            for frame in stream.iter_sse(timeout_seconds=10):
                self.wfile.write(frame)
                self.wfile.flush()
    class SilentServer(HTTPServer):
        def handle_error(self,*args): pass
    server=SilentServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.05},daemon=True)
    thread.start()
    holder['request_started']=time.perf_counter()
    observations=[]
    receiver_failure=None
    receiver_failed_at=None
    try:
        try:
            opener=build_opener(ProxyHandler({}))
            with opener.open('http://127.0.0.1:'+str(server.server_port)+path,timeout=240) as response:
                kind=None
                data=None
                for raw in response:
                    line=raw.decode('utf-8').rstrip('\r\n')
                    if line.startswith('event: '): kind=line[7:]
                    if line.startswith('data: '): data=json.loads(line[6:])
                    if not line and kind is not None:
                        observations.append({'event':kind,'at_seconds':time.perf_counter()-holder['request_started'],
                            'block':data.get('block'),'route':data.get('route')})
                        if kind in ('complete','error'): break
                        kind,data=None,None
            if not observations or observations[-1]['event'] not in ('complete','error'):
                raise ValueError('Missing terminal')
        except Exception as exc:
            receiver_failure=type(exc).__name__
            receiver_failed_at=time.perf_counter()-holder['request_started']
        future=holder.get('future')
        try:
            if future is None: raise RuntimeError('Producer not started')
            row=future.result(timeout=240)
        except Exception as exc:
            row={'route':'SYSTEM_ERROR','provider_attempts':[],'server_request_setup_seconds':0.,
                 'complete_response_seconds':None,'failed_attempt_seconds':time.perf_counter()-holder['request_started'],
                 'failure_reason':'ENGINE_OR_RECEIVER_START_FAILED','failure_class':type(exc).__name__}
        blocks=[e for e in observations if e['event']=='verified_block']
        terminal=observations[-1] if observations else {'event':'error','at_seconds':time.perf_counter()-holder['request_started']}
        answer_offset=(row['answer_turn_started_monotonic_seconds']-holder['request_started']
            if 'answer_turn_started_monotonic_seconds' in row else
            row['server_request_setup_seconds']+holder.get('engine_started_at_client_seconds',0))
        if receiver_failure:
            row['engine_route_before_receiver_failure']=row['route']
            row['engine_complete_response_seconds_before_receiver_failure']=row.get('complete_response_seconds')
            row['route']='SYSTEM_ERROR'
            row['complete_response_seconds']=None
            row['failed_attempt_seconds']=max(0,time.perf_counter()-holder['request_started']-answer_offset)
            row['loopback_receiver_failure_class']=receiver_failure
            row['failure_reason']='LOOPBACK_RECEIVER_FAILED'
        row['loopback_client_delivery']={'measurement':'ACTUAL_LOCALHOST_HTTP_SSE_NOT_BROWSER_OR_PUBLIC_NETWORK',
            'first_verified_output_seconds':blocks[0]['at_seconds'] if blocks else None,
            'last_verified_block_seconds':blocks[-1]['at_seconds'] if blocks else None,
            'complete_response_seconds':terminal['at_seconds'] if terminal['event']=='complete' and not receiver_failure else None,
            'terminal_event_seconds':receiver_failed_at if receiver_failure else terminal['at_seconds'],
            'terminal_event':'receiver_error' if receiver_failure else terminal['event'],
            'engine_started_at_client_seconds':holder.get('engine_started_at_client_seconds',0),
            'answer_turn_started_at_client_seconds':answer_offset,
            'received_verified_blocks':len(blocks),'events':observations,
            'raw_content_logged':False}
        timing=summarize(row)
        timing['ttft_from_client_request_seconds']=None if timing['ttft_from_turn_start_seconds'] is None else answer_offset+timing['ttft_from_turn_start_seconds']
        row['timing_measurement']=timing
        return row
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        pool.shutdown(wait=True)
