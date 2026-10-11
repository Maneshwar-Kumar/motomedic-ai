# MotoMedic A versus B: completed 30-case comparison

Completed 11 October 2026. A is the stronger choice in this tested scope: it delivered more complete answers and was faster in all 11 pairs where both methods delivered. Preserve A's deterministic gates. Reliability gaps remain before wider release.

Latest owner decision: **Arm A is selected.** See `ARM_A_SELECTION.md` and `ARM_A_LATENCY.md` for the recorded choice, measured time breakdown and optimization candidates. B remains comparison history. No new runtime deployment or provider calls were made for this analysis.

## Results

| Metric | A: exact reviewed selection | B: short generation + verification |
|---|---:|---:|
| Attempted cases | 30 | 30 |
| Delivered answers | 23/30 (76.7%) | 11/30 (36.7%) |
| Fully supported, complete answer delivered | 23/30 (76.7%) | 10/30 (33.3%) |
| Complete answer precision among delivered | 23/23 (100%) | 10/11 (90.9%) |
| Median first safe output | 9.87s | 30.31s |
| p95 first safe output | 29.59s | 50.23s |
| Median complete response | 9.88s | 30.31s |
| p95 complete response | 29.59s | 50.23s |
| Provider requests / actual retries | 24 / 0 | 42 / 0 |

The independent agent review judged B's EXP009 ambiguous/incomplete: the source's required condition “while the vehicle is driven” became “during vehicle operation.” This is a completeness defect, not a demonstrated false specification. Other delivered answers preserved their required meanings. No human inspection is claimed. Passing B's online verifier is not accuracy proof.

Claim wording you can reuse:

> On a matched regression benchmark of 30 source-reviewed initial lookup cases for the selected Himalayan BS6 owner's manual, with preselected intents and cache bypass, A delivered fully supported, complete answers in 23/30 cases (76.7%), versus 10/30 (33.3%) for B. Among delivered answers, completeness precision was 100% for A and 90.9% for B. Median measured completion was 9.88 seconds for A and 30.31 seconds for B, including conservative provider pacing, on a hosted worker with loopback HTTP/SSE delivery.

This does not establish general diagnosis, held-out accuracy, field repair success, intent detection, adaptive transitions, photo performance or public app latency. Thirty initial LOOKUP cases were frozen before outputs, balanced in five six-case strata, excluding the previous three examples and known quality holds. Bike/manual and correct intent were preselected. This is a regression sample, not a random population sample. No repeat/cache trial was performed.

## Failure and timing interpretation

A failed six `EXPERIMENT_GATE_FAILED` and one `PROVIDER_SERVICE_ERROR`. B failed six `EXPERIMENT_GATE_FAILED`, six `OUTPUT_SCHEMA`, five `INPUT_RESERVATION_EXCEEDS_EXPERIMENT_LIMIT`, and two `PROVIDER_SERVICE_ERROR`. All failed closed; no technical text was delivered. The six shared gate failures are policy-qualified GEN025, GEN027, GEN030, GEN039, EXP024 and EXP010. Source approval does not bypass runtime eligibility/dependency requirements. Withholding unsupported release is safe behavior, but does not complete these answerable lookup tasks. Failed drafts were not retained and cannot be factually scored.

Every failure remains in the 30-case correctness denominator. Successful latency uses A n=23 and B n=11. In 11 successful matched pairs, A was faster 11/11; median B minus A completion was 20.31s. Empirical p95 uses linear interpolation at `(n-1)*0.95`; tail estimates are fragile at this size. A did not meet the measured five-second warm p95 target.

The experimental limiter uses 6 requests/minute, ten seconds between starts, and 12k rolling UTF-8 byte reservations plus response allowance. These are conservative experiment rules, not verified account quotas. Five B verification envelopes exceeded its reservation limit. This compares frozen implementations under that policy; it cannot isolate intrinsic model accuracy or unlimited-capacity speed.

Subtracting idle pacing from successful server completion gives arithmetic estimates: A median 2.78s/p95 3.95s; B median 4.82s/p95 6.20s. These are not observed unpaced timings or an SLA. Fresh worker initialization 38.25s and pretrial cooldown 60.00s were excluded and separately recorded. First safe output is a complete verified unit, not a raw model token; complete delivery follows almost immediately. No incremental streaming benefit is established.

Delivery used actual localhost HTTP/SSE on the hosted worker. The receiver retained event/block/order/terminal metadata. Server text hashes were checked; client text hashes were not retained/recomputed. No fresh-browser/public-network test was performed. Retrieval model/index were loaded in the worker; the separately warmed Qdrant does not make these Cloud Run query-service timings.

## Warm instance and spending

The authorized existing private Qdrant service now has min1/max1, startup CPU boost enabled, CPU1, 512MiB, request-based billing, concurrency8, timeout30s, us-central1. Revision `motomedic-qdrant-00003-cjb` restored 532 vectors; authenticated health passed and anonymous health was rejected. This warms Qdrant only. No public rider API/UI or warm query-model service was deployed.

Lifetime budget is INR2700: previous INR800 plus INR1900 (approximately US$19.64 at checked planning FX). The live retry-enabled guard stops billing at INR2540, retaining an INR160 buffer. Delayed billing reporting prevents an instantaneous dollar cap. Main billing remains enabled, inference billing disabled; no stopped billing was re-enabled. Idle warming is estimated at US$0.324/about INR31.34 per day; thirty idle days US$9.72/about INR940.22, before shared free-tier credits and other charges. This is pricing, not an invoice or measured remaining balance.

See `warm_instance_budget_20261011.json` for configuration and health evidence and `cloud_run_recommendation_20261011.md` for official price links/formulas. Its earlier min0 recommendation is superseded by the owner's min1 authorization. Operational rollback command, not executed:

```powershell
gcloud run services update motomedic-qdrant --min=0 --project=motomedic-ai-20261009 --region=us-central1
```

Automatic approval review rejected disabling workflow 381150456 because that persistent repository action was not explicitly authorized. It remains active. Do not dispatch or rerun its exhausted allocation. Of the 90-request ceiling, 66 were used; the other 24 do not authorize another run. Explicit owner approval is needed to disable the workflow. No recurring benchmark or warming-end automation was created.

## Evidence and continuation

Owner follow-up: approved scope caveats are acceptable. Measured delivered frequency is A5/23 (21.7%) and B1/11 (9.1%); see `CAVEAT_FREQUENCY.md` and `.json` for definitions, cases and examples. Caveat presence alone is not an accuracy defect; historical runtime failures remain recorded.

Hosted [run 38128714743](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38128714743) succeeded at runtime commit `8cb63185a782192d06db79917070998b6f1242da`. Model `gemma-4-26b-a4b-it`, minimal thinking, 400 output tokens, no fallback, alternate AB/BA order, fresh sessions and cache bypass. Sixty turns, 66 requests, zero retries. The first job 38128389193 was cancelled before provider access after a byte-normalization issue; zero model calls. The corrected exact review verified committed bytes before the successful run. Both histories are retained. The successful job passed 72 offline checks; four separate budget-policy tests also passed.

- `ALL_OUTPUTS.md` / `.json`: all 60 actual delivered outputs, citations and explicit withheld failures.
- `CASE_RESULTS.csv`: sortable output/timing rows.
- `raw_result.json`: original diagnostics and measurements.
- `ab30_v2_output_assessment.json`: independent per-case source/completeness and timing audit.
- `ab30_v2_source_assessment_baseline.json`: required meanings and original-source checks before outputs.
- `ab30_v2_measurements.json`: calculations, denominators and descriptive delivery-success Wilson intervals, not population accuracy confidence.
- Frozen cases/protocol/review/approval/preflight, completed/cancelled job receipts, warm receipt, `RUN_STATUS.json` and `FILE_MANIFEST.json` hashes.

Manual SHA256 `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`; index `index_a3282c4d98cf54595e4ba168`; release v3 SHA256 `b8f8c7b5a9e1a299f0a90eecbf10127779b62b35fc105f0cd587de433e235298`. Keep records private; public PDF/excerpt/image rights remain unapproved. No release scope was enlarged.

Next: fix the six policy-qualified gate failures without weakening gates; fix B schema/reservation failures and EXP009's driving condition; evaluate verified quota-aware pacing separately; then test a freshly authorized independently reviewed held-out set and the actual deployed query API from a browser. Do not tune on this regression set and call it held-out performance. No more calls are authorized by this completed allocation. This folder preserves the results and continuation context so the chat can be removed.
