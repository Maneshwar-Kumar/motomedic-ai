"""Recompute observed v4 token/delivery and idle wait accounting; no provider calls."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from architecture_measurement import summarize


def audit(path,run_id):
    raw=json.loads(Path(path).read_text(encoding='utf-8'))
    assert raw['schema_version']=='architecture-comparison-v4'
    assert len(raw['rows'])==len(raw['cache_repeat_rows'])==9
    rows=raw['rows']+raw['cache_repeat_rows']
    assert len({(r['phase'],r['record_id'],r['architecture']) for r in rows})==18
    calls=sorted([c for r in rows for c in r['provider_attempts']],key=lambda c:c['call'])
    assert [c['call'] for c in calls]==list(range(1,len(calls)+1))
    assert len(calls)==raw['external_provider_attempts']<=34
    assert sum(c['attempt_index']>0 for c in calls)<=2
    output=[]
    for row in rows:
        computed=summarize(row)
        saved=row['timing_measurement']
        for key,value in computed.items():
            if type(value) is float: assert abs(value-saved[key])<1e-6,key
            else: assert saved[key]==value,key
        client=row['loopback_client_delivery']
        events=client['events']
        assert [e['at_seconds'] for e in events]==sorted(e['at_seconds'] for e in events)
        if row['route']=='SUPPORTED':
            assert client['terminal_event']=='complete'
            assert client['first_verified_output_seconds']<=client['complete_response_seconds']
            assert row['session_saved_before_first_delivery'] and row['citation_closure_complete']
        else: assert client['complete_response_seconds'] is None
        if row['semantic_cache']=='EXACT_AUTHORITY_VALIDATED_CANDIDATE_HIT':
            assert saved['generator_provider_ttft_seconds'] is None
            assert all(c['kind']=='VERIFY' for c in row['provider_attempts'])
        if client['terminal_event']=='receiver_error':
            assert client['received_verified_blocks']<=row.get('stream_event_count',0)
        else: assert client['received_verified_blocks']==row.get('stream_event_count',0)
        output.append({'record_id':row['record_id'],'architecture':row['architecture'],'phase':row['phase'],
            'route':row['route'],'semantic_cache':row['semantic_cache'],'cache_lookup_seconds':row.get('cache_lookup_seconds'),
            'cache_store_result':row.get('cache_store_result'),'failure_reason':row.get('failure_reason'),
            'provider_requests':len(row['provider_attempts']),'timing':saved,'client':client,
            'retrieval_trace':row.get('retrieval_trace')})
    return {'schema_version':'architecture-v4-result-audit-v1','run_id':run_id,
        'source_report_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        'audited_at_utc':datetime.now(timezone.utc).isoformat(),'audit_decision':'PASS_18_CELLS_ALL_ATTEMPTS_AND_CLIENT_TIMINGS',
        'provider_calls':len(calls),'http_status_counts':dict(Counter(str((c.get('transport') or {}).get('http_status')) for c in calls)),
        'retry_attempts':sum(c['attempt_index']>0 for c in calls),
        'initial_supported':raw['successful_supported_responses'],'repeat_supported':raw['successful_repeat_responses'],
        'cache_repeat_hits':sum(r['semantic_cache']=='EXACT_AUTHORITY_VALIDATED_CANDIDATE_HIT' for r in raw['cache_repeat_rows']),
        'worker_startup_seconds':raw['startup_seconds_excluded_from_turns'],'startup_stages':raw['startup_stages_seconds'],
        'retrieval_control_seconds':raw['retrieval_control_seconds_excluded_from_readiness'],
        'cooldown_seconds':raw['pretrial_cooldown_seconds_excluded_from_turns'],
        'rows':output,'retrieval_paired_controls':raw['retrieval_paired_controls'],
        'actual_browser_or_public_network_measured':False,'p95_established':False,
        'latency_improvement_statistically_established':False,'adjusted_times_are_not_unpaced_measurements':True}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.write_text(json.dumps(audit(args.report,args.run_id),indent=2,allow_nan=False)+'\n',encoding='utf-8')
