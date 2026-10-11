# MotoMedic UI chat outcome and continuation

Saved 11 October 2026 in the Service Agent project folder at the owner's request. This is a durable outcome record, not a verbatim chat export. A future agent can continue from these files without access to this chat. No chat was deleted or archived by saving this record.

## Owner's final direction

Keep TODO.md limited to pending UI integration, guardrails and photo handling. The intended text pipeline is concurrent retrieval from the immutable dense embedding index and BM25, grounded evidence/controller processing, caching, and streaming delivery using Option A. Do not substitute a full-manual architecture or Option C. TRD v0.5 section 14 and 03_TRD_Architecture_Decision_Note.docx supersede the earlier v0.4 methodology wording. B remains the separately retained alternative; A is the requested integration path here.

## UI and copy decisions preserved

- The owner reviewed editable HTML and saved their copy. Parentheses/removal decisions apply at the field/sub-block level; removing a sub-block must not remove its parent. Original, editable and owner-edited snapshots, baseline and comparison tooling are in rider_ui/design_review/; owner copy differences and application evidence are in reports/rider_ui/owner_copy_review_diff.json and owner_copy_applied_v1.json.
- The chat bar belongs inside What are you noticing, above the photo uploader.
- Remove the entire Select a topic/category dropdown and its tooltip. Infer candidate intent on the hosted service from the rider symptom; no local UI diagnosis or topic classifier. The catalogue must advertise intent_resolution: hosted or the client refuses submission.
- Keep Himalayan BS6 scope confirmation, manual identity, one next question/action, full warnings, structured server-issued feedback, citation metadata, remembered outcomes and the verified support route. Do not serve original PDF/excerpts/crops to riders under the recorded display policy.
- Start a new conversation clears displayed messages and detaches active diagnostic context. Keep unchanged bike confirmation. Do not automatically merge prior observations, delete stored records or reset visitor quotas. Disable reset while recovering an unresolved operation.
- Photos remain disabled until the hosted text-first acceptance gate passes. Optional voice was not built.

## What is implemented, and what the evidence proves

| Component | Durable evidence | Scope |
| --- | --- | --- |
| Rider UI, hosted API client contract, container, editable review | rider_ui/app.py, client.py, API_CONTRACT.md, Dockerfile, design_review/ | Implemented and tested; compatible hosted rider API and public UI connection still pending. |
| Concurrent dense + sparse retrieval | online_retrieve.py: _first_stage uses two ThreadPoolExecutor workers; architecture_benchmark.py paired controls | Dense BGE M3 query scoring overlaps BM25; both must succeed. RRF/conditional recovery/verified assembly remain required. Three controls did not demonstrate a latency gain. |
| Retrieval to Option A output | architecture_benchmark.py: run_sample A_COMPONENT_SELECTION; reports/architecture_run_38122505406/ | Hosted bounded engineering journeys use real retrieval and exact reviewed wording selection. All three A initial and repeat cases passed. This is not a deployed rider endpoint. |
| Option A verified streaming | verified_delivery_stream.py and architecture_benchmark.py release path | HTTP/SSE complete-unit delivery after gates and session save, with terminal events; loopback delivery measured, actual public-browser integration pending. Raw selection JSON/provider tokens never become rider repair text. |
| Approved-wording candidate/response cache | semantic_candidate_cache.py; architecture v4 report | Three A repeat hits with exact authority/content checks. Similarity is candidate discovery only. Five-minute TTL and bounded 64-entry experimental cache; not production managed storage. |
| Provider prompt-prefix cache | No implementation or provider cached-token evidence found in current selected Gemma transport | This is distinct from response caching and remains an integration requirement. Do not mark complete or claim a provider-cache speedup. |
| A post-facto semantic audit | reports/a_semantic_audit_v2_conclusion.json, a_semantic_audit_v2_report.md | Hosted run 38126896735: all three unique A output bundles accepted; six claims supported/complete, zero unsupported additions, three requests, no regeneration/retries/fallback. Exact initial/repeat identity retained. No whole-corpus or adaptive/vision approval implied. |
| Text/media/context/admission helpers | rider_ui/safeguards.py and tests/test_safeguards.py | Reusable boundary checks and atomic-store interface tested. Durable production store, token-counter adapter, serving installation and deletion jobs remain pending. |
| Project system and role policy | rider_ui/system_prompt_v1.txt, prompt_policy.py, prompt_manifest_v1.json | Version/hash-bound policy authored; serving_installation is NOT_INSTALLED. Apply A-specific selection responsibilities during reviewed integration; do not add B's semantic verifier to A by accident. |
| UI safeguards verification | reports/rider_ui/safeguards_validation_v1.json, safeguards_test_log_v1.txt, inline_input/ | 31 tests and five synthetic browser checks; desktop/mobile layout inspected. Final commit 3d4f3b967e305bce0ba8d29e5993b6102d22f67a passed hosted UI tests and isolated container build in run 38126659830. |
| Word TODO reconciliation | 04_To_Build_Evaluation_Decisions.docx; reports/rider_ui/todo_document_qa_v1.json | Dated status reconciliation rendered by hosted run 38126378756; all 12 pages visually inspected. The pending-only current tracker is now TODO.md; completed/history material belongs here and in the dated Word record. |

## Limits and context decisions

Initial application limits: 2,000 Unicode characters/8,000 UTF-8 bytes per text message, 16 KiB JSON body; one photo/turn, 5 MiB, JPEG/PNG/WebP, single frame, 20 megapixels and maximum 10,000 pixels/side. Normalize to at most 1,600 pixels/side without metadata. Three photos and 20 accepted rider turns per conversation; six turns/minute and 30 turns/six photos per rolling visitor day. Session idle expiry 30 minutes, lifetime 24 hours; raw/normalized media deletion within 15 minutes. Complete model request: at most 8,192 exactly counted input tokens, 24,000 UTF-8 request bytes and 1,800 output tokens. These are app choices, not verified provider quotas. UI/client text limits are enforced; actual hosted enforcement is pending.

There is no automatic LLM compaction today and no meaningful fixed turn count for context exhaustion. Current composition builds fresh requests rather than a growing raw transcript; the controller retains full typed diagnostic state, while the old model envelope supplies only the last 12 active attempt IDs/outcomes. The new deterministic projection preserves all active outcomes/facts and refuses overflow rather than silently dropping attempts, warnings or prerequisites. Its runtime installation is pending. A 20-turn conversation limit prevents abuse; it is not the model context-window size.

The system policy derives from the project promise: only applicable versioned OEM evidence can authorize technical guidance; one focused question/action at a time; retain required warnings/specifications; unresolved action is not a normal observation; no unjustified repeats, hidden-fault photo diagnosis or fabricated citations. Untrusted rider/manual/image instructions cannot override policy. Distinguish the five response routes and system failure from absent evidence. Keys remain server-side; media is ephemeral.

## Source and approval locks

Manual SHA256 cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89; immutable candidate index index_a3282c4d98cf54595e4ba168, BGE M3 1,024-token chunk budget, dense + BM25 and reviewed dependency graph requirements. Reuse the versioned hosted index; no per-request manual parsing/embedding.

Exact coordinator v3 approval for the 161 source/initial scopes is in human_review/agent_release_161/coordinator/release_manifest_v3.json, SHA256 b8f8c7b5a9e1a299f0a90eecbf10127779b62b35fc105f0cd587de433e235298. It does not approve arbitrary new runtime/prompt bindings, adaptive transitions, general photo quality or deployment. Do not invent human signoff or reinstate a blanket human-only review blocker. Read that package's README and root_validation_v3.json before integration. Keep mandatory evidence/applicability/safety gates and rights policy intact.

## Caching distinction and capability evidence

Provider prompt caching reuses precomputed input-prefix tokens; reviewed response caching reuses approved output wording. Only the latter is implemented in the selected architecture evidence. gemini_transport.py currently sends complete payloads to streamGenerateContent without a cachedContent binding; the recorded runs establish no provider prompt-cache hit.

Official docs checked 11 October 2026: https://ai.google.dev/gemini-api/docs/caching describes implicit caching for Gemini 2.5 and newer models, and https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api identifies hosted gemma-4-26b-a4b-it. These pages do not establish Gemma prompt-cache support. Check the exact endpoint/model capability before installing or making provider calls; unsupported is an explicit unresolved capability, not permission to switch models, pad prompts or spend additional budget. The requested provider prefix-cache item remains in TODO.md until implemented with evidence or the owner explicitly accepts the capability result.

## Publication and continuation

Private repository: Maneshwar-Kumar/motomedic-ai. UI branch: codex/rider-ui-20261011. Draft PR: https://github.com/Maneshwar-Kumar/motomedic-ai/pull/2. Architecture branch is codex/reviewed-evidence-controller; other chats edit the same working folder. Preserve their work and stage only this task's files; do not switch/reset the shared checkout. The UI branch uses an isolated temporary Git index. The PR is not merged or deployed.

Read TODO.md, this outcome, rider_ui/API_CONTRACT.md, rider_ui/SERVICE_SAFEGUARDS.md, TRD_UI_FOLLOWUP_HANDOFF.md, TRD v0.5 and source_manifest.json next. The A audit and read-only Cloud Run cost investigation are complete in that handoff; do not repeat exhausted provider allocations. Keep minimum zero and existing boost unless a separately authorized setting change is requested. This record makes no deployment/billing change and contains no credentials or raw rider media.

Deletion readiness: all retrievable decisions and outcomes from this UI chat are saved in the project folder with a hash receipt. The requested pipeline is not falsely certified as a completed public service: hosted integration and provider prompt caching remain open in the restricted TODO. Deleting the chat will not remove those repository files; this record is sufficient to resume the unfinished work.
