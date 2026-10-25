# Final v8 UI wiring software review

The existing rider UI is connected in code to the open manual draft/verify/save/stream API. Server-side fallback needs no model selector or provider key in the UI. README and API_CONTRACT now link the v8 software receipts and the concrete connection handover. No frozen serving file was changed during this wiring task.

All 69 tests pass. The final receipt in `validation.json` binds the current 64-file serving freeze and reviewed UI/test/document hashes, with zero freeze mismatches before or after testing and zero reviewed-file changes during testing. The existing 60 UI/client tests took 11.916 seconds; six backend delivery tests plus three new full-path tests took 11.075 seconds. These are offline test durations. Earlier `ui_streaming/validation.json` and logs remain historical evidence of the earlier v8 bytes, not the final composer revision.

The new tests use real open Questions, Composer, FallbackProvider, ClaudeProvider, API handlers, strict production RiderAPI and SSE validation. Immutable source approval/assembly is loaded from the existing index. Retrieval selection, provider HTTP responses, and transactional storage transport are fixtures; no provider request leaves the process. Primary availability failure selects the configured fallback for drafting and checking. The accepted response is committed before the client callback, streamed exactly, and recovered/replayed without another request. Rejection and malformed checking produce exact neutral wording with no accepted text callbacks or chunks.

The authenticated saved view retains redacted runtime/provider metadata for the server. The product renderer displays rider text, status, citations and operational progress; it does not display provider selection or private verification details. Raw private draft/verifier payloads and credentials remain absent from the tested saved view.

The initial new-test authoring checks exposed fixture setup and an over-broad assertion forbidding all server telemetry; both were corrected in the new test only. They required no serving-code change. The final receipt records the reproducible passing run.

These are software integration checks, not model-quality or hosted-browser acceptance. The separate actual run `38160944967` released no technical answer; it cannot establish live useful-answer acceptance. Deployment/managed connection, exact current health/capability checks, and fresh browser acceptance remain required. This task performed zero paid calls, deployments, billing changes or secret reads.
