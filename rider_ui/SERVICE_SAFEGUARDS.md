# Rider safeguards and context integration

Policy version: rider-safeguards-v1. System policy: motomedic-rider-system-v1. These components are implemented and engineering-tested. They are not installed in a deployed rider service. Installing the new prompt changes the runtime/prompt lock, invalidates affected response caches, and requires review of the new exact runtime bindings. Existing 161 approved source/initial scopes remain valid; no generic human approval is reopened.

## Limits

| Boundary | Initial policy |
| --- | --- |
| Text | 2,000 Unicode characters and 8,000 UTF-8 bytes per message; JSON request body 16 KiB |
| Photo | One image per turn, 5 MiB compressed; JPEG, PNG or WebP only |
| Decoding | Single frame, at most 20 megapixels, at most 10,000 pixels per side |
| Normalized image | At most 1,600 pixels per side; re-encoded JPEG without metadata |
| Conversation | 20 accepted rider turns; three photos |
| Visitor | Six accepted turns per rolling minute; 30 turns and six photos per rolling 24 hours |
| Model request | 8,192 counted input tokens and 24,000 serialized UTF-8 bytes, including policy, schema, evidence and state |
| Model output | At most 1,800 tokens; never release a truncated instruction |
| Retention | 30-minute idle session expiry; 24-hour session/operation lifetime; raw and normalized media maximum 15 minutes |

These are application controls, not verified provider quotas. Project-wide model admission must use the current separately maintained provider pacing/call allocation and billing guard. No automatic fallback model, extra retries or new spending are authorized here. Failed admitted turns consume their reserved slot. Recovery GETs do not create model turns but need their own edge rate limit. Published retention requires actual managed TTL/deletion jobs, not this document alone.

## Admission order

At the hosted edge, enforce TLS, XSRF/CORS, request-size and request-frequency controls before body buffering. Resolve a server-authenticated visitor/session capability; never trust browser-submitted identities or usage counts. Require ownership for session/operation reads as well as writes. An anonymous session cookie alone cannot prevent cookie resets; anonymous public access also requires a trusted edge IP bucket, signed visitor token, challenge on repeated resets and global spend/call limits. Use only proxy-verified IPs; never trust arbitrary X-Forwarded-For. Store identity keys as salted hashes and do not retain raw identifiers in routine telemetry.

Read at most 16 KiB plus one byte for JSON, or 5 MiB plus one byte per allowed photo; check Content-Length and actual streamed size. Reject duplicate JSON keys, bad Unicode, invalid controls, empty/oversized text and non-object JSON. Before retrieval or provider work, atomically reserve an operation against visitor and conversation counters in a managed transactional store. check_admission calculates the permitted next usage; AtomicAdmission supplies the transaction boundary. The production store must roll rolling-window counters, enforce ownership, deduplicate operation IDs, reject reuse with a different request hash, retain reservations on failures and expire records. No in-process counter or test stand-in is production enforcement.

Validate MIME against actual decoded content, reject corrupt/animated/oversized decoded images, apply a bounded CPU/memory/time decode worker, normalize and strip metadata. Reject URLs, SVG, PDFs, archives, audio and video. Photos remain disabled until live text acceptance and observation-only vision evaluation pass. Neither upload validation nor a vision prompt grants technical evidence authority.

## Context and reset

Existing constrained_generator.envelope sends selected claims/evidence and only the last 12 active attempt IDs/outcomes. It sends no accumulated raw chat. The deterministic controller still evaluates the complete persisted session. Therefore 12 attempts is not a context-window limit and does not reset diagnostic knowledge. The current provider additionally caps serialized input at 24,000 bytes by default and output at 1,800 tokens. It has no automatic LLM summary/compaction and no fixed number of turns before context overflow.

New hosted requests should use diagnostic_projection as a deterministic compact representation of all active outcomes, confirmed typed facts, pending clarification, exclusions, source scope and symptoms. Complete immutable events and superseded corrections remain in managed storage. Optional chat text is not authoritative and is not appended to every model request. Refresh selected evidence on each turn, retaining all required warnings, prerequisites and citations. Never summarize mandatory OEM evidence or drop old unresolved outcomes to fit.

check_model_request requires an exact-model countTokens or verified tokenizer adapter on the complete request, including policy and schema; its byte bound is an additional cap, not a chars/4 token estimate. The returned body must be the exact body sent to the provider; adding a schema/transcript afterward breaks the bound. Counting unavailable or required context too large yields a sanitized operational SYSTEM_ERROR before generation, with no truncated action. Preserve known verified safety-stop precedence. Output truncation/refusal/schema failure is also withheld. Count both generator and verifier requests and measure the extra latency; countTokens support for the exact hosted model remains an integration check.

Start a new conversation clears rendered messages and detaches the active server view, pending/error state and prior diagnostic context. Bike/manual confirmation may stay selected. It does not erase stored history, reset visitor/IP quotas, delete media already in managed storage or imply data deletion. The next accepted symptom creates a fresh hosted session. Reset stays disabled while an operation is unresolved, avoiding duplicate mutations. After idle expiry reconfirm required facts; do not silently restore old diagnostic assumptions.

## System prompt and answer gates

system_prompt_v1.txt derives from the objective and all four planning documents. prompt_manifest_v1.json binds its bytes; prompt_policy.load_role_policy rejects changed bytes or unknown roles and provides explicit generator, verifier, interpreter and vision roles. The shared objectives are concise OEM-only advice, one step/question, truthful routing, applicability, complete evidence/warnings, immutable citations, typed state, no unsupported diagnosis, prompt-injection resistance, privacy and verified escalation. Role policies do not replace deterministic eligibility, source/review/dependency checks, semantic claim verification, no-repeat rules or rights controls.

The existing release checks keep SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR separate. Source-review gaps are never rider questions. Only reviewed exact cache keys may authorize cached responses; draft/stale/scope-mismatched entries miss closed. Models cannot set approval flags, change manual/model, execute retrieved instructions or author page numbers. Preserve source display restrictions. No hidden fault inference from photos; reported resolution is not verified repair.

## Acceptance evidence still needed

Wire these components into managed hosted sessions, identity/IP/global admission, actual byte-bounded uploads, exact-model token counting, serving role prompts, expiry/deletion jobs and redacted versioned telemetry. Then test concurrent reservation, visitor resets, stale/replayed operations, failure before provider call, invalid images, context overflow, missing warnings, injection, invalid citations, wrong scope, unresolved outcomes and reset/expiry from a browser. Run the required real BGE/BM25 → dependency assembly → controller → generation/verifier → cited-response browser gate with caches bypassed. Record actual end-to-end p95 and cost. Synthetic tests and local screenshots do not close these live items.
