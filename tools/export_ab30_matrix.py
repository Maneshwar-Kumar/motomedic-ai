"""Export observed accuracy, speed and pricing-based inference cost together."""
import hashlib, json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'MotoMedic_AB30_20261011'
raw = json.loads((p/'raw_result.json').read_text(encoding='utf-8'))
review = json.loads((p/'ab30_v2_output_assessment.json').read_text(encoding='utf-8'))
timing = json.loads((p/'ab30_v2_measurements.json').read_text(encoding='utf-8'))
methods = {}
for name in raw['architectures']:
    rows = [r for r in raw['rows'] if r['architecture'] == name]
    attempts = [a for r in rows for a in r.get('provider_attempts', [])]
    a = review['aggregate'][name]
    methods[name] = {'attempted_cases': 30,
        'complete_accurate_deliveries': a['fully_source_supported_complete_delivery_count'],
        'complete_accurate_delivery_fraction': a['fully_source_supported_complete_delivery_fraction'],
        'delivered_answers': a['delivery_coverage_count'],
        'complete_accuracy_among_delivered': a['complete_precision_among_delivered'],
        'supported_scope_caveats_accepted': True,
        'successful_latency': timing['methods'][name]['latency'],
        'provider_requests': len(attempts),
        'reported_input_tokens': sum(x.get('input_tokens', 0) or 0 for x in attempts),
        'reported_output_tokens': sum(x.get('output_tokens', 0) or 0 for x in attempts),
        'inference_usd_at_configured_free_tier_price': 0,
        'inference_cost_basis': 'Configured free-only inference project, billing disabled; current official Gemma4 Gemini API input/output pricing free. Pricing-based inference charge, not total project invoice.'}
result = {'scope': 'Frozen matched30 initialLOOKUP regression with preselected intents; approved scope caveats already accepted; no new provider calls.',
    'pricing_checked_date_ist': '2026-10-11',
    'pricing_source': 'https://ai.google.dev/gemini-api/docs/pricing#gemma-4',
    'methods': methods,
    'shared_warm_qdrant_idle_gross_estimate': {'usd_per_day': 0.324, 'inr_per_day': 31.34076923076923,
        'usd_per_30_days': 9.72, 'inr_per_30_days': 940.2230769230769,
        'method_allocation': 'SHARED_NOT_ATTRIBUTED_TO_A_OR_B',
        'excludes': 'Active requests, startup boost, other services, credits; account-wide free-tier availability unknown.'},
    'total_actual_project_or_github_spend': 'NOT_MEASURED_NO_INVOICE_RECONCILIATION',
    'budget_inr': 2700, 'billing_guard_inr': 2540,
    'accuracy_change_due_to_caveat_acceptance': 'NONE; caveats were already accepted. Six common runtime gate failures did not deliver an answer and cannot be credited retrospectively.'}
(p/'ACCURACY_SPEED_SPEND.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
report = '''# Accuracy, speed and spend with approved scope caveats accepted

Accepting the approved scope caveats does **not** change the measured scores: the original assessment already accepted them. The six shared gate failures did not release an answer, so they cannot be retrospectively credited as accurate deliveries. B's EXP009 ambiguity concerns a required driving condition, not an optional scope caveat.

| Metric | A | B |
|---|---:|---:|
| Complete accurate answers / all attempts | 23/30 (76.7%) | 10/30 (33.3%) |
| Complete accuracy among delivered answers | 23/23 (100%) | 10/11 (90.9%) |
| Delivered answers | 23/30 | 11/30 |
| Median first safe output | 9.87s | 30.31s |
| p95 first safe output | 29.59s | 50.23s |
| Median complete response | 9.88s | 30.31s |
| p95 complete response | 29.59s | 50.23s |
| Provider requests | 24 | 42 |
| Reported input / output tokens | 6,361 / 213 | 20,610 / 1,629 |
| Reported total tokens | 6,574 | 22,239 |
| Inference charge at configured free-tier pricing | US$0 | US$0 |

All failures remain in the accuracy denominator of30. Successful-response speed denominators: A23, B11; B speed includes its delivered but incomplete EXP009 answer. Actual timings include conservative provider pacing. These are hosted-worker loopback HTTP/SSE results, not browser/public Cloud Run API times. A was faster in all11 pairs where both delivered. Empirical p95 on this small sample is descriptive.

Arithmetic server completion minus idle pacing, not measured unpaced speed: A median2.78s/p95 3.95s; B median4.82s/p95 6.20s. Neither these adjusted values nor the complete-answer precision among deliveries alone establishes an end-to-end SLA or general diagnosis accuracy.

The benchmark used free-only Gemma4 inference with inference billing disabled. Google's [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing#gemma-4), checked11October2026, lists Gemma4 input/output as free of charge. US$0 is the configured inference pricing result, **not** a claim that the total benchmark or project had zero cost. Reported token totals exclude unknown usage on failed HTTP500 calls; request counts include those calls. B used1.75times as many requests and approximately3.38times the reported tokens in this run, but both remain free under the tested API configuration. This does not predict paid-model pricing.

Shared warm Qdrant idle gross estimate: US$0.324/about INR31.34 per day, or US$9.72/about INR940.22 per30days before shared free-tier credits. It is shared infrastructure, not a separate charge for each method, and excludes active traffic, startup boost and other services. Actual total GCP/GitHub spend was not invoice-reconciled. Lifetime budget INR2700 and billing guard INR2540 are limits, not amounts spent. See the warm-instance receipt and pricing recommendation for region, formulas, FX and limitations.

A remains the stronger tested implementation for this initialLOOKUP regression. This comparison does not claim general diagnosis, held-out accuracy or a measured benefit from warming Qdrant. No additional cases were run for this matrix.
'''
(p/'ACCURACY_SPEED_SPEND.md').write_text(report, encoding='utf-8')
manifest = {'schema_version': 'local-ab30-export-v1', 'files': {x.name: hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(p.iterdir()) if x.is_file() and x.name != 'FILE_MANIFEST.json'}}
(p/'FILE_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Saved accuracy/speed/spend matrix. Additional provider calls:0.')
