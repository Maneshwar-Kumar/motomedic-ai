# Rider API v1 integration contract

The selected v10 public gateway hosts Streamlit and calls the private IAM-protected API implemented in `cloud/arm_a/rider_api.py`. The browser receives presentation, progress and a signed visitor cookie; provider credentials stay server-side. Backend/worker/Qdrant remain private. See [current status](../docs/STATUS.md) and the [recorded operational scope](../reports/public_evaluator/20261012/owner_scope_v1.json); v10 hosted/browser acceptance is pending. Do not point the UI at the retrieval-only Qdrant URL.

Source locks:

- Schema: `motomedic-rider-api-v1`
- Manual SHA-256: `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`
- Index: `index_a3282c4d98cf54595e4ba168`
- Variant: `Himalayan BS6`
- Source display: citation metadata only; PDF, excerpts and figure crops prohibited.

## HTTP boundary

Every UI-to-backend request has a managed audience-bound `Authorization: Bearer ...` service identity and its owned signed visitor capability. Every rider mutation also has a unique `Idempotency-Key`. Transport uses HTTPS and rejects redirects. No automatic mutation retry. JSON responses are capped at 256 KiB; request text at 2,000 characters.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /v1/catalogue | Source locks and open-question capability |
| POST | /v1/sessions | Confirm scope and retrieve for raw question |
| POST | /v1/sessions/{id}/questions | Ask another question using expected_version |
| POST | /v1/sessions/{id}/feedback | Apply exactly one issued server choice and run next turn |
| GET | /v1/sessions/{id} | Retrieve latest saved view |
| GET | /v1/operations/{idempotency_key} | Recover a mutation's committed response without executing it again |

Catalogue: schema_version, manual_checksum, index_id, question_input=open, diagnostic_wizard=false, streaming=DRAFT_VERIFY_STREAM for the current open-verification service. Hosted UI capability checks reject the retired complete-unit service; neutral explicit engineering loopback fixtures remain available. The UI exposes no topic selector or symptom routing.

Create request: query, bike_variant, confirmed_himalayan_bs6=true, manual_checksum, index_id, cache_mode=bypass. Continued questions add expected_version. Actual question and relevant saved history reach authenticated Qdrant + concurrent BM25, RRF, reviewed dependency assembly and conditional distinct-parent rank-disagreement reranking. Ordinary questions require no canonical question, authored answer scope or registered action. Pinned Gemma drafts privately; the distinct pinned Claude Haiku verifier checks question coverage and claims over the exact finalized response. Both model contracts bind the verdict and saved admission. All conditions/warnings/citations are finalized before verification; at most one correction and fresh verification is permitted. Answer-cache shortcuts stay disabled. Display/recovery causes no generation call.

The direct public gateway signs a secure HttpOnly SameSite 24-hour cookie after a 14-bit proof challenge and private visitor reservation. Challenge validity is 120 seconds. `/internal/visitors/reserve` accepts only the exact IAM-authenticated UI service account and one proof SHA; task/other callers cannot issue visitors. Firestore atomically rejects spent proofs and bounds issuance to ten/minute and 60/rolling day. The UI forwards its signed `X-MotoMedic-Visitor` capability; backend ownership binds the UI principal and cookie nonce. No client or forwarded IP is trusted. A cookie identifies the visitor across refresh/new conversations; replacing it creates a new subject but cannot reset persistent global issuance/request or provider budgets. Every mutation uses a 32-hex key. Technical text streams only after durable commit; disconnect recovery reads that operation without rerunning it.

Feedback request: expected_version, choice_id, cache_mode=bypass. **No client-supplied fact, approval, evidence, or model output.** Server looks up the choice previously issued for this exact session version, validates its reviewed typed binding, then applies ReviewedService.feedback and the next turn. Unresolved action never seeds an observation.

## Saved view

Required top-level fields: schema_version, manual_checksum, index_id, session_id (opaque identifier), version (nonnegative integer), response. Production requires runtime_policy=`open-manual-draft-verify-v10` on every route, including neutral fallback/errors and JSON recovery. V9, older and missing policies are rejected before display, continuation or feedback. Explicit engineering loopback fixtures remain separate; enabling loopback does not relax a remote HTTPS service.

Response fields:

- type: exactly SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP or SYSTEM_ERROR.
- natural_language: the complete gated rider text, including mandatory conditions and warnings. UI displays it literally.
- technical_content: boolean, default true. False only for nontechnical acknowledgments such as customer-reported resolution, independently controlled by the server.
- release_gate_passed: true only after the actual deterministic/semantic checks required by the selected serving architecture. It is an authenticated server assertion, not a client evidence verifier.
- cited_pages: list of immutable metadata objects: evidence_id, pdf_page (1–149), pdf_page_index (zero based), optional printed_page_label, manual_checksum, index_id.
- trace_id: redacted correlated response identifier.

Optional top-level fields:

- choices: at most eight id/label/outcome objects. Canonical outcome enums are unchanged. These are exact issued choices bound on the server to typed facts when needed. Do not invent generic Yes/No controls for ambiguous numeric or enum rules.
- history: list of label objects describing server-recorded attempts. Keep unresolved vs normal distinct; corrections supersede previous observations.
- escalation_uri: null or the verified `mailto:support@royalenfield.com`.

No evidence_uri, source text/excerpt, crops, raw source objects, provider bodies, secret values or raw media. Stopped/error paths issue no action feedback choices. A known applicable verified safety stop retains precedence even when optional storage/telemetry fails, consistent with existing controller semantics.

## Progress and accepted-answer delivery

Mutations request `Accept: text/event-stream`. V10 operations are committed to Firestore and dispatched as named authenticated Cloud Tasks to a dedicated private worker service. The worker has separate capacity from the private API/SSE service. SSE observes durable progress; closing the browser stream does not terminate generation. Every event binds to the operation's 32-hex ID and consecutive integer sequence, starting at one:

| Event | Payload and rule |
| --- | --- |
| progress | operation_id, sequence and stage. Stage is retrieving, drafting, verifying or displaying. Constant client labels are shown only when the backend records a real stage. |
| verified_block | operation_id, sequence, response_sha256 and the complete saved view. The persisted delivery binding, selected source, response hash and release gate must validate before any answer callback. |
| answer_chunk | operation_id, sequence, response_sha256, offset and text. Offset counts Python Unicode codepoints; text must be the exact next slice of the buffered accepted response. |
| complete | operation_id, sequence, response_sha256 and the identical saved view. Its full text must equal concatenated chunks and the accepted response hash. |
| error | Sanitized operational failure; private drafts and verifier output are never displayed. |

Displaying is emitted only after verification, final integrity checks and durable save. Progress contains no technical text, private drafts, chain-of-thought, confidence, percentages or simulated timing. A correction can emit drafting/verifying again, with no private answer token release. SYSTEM_ERROR uses neutral completion without accepted-answer chunks. Verified clarifications, supported partial responses and refusals retain their distinct routes.

Persisted `delivery` contains operation_id, response_sha256, runtime_lock, manual_checksum, index_id and `event_protocol: operation-sequence-v1`, plus the semantic verification and evidence payload hashes. The response hash is SHA-256 of UTF-8 JSON for the complete response object with sorted keys, compact separators, no non-finite values and Unicode preserved. The client checks these bindings during streaming and recovery. A disconnect retains the entire accepted view, then retrieves the original operation; any changed saved view is blocked. Replay streams the existing buffer and starts no drafting or verification call. Neutral fallback/error buffers emit completion without a verified block or answer chunks.

The observation stream polls once per second and stops after 150 seconds with a recoverable operational error if work is still active. Recovery reads the same operation. Proven terminal failures clear the UI's pending request; an uncertain store or transport failure preserves it. Operations have a 1,200-second deadline and fenced worker lease. Admission reads that exact durable deadline and rechecks it after bounded pacing waits before paid transmission. Delayed permits are atomically repositioned to preserve the existing rolling rate limits; expired or uncertain slots remain reserved. An expired or abandoned worker is terminally reconciled on task redelivery, status read or the next session turn; it is never allowed to retry an uncertain paid call. A pending dispatch uses the same hashed task name after an uncertain create response.

## Hosted implementation obligations

Use the exact source-approved registry, immutable BGE/BM25 chunks, complete reviewed source assembly and selected v10 model contracts. Do not import test fixtures, rebuild embeddings, silently switch models or bypass applicability, rights, context or claim checks. Registered legacy action eligibility does not restrict ordinary manual Q&A. Model roles are server-controlled; the UI contains no selector.

Use managed transactional session storage with immutable attempt snapshots and compare-and-swap versions. SQLite/local Streamlit state is not the production store. Atomically reserve and deduplicate operation IDs before model calls; persist/retrieve the final response and choices. A concurrent or stale feedback returns 409. Repeated same operation returns the original response without another model call. An operation still executing should report a recoverable status, not re-execute it.

Enforce authenticated ownership/capability on session and operation reads. Shared UI-to-API authentication alone is not a substitute for per-session authorization. Apply global and per-session rate/call limits, provider spending reservations and a fresh budget/guard preflight under the existing project authorization. Respond 429 when limited; no fallback after quota/rate failure and no automatic retries. Redact query text and credentials from logs. Expire sessions and operation records under a published retention policy.

The selected Haiku verifier caches only the exact policy/source-evidence prefix for five minutes. Question/history/finalized response and verdict bindings remain dynamic. Hosted cache creation followed by positive reads is required; configured caching alone proves no savings. No answer or verdict cache is permitted. The separate optional Gemma-to-Haiku availability chain remains disabled; selecting Haiku as verifier does not activate it, and an environment switch cannot override frozen policy. Source/integrity failures, quota, malformed output and semantic rejection never authorize switching. Whole-manual Claude remains retired.

Before connecting a UI revision, authenticated `/healthz` must report the intended architecture, `streaming=DRAFT_VERIFY_STREAM`, exact draft/verifier providers and selected prefix-cache policy. `/v1/catalogue` must report open questions and the same streaming capability. Validate a saved v10 view and recover its unchanged operation through the production client. Historical [v8 handover](../reports/grounded_generation/v8/ui_wiring/CONNECTION_HANDOVER.md) and [software receipt](../reports/grounded_generation/v8/ui_streaming/REPORT.md) remain evidence of older revisions. Recorded operational authorization permits this evaluator; live acceptance is separate.

## Live acceptance (pending)

Public browser → cookie/proof gateway → private owned API → dedicated task worker → authenticated Qdrant + concurrent BM25 → conditional rank-disagreement reranking/complete source assembly → private Gemma draft → distinct cached Haiku verification → final checks/durable save → exact streamed cited response and follow-up/recovery.

Run fresh ordinary questions, a useful partial answer, follow-up, fixed fallback, and verifier failure in a fresh browser. Answer caching remains disabled. Retain correlated redacted browser/service traces, immutable version bindings, actual provider execution, rendered matching citations, no-repeat results and browser-to-complete-response timings. Warm/cold p95 needs a suitable sample size; three samples do not establish p95.

UI fixture tests or localhost screenshots do not meet this gate. The photo control remains disabled until this text gate passes and an observation-only vision path is implemented/evaluated.


## Safeguards v1 serving integration

Use [SERVICE_SAFEGUARDS.md](SERVICE_SAFEGUARDS.md) and [TODO](../TODO.md) as the implementation/release register. Preserve API v1 response/choice semantics. Text is at most 2,000 Unicode characters and 8,000 UTF-8 bytes; request JSON at most 16 KiB. Hosted handlers repeat bounds before retrieval. Bind browsers to signed visitors and owned sessions; service IAM alone is insufficient. Counters survive new conversations, and persistent proof/issuance/global/provider controls bound cookie reset abuse without a trusted-IP claim.

The managed transaction must reserve an operation against six turns per rolling minute, 30 turns per rolling 24 hours, and 20 turns per session. Same-operation replay returns its original reservation/view without another model call; a different payload hash conflicts. Retrieval/provider failures consume admitted slots. Counters and model-call/budget admission must be project-wide across workers. A caller must not provide usage counts. Admission-store outage blocks new inference with a sanitized operational error; preserve already established applicable safety-stop semantics.

The existing 100-slot non-recurring provider allocation supports at most 12 conservative eight-slot turns from a fresh ledger, including hosted validation usage. It never resets or refunds unused/uncertain reservations. Gemma uses the existing free primary configuration with unsupported cache capability; paid Haiku uses the unchanged persistent USD1 guard. INR2,700/INR2,540 limits and disabled inference billing remain unchanged. This evaluator offers bounded remaining capacity, not unlimited public use.

The current open-Q&A serving context uses bounded conversation history and freshly retrieved manual evidence. Fresh evidence plus trusted policy and schema must fit 8,192 exactly counted input tokens and 65,536 bytes; cap output at 1,800 tokens. Check both generation and verification requests before spending. Never trim warnings, prerequisites or unresolved attempts to fit. Missing token-count adapter, overflow or truncated model output gives SYSTEM_ERROR with no partial technical instruction. Bind draft, verifier, accepted presentation and stored response to the current runtime, source and evidence payload; retired runtime receipts cannot authorize recovery.

When the text gate passes, add a separately versioned authenticated multipart media endpoint: one JPEG/PNG/WebP per turn, 5 MiB/photo, three/session and six/visitor/day. Stream byte caps, decode actual MIME, reject animation/corruption/20-megapixel or 10,000-pixel-side violations, normalize to 1,600-pixel-side JPEG without metadata, and enforce worker resource limits. No client URL-fetch inputs. Raw and normalized media expire/delete within 15 minutes; session idle expiry 30 minutes and lifetime 24 hours. TTL/deletion evidence remains required before public release.

Starting a new conversation detaches the old active session and clears displayed messages/attempt context; it is not a storage-delete request and cannot reset visitor counters. Retain scope confirmation if unchanged, create a fresh session for a new symptom, and never merge old observations automatically. Recovery reads are separately edge-rate-limited and do not count as a new model turn.
