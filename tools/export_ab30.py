"""Package completed private engineering evidence; no provider or cloud calls."""
import csv, hashlib, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'MotoMedic_AB30_20261011'
RAW = ROOT / 'reports/ab30_run_38128714743/ab30-38128714743/ab30_v1_result.json'

def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')

def main():
    raw = json.loads(RAW.read_text(encoding='utf-8-sig'))
    assert len(raw['rows']) == 60
    assert len({(r['record_id'], r['architecture']) for r in raw['rows']}) == 60
    OUT.mkdir(exist_ok=True)
    (OUT / '.gitattributes').write_text('* -text\n', encoding='utf-8')
    shutil.copy2(RAW, OUT / 'raw_result.json')
    names = ['ab30_v1_cases.json', 'ab30_v2_protocol.json', 'ab30_v2_review.json',
             'ab30_v2_approval.json', 'ab30_v2_budget.json', 'ab30_v1_cancelled_job.json',
             'ab30_v2_completed_job.json', 'ab30_v2_measurements.json',
             'ab30_v2_source_assessment_baseline.json', 'ab30_v2_output_assessment.json',
             'warm_instance_budget_20261011.json', 'cloud_run_recommendation_20261011.md']
    for name in names:
        source = ROOT / 'reports' / name
        assert source.exists(), f'Missing final evidence: {name}'
        shutil.copy2(source, OUT / name)
    cases = json.loads((ROOT / 'reports/ab30_v1_cases.json').read_text(encoding='utf-8-sig'))
    save(OUT / 'ALL_OUTPUTS.json', [{'record_id': r['record_id'], 'method': r['architecture'],
        'route': r['route'], 'failure_reason': r.get('failure_reason'),
        'delivered_units': r.get('engineering_delivered_units', []),
        'client_receipt': r.get('loopback_client_delivery'),
        'failed_draft_retained': False} for r in raw['rows']])
    lines = ['# All 60 measured turns', '', 'Private engineering export. Failed drafts were withheld and not retained.', '']
    with (OUT / 'CASE_RESULTS.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['record_id', 'method', 'route', 'failure_reason', 'first_safe_seconds', 'complete_seconds', 'provider_requests', 'delivered_text'])
        for r in raw['rows']:
            texts = [text for unit in r.get('engineering_delivered_units', []) for text in unit['texts']]
            client = r.get('loopback_client_delivery', {})
            writer.writerow([r['record_id'], r['architecture'], r['route'], r.get('failure_reason', ''), client.get('first_verified_output_seconds'), client.get('complete_response_seconds'), r['provider_requests_this_turn'], '\n'.join(texts)])
            lines += [f"## {r['record_id']} / {r['architecture']}", '', f"Route: {r['route']}. Failure: {r.get('failure_reason') or 'none'}.", '']
            lines += texts or ['No technical output delivered.']
            for unit in r.get('engineering_delivered_units', []):
                lines += ['', 'Citations: ' + '; '.join(f"{c['evidence_id']} (PDF page {c['pdf_page']})" for c in unit['citations'])]
            lines += ['']
    (OUT / 'ALL_OUTPUTS.md').write_text('\n'.join(lines), encoding='utf-8')
    save(OUT / 'RUN_STATUS.json', {'status': 'COMPLETE_WITH_RECORDED_FAILURES', 'run_id': 38128714743,
        'runtime_commit': '8cb63185a782192d06db79917070998b6f1242da', 'case_count': 30,
        'measured_turns': 60, 'external_provider_requests': raw['external_provider_attempts'],
        'retries': 0, 'further_calls_authorized_by_this_allocation': 0,
        'workflow_state': 'active', 'workflow_disable': 'AUTO_REVIEW_REJECTED_REQUIRES_EXPLICIT_OWNER_APPROVAL',
        'public_api_deployed': False, 'output_review': 'ab30_v2_output_assessment.json'})
    save(OUT / 'FILE_MANIFEST.json', {'schema_version': 'local-ab30-export-v1',
        'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name != 'FILE_MANIFEST.json'}})

if __name__ == '__main__':
    main()
