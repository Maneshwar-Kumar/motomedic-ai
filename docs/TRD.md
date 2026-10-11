# MotoMedic technical requirements

Version 1.0 reset · 11 October 2026 · Status: target contract; current runtime has open acceptance gaps.

This is the single current technical specification paired with [PRD.md](PRD.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [TODO.md](../TODO.md). It consolidates the owner's open-manual draft, verify, stream method and evidence-only optional Claude fallback. Earlier exact-answer selection, universal StepDefinition admission and omitted-semantic-verifier methods are superseded. Exact source approvals and permissions retain their original scope and bytes; this specification is not release or deployment approval.

## 1. Selected architecture and boundaries

| Component | Contract |
| --- | --- |
| Hosted ingestion job | Versioned Docling parsing and parent/child chunking once per source/parser/chunk/model version. |
| Evidence artifacts | Immutable source objects, page registry, reviewed relationships and manifest in private object storage. |
| Dense retrieval | Query embedding with pinned BGE M3; authenticated Qdrant query against the selected immutable collection. |
| Sparse retrieval | BM25 postings from the same snapshot; run concurrently with the dense path. |
| Retrieval orchestrator | RRF, selective reviewed context assembly, one bounded recovery and one conditional cross-encoder rerank. |
| Private composer | Complete evidence-only draft using question, relevant history, typed outcomes and source policy. |
| Separate verifier | Strict semantic coverage/claim verdict over the exact finalized response and evidence. |
| Application gate | Validate bindings, schemas, applicability, citation membership, warnings and delivery integrity; cannot replace semantic verification. |
| Durable state | Firestore sessions, facts/outcomes, operation leases, reservations and accepted response transaction. |
| Planned work dispatch | Cloud Tasks to an authenticated worker endpoint; generation lifetime is independent of the browser SSE connection. This is a planned change, not a deployed claim. |
| Delivery | Authenticated API/SSE progress and exact saved-buffer streaming; idempotent recovery. |
| Operations | Immutable build images, managed secrets/identity, durable artifacts, admission/spend limits and redacted traces. |

Qdrant stores/searches dense vectors; it does not authorize answers. BM25 does not prove claim support. The verifier is probabilistic and requires independent evaluation. Source review and deterministic application checks remain separate controls.

Current candidate index: `index_a3282c4d98cf54595e4ba168`, 532 child search chunks, 277 section parents, pinned BGE M3 with 1,024-token chunk budgets. Reuse it while fixing serving orchestration when source/parser/chunk/embedding content is unchanged. Query embedding is per request; document embedding is not.

## 2. Version identity and ingestion

Define index identity from source SHA-256, parser version/options, chunking configuration, embedding model/revision and dense/sparse settings. A change to any ingestion input creates a new index. Retrieval policy, prompts or controller changes create a new runtime version but do not automatically require unchanged document vectors to be rebuilt.

The hosted job must:

1. Check the PDF against `source_manifest.json`; record immutable object generation and checksum.
2. Parse layout, reading order, PDF index and printed page labels, headings, tables/headers/units, warnings, captions/figures and source bounding boxes.
3. Produce typed source objects and stable source-bound IDs. Mark uncertain extraction explicitly; retain page 103's flagged fallback rather than claiming clean Docling extraction.
4. Create searchable children with parent links and table/header/unit context. A parent label or reviewed child does not authorize an entire parent body.
5. Register only provenance-backed reviewed relationships for required warnings, conditions, prerequisites and references. Inferred semantic relationships cannot authorize technical content.
6. Embed children once, create Qdrant points and BM25 postings, and write artifact/model/config hashes and ingestion QA.
7. Validate page/object coverage and reproducible reload. Cached parsing is valid only when its manifest matches PDF hash, parser version/options and parsed artifact hash.

Store durable snapshots in private Cloud Storage under immutable versioned object references. Expiring GitHub Actions artifacts may contain temporary logs, but cannot be the sole index or deployment input.

## 3. Core contracts

| Object | Required data |
| --- | --- |
| ManualVersion | Manual ID, checksum, model/variant, edition, language, applicability policy, display policy, source metadata and support route binding. |
| EvidenceObject | Immutable ID and content hash, manual checksum, type, source text/asset reference, PDF page and printed label, section, bbox, extraction/review scope. |
| EvidenceDependency | Source and required target IDs, relationship type, provenance and exact approved context binding. |
| SearchChunk | Chunk ID, index ID, evidence membership/hashes, parent IDs, index text, token count and applicability tags. |
| IndexManifest | Source/parser/chunk/model revisions, Qdrant collection, BM25 artifact, object generations/hashes, counts and QA status. |
| Session | Owner, selected manual/variant, expiry, monotonic version, relevant topic and typed facts/outcomes separate from chat text. |
| OutcomeRecord | Stable referenced check/action, outcome enum, user turn, timestamp and optional superseded record. |
| EvidenceBundle | Question/history identity, source/index identity, admitted evidence and hashes, mandatory/attached/missing context, source gaps, applicability, conflicts and provenance. |
| RetrievalDecision | Policy/config, rank signals, recovery/rerank attempts, fetched/missing IDs, skip reason, stage durations and final route. |
| Draft | Final proposed text, complete claim-to-evidence map, server citations, included limitations/conditions/warnings and response hash. |
| VerificationVerdict | Strict decision, question coverage, per-claim support, omissions/conflicts, limitation/clarification flags, correction possibility and exact binding hash. |
| DeliveryOperation | Owner/session version, idempotency/payload hash, state/lease/deadline, accepted buffer and response/evidence/runtime bindings, completion/error and expiry. |
| ProviderReservation | Allocation/window, complete-request token estimate, conservative maximum cost, committed usage and retained uncertain-call state. |

Bind an answer verdict to the exact question, relevant history and typed-state projection, manual/index/source context, response and claim map, runtime, prompt and model policy. Reject missing, changed, extra or mismatched fields. Evidence IDs alone are insufficient without their content/version bindings.

## 4. Request sequence

1. Authenticate the visitor capability, validate limits and selected manual, establish session ownership, and deduplicate the operation by idempotency key plus payload hash.
2. Read relevant history and immutable outcomes. Preserve an explicit topic for short follow-ups; any query expansion remains source retrieval context and cannot invent observations.
3. Start dense and BM25 paths concurrently. The dense path computes the query vector and calls Qdrant. Both apply selected source/index/applicability filters before ranking.
4. Fuse ranks with RRF, assemble reviewed source objects and required context, and evaluate integrity/applicability/source gaps separately from ranking uncertainty.
5. Perform at most one exact-ID dependency recovery and one candidate expansion when reviewed required objects are missing. Rerank at most once only for uncertain ordering among admissible candidates; reassemble afterward.
6. Select a complete, bounded evidence representation. Prefer relevant reviewed objects plus required dependency closure instead of whole section bodies. Never silently remove a warning, unit, header, condition, relevant history or unsupported-source limitation to fit.
7. Count and reserve the complete private draft request; draft using only the evidence. There is no preliminary evidence-assessment LLM call.
8. Finalize every server-derived condition, warning, citation, support route and limitation in the complete proposed response. Construct its bindings.
9. Count/reserve and call the separate verifier against that exact response, actual question/history, claims and evidence. Its decision does not directly write to the rider stream.
10. If a valid correctable rejection can be repaired from admitted evidence, allow one correction and one new verification. Otherwise route to fixed fallback; a required operational failure routes to SYSTEM_ERROR.
11. Perform final deterministic checks and atomically persist the accepted outcome, exact response and session transition. Only then release technical content.
12. Stream exact slices of the saved response. Recovery reads the same operation and response; it does not regenerate.

## 5. Retrieval scheduling and evidence assembly

Normal mode is conditional. Off and always-diagnostic modes exist only for measured ablations and cannot bypass source or answer gates.

| Setting | Current bounded starting value |
| --- | --- |
| Fused candidate pool / assembled hits | 20 / 5 |
| Recovery candidate pool | 40 |
| Cross-encoder pool / pair maximum | 20 / 100 |
| Mandatory dependency maximum | 256; overflow is SYSTEM_ERROR without truncation |
| Initial uncertainty signals | Distinct top-three parent overlap below 0.5, or relative RRF margin at most 0.05 |
| Calibration | PROVISIONAL_UNCALIBRATED until reviewed tuning and held-out evaluation |

Zero BM25 hits supply no sparse agreement signal. Sibling chunks of one section do not create false disagreement. Cross-encoder query/pair bounds must be explicit; an overlong query skips that optional inference with a reason and preserves the full query. A required component outage or malformed result is SYSTEM_ERROR, not evidence insufficiency.

The scheduling input is reviewed source-context completeness for open Q&A, not a required legacy `step_id`. Missing review is a maintainer gap; it cannot be repaired by reranking or a rider clarification. When only some requested claims have complete evidence, drafting may produce an explicitly limited partial answer supported by those objects.

Sources for accepted claims must be approved exact objects with applicable warnings, prerequisites, table headers, units and referenced context. Chunk membership containing another unapproved object must not automatically discard independently complete reviewed evidence; object selection must also prove that excluded context is unnecessary. Empty dependencies do not establish completeness unless an exact source-context review establishes that none are required.

## 6. Draft and verification contract

The currently authorized primary model is `gemma-4-26b-a4b-it`. Lock the exact configured model/provider identity in the runtime; model changes require their applicable permission and fresh evaluation.

The draft has complete response text and explicit claim mapping. PDF/user/history content is data and cannot override policy. The model may assemble and paraphrase supported facts and concise checklists; it may not infer hidden faults, undocumented repairs, causation or OEM diagnostic ordering.

Verifier ordinary decisions are exactly:

| Decision | Meaning and application route |
| --- | --- |
| RELEASE_COMPLETE | Question meaningfully answered; every technical claim supported; no missing mandatory context. Route SUPPORTED after final checks/save. |
| RELEASE_PARTIAL | Useful supported subset; finalized text clearly states the unanswered portion. Route SUPPORTED with recorded partial coverage after final checks/save. |
| SHOW_FALLBACK | Proposed answer irrelevant, lacks support or correction unsuccessful. Discard it; route UNSUPPORTED with the fixed application wording. |

Special decisions `RELEASE_CLARIFICATION` and `RELEASE_SAFETY_STOP` preserve AMBIGUOUS and SAFETY_STOP. A clarification must be necessary and rider-resolvable. An established applicable verified safety warning has precedence; it cannot authorize unrelated advice.

Strict verifier fields include `binding_sha256`, `decision`, `question_coverage`, `per_claim_support`, `omissions`, `conflicts`, `coverage_limitation_clear`, `clarification_is_rider_resolvable`, `release_eligible` and `correction_possible`. Every claim requires supported evidence membership and source meaning, including numeric values, units, variants and safety conditions. Confidence is not an acceptance field. Unknown decisions, extra fields, invalid types, missing claims and binding mismatch fail closed.

Malformed output, timeout, outage, quota exhaustion and integrity failure are SYSTEM_ERROR. Valid semantic rejection can lead to one correction; operational failure cannot masquerade as a source limitation. Fixed neutral messages are specified in the PRD and do not depend on model success. Record fallback reason `IRRELEVANT_ANSWER`, `MISSING_SUPPORT` or `CORRECTION_UNSUCCESSFUL`; retain specific operational reason codes internally.

## 7. Claude fallback and caching

Optional `claude-haiku-5-5` is a backend-only availability fallback and remains disabled by default until activation is authorized. It receives retrieved applicable evidence and relevant history, never the full manual. Eligible primary failures are explicit 500/502/503/504 or unconfigured primary. Schema/malformed output, quota exhaustion, ambiguous timeout/schema errors, semantic rejection and source/applicability/integrity failures cannot select it.

Count the complete Claude request with its configured model adapter; validate model, content, stop reason, usage and strict JSON. Reserve the conservative maximum tokens and monetary cost before transmission. One Claude transport attempt per call; no automatic Claude retry. Retain uncertain reservations. Missing primary credentials must not prevent a fallback-eligible request from reaching correct fallback counting and transport.

Current input/output/request limits are 8,192 input tokens, 1,800 output tokens and 65,536 provider-request bytes. Exceeding a required bound is SYSTEM_ERROR, never silent source truncation. A persistent ledger must enforce the authorized non-recurring allocation across runs; a process restart or new validation run cannot reset it.

Provider prompt caching is an optimization only when supported by the exact authorized model/account/API. The current Gemma configuration has no demonstrated support; claim no cached-token savings. Never pad prompts or change models silently to enable it. Old exact-response caches and semantic answer reuse stay disabled for this pipeline; neither bypasses the separate verification step.

## 8. Session and operation integrity

Outcome enum: `NOT_TRIED`, `OBSERVED_NORMAL`, `OBSERVED_ABNORMAL`, `ACTION_COMPLETED_UNRESOLVED`, `NOT_APPLICABLE`, `UNCLEAR`, `RESOLVED`. Store evidence-linked attempts/facts separately from conversational text. Corrections supersede records; they do not rewrite history. An unresolved attempt never implies a normal observation, and reported success never establishes a verified repair.

Use transactional compare-and-set for session version, operation ownership/deduplication, reservations and final commit. A completed operation returns its saved outcome. Conflicting duplicate payloads reject. A provider call with an uncertain result is not silently retried; reconcile its reservation and operation explicitly.

Do not rely on a daemon thread surviving after an SSE request ends. The target is durable Cloud Tasks dispatch to an authenticated worker, with a Firestore operation lease and browser SSE reading progress/accepted buffers. Its build, deployment and cost remain subject to existing permission. Deduplicate task delivery before a provider call; an uncertain provider result cannot be retried merely because a task is redelivered. Set operation deadline and terminal failure handling; stale RUNNING leases must reconcile. Exceptions and session conflicts must not leave an operation indefinitely running.

Progress events name actual stages: retrieval, drafting, checking and displaying the verified answer. Technical chunks begin only after durable commit. Bind events to operation, response hash and sequence. Fixed fallback/error events carry no technical-answer chunks or verified-answer label.

## 9. Admission, privacy and DevOps

Admission budgets the entire permitted turn, including separate draft/verify and optional correction/re-verification, against real provider windows. A legacy 10,000-token-per-minute ceiling cannot be treated as sufficient for two requests whose combined reservations exceed it. Implement bounded queue/pacing or reject before starting work; do not accept a turn and predictably strand its verifier. Limits remain within current provider and spending permissions.

Preserve the recorded text/visitor/session controls: 2,000-character/8,000-byte user text; six accepted turns/minute, 30/rolling day and 20/conversation; 30-minute idle and 24-hour session retention unless a separately approved policy changes them. Count complete model requests independently from user-text limits. Owner-bound sessions, expiry/deletion, global reservations, rate counters and fail-closed managed-store behavior require hosted tests. New conversations do not reset visitor budgets.

Keep model credentials in managed secrets, use least-privilege service identities and authenticated Qdrant/backend access, and redact routine traces. No raw user media, credential content or private model drafts in repository or routine telemetry. Photo/voice remain disabled until their scoped privacy and source-grounding acceptance is complete.

CI must run provider-free contract tests on every pull request and main change. Builds use a pinned source commit, explicit runtime inputs, dependency locks and image digest. Promotion verifies the exact source/runtime/index/approval identities and service kind; an arbitrary successful build's first image is not a valid release artifact. Real provider validation is separately budgeted and never part of routine unguarded CI.

Publish durable versioned index artifacts and deployment receipts. Readiness must prove required artifacts/models/index and serving dependencies are loaded; configured point counts alone are not process health. Record compatible UI/backend revisions, managed-secret references, live private-browser stream/recovery tests, cold start, rollback and cost receipts before public opening.

Use the latest recorded budget/configuration in [deployment_status.json](../cloud/deployment_status.json), not the superseded initial INR800 allocation. It records owner-authorized additions giving a non-recurring INR2,700 lifetime budget, alerts at INR1,350/2,160/2,700 and the INR2,540 billing-disconnect guard. The existing private Qdrant configuration records one minimum instance and startup CPU boost; these are already recorded changes, not new reset actions. Delayed reporting prevents an instantaneous exact cap. Never restart stopped billing or change service settings without applicable authorization; no new deployment or budget change is implied here.

## 10. Validation and implementation gaps

Use source-checked tuning/regression and held-out cases with exact source/checksum/runtime bindings. Held-out answers are never prompt/index enrichment. Evaluate complete and partial questions, specifications, tables, warnings, unsupported repairs, short follow-ups, injection, wrong variant, source gaps, provider failures, quota/store failures, correction and disconnect/replay. Review real outputs against original pages independently of serving generator and verifier.

Measure complete evidence recall, answerable coverage, proper abstention, citation and claim support, false verifier acceptance/refusal, recovery/rerank rescues/regressions, contextual follow-up correctness, unjustified repeats, all stage latency, first verified answer, cold start and cost per correctly handled case. Synthetic tests, historical retrieval diagnostics and real provider measurements must have separate labels.

The implementation sequence in TODO must close these observed departures before claiming this contract complete:

1. Replace serving NumPy dense similarity with real authenticated Qdrant requests while retaining concurrent BM25.
2. Make conditional recovery/reranking consume open-Q&A reviewed source context rather than mandatory step manifests.
3. Pack relevant complete reviewed objects/dependencies within existing token bounds; repair partial-support admission and short-follow-up topic retention.
4. Admit and pace a whole draft/verify turn; enforce persistent provider allocations and correct fallback count configuration.
5. Prove terminal durable operations and exact stream/recovery equality on Cloud Run/Firestore, including disconnect and worker failure.
6. Replace expiring deployment inputs and weak image selection with immutable durable artifact promotion and provider-free CI.

The preserved v8 software checks passed, but its real-provider run released zero technical answers and covered 0 of 4 clearly answerable/partially answerable turns. It is a failed coverage baseline, not release acceptance. Preserve exact approval packages, runtime receipts and failed-run adjudications needed for reproducibility. Cleanup removes obsolete active designs and duplicate generated outputs without discarding the evidence governing this contract.
