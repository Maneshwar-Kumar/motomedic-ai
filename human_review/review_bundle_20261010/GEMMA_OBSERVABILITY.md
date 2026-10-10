# Gemma API observability and reviewed grounding evaluation

Selected candidate: Google Gemini API `gemma-4-31b-it`, separate unbilled project `motomedic-inference-20261009`. The restricted key is stored in repository secret `MOTOMEDIC_GEMINI_API_KEY`. The bounded Gemini composer/verifier adapter is now integrated in `generation_providers.py` and `gemini_transport.py`. A working smoke endpoint does not approve the grounded generator; source review, conditional authoring scopes and live semantic calibration remain pending.

## Timing probes

`gemma_api_smoke.py` sends only the fixed synthetic `Reply with READY.` prompt with minimal thinking, at most 64 output tokens, one fresh connection per request, no redirects or retries, a 10-second connection bound and 30-second curl total bound. The CLI permits one to three requests. Keys enter curl configuration through stdin and never command arguments or files. SSE text and HTTP bodies are not logged. curl stderr is drained concurrently to avoid subprocess pipe blocking; only allowlisted scalar timing/status fields are retained.

The private manual `Gemma API access smoke` workflow runs one request and retains a redacted JSON artifact for seven days. Push-triggered tests are offline and do not use the key. Local and GitHub origins are recorded separately.

Captured signals: DNS completion; TCP connection; TLS completion; request-ready time; first HTTP response byte; first parsed SSE event; first visible non-thinking text; stream completion; status, curl exit code, finish reason, returned model, token usage and service tier. Client first-event timestamps include process startup and line parsing; curl timestamps start within curl. Do not subtract these two clocks to estimate individual phases. A timeout has no first-byte/token time, rather than a zero-second response.

`request_ready_to_first_byte_seconds` includes request upload, network transit and remote waiting. It cannot reveal Google's queue or accelerator startup. No server timing, trace identifier or backend logs were supplied, so those causes remain hypotheses. A small prompt and fast connection can narrow attribution but cannot prove a particular backend cause. Streaming did not make the first token immediate in the local sample. Do not interpret three requests as p95, a warm/cold benchmark, or a capacity guarantee.

Local results are in `reports/gemma_timing_local_20261009.json`; the independently run GitHub result is in `reports/gemma_timing_github_20261009.json` ([run 37941737044](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/37941737044)).

| Origin/request | Connection ready | First HTTP byte | Total curl time | Outcome |
| --- | ---: | ---: | ---: | --- |
| Local 1 | 0.570 s | 1.316 s | 1.316 s | Google HTTP 500 |
| Local 2 | 0.570 s | None | 30.012 s | Timeout; zero response bytes |
| Local 3 | 0.566 s | 15.760 s | 15.805 s | READY, STOP, 4 input + 1 output token |
| GitHub 1 | 0.093 s | 0.434 s | 0.434 s | Google HTTP 500 |

The independent HTTP 500 reproduces across both networks. Local connection establishment was fast; the successful request spent about 15.194 seconds after connection readiness before receiving its first byte, then completed in about 0.045 seconds. This points toward the API serving path rather than local application work, without identifying queueing, backend startup or another internal cause. One of four measured probes succeeded; this tiny sample is diagnostic, not a reliability estimate. Only the successful request supplied usage (five tokens); usage for the other calls is unknown. Four timing/regression tests passed locally and in GitHub; the live workflow correctly failed on HTTP 500 rather than hiding the outage. One earlier harness attempt was stopped due to stderr pipe blocking; its outcome and usage are unknown and it is excluded from latency comparisons. Failed calls without usage are not assumed to cost zero tokens. The existing INR640 project guard is not changed; the inference project has billing disabled.

## After the owner reviews the eleven records

1. Review final record content against original manual pages, not only the eleven IDs. Bind human decisions to content digests and source checksum. Include every claim, exact units/table headers, mandatory warnings, prerequisites, variant fit and stopping conditions. Source, evidence, rules, procedure boundaries and dependency manifests have their own review checks; approving a step alone cannot bypass them.
2. Resolve authoring fields before sign-off: the original active claims lack `response_role`; the reconciled draft proposes roles while dependency scopes remain unconfirmed, and procedure boundaries are unchecked. End-user text requires reviewed `presentation_mode=REVIEWED_PARAPHRASE`; engineering excerpts remain separate. Editing these fields after approval invalidates the approval. Do not mark flags complete merely to make a test pass.
3. Run the reviewed deterministic controller first on existing golden dialogues and lookup probes. This isolates retrieval completeness, eligibility, citations, warning scope, typed outcomes and stopping/non-repeat behavior from model errors. Keep the same immutable index and manual checksum; do not re-embed for these tests.
4. Configure and test a bounded Gemini composer/verifier adapter, then run the same reviewed cases through the grounded pipeline. Attribute failures separately to retrieval, controller, composer, deterministic output checks, semantic verifier or provider. Use the original manual and independently adjudicated expected answers as truth; the model does not approve its own response.
5. Calibrate semantic verification with reviewed supported claims and controlled unsupported additions, changed units/numbers, omitted warnings and wrong citations. Keep cases used for tuning out of the held-out score. Existing draft goldens are the starting dataset, not a new parallel set of invented repair advice. Report grounding and answerable coverage separately from latency and provider errors; an outage is SYSTEM_ERROR, not UNSUPPORTED.

This work adds diagnostic observability only. Source review, public release, rider media, managed tracing, rate/day-spend controls and live Gemma semantic calibration remain pending.


## Grounding transport update

The production-boundary candidate transport uses the same fixed Gemma31B SSE endpoint and exposes first-byte/token/completion fields for composer and verifier independently. Tests reserve each call before attempting transport, reject altered claims before semantic inference, preserve unresolved actions without repetition, and distinguish provider errors from semantic rejection. No additional live timing or grounding calls accompanied this update. Review the original eleven draft gate report and reconciled draft report alongside GENERATOR_INTEGRATION.md; all are source-gated, not release results.
