# Rider API v1 integration contract

The Streamlit server calls this authenticated hosted API. The browser receives presentation only. The UI is implemented; this API is a required integration boundary, implemented in cloud/arm_a/rider_api.py, with separate hosted acceptance in reports/arm_a/ui_wiring_v1/. Do not point the UI at the Qdrant URL: that service is candidate retrieval only.

Source locks:
- Schema: `motomedic-rider-api-v1`
- Manual SHA-256: `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`
- Index: `index_a3282c4d98cf54595e4ba168`
- Variant: `Himalayan BS6`
- Source display: citation metadata only; PDF, excerpts and figure crops prohibited.

## HTTP boundary

Every request has a server-side `Authorization: Bearer ...` credential. Every mutation also has a unique `Idempotency-Key`. Transport uses HTTPS and rejects redirects. No automatic mutation retry. JSON responses are capped at 256 KiB; request text at 2,000 characters.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /v1/catalogue | Source locks and open-question capability |
| POST | /v1/sessions | Confirm scope and retrieve for raw question |
| POST | /v1/sessions/{id}/questions | Ask another question using expected_version |
| POST | /v1/sessions/{id}/feedback | Apply exactly one issued server choice and run next turn |
| GET | /v1/sessions/{id} | Retrieve latest saved view |
| GET | /v1/operations/{idempotency_key} | Recover a mutation's committed response without executing it again |

Catalogue: schema_version, manual_checksum, index_id, question_input=open, diagnostic_wizard=false, streaming=DRAFT_VERIFY_STREAM for the current open-verification service. Hosted UI capability checks reject the retired complete-unit service; neutral explicit engineering loopback fixtures remain available. The UI exposes no topic selector or symptom routing.

Create request: query, bike_variant, confirmed_himalayan_bs6=true, manual_checksum, index_id, cache_mode=bypass. Continued questions add expected_version. The actual rider question and relevant saved conversation reach the applicable immutable source-evidence pipeline. Source-supported factual and procedural answers require no canonical question, authored answer scope or registered diagnostic action. A complete private draft is followed by a separate question-coverage and claim-support verifier call. Code retains source/version integrity, applicability, schema/citation limits, ownership and delivery checks. All final technical content, server-added conditions/warnings and citations are finalized before verification. A rejected draft is withheld; at most one correctable revision is verified again. Incompatible Arm A and exact-answer cache shortcuts are disabled. No new model call occurs while displaying accepted text.

The private UI uses managed audience-bound tokens and a signed X-MotoMedic-Visitor capability. Its IAM-verified principal derives a stable keyed visitor nonce across refresh/reset. Backend ownership binds the UI service principal and visitor nonce. Anonymous public access is outside this design. Every mutation uses a 32-hex operation key. Complete technical answer units stream only after their operation/session view is atomically committed; disconnected delivery retrieves the saved operation without rerunning it.

Feedback request: expected_version, choice_id, cache_mode=bypass. **No client-supplied fact, approval, evidence, or model output.** Server looks up the choice previously issued for this exact session version, validates its reviewed typed binding, then applies ReviewedService.feedback and the next turn. Unresolved action never seeds an observation.

## Saved view

Required top-level fields: schema_version, manual_checksum, index_id, session_id (opaque identifier), version (nonnegative integer), response.

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

Mutations request `Accept: text/event-stream`. All v6 events bind to the mutation's 32-hex operation ID:

| Event | Payload and rule |
| --- | --- |
| progress | Exactly operation_id and stage. Stage is retrieving, drafting, verifying or displaying. Constant client labels are shown only when the backend emits a real stage. |
| verified_block | operation_id, response_sha256 and the complete saved view. The persisted delivery binding, selected source, response hash and release gate must validate before any answer callback. |
| answer_chunk | operation_id, response_sha256, offset and text. Offset counts Python Unicode codepoints; text must be the exact next slice of the buffered accepted response. |
| complete | The identical saved view. Its full text must equal concatenated chunks and the accepted response hash. |
| error | Sanitized operational failure; private drafts and verifier output are never displayed. |

Displaying is emitted only after verification, final integrity checks and durable save. Progress contains no technical text, private drafts, chain-of-thought, confidence, percentages or simulated timing. A correction can emit drafting/verifying again, with no private answer token release. SYSTEM_ERROR uses neutral completion without accepted-answer chunks. Verified clarifications, supported partial responses and refusals retain their distinct routes.

Persisted `delivery` contains operation_id, response_sha256, runtime_lock, manual_checksum and index_id. The response hash is SHA-256 of UTF-8 JSON for the complete response object with sorted keys, compact separators, no non-finite values and Unicode preserved. The client checks these bindings during streaming and recovery. A disconnect retains the entire accepted view, then retrieves the original operation; any changed saved view is blocked. Replay streams the existing buffer and starts no drafting or verification call.

## Hosted implementation obligations

Use the exact source-approved registry, immutable BGE/BM25 chunks, source-linked complete assembly and current open drafting/verification runtime. Do not import test fixtures, rebuild embeddings, silently switch provider models, or bypass applicability, rights, source warning/condition or claim checks. Registered legacy action eligibility does not restrict ordinary manual Q&A. The UI contains no model selection; the other implementation chat owns this configuration.

Use managed transactional session storage with immutable attempt snapshots and compare-and-swap versions. SQLite/local Streamlit state is not the production store. Atomically reserve and deduplicate operation IDs before model calls; persist/retrieve the final response and choices. A concurrent or stale feedback returns 409. Repeated same operation returns the original response without another model call. An operation still executing should report a recoverable status, not re-execute it.

Enforce authenticated ownership/capability on session and operation reads. Shared UI-to-API authentication alone is not a substitute for per-session authorization. Apply global and per-session rate/call limits, provider spending reservations and a fresh budget/guard preflight under the existing project authorization. Respond 429 when limited; no fallback model or automatic retries. Redact query text and credentials from logs. Expire sessions and operation records under a published retention policy.

## Live acceptance (pending)

Browser → hosted session/controller → actual BGE + BM25 retrieval → verified graph/dependency assembly → private draft → separate online verification → final checks and durable save → exact buffered answer streaming → saved cited response.

Run fresh ordinary questions, a useful partial answer, follow-up, fixed fallback, and verifier failure in a fresh browser. Answer caching remains disabled. Retain correlated redacted browser/service traces, immutable version bindings, actual provider execution, rendered matching citations, no-repeat results and browser-to-complete-response timings. Warm/cold p95 needs a suitable sample size; three samples do not establish p95.

UI fixture tests or localhost screenshots do not meet this gate. The photo control remains disabled until this text gate passes and an observation-only vision path is implemented/evaluated.


## Safeguards v1 serving integration

Use SERVICE_SAFEGUARDS.md and the current TODO.md as the dated implementation/release register. Preserve API v1 response/choice semantics. Text is at most 2,000 Unicode characters and 8,000 UTF-8 bytes; streamed JSON body at most 16 KiB. The UI and client reject oversized text, but the hosted handler must repeat these checks before retrieval. Bind each browser to a server-verified visitor capability and its owned sessions; a shared API credential alone is insufficient. Visitor counters must survive new conversations. Add trusted edge IP/challenge and global spending controls for anonymous reset abuse.

The managed transaction must reserve an operation against six turns per rolling minute, 30 turns per rolling 24 hours, and 20 turns per session. Same-operation replay returns its original reservation/view without another model call; a different payload hash conflicts. Retrieval/provider failures consume admitted slots. Counters and model-call/budget admission must be project-wide across workers. A caller must not provide usage counts. Admission-store outage blocks new inference with a sanitized operational error; preserve already established applicable safety-stop semantics.

The current open-Q&A serving context uses bounded conversation history and freshly retrieved manual evidence. Fresh evidence plus trusted policy and schema must fit 8,192 exactly counted input tokens and 65,536 bytes; cap output at 1,800 tokens. Check both generation and verification requests before spending. Never trim warnings, prerequisites or unresolved attempts to fit. Missing token-count adapter, overflow or truncated model output gives SYSTEM_ERROR with no partial technical instruction. Bind draft, verifier, accepted presentation and stored response to the current runtime, source and evidence payload; retired runtime receipts cannot authorize recovery.

When the text gate passes, add a separately versioned authenticated multipart media endpoint: one JPEG/PNG/WebP per turn, 5 MiB/photo, three/session and six/visitor/day. Stream byte caps, decode actual MIME, reject animation/corruption/20-megapixel or 10,000-pixel-side violations, normalize to 1,600-pixel-side JPEG without metadata, and enforce worker resource limits. No client URL-fetch inputs. Raw and normalized media expire/delete within 15 minutes; session idle expiry 30 minutes and lifetime 24 hours. TTL/deletion evidence remains required before public release.

Starting a new conversation detaches the old active session and clears displayed messages/attempt context; it is not a storage-delete request and cannot reset visitor counters. Retain scope confirmation if unchanged, create a fresh session for a new symptom, and never merge old observations automatically. Recovery reads are separately edge-rate-limited and do not count as a new model turn.
