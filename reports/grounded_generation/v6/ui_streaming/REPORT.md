# Private rider delivery verification — v6

64 software tests passed: 58 rider UI/client tests and six backend/client integration tests. The UI suite took 17.998 seconds and the integration suite 0.842 seconds in the local test runner. These are software-test durations, not hosted response latency.

The UI now displays progress only from backend stage events. It retains the complete accepted response before showing exact answer slices, validates operation/runtime/source/response and verification-receipt bindings, and requires the terminal saved view to equal the accepted view. Open questions use the “Answer” label. The existing appearance, anonymous identity and media privacy controls remain in place.

The synthetic integration tests block retrieval, verification and durable save independently. They verify immediate real-stage progress, no answer text before verification and commit, streamed/accepted/recovered equality, worker completion after disconnect, and idempotent replay without another pipeline call. Retired runtime responses and changed source authority, index, source readiness or receipt bindings fail closed during recovery. API failures remain neutral.

The owner’s fixed fallback completes without a verified-answer block, displaying stage or answer chunks. Verifier failures retain the distinct SYSTEM_ERROR route and fixed operational-error wording.

Machine-readable results, exact commands, file hashes and limitations are in [validation.json](validation.json). Exact test names and outputs are in [ui_tests.log](ui_tests.log) and [backend_client_tests.log](backend_client_tests.log). Intermediate dependency-shadowing and missing synthetic source-binding failures remain recorded; neither was resolved by weakening serving gates.

No provider or real-retrieval calls, deployment, billing changes or new spending occurred. The draft and verifier are synthetic test doubles. This does not establish semantic quality, original-manual support, verifier false-acceptance/refusal rates, live-browser acceptance, warm/cold p95, or public release approval. Those require a separately versioned real-output evaluation.
