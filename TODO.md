# MotoMedic current TODO register

Reconciled 11 October 2026 against the project objective, 01 Concept Architecture, 02 PRD, authoritative TRD v0.4, 04 To Build Evaluation Decisions, source_manifest.json, the exact v3 coordinator approval and implementation evidence. This current repository tracker updates the dated planning TODO statuses. The Word To Build register has also been updated with current statuses and this dated reconciliation; the other planning documents remain the design record. Historical progress statements are not current release claims. TRD safety/evidence contracts and exact source approval scopes remain authoritative.

## Implemented and checked

- [x] Build the rider UI separately from model/architecture experiments; confirm Himalayan BS6, show selected source, full gated response, structured feedback, citation metadata and remembered outcomes.
- [x] Apply the owner's saved HTML copy review with field-level removal and preserve original/saved review hashes.
- [x] Place the text chat input inside What are you noticing; remove category help text while retaining the topic dropdown.
- [x] Make conversation reset clear displayed chat and active diagnostic context, preserve selected bike scope, and disable reset while recovering an unresolved operation.
- [x] Enforce 2,000-character text input in both the UI and client request path; provide reusable hosted UTF-8/JSON request checks.
- [x] Implement actual photo type/decode/animation/pixel/byte validation and metadata-free bounded normalization; keep rider uploads disabled pending the text-first gate.
- [x] Implement visitor/session quota checks and an atomic managed-store admission interface, with identity/dedupe/outage safeguards and tested limits. Production counter integration remains open below.
- [x] Implement deterministic diagnostic projection without dropping active attempts; add full-request token/byte/output admission checks that refuse overflow or unavailable counting.
- [x] Author a project-derived versioned system policy and role policies for generator, verifier, interpreter and observation-only vision; bind policy bytes in a manifest. Serving installation remains open below.
- [x] Retain existing source/applicability/mandatory-evidence/warning/claim/citation/rights gates, five route states, no-repeat semantics and exact cache rejection.
- [x] Accept the exact coordinator-approved 161 source/initial scopes and selected Himalayan BS6 scope; do not reinstate generic human-only blockers. Approval does not cover new prompt/runtime bindings or general adaptive/photo quality.
- [x] Retain real bounded 26B text-journey successes as Step 2 evidence. Architecture timing comparisons, provider pacing and model choice continue separately; three samples do not prove p95.

Evidence: rider_ui/tests, reports/rider_ui/safeguards_test_log_v1.txt, reports/rider_ui/inline_input/browser_smoke.json, rider_ui/prompt_manifest_v1.json, IMPLEMENTATION_PROGRESS.md and the exact source release manifest. Synthetic UI/model-adapter checks establish software behavior only.

## Required to close hosted text release

- [ ] Install the authenticated rider session/catalogue/feedback/recovery API over the approved registry/controller and real immutable index; durable managed sessions with ownership, CAS and operation dedupe.
- [ ] Implement production atomic visitor/session counters, trusted edge IP/challenge controls, project-wide provider admission and per-day spend reservations. Verify reset/cookie rotation cannot reset limits. UI checks alone cannot stop abuse.
- [ ] Install the new system/role policy and context-admission body in a new reviewed runtime/prompt version; invalidate affected caches. Validate exact hosted model countTokens/tokenizer support. Preserve source approvals and signed bytes.
- [ ] Enforce request streaming/body caps, deadlines, raw/normalized media TTL, idle/session expiry and actual deletion jobs. Do not call retention configured until verified.
- [ ] Pass hostile-input, ownership, concurrent-operation, duplicate/stale-feedback, wrong-variant, missing-warning, injection, citation, context-overflow, truncated-output and system-outage tests in the hosted service. Known applicable safety stop keeps precedence.
- [ ] Demonstrate Browser → hosted session/controller → real BGE + BM25 → graph/dependency assembly → gated generation/verifier → complete cited response, cache bypassed. Retain one correlated redacted trace and exact runtime/source/index locks.
- [ ] Measure browser-to-complete-response warm/cold latency, error rates and cost on a suitable sample. Five-second p95 remains the target, not a proven result.
- [ ] Deploy a shareable text URL under existing budget/guard authorization and test from a fresh logged-out browser. No billing restart or new provider budget is authorized by this tracker.

## Required to close photo release and handover

- [ ] After text acceptance, connect bounded photo upload to observation-only vision, clarify uncertainty and route through the same evidence gate. Review visible-observation accuracy and prompt injection in images; never infer hidden faults.
- [ ] Verify one photo/turn, 5 MiB/photo, three/session and six/visitor/day in the actual hosted path; reject unsupported media and URL input; use bounded decode workers.
- [ ] Complete held-out, multi-turn, safety, photo, unsupported and failure evaluation with versioned adjudication. Initial source approval does not cover arbitrary adaptive transitions.
- [ ] Publish verified support/source-display policy, deployment/rollback/retention notes, reproducible browser demo script and known limitations. Optional voice remains later work.

## Decisions recorded today

Text maximum 2,000 characters and 8,000 UTF-8 bytes. JSON body maximum 16 KiB. Photos maximum one/turn, 5 MiB, JPEG/PNG/WebP, single-frame, 20 megapixels, 10,000 pixels/side; normalized to at most 1,600 pixels/side without metadata. Conversation maximum 20 accepted rider turns and three photos. Visitor maximum six turns/minute and 30 turns/six photos per rolling 24 hours; reset does not clear these counters. Model input maximum 8,192 counted tokens plus 24,000 request bytes, output maximum 1,800 tokens. Session idle expiry 30 minutes, lifetime 24 hours; media deletion maximum 15 minutes. These are initial application choices to measure and tune, not provider quotas or deployed guarantees.

There is no automatic LLM compaction today. Current composition requests do not accumulate chat. The controller uses complete typed state; its model envelope includes only the last 12 active attempt IDs/outcomes. The new projection preserves every active outcome/fact and fails closed if the complete required request exceeds its budget. No fixed turn count predicts context-window exhaustion. The 20-turn conversation cap is an abuse bound, not the model's context capacity.
