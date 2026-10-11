"""Compare the frozen baseline and completed targeted policy-caveat candidate."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/arm_a/policy_caveats_v2'
BASE=ROOT/'reports/arm_a/golden161_validation_v1'
def main():
 prep=json.loads((OUT/'preparation.json').read_text(encoding='utf-8'))
 assert hashlib.sha256((BASE/'verified_results.json').read_bytes()).hexdigest()==prep['baseline_verified_results_sha256']
 data=json.loads((OUT/'partial_results.json').read_text(encoding='utf-8'));summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
 old={r['record_id']:r for r in json.loads((BASE/'partial_results.json').read_text(encoding='utf-8'))['cases']}
 rows=data['cases'];targets=prep['target_records']
 assert data['build_status']=='SUCCESS' and len(rows)==len(targets)
 software=json.loads((OUT/'software_checks.json').read_text(encoding='utf-8'))
 assert software['passed'] is True and software['test_count']==125
 assert {r['record_id'] for r in rows}==set(targets)
 assert len({r['record_id'] for r in rows})==len(rows)
 assert all(r['query_sha256']==old[r['record_id']]['query_sha256'] for r in rows)
 assert all(r['expected_route']==old[r['record_id']]['expected_route'] for r in rows)
 assert min(r['gap_since_previous_completion_seconds'] for r in rows[1:])>=7
 assert summary['provider_calls']==0 and summary['retries']==0
 comparison=[{'record_id':r['record_id'],'expected_route':r['expected_route'],'baseline_route':old[r['record_id']]['actual_route'],'baseline_passed':old[r['record_id']]['passed'],'candidate_route':r['actual_route'],'candidate_passed':r['passed'],'checks':r['checks'],'reason_codes':r['response_reason_codes']} for r in rows]
 result={'build_id':data['build_id'],'target_count':len(targets),'baseline_target_passed':sum(old[rid]['passed'] for rid in targets),'candidate_target_passed':sum(r['passed'] for r in rows),'candidate_target_failed':sum(not r['passed'] for r in rows),'minimum_gap_seconds':summary['minimum_gap_seconds'],'provider_calls':0,'retries':0,'all_cases_same_raw_questions':True,'baseline_preserved':True,'deployment_changed':False,'software_checks_passed':software['test_count'],'technical_bad_checks':[r['record_id'] for r in rows if r['technical_content'] and not all(r['checks'].values())],'comparison':comparison,'remaining_baseline_source_failures':[rid for rid,r in old.items() if r['category']=='source_step' and not r['passed'] and rid not in targets]}
 (OUT/'comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 lines=['# Exact approved policy-caveat validation','',f"All {software['test_count']} hosted software checks passed.",'',f"Targeted hosted regression: {result['candidate_target_passed']}/{len(targets)} passed, compared with {result['baseline_target_passed']}/{len(targets)} in the preserved baseline.",'','## Change','', 'Technical claims retain OEM evidence, applicability, mandatory warnings, claim mappings and immutable page citations. Exact policy-only caveats can use their approved, intact PRODUCT_POLICY references. Approval is bound to the same selected record and exact wording. Policy IDs cannot become manual citations, cover mandatory manual warnings or authorize a changed technical claim. Arm A and finite approved safety wording use this allowance; the B generator remains strict.','',f"Both runs used identical raw questions and the same immutable manual/index. Targeted pauses were seven seconds after each completed case (minimum {summary['minimum_gap_seconds']:.6f} seconds); no retries or model-provider calls. This is hosted real-retrieval core validation, not production HTTP, browser, Gemma or full adaptive-dialogue testing.",'', '## Comparison','', '| Record | Expected | Baseline | Candidate | Passed |','|---|---|---|---|---|']
 for r in comparison:lines.append(f"| {r['record_id']} | {r['expected_route']} | {r['baseline_route']} | {r['candidate_route']} | {r['candidate_passed']} |")
 lines += ['','## Limits and retained failures','',f"The complete baseline source-backed result was 61/92. Only the {len(targets)} selected caveat failures were rerun. {len(result['remaining_baseline_source_failures'])} other baseline source failures remain open; this targeted result is not a new full-corpus pass rate. The 69 policy/outage fixtures still need separate trusted-event injection testing. Existing quality holds and conservative question selection remain active.",'','The candidate is implemented and validated in a separate hosted build. The deployed service remains on the baseline image.','', '## Reproducible evidence','', 'The first candidate attempt passed 123/124 checks and stopped on an outdated GEN025 rejection assertion. It is preserved in `../policy_caveats_v1/`. Version 2 retains the runtime code, preserves scope/injection checks and validates the approved caveat stream explicitly.','', '- `preparation.json`: exact candidate bindings, owner authorization and baseline hash.','- `build_result.json`: hosted completion receipt.','- `software_checks.json`: hosted software-check summary.','- `comparison.json`: per-record before/after checks and remaining failures.','- `partial_results.json`: complete targeted events and retrieval evidence.','- `summary.json`: paced runner summary.','']
 (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k not in ('comparison','remaining_baseline_source_failures')}))
if __name__=='__main__':main()
