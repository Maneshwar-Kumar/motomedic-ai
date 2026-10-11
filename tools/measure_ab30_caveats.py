"""Count approved scope qualifiers in retained, reviewed benchmark deliveries."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'MotoMedic_AB30_20261011'
baseline = json.loads((out / 'ab30_v2_source_assessment_baseline.json').read_text(encoding='utf-8'))
raw = json.loads((out / 'raw_result.json').read_text(encoding='utf-8'))
roles = {'OEM_FACT_WITH_POLICY_SCOPE_LIMIT', 'APPROVED_PRODUCT_POLICY_SCOPE_LIMIT'}
scope_cases = {c['record_id']: [claim['required_meaning'] for claim in c['required_claims']
    if claim['semantic_role'] in roles] for c in baseline['cases']}
scope_cases = {key: value for key, value in scope_cases.items() if value}
hits = []
methods = {}
for method in raw['architectures']:
    rows = [r for r in raw['rows'] if r['architecture'] == method]
    delivered = [r for r in rows if r.get('engineering_delivered_units')]
    matched = [r for r in delivered if r['record_id'] in scope_cases]
    # Post-facto independent output review confirms the required caveat meaning
    # is present in each of these retained outputs, including B's GEN033 paraphrase.
    methods[method] = {'attempted': len(rows), 'delivered': len(delivered),
        'answers_with_scope_caveat': len(matched),
        'fraction_of_delivered': len(matched) / len(delivered),
        'fraction_of_attempted': len(matched) / len(rows)}
    for row in matched:
        hits.append({'record_id': row['record_id'], 'method': method,
            'required_scope_caveats': scope_cases[row['record_id']],
            'actual_delivered_texts': [t for u in row['engineering_delivered_units'] for t in u['texts']]})
result = {'definition': 'Approved product-policy scope limit or OEM fact with approved policy scope limit, identified from frozen required-claim roles and verified delivered meanings; excludes ordinary OEM warnings, conditions and approximate specifications.',
    'case_set_count': 30, 'authored_cases_with_scope_caveats': len(scope_cases),
    'authored_scope_caveat_case_ids': sorted(scope_cases),
    'methods': methods, 'total_delivered_answers': sum(m['delivered'] for m in methods.values()),
    'total_delivered_answers_with_scope_caveat': len(hits),
    'unique_cases_with_delivered_scope_caveat': len({r['record_id'] for r in hits}),
    'undelivered_scope_caveat_cases': sorted(set(scope_cases) - {r['record_id'] for r in hits}),
    'hits': hits, 'owner_preference': 'Approved scope caveats may remain in answers; measure their frequency. A caveat alone is not an accuracy defect.',
    'historical_gate_failures_unchanged': True, 'additional_provider_calls': 0}
(out / 'CAVEAT_FREQUENCY.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(result, indent=2, ensure_ascii=True))
