# MotoMedic technical requirements

Version 1.1 · 12 October 2026 · Selected v10 public evaluator; hosted acceptance pending.

This is the single current technical specification paired with [PRD.md](PRD.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [TODO.md](../TODO.md). The selected v10 contract covers the owner's public evaluator request: open-manual drafting and verification by distinct models, Haiku policy/evidence-prefix caching, conditional dense/BM25 rank-disagreement reranking, saved streaming and follow-ups. The latest instruction adds a 100-word rider limit and selects Gemma draft/Haiku verify for smaller complete requests, Haiku draft/Gemma verify for larger ones, using native model windows instead of the former assembled-prompt cap. These new v10.7 bindings are in progress. [Operational scope](../reports/public_evaluator/20261012/owner_scope_v1.json) and [credential approval](../reports/public_evaluator/20261012/owner_credential_scope_v1.json) preserve the earlier exact operational authority separately from live acceptance. Exact source approvals retain their original scope and bytes; earlier exact-answer/StepDefinition gates and omitted-semantic-verifier designs are superseded.

## 1. Selected architecture and boundaries

| Component | Contract |
| --- | --- |
| Hosted ingestion job | Versioned Docling parsing and parent/child chunking once per source/parser/chunk/model version. |
| Evidence artifacts | Immutable source objects, page registry, reviewed relationships and manifest in private object storage. |
| Dense retrieval | Query embedding with pinned BGE M3; authenticated Qdrant query against the selected immutable collection. |
| Sparse retrieval | BM25 postings from the same snapshot; run concurrently with the dense path. |
| Retrieval orchestrator | RRF, selective reviewed context assembly, one bounded recovery and one cross-encoder rerank only for observed distinct-parent rank disagreement. |
| Private composer | Complete draft requests at or below 8,192 native-counted tokens select pinned Gemma `gemma-4-26b-a4b-it`; larger requests select pinned Haiku `claude-haiku-5-5`, using question, relevant history, typed outcomes and applicable evidence. The threshold routes; it does not reject evidence. |
| Separate verifier | The other pinned model verifies the exact finalized response: Haiku for a Gemma draft, Gemma for a Haiku draft. Bind both contracts and selected roles through admission, verdict and delivery. |
| Haiku prefix cache | Explicit five-minute policy and exact source-evidence breakpoints for the selected Haiku role; question/history/final response stay in the dynamic uncached block. |
| Application gate | Validate bindings, schemas, applicability, citation membership, warnings and delivery integrity; cannot replace semantic verification. |
| Durable state | Firestore sessions, facts/outcomes, operation leases, reservations and accepted response transaction. |
| Work dispatch | Named Cloud Tasks to a dedicated private Cloud Run worker, separate from the browser API/SSE service; leases and deadline fencing survive disconnects. Code is implemented; hosted acceptance is pending. |
| Public frontend | Direct Cloud Run gateway with signed 24-hour cookie, 14-bit proof challenge and private persistent visitor issuance. No forwarded/client IP is trusted. |
| Delivery | UI service-account IAM access to private API/SSE; owner-bound progress and exact saved-buffer streaming with idempotent recovery. |
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

1. Authenticate the visitor capability, reject rider questions over 100 words without truncation, validate the other applicable transport limits and selected manual, establish session ownership, and deduplicate the operation by idempotency key plus payload hash.
2. Read relevant history and immutable outcomes. Preserve an explicit topic for short follow-ups; any query expansion remains source retrieval context and cannot invent observations.
3. Start dense and BM25 paths concurrently. The dense path computes the query vector and calls Qdrant. Both apply selected source/index/applicability filters before ranking.
4. Fuse ranks with RRF, assemble reviewed source objects and required context, and evaluate integrity/applicability/source gaps separately from ranking uncertainty.
5. Perform at most one exact-ID dependency recovery and one candidate expansion when reviewed required objects are missing. Rerank at most once only for uncertain ordering among admissible candidates; reassemble afterward.
6. Select final-ranked reviewed anchors and their applicable dependency closure instead of unapproved whole section bodies. Preserve validated source-gap obligations without making every pre-rerank candidate mandatory. Evidence may be large; never silently remove a warning, unit, header, condition, relevant history or unsupported-source limitation to fit a former per-call cap.
7. Native-count complete requests and select the pinned draft/other-model verifier pair before generation. Check real windows and reserve the initial draft/verification phase under unchanged lifetime token/attempt and monetary guards: at most three attempts across the two roles. Draft using only applicable evidence. There is no preliminary evidence-assessment LLM call.
8. Finalize every server-derived condition, warning, citation, support route and limitation in the complete proposed response. Construct its bindings.
9. Count/reserve and call the separate verifier against that exact response, actual question/history, claims and evidence. Its decision does not directly write to the rider stream.
10. If a valid correctable rejection can be repaired from admitted evidence, native-count and reserve the separate conditional correction/re-verification phase before transmission: at most three further attempts. Allow one correction and one new verification. Unneeded correction capacity is never reserved or refunded. Otherwise route to fixed fallback; a required operational/admission failure routes to SYSTEM_ERROR.
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
| Conditional gate | Compare observed ordered top-three distinct parent IDs from dense and BM25; rerank only when an available comparable rank position differs |
| Frozen v10.6 runtime / gate | `authenticated-open-hybrid-rank-disagreement-v4` / `ordered-distinct-parent-rank-disagreement-v3` |
| New v10.7 retrieval / authority | `authenticated-open-hybrid-rank-disagreement-v5` / `open-reviewed-anchor-authority-v4`; code/tests/freeze pending |
| Calibration | PROVISIONAL_UNCALIBRATED until reviewed tuning and held-out evaluation |

Zero hits from either backend supply no comparable rank signal. Collapse sibling chunks before comparing parent order; unmatched trailing depth creates no disagreement. RRF margin and set overlap are diagnostics, not triggers. Cross-encoder query/pair bounds must be explicit; an overlong query skips that optional inference with a reason and preserves the full query. A required component outage or malformed result is SYSTEM_ERROR, not evidence insufficiency.

The scheduling input is reviewed source-context completeness for open Q&A, not a required legacy `step_id`. Missing review is a maintainer gap; it cannot be repaired by reranking or a rider clarification. When only some requested claims have complete evidence, drafting may produce an explicitly limited partial answer supported by those objects.

Sources for accepted claims must be approved exact objects with applicable warnings, prerequisites, table headers, units and referenced context. Chunk membership containing another unapproved object must not automatically discard independently complete reviewed evidence; object selection must also prove that excluded context is unnecessary. Empty dependencies do not establish completeness unless an exact source-context review establishes that none are required.

## 6. Draft and verification contract

Frozen v10.6 runtime `open-manual-draft-verify-v10` selects Google Gemma `gemma-4-26b-a4b-it` for drafts and Anthropic Claude `claude-haiku-5-5` for verification. The [latest owner model scope](../reports/public_evaluator/20261012/owner_model_scope_v1.json) authorizes v10.7 size selection: complete draft requests at or below 8,192 native-counted tokens retain that pair; larger requests use Haiku drafting and Gemma verification. Count the complete assembled request and bind the route before generation. Published context windows are 256,000 for Gemma and 1,000,000 for Haiku in that scoped receipt; native model-metadata readback and account counting remain pending. Do not use the routing threshold as an assembled-prompt rejection cap. Bind both exact contracts, selected roles and selection identity to config, verdict, durable admission and delivery; reject same-model verification, model mismatch or changed contracts. This is deterministic size selection, not activation of availability fallback. V9 production replay is rejected. Fresh exact-role evaluation is required.

The [read-only quota summary](../reports/public_evaluator/20261012/provider_quota_summary_v1.json) records the same normal Gemma26B input allowance on both existing projects: 16,000 tokens/minute, 30 requests/minute and 14,400 requests/day. The provider API key's project association is not established by that readback. Context window and account throughput are different constraints: a large Haiku draft still needs a complete Gemma verification request that fits the actual account's rate window. Count that request and admit its real pacing/token budget before spending; never truncate evidence or call the quota a smaller native context window. Quota or remaining-allocation failure is SYSTEM_ERROR, not missing manual support. No quota, billing or allocation was increased.

The new hosted count-only preflight measures the full initial Gemma request to select the route, then the selected Haiku draft request when applicable. It separately measures the unavoidable full-source/actual-history BASE verifier prefix and labeled maximum warning/claim stress against native windows, with Gemma 16K throughput recorded separately. Synthetic stress is not a real prospective answer and cannot prove that the unknown finalized Gemma request fits. The synthetic maximum-claim minimal-verdict output count is also a diagnostic: exceeding1,800tokens cannot establish that an unknown actual verdict is impossible. Actual finalization attaches warnings from `authority.select` for the draft's cited evidence. A preflight pass must state these limits; production still native-counts/gates the exact finalized verifier before generation and requires complete actual claim coverage, output bounds and strict schema before release. Preflight makes no generation/reservation and retains equal ledgers. Metadata GETs must be exact allowlisted endpoints with keys confined to hosted secrets; advertised windows may exceed the pinned conservative256K/1M bounds.

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

## 7. Haiku prefix caching and retained disabled fallback

Frozen v10.6's Haiku verifier uses its native strict JSON output schema, disabled thinking and medium effort. The new selected Haiku role must use the separately bound draft or verifier schema/policy. Two explicit five-minute cache breakpoints cover that role's actual policy and exact source-evidence prefix; raw question/history, finalized answer and per-call binding stay outside the prefix. No padding, unrelated evidence or whole-manual payload is permitted. A configured breakpoint is not a demonstrated cache hit: exact-role hosted usage must record cache creation and positive reads for the same prefix. The historical verifier probe proves only its bound role/schema. Paired latency/cost measurements are required before claiming savings. V10.6's lossless serialization retained source authority but failed its old prompt limits; new size routing changes those serving limits without changing source/index content. Paid-call attempt/usage traces must survive exceptions and uncertainty. [Provider contract and probe receipt](../reports/public_evaluator/20261012/providers/README.md).

Count the complete request before transmission. Usage must report nonnegative integer fresh-input, cache-creation and cache-read totals; their sum stays within the selected model's pinned native window. Five-minute cache-duration detail must match the pinned TTL. Conservatively reserve each selected Haiku request's all-input cache-write and bounded-output maximum under the unchanged persistent USD1 guard before generation. The former USD0.001924-per-verifier reservation was specific to the historical 8,192-input limit and cannot authorize a larger request. Cache writes happen within generation and do not create new allocation or admission slots. Retain unused/uncertain reservations; no automatic verifier retry. Verification still checks each exact response and cannot reuse a prior verdict or cached answer.

The separate retained `claude-haiku-5-5` availability fallback remains disabled in this paired evaluator. Verifier selection does not activate it. Its existing contract receives retrieved applicable evidence and relevant history, never the full manual; activation still needs its own authority. Eligible primary failures are explicit 500/502/503/504 or unconfigured primary. Schema/malformed output, quota exhaustion, ambiguous timeout/schema errors, semantic rejection and source/applicability/integrity failures cannot select it.

Count the complete Claude request with its configured model adapter; validate model, content, stop reason, usage and strict JSON. Reserve the conservative maximum tokens and monetary cost before transmission. One Claude transport attempt per call; no automatic Claude retry. Retain uncertain reservations. Missing primary credentials must not prevent a fallback-eligible request from reaching correct fallback counting and transport.

Frozen v10.6 limited requests to 8,192 input tokens, 1,800 output tokens and 65,536 serialized bytes; its failed receipts preserve those exact gates. The latest owner instruction removes that assembled-evidence token/byte cap for the new candidate. Pin and enforce the selected providers' documented native windows and applicable transport limits, the bounded output policy, and the existing total token/attempt/monetary allocation. Requests that cannot fit the selected real window or remaining budget fail as SYSTEM_ERROR before generation; never silently truncate required source context. A process restart or new validation run cannot reset the persistent allocation.

Gemma drafting retains no demonstrated prompt-cache support and claims no savings. The [hosted Haiku capability probe](../reports/public_evaluator/20261012/cache_probe_capability_v2.json) proves 6,113 policy/evidence cache-write then cache-read tokens for the bound verifier/schema; it establishes neither answer quality nor paired latency/cost savings. Exact-response caches and semantic answer reuse stay disabled for both roles; neither bypasses fresh verification.

## 8. Session and operation integrity

Outcome enum: `NOT_TRIED`, `OBSERVED_NORMAL`, `OBSERVED_ABNORMAL`, `ACTION_COMPLETED_UNRESOLVED`, `NOT_APPLICABLE`, `UNCLEAR`, `RESOLVED`. Store evidence-linked attempts/facts separately from conversational text. Corrections supersede records; they do not rewrite history. An unresolved attempt never implies a normal observation, and reported success never establishes a verified repair.

Use transactional compare-and-set for session version, operation ownership/deduplication, reservations and final commit. A completed operation returns its saved outcome. Conflicting duplicate payloads reject. A provider call with an uncertain result is not silently retried; reconcile its reservation and operation explicitly.

Cloud Tasks dispatches to a dedicated IAM-protected worker with an exact OIDC audience and private task-caller identity. The worker is separate from the browser API service so long SSE connections cannot consume all generation request capacity. Firestore owns operation leases, fencing and the 1,200-second deadline; browser SSE only observes progress/accepted buffers and may recover after its shorter observation window. Deduplicate task delivery before a provider call; an uncertain provider result cannot be retried because a task is redelivered. Stale RUNNING leases, exceptions and session conflicts must reconcile terminally. Software behavior is implemented; deployed disconnect/worker acceptance remains pending.

Progress events name actual stages: retrieval, drafting, checking and displaying the verified answer. Technical chunks begin only after durable commit. Bind events to operation, response hash and sequence. Fixed fallback/error events carry no technical-answer chunks or verified-answer label.

## 9. Admission, privacy and DevOps

Admission reserves each draft/verification pair against real provider windows before beginning that phase. The initial phase uses three attempts; one separate conditional correction phase uses three only after a valid correctable rejection and fresh admission. Each actual request must fit its phase forecast, native window and real pacing. A legacy flat 9,992-token slot cannot size a larger selected request, and a throughput ceiling is not a native context window. Fail before starting a phase that cannot fund its verifier. Limits remain within current provider and spending permissions; no new allocation, refund or reset is introduced.

The engineering six-case client uses the exact count receipt's measured initial/correction phase forecasts rather than six flat eight-slot turns. Before each question it rereads permanent ledgers and requires remaining planned initial phases, that question's conditional correction envelope and three maximum measured initial-phase envelopes to fit attempt/token/USD1 guards. Those three envelopes retain capacity for one planned public direct turn and two human turns. Bind count/source/manifest/role-plan/native-count/cost identities and retained baseline charges. Insufficient capacity stops before provider work. This is a measured engineering envelope, not a promise that arbitrary future questions or unknown finalized verification bodies fit; production native counting and admission remain authoritative.

The unchanged 100-slot lifetime allocation allowed at most 12 conservative eight-slot turns from a fresh ledger under the original request sizes, shared with hosted validation. Allocation version, 100 attempts and 999,200 reserved-token ceiling remain permanent; larger selected requests can exhaust the token or USD1 guard earlier. There is no restart/new conversation/day refund or reset. Pacing policy `whole-turn-sealed-unused-pacing-v2` atomically seals only the ending turn's own never-consumed future slots; all events, attempt counts and token charges remain retained. Consumed/uncertain slots stay active, and sealing failure gives no release. The new selected-role requests must fit real provider pacing before starting. Gemma retains its existing free configuration and unsupported caching; paid Haiku uses the unchanged persistent USD1 guard. Public issuance/request quotas are ceilings, not a promise of that many affordable model turns.

Preserve the recorded text/visitor/session controls: 2,000-character/8,000-byte user text; six accepted turns/minute, 30/rolling day and 20/conversation; 30-minute idle and 24-hour session retention unless a separately approved policy changes them. Count complete model requests independently from user-text limits. Owner-bound sessions, expiry/deletion, global reservations, rate counters and fail-closed managed-store behavior require hosted tests. New conversations do not reset visitor budgets.

Enforce the owner's latest 100-word rider-question maximum in UI and API with the same versioned word-count rule. Accept exactly 100 words, reject 101 before retrieval/provider reservation, and preserve submitted text without silent truncation. This is a length limit, not an authored-question restriction. Full policy/schema, relevant history and applicable source evidence are counted separately; retrieval chunks and evidence may be large.

Keep model credentials in managed secrets, use least-privilege service identities and authenticated Qdrant/backend access, and redact routine traces. No raw user media, credential content or private model drafts in repository or routine telemetry. Photo/voice remain disabled until their scoped privacy and source-grounding acceptance is complete.

Only the direct Cloud Run frontend is public. Its gateway validates the configured host, signs secure HttpOnly SameSite cookies, and checks a 14-bit proof challenge expiring in 120 seconds. Before issuing a 24-hour visitor cookie it calls private `/internal/visitors/reserve` using its service-account identity. The private backend atomically rejects spent proofs and caps issuance at ten/minute and 60/rolling day. Task callers and other IAM callers cannot issue visitors. Browser headers and forwarded IPs grant no identity or quota authority. A cookie identifies the visitor across refresh/new conversations; a replacement creates a new subject but cannot reset persistent global issuance/request or provider budgets. Proof difficulty establishes neither human identity nor a DDoS guarantee.

CI must run provider-free contract tests on every pull request and main change. Builds use a pinned source commit, explicit runtime inputs, dependency locks and image digest. Promotion verifies the exact source/runtime/index/approval identities and service kind; an arbitrary successful build's first image is not a valid release artifact. Real provider validation is separately budgeted and never part of routine unguarded CI.

Publish durable versioned index artifacts and deployment receipts. Readiness must prove required artifacts/models/index and serving dependencies are loaded; configured point counts alone are not process health. Hosted packaging must create/chown only the serving-artifact cache and verify writability as the actual container user. Build provenance can verify exact source/input/archive/image bindings without claiming release acceptance. Promotion additionally requires compatible UI/backend/worker revisions, rollback and live acceptance. Record managed-secret version references, positive caching, public-browser direct/follow-up stream/recovery checks, cold start and costs before closing the evaluator goal.

Use authenticated `/v1/health` for external API readiness and `/health` for the public gateway's sanitized Streamlit readiness. Keep `/healthz` only for internal probes; Cloud Run reserves the external path. The preserved v10.3 evaluator preflight returned frontend HTTP404 before any question or provider call. V10.4 repaired routes and passed private shell, but all six actual evaluator cases returned SYSTEM_ERROR. [V10.6 private readiness](../reports/public_evaluator/20261012/private_readiness_v10_6.json) passed for API, worker and UI with zero provider calls; its native-count failure still blocks paid quality/public opening. V10.7 requires a new immutable freeze/build and selected-role count/quality acceptance.

Use the latest recorded budget/configuration in [deployment_status.json](../cloud/deployment_status.json), not the superseded initial INR800 allocation. Preserve the non-recurring INR2,700 lifetime budget, alerts at INR1,350/2,160/2,700 and INR2,540 billing-disconnect guard. Main-project billing remains enabled; inference-project billing remains disabled. The exact public-evaluator scope authorizes necessary hosted deployment/validation and the separate credential receipt authorizes managed secret transfer/identity wiring. Neither restarts stopped billing, increases the allocation, activates fallback or changes source display. Existing private Qdrant minimum-instance/startup settings are recorded history. Delayed reporting prevents an instantaneous exact cap.

## 10. Validation and implementation gaps

Use source-checked tuning/regression and held-out cases with exact source/checksum/runtime bindings. Held-out answers are never prompt/index enrichment. Evaluate complete and partial questions, specifications, tables, warnings, unsupported repairs, short follow-ups, injection, wrong variant, source gaps, provider failures, quota/store failures, correction and disconnect/replay. Review real outputs against original pages independently of serving generator and verifier.

Measure complete evidence recall, answerable coverage, proper abstention, citation and claim support, false verifier acceptance/refusal, recovery/rerank rescues/regressions, contextual follow-up correctness, unjustified repeats, all stage latency, first verified answer, cold start and cost per correctly handled case. Synthetic tests, historical retrieval diagnostics and real provider measurements must have separate labels.

The v10 software implements the following repairs; TODO keeps their hosted acceptance exits open:

1. Authenticated Qdrant requests with concurrent BM25 and the unchanged immutable index; live RPC/source identity still needs proof.
2. Open-Q&A reviewed source context and distinct-parent rank-disagreement reranking without mandatory authored steps. Candidate retrievalv4 preserves reviewed dependencies and validated immutable gap obligations; gaps cannot suppress real ordered-rank disagreement when reviewed anchors exist or invent a trigger from missing ranks. Live direct/follow-up recall remains unaccepted.
3. Frozen v10.6 lossless reviewed objects/dependencies and follow-up topic projection; useful partial answers remain unaccepted. Approved v10.7 final-rank selection, gap-only retention, honest recovery and deictic history repairs are in progress. A separate semantic projection proposal remains unimplemented; necessary evidence may be large.
4. Persistent whole-turn pacing and spend reservations, different Gemma/Haiku roles and demonstrated hosted evidence-prefix cache reads; current hosted account limits and answer quality remain unaccepted.
5. Dedicated-worker durable operations and exact saved stream/recovery bindings; deployed disconnect, IAM and worker failure tests remain open.
6. Immutable artifacts, provider-free CI, locked dependencies and strict provenance; v10.6 freeze/CI/images/private readiness succeeded, but native-count preflight failed without generation/reservations. Paid v10.6 Q&A was not submitted. New v10.7 rider-limit/size-routing and retrieval/history repairs need final tests, freeze, builds and native counts; useful-answer quality, compatible rollback and public acceptance remain pending.

The preserved v8 software checks passed, but its real-provider run released zero technical answers and covered 0 of 4 clearly answerable/partially answerable turns. It is a failed coverage baseline, not release acceptance. Preserve exact approval packages, runtime receipts and failed-run adjudications needed for reproducibility. Cleanup removes obsolete active designs and duplicate generated outputs without discarding the evidence governing this contract.
