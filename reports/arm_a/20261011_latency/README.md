# Arm A time breakdown and optimization candidates

Owner selected Arm A on11October2026. Decision: docs/architecture/ARM_A_SELECTION_20261011.md. This is an offline analysis of frozen run38128714743, with no new model requests or runtime/deployment changes. `measurements.json` binds the raw source hash; `case_timings.csv` records each successful case. Matching copies and the decision are in MotoMedic_AB30_20261011/.

## Where measured time went

The following additive breakdown uses **means over the same23 successful A responses**. Percentages use total stage seconds divided by total completion seconds; rows sum to the13.65s mean. The previously reported9.88s is the **median**, and medians of stages should not be added. Seven failed A turns remain in the raw record and accuracy denominator; this successful-response table does not describe failure latency.

| Stage | Mean per successful response | Share of total client time | Stage median | Stage p95 |
|---|---:|---:|---:|---:|
| Waiting for experimental provider admission | 10.837s | 79.4% | 7.788s | 26.671s |
| Retrieval, assembly and controller gates | 1.974s | 14.5% | 2.094s | 3.093s |
| Active provider request, transport and parsing | 0.685s | 5.0% | 0.655s | 0.853s |
| Remaining request setup, validation, save and delivery | 0.154s | 1.1% | 0.141s | 0.189s |
| Complete client response | **13.650s** | **100%** | **9.884s** | **29.595s** |

The active-provider row is not isolated GPU/model inference. The final row's residual includes unseparated work; it must not be called pure network delay. Recorded session/delivery commits were only0.00235s on average, and client-to-answer-start offset was0.113s on average, both subsets of that residual. A has no separate runtime LLM verification call; deterministic source/release checks remain.

Retrieval detail, **nested inside1.974s**, not additional time:

| Component | Mean seconds | Interpretation |
|---|---:|---|
| Initial parallel dense+BM25 retrieval | 0.227 | Dense query embedding/scoring0.225s; BM25 about0.00123s, measured concurrently |
| Conditional cross-encoder reranking | 1.698 | Ran23/23 successful turns; approximately86.0% of retrieval/controller time |
| Everything else within retrieval/controller | 0.049 | Assembly, recovery, gate/controller overhead and unseparated bookkeeping |

Dependency recovery ran8/23 turns and averaged0.000599s across all23. Its time is included above. Conditional reranking effectively ran on every successful lookup in this sample; thresholds remain provisional, so turning it off without evidence is not justified.

Example of a slow response: EXP018 completed in29.633s, of which26.919s was admission wait,1.988s retrieval/gates,0.590s active provider and0.136s remaining. This was not a29-second model inference. The actual median-completion case EXP039 was9.884s:6.516s wait +2.686s retrieval/gates +0.543s provider +0.138s remaining.

## Why the wait is large

`benchmark_pacing.py` imposes6requests/minute, at least10seconds between request starts, and a12,000 rolling reservation limit. The reservation is UTF-8 JSON bytes plus1,024 bytes of protocol allowance, despite a token-labelled field; it is not tokenizer-measured input. Successful A selection calls reserved47,561 bytes against6,361 reported input tokens (7.48 reservation bytes per reported token). Bytes and tokens are different units; this is evidence of conservative sizing, not a measured tokenizer overcount factor.

One `Allocation`/`Admission` instance was shared by A and B. B's generation and verifier reservations therefore also occupied the limiter that A waited on. These alternating results cannot establish an A-only production queue delay. A-only service removes B workload, but real shared project quotas and competing clients must still be respected. Google documents project-level RPM/TPM/RPD limits and directs users to their [active AI Studio quotas](https://ai.google.dev/gemini-api/docs/rate-limits); the experiment did not verify those account limits.

## Recommended order of work

1. **Deterministic singleton wording selection.** In every23 successful sample envelopes, each claim had exactly one approved wording option. Selecting index0 for each claim produces byte-identical text and order to all23 actual deliveries. There is no wording choice for an LLM to make. For a trusted, fully gated envelope with one option per claim, select deterministically, revalidate bindings/envelope, and save/deliver through the same gate. Keep existing A selection for genuinely multiple options. This does not solve intent detection, six policy-qualified gate failures or missing evidence, and must not bypass those gates. A versioned runtime change needs fresh exact review and regression checks before live use.

   Arithmetic estimate of removing both the observed idle pacing and provider work, retaining all other measured time: mean2.128s, median2.248s, p95 3.256s at the client. This is a **counterfactual arithmetic estimate, not a measured fast-path SLA**. Offline exact text/order parity is23/23; no shortcut was installed or timed. Gate validation and runtime overhead could differ when implemented.

2. **Make necessary provider calls quota-aware.** Check active model/project RPM, TPM and daily limits without upgrading billing. Replace the unexplained fixed10-second pacing only with a verified shared-project admission policy. Use a model-supported token estimator/counting approach with bounded reservations and reconciliation to returned usage. Do not add an extra token-count network call to every request without measuring its cost/latency; model-specific count support and schema accounting need checking. Google's [token guide](https://ai.google.dev/gemini-api/docs/tokens) describes counting; account/model compatibility is not demonstrated here. Preserve rate/spend bounds and coordinated competing clients. No quota values have been invented or limiter settings changed.

3. **Investigate reranking next.** Its mean1.70s is the dominant computation once provider waiting is removed. Compare current conditional scheduling against calibrated narrower triggers and smaller candidate sets on independently reviewed tuning cases, then held-out cases. Preserve complete evidence recall, mandatory dependency attachment and eligibility. Faster execution of the same reranker is another candidate. The current sample alone cannot justify disabling it or predict a safe gain.

4. **Warm the actual query worker for cold starts.** This run separately measured38.25s startup: registry3.66s, model/index24.86s, reranker/first-query9.73s, plus60s experimental cooldown. Neither is part of warm response time. Qdrant min1/CPU boost warms vector storage, not BGE, the reranker or a future query/API process. For the actual query deployment, package pinned model assets, load once per worker and measure readiness/cold requests. Additional service sizing/deployment needs its own cost plan and authorization; none was performed here.

5. **Consider exact approved reuse for repeated paths.** Cache only exact version/scope/typed-path matches with valid approved wording and full current gates. Draft/stale/semantic matches must not authorize advice. The30-case batch bypassed caches, so it provides no cache speed result. Session saves and streaming transport are already small components; prioritize the work above before optimizing those milliseconds.

## Evidence limits and acceptance for a future change

Measured boundary: warmed GitHub query worker, actual localhost HTTP/SSE. Not browser/public-network or Cloud Run query-service latency. All response text remains source-bound; receiver retained block/event metadata rather than client content hashes. Stage p95 values are marginal and do not add to response p95. Small successful samples give descriptive tails only.

For a versioned optimization, verify identical full wording/order, warnings, prerequisites, immutable citations, source/applicability and typed state gates; verify failures remain fail-closed and no additional undocumented paths appear. Keep initial singleton, multi-option, mismatched/stale, missing-warning, unsafe and correction cases distinct. Measure actual A-only client first safe output and complete delivery including admission, report all failures, and compare on a frozen independently reviewed evaluation set. No new provider calls are authorized under the completed30-case allocation, and no deployment or billing changes were made by this analysis.

Validation: all23 deterministic singleton text/order parity checks passed, the additive timing partition reconciles to total client time, and the local package file hashes passed. Repository navigation check found no missing navigation files and no broken links (231 checked). Its overall result remains false because the existing root `ab30_benchmark.py` and `test_ab30_benchmark.py` are not in the layout allowlist; this analysis did not move those bound runtime files or change that allowlist. See `navigation_validation.json`. This layout finding does not invalidate the frozen run measurements.
