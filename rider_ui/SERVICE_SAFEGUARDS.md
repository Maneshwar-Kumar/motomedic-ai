# Rider safeguards and context integration

Selected serving policy: `open-manual-haiku-draft-verify-v10_12`, with `gcp-public-cloud-run-cookie-v2` frontend access. Code and provider-free boundary checks are implemented; v10 hosted/browser acceptance remains pending. The [owner scope](../reports/public_evaluator/20261012/owner_scope_v1.json) and [credential approval](../reports/public_evaluator/20261012/owner_credential_scope_v1.json) authorize this public evaluator's necessary deployment/identity setup within existing limits. Exact 161-case source/initial approvals remain valid and unchanged; no generic human blocker is reopened.

## Limits

| Boundary | Selected policy |
| --- | --- |
| Text | New scoped rider maximum 100 words, rejected without truncation before retrieval/reservation; separately applicable 2,000-character/8,000-UTF-8-byte transport checks and 16 KiB JSON body |
| Photo (disabled future scope) | One image per turn, 5 MiB compressed; JPEG, PNG or WebP only |
| Decoding (future scope) | Single frame, at most 20 megapixels, at most 10,000 pixels per side |
| Normalized image (future scope) | At most 1,600 pixels per side; re-encoded JPEG without metadata |
| Conversation | 20 accepted text turns; future photo scope three/session |
| Visitor | Six accepted turns per rolling minute; 30 per rolling 24 hours; future photo scope six/day |
| Global rider requests | 60/minute and 250/day; provider allocation may exhaust much sooner |
| Public visitor issuance | Ten/minute and 60/rolling day; atomic spent-proof rejection |
| Public cookie/proof | Secure HttpOnly SameSite cookie valid 24 hours; 14-bit challenge valid 120 seconds |
| Model request | Complete applicable evidence/policy/history native-counted against selected model windows, actual account throughput and existing total budget; former 8,192-token/65,536-byte assembled-input cap removed in new scope |
| Model output | At most 1,800 tokens; never release a truncated instruction |
| Retention | 30-minute idle session expiry; 24-hour session/operation lifetime; raw and normalized media maximum 15 minutes |

These application ceilings do not promise that many provider turns. Existing 100 attempts/999,200 reserved tokens remain permanent and shared with hosted validation; larger requests can exhaust capacity earlier than the historical twelve-turn ceiling. Unused/uncertain reservations remain consumed across restarts, conversations and days. Gemma retains its existing free configuration; the selected paid Haiku role reserves full cache-write/bounded-output cost through the unchanged USD1 guard. INR2,700 lifetime/INR2,540 disconnect limits and stopped inference billing remain unchanged. Availability fallback stays disabled. Recovery reads cause no model turn but still require request limits. Published retention requires actual managed TTL/deletion evidence.

## Admission order

Only the direct Cloud Run gateway is public. It checks the configured host, signed cookie and proof before forwarding browser traffic to loopback Streamlit. It reserves every new visitor through private `/internal/visitors/reserve`; only the exact UI service-account identity can call it. Persistent Firestore issuance/spent-proof transactions fail closed; the UI needs no datastore role. Browser/client forwarding headers supply no trusted IP or identity authority. Proof is a bounded admission challenge, not proof of a human or DDoS protection. Replacing a cookie creates a new visitor subject but cannot reset global issuance/request or provider budgets. Retain no raw proof, cookie, IP or credentials in routine telemetry.

Read at most 16 KiB plus one byte for text JSON and check actual size, duplicate keys, Unicode, controls and empty/oversized text before retrieval. The IAM-protected API also verifies the signed visitor capability and ownership on reads/writes. Firestore atomically reserves visitor/session/global usage, operation identity/payload and completion. Duplicate payloads recover the same operation; conflicting reuse rejects. Failures retain reservations. Dedicated authenticated Cloud Tasks work is separate from SSE capacity and uses fenced leases, terminal reconciliation and an exact deadline. No process-local counter or synthetic store is production enforcement.

Validate MIME against actual decoded content, reject corrupt/animated/oversized decoded images, apply a bounded CPU/memory/time decode worker, normalize and strip metadata. Reject URLs, SVG, PDFs, archives, audio and video. Photos remain disabled until live text acceptance and observation-only vision evaluation pass. Neither upload validation nor a vision prompt grants technical evidence authority.

## Context and reset

V10 projects actual question, relevant saved conversation/topic and optional typed observations/attempts separately from chat text. Short follow-ups retain prior rider topic for retrieval; history cannot invent an observation or verify a repair. Immutable events and superseded corrections remain in managed storage. New selected-role requests use pinned native model windows and actual provider throughput, with bounded output; the former assembled-input8,192-token/65,536-byte caps are retired for the new scoped candidate. The system has no fixed number of turns before budget/context exhaustion and never silently crops required evidence/history to fit.

Refresh applicable reviewed evidence on each turn and retain mandatory warnings, conditions, prerequisites, table headers/units, references and citations. Ordinary Q&A requires no authored question, canonical answer or StepDefinition. Typed feedback must reference an exact issued server choice; unresolved action never becomes an observed normal result. Missing source context is maintainer work, never a rider-resolvable ambiguity.

Model admission requires an exact-model native counter on the complete request, including policy and schema; character estimates cannot replace it. The returned body must be the exact body sent to the provider; adding a schema/transcript afterward invalidates the count. Missing counting, real-window/quota overflow or insufficient remaining budget yields sanitized SYSTEM_ERROR before generation, with no truncated action. Input byte size is recorded without the former artificial assembled cap; strict 16 KiB provider-output JSON validation remains separate. Preserve known verified safety-stop precedence. Truncation/refusal/schema failure is withheld. Count both selected roles, including the finalized verifier request, and measure the latency; exact hosted support remains an integration gate.

Starting a new conversation clears rendered messages and detaches the old active view/context. Bike/manual confirmation may stay selected. It does not delete stored history or reset the cookie's visitor/global/provider limits. Reset stays disabled while an operation is unresolved. The next question creates a fresh owned session; idle expiry requires reconfirmation and cannot silently restore old diagnostic assumptions.

## System prompt and answer gates

The serving composer binds exact draft/verifier policies, schemas, source/index identities and both selected role/model contracts. The [latest model scope](../reports/public_evaluator/20261012/owner_model_scope_v3.json) selects Haiku `claude-haiku-5-5` for both distinct calls. The separately invoked verifier checks the finalized complete/partial response under a distinct policy and schema, including server warnings/limitations/citations, using only admitted evidence, relevant request context and the exact buffer. Same-model calls do not establish cross-model agreement. At most one correction receives fresh verification. Legacy prompt helpers remain compatibility artifacts; they cannot install or authorize a competing design.

The selected Haiku role caches only its exact policy/source-evidence prefix for five minutes. Raw question/history/final response and verdict bindings stay uncached. Prefix reuse cannot authorize a reused answer/verdict, and actual-role cache reads are required before claiming support; savings need paired measurements. Both Haiku roles require current-role cache creation and positive reads. SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR remain distinct. Models cannot set approval flags, change source/model, execute retrieved instructions or author page numbers. PDF/excerpts/figure crops remain prohibited; whole-manual Claude and availability fallback remain disabled. Reported resolution never verifies repair.

## Acceptance evidence still needed

V10.3 exact-verifier cache proof and v10.4 private shell succeeded; six v10.4 SYSTEM_ERROR cases released zero technical answers. V10.6 CI/images and [private readiness](../reports/public_evaluator/20261012/private_readiness_v10_6.json) passed, but native-count preflight failed with zero generation/reservations and no paid Q&A. The Haiku-only v10.12 candidate retains the 100-word input rule and full evidence/history; current-role hosted validation and public acceptance remain required. API `/v1/health` and gateway `/health` remain external readiness routes. Complete independent original-page answer adjudication and anonymous public acceptance. Test persistent quotas, stale/replayed operations, provider/store failure, native-window/throughput/budget overflow, missing warnings, injection, 100/101-word boundaries, wrong scope, follow-ups and dedicated-worker disconnect/recovery. Verify expiry/deletion and redacted traces. Record actual cold/warm latency and costs with exact runtime/images/revisions/rollback. Software tests, private shell and screenshots do not close those gates; photos/uploads/voice stay disabled pending separate scope and evaluation.
