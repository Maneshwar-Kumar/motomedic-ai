# Accuracy, speed and spend with approved scope caveats accepted

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
