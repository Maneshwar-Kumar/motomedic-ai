"""Audit and report the complete hosted golden run without changing runtime."""
import csv, hashlib, json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/arm_a/golden161_validation_v1'

def main():
 data=json.loads((OUT/'partial_results.json').read_text(encoding='utf-8'))
 audit=json.loads((OUT/'dataset_audit.json').read_text(encoding='utf-8'))
 summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
 rows=data['cases']; expected={x['record_id']:x for x in audit['cases']}
 assert data['build_status']=='SUCCESS', 'Hosted build has not completed successfully'
 assert len(rows)==161 and len({r['record_id'] for r in rows})==161
 assert set(expected)=={r['record_id'] for r in rows}
 assert [r['ordinal'] for r in rows]==list(range(1,162))
 for row in rows:
  e=expected[row['record_id']]
  assert row['query_sha256']==hashlib.sha256(e['query'].encode()).hexdigest()
  assert row['expected_route']==e['expected_route']
 assert min(r['gap_since_previous_completion_seconds'] for r in rows[1:])>=7
 assert summary['provider_calls']==0 and summary['retries']==0
 assert summary['record_count']==161
 assert summary['passed']==sum(r['passed'] for r in rows)
 source=[r for r in rows if r['category']=='source_step']
 policy=[r for r in rows if r['category']=='trusted_policy_fixture']
 assert len(source)==92 and len(policy)==69
 failures=[dict(r,query=expected[r['record_id']]['query'],failed_checks=[k for k,v in r['checks'].items() if not v]) for r in rows if not r['passed']]
 registry_path='human_review/agent_release_161/coordinator/approved_package_v3/candidate_registry.json'
 lock=json.loads((ROOT/'MotoMedic_ArmA_Production_20261011/arm_a_release.json').read_text(encoding='utf-8'))
 assert hashlib.sha256((ROOT/registry_path).read_bytes()).hexdigest()==lock['file_sha256'][registry_path]
 registry=json.loads((ROOT/registry_path).read_text(encoding='utf-8'))
 static=[]
 for row in failures:
  if row['category']!='source_step':continue
  sid=expected[row['record_id']]['bound_step'];step=registry['steps'][sid]
  empty=[c['claim_id'] for c in step['claims'] if not c['evidence_ids'] and c.get('policy_support_ids')]
  if empty:static.append({'record_id':row['record_id'],'actual_route':row['actual_route'],'policy_only_claim_ids':empty,'gate_incompatibility':'Current constrained_generator.envelope rejects every claim with empty manual evidence_ids as INVALID_CLAIM_CITATION. Policy support IDs are separately approved but are not manual citations. This is static bound-metadata diagnosis; response reason codes were not captured in the hosted runner.'})
 (OUT/'static_gate_diagnosis.json').write_text(json.dumps({'registry_sha256':lock['file_sha256'][registry_path],'findings':static},indent=2)+'\n',encoding='utf-8')
 breakdown=[]
 for route in sorted({r['expected_route'] for r in source}):
  group=[r for r in source if r['expected_route']==route]
  breakdown.append({'expected_route':route,'count':len(group),'passed':sum(r['passed'] for r in group),'actual_routes':dict(Counter(r['actual_route'] for r in group))})
 verified={'completed':True,'build_id':data['build_id'],'record_count':161,'source_step_count':92,'source_step_passed':sum(r['passed'] for r in source),'strict_total_passed':summary['passed'],'strict_total_failed':summary['failed'],'source_step_breakdown':breakdown,'source_step_wrong_technical_scope':[r['record_id'] for r in source if not r['checks'].get('technical_scope_matches',True)],'source_step_bad_technical_checks':[r['record_id'] for r in source if r['technical_content'] and not all(v for k,v in r['checks'].items() if k!='route_matches')],'trusted_policy_raw_route_matches':sum(r['checks'].get('route_matches',False) for r in policy),'failure_injection_tested':False,'minimum_gap_seconds':summary['minimum_gap_seconds'],'provider_calls':0,'retries':0,'production_http_latency_measured':False,'held_out':False,'duplicate_question_groups':audit['duplicate_question_groups'],'policy_only_claim_incompatibilities':static,'failures':failures}
 (OUT/'verified_results.json').write_text(json.dumps(verified,indent=2)+'\n',encoding='utf-8')
 with (OUT/'cases.csv').open('w',encoding='utf-8',newline='') as f:
  fields=['ordinal','record_id','category','expected_route','actual_route','passed','technical_content','seconds','gap_since_previous_completion_seconds','error']
  writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
 lines=['# Hosted 161-case question wiring validation','',f"Completed all 161 records. Strict recorded checks passed {summary['passed']}/161; {summary['failed']} records failed at least one check.",'',f"Source-backed initial questions: {verified['source_step_passed']}/92 passed. The other 69 records require trusted policy or failure events; raw question text matched {verified['trusted_policy_raw_route_matches']}/69 expected routes, but these are not injected-failure results.",'','## Method','',f"The hosted job used the exact deployed backend image and release bindings, real hybrid retrieval, the Arm A question adapter, controller and display gates. Each record began with only the selected Himalayan BS6 manual confirmed. Seven-second pauses followed each completed case (observed minimum {summary['minimum_gap_seconds']:.6f} seconds). No retries or Gemma/provider calls occurred.",'','This validates the question core. It does not measure production HTTP, Firestore, browser streaming, Gemma reliability, complete adaptive dialogues or held-out accuracy. The approved corpus was used during development. No deployment or runtime tuning was made during this run.','', '## Source-backed results','', '| Expected route | Cases | Passed | Actual routes |','|---|---:|---:|---|']
 for b in breakdown:lines.append(f"| {b['expected_route']} | {b['count']} | {b['passed']} | {json.dumps(b['actual_routes'],sort_keys=True)} |")
 lines += ['',f"Source-backed technical responses with a wrong selected record: {len(verified['source_step_wrong_technical_scope'])}. Technical responses failing wording, citation, evidence or display checks: {len(verified['source_step_bad_technical_checks'])}.",'','The four no-start records share the same input text but encode different intended branches. No case ID or hidden branch facts were supplied to the question core. Their individual mismatches remain in the results.','', '## Gate diagnosis','',f"Bound metadata shows {len(static)} failing source records contain approved policy-only caveats with no OEM evidence IDs. The current composer requires an OEM evidence ID on every claim and rejects such claims. Policy references must remain distinct from manual citations; addressing this needs an explicit runtime contract change, not fabricated citations. The runner did not capture response reason codes, so this static finding is not claimed as the sole cause of every failure. See `static_gate_diagnosis.json`.",'', '## Recorded failures','', '| Record | Category | Expected | Actual | Failed checks |','|---|---|---|---|---|']
 for r in failures:lines.append(f"| {r['record_id']} | {r['category']} | {r['expected_route']} | {r['actual_route']} | {', '.join(r['failed_checks'])} |")
 lines += ['','## Evidence','',f"Cloud Build: `{data['build_id']}`.",'','- `preparation.json`: pinned image, runner and approval versions.','- `build_result.json`: completed hosted build receipt.','- `summary.json`: runner totals and route confusion.','- `verified_results.json`: independent completeness, question hash, interval and subgroup audit; all failure details.','- `cases.csv`: compact per-record results.','- `partial_results.json`: full recorded events and retrieval/citation checks.','- `dataset_audit.json`: exact inputs and duplicate questions.','']
 (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
 print(json.dumps({k:v for k,v in verified.items() if k not in ('failures','duplicate_question_groups','policy_only_claim_incompatibilities')}))
if __name__=='__main__':main()
