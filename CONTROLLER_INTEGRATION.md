# Reviewed evidence controller integration

The TRD v0.4 controller boundary is implemented alongside the existing hosted retrieval stack. The eleven authored step/lookup records are **draft candidates**. No OEM technical claim, procedure, dependency, rule, golden case or cache path has been independently approved by this build. The current online verification exercises fail-closed behavior and synthetic approved software fixtures.

## Decisions and implementation plan

The implementation separates three decisions: source-reviewed predicates determine eligibility; a complete reviewed dependency manifest permits composition; deterministic citation/warning checks and a supplied semantic support verifier permit technical text to be released. Retrieval relevance never supplies any of these approvals.

Use a review overlay over the existing BGE M3 snapshot, rather than edit extraction objects or rebuild embeddings. This preserves the original checksum, evidence IDs, BM25 postings, chunks, vectors and document graph. The existing conditional policy still permits at most one exact dependency recovery and one rerank. Review gaps stop before inference; `may_generate_procedural_advice` remains false on raw retrieval bundles.

Use immutable typed Python contracts and allowlisted comparisons, rather than executing expressions extracted from the manual. Use a deterministic controller and versioned product policy, rather than model-generated next steps. Explicit, reviewed OEM next-step links take precedence; otherwise selection uses stable product ordering without an OEM-priority claim.

Use content-bound human review records, rather than an `APPROVED` string embedded in a candidate. The private repository and code review are the authorization boundary. Hashes detect changed content; they are not reviewer authentication or digital signatures. An LLM judge may propose assessments, but independent original-page comparison and human sign-off are required to authorize a record.

## Owner decisions recorded on 9 October 2026

The owner accepts a rider confirming Himalayan and BS6 as the demo selection rule. The manual edition is pinned internally; riders need not identify its publication code or a model year. The supplied PDF cover says BS VI, page 3 identifies a 452 cc Sherpa engine, and original PDF pages 4 and 149 identify RAM00818/A, edition 4 November 2025. These are agent-checked metadata observations, not independent procedure approval. The source checksum is unchanged.

Engineering PDF/excerpt use is authorized by the owner. End-user PDF, excerpts and figure crops are prohibited. This later owner instruction overrides the earlier PRD requirement to open source pages in the rider UI. Internal review packets retain original spans; the end-user projection removes evidence asset routes and claim text from citation mappings. Evidence access defaults to denial for end users. A source warning may be displayed verbatim only in engineering output; an end-user safety stop retains its status and support routing without exposing that excerpt. Reviewed paraphrases still require the ordinary claim checks.

The requested escalation is: "Kindly write to Royal Enfield at support@royalenfield.com". The address appears in original PDF page 2 and was checked on the official Himalayan support page on 9 October 2026: https://www.royalenfield.com/in/en/support/digital-quickstart/new-himalayan/contact-us/ . The owner-selected email is available even while procedural review is pending. No email is sent by the assistant or this implementation.

The OEM owner-manual portal is recorded separately from an unverified exact download URL. Model year and market remain unknown metadata; the owner's selection policy does not require them as rider prompts. Private engineering authorization is not recorded as an OEM redistribution license.

## Runtime contracts and boundaries

- `controller_contracts.py`: immutable `StepDefinition`, `ApplicabilityRule`, `DependencyManifest`, `EligibilityDecision`, `DiagnosticSession`, `StepAttempt`, facts, outcomes and five response types.
- `evidence_registry.py`: version/index/checksum checks, exact-content approval, reviewed procedure boundaries, dependency scope, evidence overlays and engineering-only source access.
- `reviewed_controller.py`: TRUE/FALSE/UNKNOWN eligibility, focused questions, selection, canonical routing, verified safety-stop precedence, evidence/citation/claim gates and end-user projection.
- `online_retrieve.py`: `Retriever.reviewed_controller(...)` binds the registry to the existing retrieval implementation. No document parsing or embedding is performed per turn.
- `diagnose.py`: `ReviewedService` uses that boundary, the constrained response pipeline and a session store. The ordinary technical pipeline defaults to an unconfigured fail-closed provider/verifier. The legacy `Session`/CLI and draft cache remain engineering prototypes and are never invoked by this service.
- `session_store.py`: append-only session snapshots with optimistic concurrency and immutable history checks. SQLite is suitable for a single private hosted worker or CI; ephemeral Cloud Run files are not durable rider storage. A multi-worker public UI must inject a managed transactional store before release.
- `reviewed_cache.py`: exact version/checksum/variant/path keys and closed misses for legacy/draft/stale caches. A matching reviewed entry supplies only a draft for revalidation, never a released response. The service currently selects through the controller and does not serve cached technical text.

`ACTION_COMPLETED_UNRESOLVED`, `UNCLEAR` and `NOT_APPLICABLE` cannot create inspection facts. Corrections append an event with `supersedes`; the old event remains unchanged and `superseded_by` is derived. Corrections must actually change a typed observation. Repeat exceptions require a relevant correction, a changed applicable symptom set, or an approved manual repeat predicate, with an explanation. An unrelated added symptom does not unlock a repeated action. `NOT_APPLICABLE` requires scope reconfirmation in a new session.

A successful user report closes as `CUSTOMER_REPORTED_RESOLVED`, not a verified repair. Source/version switches require a new confirmed session. Typed facts and attempts stay separate from query text. Public service responses use the end-user projection by default; engineering callers must explicitly select that audience.

The service exposes redacted eligibility/retrieval traces containing version IDs, statuses, reason codes, source IDs, state transitions and confirmed-input TTFO. Raw query text/media are absent. Estimated cost remains unknown until a provider adapter measures it. A supplied trace sink must use private storage. No production tracing backend, vision or voice adapter is claimed.

## Independent review workflow

1. Run the private **Verify reviewed evidence controller** GitHub workflow. It reuses artifact `owner-manual-index-37908240500`, authors draft candidates online from existing objects, validates the committed registry and exports an engineering review packet. No GCP resource or billing operation is part of this workflow.
2. Author precise action/condition spans, full procedure boundaries and mandatory dependency categories in `registry/candidate_registry.json`. Concrete span/role proposals and prerequisites were authored after visual source inspection. Table objects preserve the full source table; row selection and warning/figure scope still need independent review. `scope_review_complete` and `boundaries_checked` start false; unclassified dependency sets cannot pass. Do not assume the existing conversational question order is OEM order.
3. Export a review packet for each source, evidence object, procedure, rule, dependency and step. Inspect original PDF pages and bbox spans independently of search output; tables need headers/units, warnings need complete scope, and figures need the actual image. Record each check and any not-applicable explanation.
4. Fill the packet's decision template with reviewer identity, decision, checked source spans, all required checks, notes, `independent_original_page_review` and `human_signoff`. Apply it with `record`. Rejections and stale decisions also remain in the ledger. Review a candidate's content before approval; changing it invalidates its prior decision.
5. Commit review decisions in the private repository through normal review. Validate again and independently adjudicate acceptance cases. Review/schema/code/source changes invalidate session/cache locks. New manual/parser/chunker/embedding versions still require a new immutable index; policy-only changes reuse document vectors.

```bash
python registry_workflow.py validate --index build/index
python registry_workflow.py packet --index build/index --kind step --id lookup_oil_grade --output build/review-packet.json
python registry_workflow.py record --index build/index --decision build/completed-review-decision.json
python verify_controller.py --index build/index --output build/controller-verification.json
```

Authoring output never overwrites an existing registry. To propose another version, use a fresh destination. Engineering review packets are private artifacts; do not publish them as rider evidence endpoints.

## Acceptance and remaining gates

`registry/acceptance_scenarios.json` establishes five direct questions: oil grade, tyre pressure, fan fuse/rating, starter duration and USB charging. Three multi-turn seeds cover no-start with documented service escalation after unresolved fuse work, first-gear stall after unresolved stand action, and misfire after unresolved cooling. Required object IDs and original page lists are traceable to the selected hosted snapshot. These seeds reuse draft regression material and must not be called held-out cases.

Current execution requires all eight to abstain without issuing technical text. Post-review route sequences are authoring targets needing independent original-page adjudication. Separate synthetic contract tests exercise supported lookups, advancement, clarification, correction, closure, exhaustion, non-repeat rules, review invalidation, safety/error precedence, citation/warning failures, cache rejection, privacy projection and store concurrency. Passing these tests is not an OEM acceptance score.

Before technical answers are enabled, the owner/reviewer must approve precise procedures, rules, dependencies, claims and source metadata. PDF page 103 remains a flagged extraction gap. The original exact PDF download URL is unverified. An actual semantic support verifier must be configured and assessed; absence or failed verification returns `SYSTEM_ERROR`. The concrete action drafts include proposed prerequisites and safety scope, which remain unapproved. Independently reviewed safety-stop records and safe intent/feedback interpretation are also required for broader rider input.

The rider UI, durable hosted session adapter, public upload/rate/day-spend limits, semantic-verifier calibration, held-out evaluation and public release remain separate gates. An agent-checked conflict is recorded for legacy D024/D035: PDF page 121 calls for authorised service when a fuse problem persists. The reviewed controller follows an approved stopping condition instead of automatically advancing. Those old paths remain draft material needing adjudication.

The existing private Qdrant service and INR800 budget/INR640 billing guard are unchanged. Do not re-enable billing after a real budget stop without owner authorization. No public release or new GCP deployment is authorized by passing this engineering workflow.

## Constrained generation implementation

The composition/validation boundary is implemented in `constrained_generator.py`, `generation_contracts.py` and `generation_providers.py`. See `GENERATOR_INTEGRATION.md` for the reviewed-wording/claim-role contract, separate semantic adapter, provider authorization, session/cache runtime locks and bounded private evaluation. This implementation does not approve the eleven real draft records or demonstrate live semantic accuracy. The legacy injected template verifier remains an engineering/controller compatibility interface; ordinary `ReviewedService` technical answers use the new pipeline. Verified safety stops and nontechnical clarification/escalation remain deterministic.
