"""Pure arithmetic export of frozen matched hosted measurements; no inference."""
import argparse,json,math,hashlib,shutil
from pathlib import Path

def percentile(values,p):
 values=sorted(values)
 if not values:return None
 position=(len(values)-1)*p;lo=math.floor(position);hi=math.ceil(position)
 return values[lo]+(values[hi]-values[lo])*(position-lo)
def wilson(k,n):
 z=1.959963984540054;den=1+z*z/n;center=(k/n+z*z/(2*n))/den
 half=z*math.sqrt(k/n*(1-k/n)/n+z*z/(4*n*n))/den
 return [max(0,center-half),min(1,center+half)]
def valid_delivery(row):
 client=row.get('loopback_client_delivery',{})
 return row['route']=='SUPPORTED' and client.get('terminal_event')=='complete' and client.get('complete_response_seconds') is not None and client.get('received_verified_blocks',0)>0

def summarize(raw):
 assert len(raw['rows'])==60, 'Incomplete run: cannot report a completed30-case benchmark'
 assert len({r['record_id'] for r in raw['rows']})==30
 assert len({(r['record_id'],r['architecture']) for r in raw['rows']})==60
 assert all(sum(r['architecture']==method for r in raw['rows'])==30 for method in ('A_COMPONENT_SELECTION','B_SHORT_GENERATION'))
 out={'schema_version':'ab30-measurements-v1','case_count':30,'method_turns':60,'quantile_method':'linear interpolation at (n-1)*p','interval':'Wilson95percent binomial interval; regression set not a population random sample','timing_boundary':raw['timing_boundary'],'startup_excluded':raw['warmup_seconds_excluded'],'pretrial_cooldown_excluded':raw['pretrial_cooldown_seconds_excluded'],'provider_requests':raw['external_provider_attempts'],'methods':{},'claim_scope':'Reviewed initial LOOKUP/preselected intent regression; delivery success is not independent semantic accuracy','model':raw['model'],'library_versions':raw['library_versions']}
 for method in ('A_COMPONENT_SELECTION','B_SHORT_GENERATION'):
  rows=[r for r in raw['rows'] if r['architecture']==method]
  success=[r for r in rows if valid_delivery(r)]
  m={'turn_count':len(rows),'correctly_delivered':len(success),'not_delivered':len(rows)-len(success),'delivery_success_fraction':len(success)/len(rows),'delivery_success_wilson95':wilson(len(success),len(rows)),'routes':{},'successful_latency_denominator':len(success),'latency':{},'provider_requests':sum(r['provider_requests_this_turn'] for r in rows),'actual_retries':sum(a.get('attempt_index',0)>0 for r in rows for a in r.get('provider_attempts',[]))}
  for row in rows:m['routes'][row['route']]=m['routes'].get(row['route'],0)+1
  fields={'client_first_safe_output_seconds':lambda r:r['loopback_client_delivery']['first_verified_output_seconds'],'client_complete_seconds':lambda r:r['loopback_client_delivery']['complete_response_seconds'],'retrieval_gate_seconds':lambda r:r.get('controller_retrieval_assembly_seconds'),'provider_active_seconds':lambda r:r.get('timing_measurement',{}).get('provider_active_union_seconds'),'idle_pacing_seconds':lambda r:r.get('timing_measurement',{}).get('pacing_idle_only_seconds'),'server_full_excluding_idle_pacing_arithmetic_seconds':lambda r:r.get('timing_measurement',{}).get('full_excluding_idle_pacing_seconds'),'generator_provider_ttft_seconds':lambda r:r.get('timing_measurement',{}).get('generator_provider_ttft_seconds')}
  for label,fn in fields.items():
   values=[fn(r) for r in success if fn(r) is not None]
   m['latency'][label]={'n':len(values),'p50':percentile(values,.5),'p95':percentile(values,.95),'min':min(values) if values else None,'max':max(values) if values else None}
  out['methods'][method]=m
 pairs=[]
 for rid in sorted({r['record_id'] for r in raw['rows']}):
  a=next(r for r in raw['rows'] if r['record_id']==rid and r['architecture']=='A_COMPONENT_SELECTION');b=next(r for r in raw['rows'] if r['record_id']==rid and r['architecture']=='B_SHORT_GENERATION')
  if valid_delivery(a) and valid_delivery(b):pairs.append(b['loopback_client_delivery']['complete_response_seconds']-a['loopback_client_delivery']['complete_response_seconds'])
 out['paired_B_minus_A_client_complete_seconds']={'n_both_successful':len(pairs),'p50':percentile(pairs,.5),'p95':percentile(pairs,.95),'A_faster_pairs':sum(v>0 for v in pairs),'B_faster_pairs':sum(v<0 for v in pairs)}
 out['known_input_tokens']=sum(a.get('input_tokens',0) or 0 for r in raw['rows'] for a in r.get('provider_attempts',[]));out['known_output_tokens']=sum(a.get('output_tokens',0) or 0 for r in raw['rows'] for a in r.get('provider_attempts',[]))
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('result',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=json.loads(a.result.read_text(encoding='utf-8-sig'));a.out.write_text(json.dumps(summarize(d),indent=2),encoding='utf-8')
