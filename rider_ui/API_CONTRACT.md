# Rider API v1 integration contract

The public gateway hosts Streamlit and calls the private IAM-protected API in [cloud/arm_a/rider_api.py](../cloud/arm_a/rider_api.py). The browser receives presentation, progress and a signed visitor cookie; provider credentials stay server-side.

Source locks:

- Schema: `motomedic-rider-api-v1`
- Runtime policy: `open-manual-section-template-v1`
- Manual SHA-256: `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`
- Index: `index_f768fbb216836c003701079e`
- Variant: `Himalayan BS6`
- Source display: citation metadata only; no PDF, excerpts or figure crops.

## HTTP boundary

Every UI-to-backend request carries a managed audience-bound `Authorization: Bearer ...` service identity and the owned signed visitor capability. Every rider mutation also carries a unique 32-hex `Idempotency-Key`. Transport uses HTTPS and rejects redirects, and mutations are never retried automatically. JSON responses are capped at 256 KiB, request JSON at 16 KiB and rider text at 2,000 characters and 8,000 UTF-8 bytes. Questions over 100 words return HTTP 413 with a limit code, before retrieval or reservation and without truncation.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /v1/catalogue | Source locks, `question_input=open`, `streaming=SAVED_RELEASE_STREAM`, answer provider |
| POST | /v1/sessions | Confirm scope and ask the first question |
| POST | /v1/sessions/{id}/questions | Ask another question with `expected_version` |
| GET | /v1/sessions/{id} | Retrieve the latest saved view |
| GET | /v1/operations/{idempotency_key} | Recover a mutation's committed view without running it again |

A create request carries `query`, `bike_variant`, `confirmed_himalayan_bs6=true`, `manual_checksum` and `index_id`. It may add `cache_mode`, which is accepted for compatibility; answer caching is disabled. Continued questions add `expected_version`. A wrong source, variant or index returns HTTP 400 `SOURCE_OR_VARIANT_MISMATCH`. A stale version or conflicting payload returns HTTP 409. Open Q&A issues no feedback choices, and there is no feedback route.

The request only admits the operation. A named Cloud Tasks task then runs it on the dedicated worker:
1. top-5 hybrid retrieval;
2. whole sections as plain text;
3. one Haiku call;
4. the deterministic gate;
5. a durable commit.

Display and recovery never cause a model call.

## Saved view

The required top-level fields are `schema_version`, `manual_checksum`, `index_id`, `session_id`, `version`, `runtime_policy` and `response`. The `response` object has these fields:

- `type`: SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP or SYSTEM_ERROR.
- `natural_language`: the complete gate-composed rider text, displayed literally.
- `technical_content`: true when the text carries cited manual content.
- `release_gate_passed`: true only for a view released by the deterministic gate after one model call. The fixed no-retrieval fallback and SYSTEM_ERROR are false.
- `cited_pages`: objects with `evidence_id`, `pdf_page` (1–149), `pdf_page_index`, `manual_checksum` and `index_id`.
- `trace_id`, `reason_codes`, `clarification_question` and `escalation_uri`.

The optional top-level fields are `escalation_uri` (null or the verified `mailto:support@royalenfield.com`) and `runtime_controls` (counts, cost and identifiers only). `choices` and `history` are always empty lists.

A gate-released view also carries `release_delivery`. It binds the operation ID and runtime lock, the manual and index, the response hash (`presentation_sha256`) and `text_sha256`. It also binds the SHA of the text sent to the model (`evidence_payload_sha256`) and of the private release record (`release_sha256`).

The persisted `delivery` carries the operation ID, response hash, runtime lock, manual, index, `evidence_payload_sha256`, `release_binding_sha256` and `event_protocol: operation-sequence-v1`. The response hash is the SHA-256 of the UTF-8 JSON response object, with sorted keys, compact separators and no non-finite values. Views never contain evidence URIs, source text, crops, provider bodies, secrets or raw media.

## Progress and delivery

Mutations request `Accept: text/event-stream`. The server-sent events (SSE) stream observes durable progress for up to 150 seconds; closing it does not stop the worker. Every event carries the 32-hex operation ID and a consecutive sequence starting at 1:

| Event | Payload and rule |
| --- | --- |
| progress | Stage `retrieving`, `drafting`, `checking` or `displaying`, emitted only when the backend reaches that stage. No text, confidence or percentages. |
| verified_block | The complete saved view and its response hash; the wire name means the block the release gate passed. It is sent after durable save, before any chunk. |
| answer_chunk | `response_sha256`, `offset` (Unicode codepoints) and `text`, the exact next slice of the saved text. |
| complete | The identical saved view. Its text equals the concatenated chunks. |
| error | A sanitized operational failure. |

Fallback and SYSTEM_ERROR views emit only `complete`, with no `verified_block` or chunks. A disconnect keeps the accepted view, and the client then recovers the original operation; any changed saved view is blocked. Operations have a 1,200-second deadline and a fenced worker lease. An expired or uncertain operation ends terminally and is never retried.

## Hosted obligations

The server must enforce these rules:
- Use the frozen section index, verified at startup, and the frozen generation contract.
- Never rebuild embeddings, switch models or add a verifier or fallback at runtime.
- Use managed transactional session storage with immutable version snapshots and compare-and-swap.
- Reserve and deduplicate operation IDs before any model call.
- Enforce authenticated ownership on session and operation reads.
- Apply the per-visitor, per-session and global limits listed in [SERVICE_SAFEGUARDS.md](SERVICE_SAFEGUARDS.md). Respond 429 when limited.
- Redact query text and credentials from logs.

Before a UI revision is connected, authenticated API `/v1/health` must report:
- architecture `SECTION_TOP5_SINGLE_CALL_TEMPLATE_GATE`;
- `review_layer: NONE` and no verifier;
- the dense backend and runtime lock;
- the source and index identities.
