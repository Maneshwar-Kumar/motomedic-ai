# MotoMedic technical requirements

**Current work: complete the frozen Haiku-only functional demonstration.** Public answering is enabled and anonymous API/worker/Qdrant inspection passed. Hosted v10.13 CI/builds and native retrieval counts passed; one direct answer and its saved delivery are proven; USB returned SYSTEM_ERROR and broader checks remain open. The [latest owner instruction](../reports/public_evaluator/20261012/public_review/owner_functional_acceptance_scope_v1.json) waives independent manual answer review for this demo, while retaining exact immutable source admission and separate finalized-response verification.

Version 1.7 · 12 October 2026 · Owner-selected fixed manual and presentation of recorded stage durations.

This is the current technical specification paired with [PRD](PRD.md), [architecture](ARCHITECTURE.md) and [TODO](../TODO.md). The [latest owner scope](../reports/public_evaluator/20261012/owner_model_scope_v3.json) selects Claude `claude-haiku-5-5` only. Use separate draft and finalized-response verifier calls, distinct role policies/schemas, role-specific prefix caching, complete evidence/history, authenticated hybrid retrieval, conditional reranking and exact durable delivery. Different-model identity is superseded. Independent manual answer adjudication is waived for the present functional demo; immutable source/content approvals and deterministic/runtime-semantic checks remain. V10.13 is frozen, built and deployed with public answering enabled after the owner's later instruction; the complete functional suite is not accepted. See [status](STATUS.md) for exact receipts.

Public answering is enabled by the [later direct owner instruction](../reports/public_evaluator/20261012/public_review/owner_public_answer_enablement_scope_v1.json), before full six-case acceptance. [Routed UI health](../reports/public_evaluator/20261012/haiku_v10_13_helpers/functional_ui_promotion_v2/enabled_health.json) passed for `motomedic-rider-ui-v10-13-functional-enabled`. The [anonymous browser](../reports/public_evaluator/20261012/public_review/browser_enabled_v1/receipt.json) observed a 97-character SUPPORTED answer in 71.06 seconds with enabled input and all four progress stages; it did not capture incremental chunk rendering or session/operation identity. The separate [private direct audit](../reports/public_evaluator/20261012/haiku_v10_13_runtime/direct_delivery_a77d_v1.json) proves exact-finalized verification and identical saved/stream/recovery. USB returned `PROVIDER_INCOMPLETE_OR_REFUSED` without a retained exact stop reason, four cases remain unrun and positive cache reads are unproven. Broader functional acceptance and merge remain pending; independent manual answer review was waived.

## 1. Selected architecture and boundaries

| Component | Contract |
| --- | --- |
| Hosted ingestion job | Versioned Docling parsing and parent/child chunking once per source/parser/chunk/model version. |
| Evidence artifacts | Immutable source objects, page registry, reviewed relationships and manifest; original hosted GCS generation/hash stays pinned, while the exact supplied manual/index archive is public under separate publication permission. |
| Dense retrieval | Query embedding with pinned BGE M3; source/index-bound Qdrant query against the selected immutable collection; read-only wrapper inspection is public under the latest owner scope. |
| Sparse retrieval | BM25 postings from the same snapshot; run concurrently with the dense path. |
| Retrieval orchestrator | RRF, selective reviewed context assembly, one bounded recovery and one cross-encoder rerank only for observed distinct-parent rank disagreement. |
| Private composer | Haiku `claude-haiku-5-5` privately drafts from actual question, relevant history, typed outcomes and complete applicable evidence. |
| Separate verifier | A separate Haiku call with verifier policy/schema checks the exact finalized response. Bind role/call identities through admission, verdict and delivery. |
| Haiku prefix cache | Explicit five-minute policy and exact source-evidence breakpoints for the selected Haiku role; question/history/final response stay in the dynamic uncached block. |
| Application gate | Validate bindings, schemas, applicability, citation membership, warnings and delivery integrity; cannot replace semantic verification. |
| Durable state | Firestore sessions, facts/outcomes, operation leases, reservations and accepted response transaction. |
| Work dispatch | Named Cloud Tasks to a dedicated Cloud Run worker with exact verified task-caller/audience authorization, separate from API/SSE capacity; public health does not authorize jobs. Leases/deadline fencing survive disconnects; broader live functional proof remains pending. |
| Public frontend | Direct Cloud Run gateway with signed 24-hour cookie, 14-bit proof challenge and private persistent visitor issuance. No forwarded/client IP is trusted. |
| Delivery | Verified UI service-account signature/audience/email access plus owned visitor capability to API/SSE; public health does not expose owner-private state. Exact saved-buffer streaming and idempotent recovery remain bound. |
| Operations | Immutable build images, managed secrets/identity, durable artifacts, admission/spend limits and redacted traces. |

Qdrant stores/searches dense vectors; it does not authorize answers. BM25 does not prove claim support. The verifier is probabilistic. The owner waived independent manual answer evaluation for this functional demo, so no independent factual acceptance is claimed. Immutable source/content approval and deterministic application checks remain separate mandatory controls.

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

The original deployment stores durable snapshots in private Cloud Storage under immutable versioned object references. The owner separately approved public release of the exact existing [index snapshot](../reports/public_evaluator/20261012/public_review/owner_index_release_scope_v1.json); its [publication readback](../reports/public_evaluator/20261012/public_review/index_release_readback_v1.json) binds bytes and digest. Public inspection/export does not mutate the original artifact generation or approval scope. Expiring GitHub Actions artifacts may contain temporary logs, but cannot be the sole index or deployment input.

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

The UI starts with the owner-selected Himalayan BS6 manual and does not require a rider confirmation checkbox. The existing transport confirmation flag affirms that fixed source selection; it does not record a visitor attestation. Exact variant, manual checksum and index checks remain in the API.

UI timing presentation reads finite, nonnegative durations from the existing saved source-admission and composition diagnostics. Retrieval/assembly includes reranking, while the reranking duration measures the conditional cross-encoder step; these values overlap and are not added into a false total. Draft/verification phase clocks include any admission or pacing waits. Measure verified answer delivery separately using a monotonic UI-server clock, retain it outside the saved view, and show unavailable measurements honestly after recovery. No timing change modifies the finalized answer, verification binding, saved buffer or SSE equality checks.

1. Authenticate the visitor capability, reject rider questions over 100 words without truncation, validate the other applicable transport limits and selected manual, establish session ownership, and deduplicate the operation by idempotency key plus payload hash.
2. Read relevant history and immutable outcomes. Preserve an explicit topic for short follow-ups; any query expansion remains source retrieval context and cannot invent observations.
3. Start dense and BM25 paths concurrently. The dense path computes the query vector and calls Qdrant. Both apply selected source/index/applicability filters before ranking.
4. Fuse ranks with RRF, assemble reviewed source objects and required context, and evaluate integrity/applicability/source gaps separately from ranking uncertainty.
5. Perform at most one exact-ID dependency recovery and one candidate expansion when reviewed required objects are missing. Rerank at most once only for uncertain ordering among admissible candidates; reassemble afterward.
6. Select final-ranked reviewed anchors and their applicable dependency closure instead of unapproved whole section bodies. Preserve validated source-gap obligations without making every pre-rerank candidate mandatory. Evidence may be large; never silently remove a warning, unit, header, condition, relevant history or unsupported-source limitation to fit a former per-call cap.
7. Native-count complete requests and bind the separate pinned Haiku draft and verifier call roles before generation. Check real windows and reserve the initial draft/verification phase under the freshly resolved authorized lifetime token ceiling and unchanged attempt/shared monetary guards: two attempt-one slots, one for each role. Draft using only applicable evidence. There is no preliminary evidence-assessment LLM call.
8. Finalize every server-derived condition, warning, citation, support route and limitation in the complete proposed response. Construct its bindings.
9. Count/reserve and call the separate verifier against that exact response, actual question/history, claims and evidence. Its decision does not directly write to the rider stream.
10. If a valid correctable rejection can be repaired from admitted evidence, native-count and reserve the separate conditional correction/re-verification phase before transmission: two further attempt-one slots, one correction and one fresh verifier. Allow one correction and one new verification. Unneeded correction capacity is never reserved or refunded. Otherwise route to fixed fallback; a required operational/admission failure routes to SYSTEM_ERROR.
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
| Current retrieval / authority | `authenticated-open-hybrid-rank-disagreement-v5` / `open-reviewed-anchor-authority-v4`; authenticated runtime retained; current acceptance pending |
| Calibration | PROVISIONAL_UNCALIBRATED until reviewed tuning and held-out evaluation |

Zero hits from either backend supply no comparable rank signal. Collapse sibling chunks before comparing parent order; unmatched trailing depth creates no disagreement. RRF margin and set overlap are diagnostics, not triggers. Cross-encoder query/pair bounds must be explicit; an overlong query skips that optional inference with a reason and preserves the full query. A required component outage or malformed result is SYSTEM_ERROR, not evidence insufficiency.

The scheduling input is reviewed source-context completeness for open Q&A, not a required legacy `step_id`. Missing review is a maintainer gap; it cannot be repaired by reranking or a rider clarification. When only some requested claims have complete evidence, drafting may produce an explicitly limited partial answer supported by those objects.

Sources for accepted claims must be approved exact objects with applicable warnings, prerequisites, table headers, units and referenced context. Chunk membership containing another unapproved object must not automatically discard independently complete reviewed evidence; object selection must also prove that excluded context is unnecessary. Empty dependencies do not establish completeness unless an exact source-context review establishes that none are required.

## 6. Draft and verification contract

The frozen v10.13 candidate uses only Haiku `claude-haiku-5-5` under [scope3](../reports/public_evaluator/20261012/owner_model_scope_v3.json). Its separate draft and verifier calls require distinct policies/schemas and exact role/request/response bindings. Preserve the pinned 1,000,000-token native window and application 1,800-token output bound, with complete native counting and bounded counter headroom. Replace different-model rejection with checks that the draft invocation cannot serve as its own verifier. Model equality is now allowed; role/call/binding equality that bypasses separate verification is not. No provider-switch fallback is enabled.

The preserved [Gemma quota summary](../reports/public_evaluator/20261012/provider_quota_summary_v1.json) concerns the retired Google route: 16K input TPM was separate from its native window. Google 2.5 access probes are retained failure evidence and need no further work after the Haiku-only steer. For Haiku, independently enforce complete native context, actual provider quota, pacing and remaining shared monetary/token allocation. Quota or budget failure remains SYSTEM_ERROR.

The hosted count-only preflight measures complete fixed-pair draft and verifier requests from actual retrieval, including relevant history. Labeled synthetic stress is diagnostic, not a factual answer or proof that an unknown final response fits. Production native-counts the actual finalized verifier request before generation and requires strict output schema, every-claim coverage and binding equality before release. Count preflight performs no generation or reservation and verifies unchanged ledgers. Model metadata uses exact allowlisted endpoints and hosted secrets.

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

Haiku verification uses native strict JSON, disabled thinking and medium effort. Two five-minute cache breakpoints cover the actual verifier policy and exact source-evidence prefix; question, history, finalized answer and binding remain dynamic. No padding or whole-manual payload is permitted. Hosted usage must demonstrate cache creation followed by positive reads for this exact role. Historical capability evidence proves its own bound role only; paired savings remain unmeasured. Exceptions must retain attempt and usage traces. [Provider contract and probe receipt](../reports/public_evaluator/20261012/providers/README.md).

Count the complete request before transmission. Usage must report nonnegative integer fresh-input, cache-creation and cache-read totals; their sum stays within the selected model's pinned native window. Five-minute cache-duration detail must match the pinned TTL. Conservatively reserve each selected Haiku request's all-input cache-write and bounded-output maximum under the unchanged persistent USD1 guard before generation. The former USD0.001924-per-verifier reservation was specific to the historical 8,192-input limit and cannot authorize a larger request. Cache writes happen within generation and do not create new allocation or admission slots. Retain unused/uncertain reservations; no automatic verifier retry. Verification still checks each exact response and cannot reuse a prior verdict or cached answer.

The separate retained `claude-haiku-5-5` availability fallback remains disabled in this paired evaluator. Verifier selection does not activate it. Its existing contract receives retrieved applicable evidence and relevant history, never the full manual; activation still needs its own authority. Eligible primary failures are explicit 500/502/503/504 or unconfigured primary. Schema/malformed output, quota exhaustion, ambiguous timeout/schema errors, semantic rejection and source/applicability/integrity failures cannot select it.

Count the complete Claude request with its configured model adapter; validate model, content, stop reason, usage and strict JSON. Reserve the conservative maximum tokens and monetary cost before transmission. One Claude transport attempt per call; no automatic Claude retry. Retain uncertain reservations. The preceding availability contract is retained historical compatibility only. This serving candidate never selects that fallback or continues Google model access work; both draft and verifier use the sole pinned Haiku model.

Frozen v10.6 limited requests to 8,192 input tokens, 1,800 output tokens and 65,536 serialized bytes; its failed receipts preserve those exact gates. The latest owner instruction removes that assembled-evidence token/byte cap for the new candidate. Pin and enforce the selected providers' documented native windows and applicable transport limits, the bounded output policy, and the existing total token/attempt/monetary allocation. Requests that cannot fit the selected real window or remaining budget fail as SYSTEM_ERROR before generation; never silently truncate required source context. A process restart or new validation run cannot reset the persistent allocation.

Haiku draft and verifier prefix caches are role-specific: distinct policy/schema and exact applicable source evidence; dynamic question/history/final response remain outside the cached prefix. A configured cache is not demonstrated usage. The [historical capability probe](../reports/public_evaluator/20261012/cache_probe_capability_v2.json) proves its own verifier role only. Current-role creation/read receipts and fresh exact verification are required; no answer/verdict cache shortcut.

## 8. Session and operation integrity

Outcome enum: `NOT_TRIED`, `OBSERVED_NORMAL`, `OBSERVED_ABNORMAL`, `ACTION_COMPLETED_UNRESOLVED`, `NOT_APPLICABLE`, `UNCLEAR`, `RESOLVED`. Store evidence-linked attempts/facts separately from conversational text. Corrections supersede records; they do not rewrite history. An unresolved attempt never implies a normal observation, and reported success never establishes a verified repair.

Use transactional compare-and-set for session version, operation ownership/deduplication, reservations and final commit. A completed operation returns its saved outcome. Conflicting duplicate payloads reject. A provider call with an uncertain result is not silently retried; reconcile its reservation and operation explicitly.

Cloud Tasks dispatches to a dedicated worker with cryptographically verified Google identity, exact OIDC audience and private allowlisted task-caller identity. Its anonymous health route does not authorize task execution. The worker is separate from the browser API service so long SSE connections cannot consume all generation request capacity. Firestore owns operation leases, fencing and the 1,200-second deadline; browser SSE only observes progress/accepted buffers and may recover after its shorter observation window. Deduplicate task delivery before a provider call; an uncertain provider result cannot be retried because a task is redelivered. Stale RUNNING leases, exceptions and session conflicts must reconcile terminally. Software behavior is implemented; deployed disconnect/worker acceptance remains pending.

Progress events name actual stages: retrieval, drafting, checking and displaying the verified answer. Technical chunks begin only after durable commit. Bind events to operation, response hash and sequence. Fixed fallback/error events carry no technical-answer chunks or verified-answer label.

## 9. Admission, privacy and DevOps

Admission reserves each draft/verification pair against real provider windows before beginning that phase. The initial phase uses two attempt-one slots, draft and verify; one separate conditional phase uses two more, correction and reverify, only after a valid correctable rejection and fresh admission. Each actual request must fit its phase forecast, native window and real pacing. A legacy flat 9,992-token slot cannot size a larger selected request, and a throughput ceiling is not a native context window. Fail before starting a phase that cannot fund its verifier. Limits remain within current provider and spending permissions; no new allocation, refund or reset is introduced.

The engineering six-case client uses the exact count receipt's measured initial/correction phase forecasts rather than six flat eight-slot turns. Before each question it rereads permanent ledgers and requires remaining planned initial phases, that question's conditional correction envelope and three maximum measured initial-phase envelopes to fit attempt/token/USD1 guards. Those three envelopes retain capacity for one planned public direct turn and two human turns. Bind count/source/manifest/role-plan/native-count/cost identities and retained baseline charges. Insufficient capacity stops before provider work. This is a measured engineering envelope, not a promise that arbitrary future questions or unknown finalized verification bodies fit; production native counting and admission remain authoritative.

Preserve all historical reserved attempt/token charges and the existing shared Haiku USD1 ledger. The default legacy token ceiling is 999,200; the owner [approved only a measured 2,000,000-token ceiling](../reports/public_evaluator/20261012/haiku_v10_13/admission/owner_token_ceiling_approval_v1.json), and its [hosted application](../reports/public_evaluator/20261012/haiku_v10_13_helpers/operator_v2/hosted_runs/57f78b4b-1385-428b-8b90-fa31f134230b/application_receipt.json) passed; current usage/readback is tracked in [status](STATUS.md). Its immutable grant changes no attempt/USD1/INR guard, version, event or reserved counter. Both new Haiku roles consume that same monetary guard; do not create separate draft/verifier allocations or reset historical Google/Haiku reservations. Recompute native-counted phase envelopes, one correction maximum and measured public/human headroom before provider work. INR2,700 lifetime/INR2,540 disconnect guards remain unchanged; delayed reporting prevents an exact instantaneous cap. New chats/restarts grant no reset or refund.

Preserve the recorded text/visitor/session controls: 2,000-character/8,000-byte user text; six accepted turns/minute, 30/rolling day and 20/conversation; 30-minute idle and 24-hour session retention unless a separately approved policy changes them. Count complete model requests independently from user-text limits. Owner-bound sessions, expiry/deletion, global reservations, rate counters and fail-closed managed-store behavior require hosted tests. New conversations do not reset visitor budgets.

Enforce the owner's latest 100-word rider-question maximum in UI and API with the same versioned word-count rule. Accept exactly 100 words, reject 101 before retrieval/provider reservation, and preserve submitted text without silent truncation. This is a length limit, not an authored-question restriction. Full policy/schema, relevant history and applicable source evidence are counted separately; retrieval chunks and evidence may be large.

Keep model credentials in managed secrets and use least-privilege verified service identities for protected API/worker routes. Public read-only Qdrant remains source/index-bound. Redact routine traces. No raw user media, credential content or private model drafts in repository or routine telemetry. Photo/voice remain disabled until their scoped privacy and source-grounding acceptance is complete.

The latest [public-review scope](../reports/public_evaluator/20261012/public_review/owner_public_review_scope_v1.json) authorizes public UI, anonymous API/worker GET `/v1/health` and the Qdrant read-only `/health`/`/query` wrapper. Anonymous core health readbacks passed. All other API/worker requests validate Google JWT signature, exact audience and an allowlisted verified service email before existing edge/visitor/Tasks/owner authorization. Its gateway validates the configured host, signs secure HttpOnly SameSite cookies, and checks a 14-bit proof challenge expiring in 120 seconds. Before issuing a 24-hour visitor cookie it calls protected `/internal/visitors/reserve` using its verified exact service-account identity. The backend atomically rejects spent proofs and caps issuance at ten/minute and 60/rolling day. Task callers and other IAM callers cannot issue visitors. Browser headers and forwarded IPs grant no identity or quota authority. A cookie identifies the visitor across refresh/new conversations; a replacement creates a new subject but cannot reset persistent global issuance/request or provider budgets. Proof difficulty establishes neither human identity nor a DDoS guarantee.

CI must run provider-free contract tests on every pull request and main change. Builds use a pinned source commit, explicit runtime inputs, dependency locks and image digest. Promotion verifies the exact source/runtime/index/approval identities and service kind; an arbitrary successful build's first image is not a valid release artifact. Real provider validation is separately budgeted and never part of routine unguarded CI.

Publish durable versioned index artifacts and deployment receipts. Readiness must prove required artifacts/models/index and serving dependencies are loaded; configured point counts alone are not process health. Hosted packaging must create/chown only the serving-artifact cache and verify writability as the actual container user. Build provenance can verify exact source/input/archive/image bindings without claiming release acceptance. Promotion additionally requires compatible UI/backend/worker revisions, rollback and live acceptance. Record managed-secret version references, positive caching, public-browser direct/follow-up stream/recovery checks, cold start and costs before closing the evaluator goal.

Use anonymous GET `/v1/health` for API/worker inspection and `/health` for gateway/Qdrant readiness; `/healthz` remains an internal probe. Current v10.13 builds, exact readiness, rollback/restore, public paused browser and 36 native counters passed. Real answers, current-role cache reads and public delivery/recovery still require bound functional evidence. Preserve superseded v10.11 and the v10.12/v8 failed runs unchanged.

Use the latest recorded budget/configuration in [deployment_status.json](../cloud/deployment_status.json), not the superseded initial INR800 allocation. Preserve the non-recurring INR2,700 lifetime budget, alerts at INR1,350/2,160/2,700 and INR2,540 billing-disconnect guard. Main-project billing remains enabled; inference-project billing remains disabled. The exact public-evaluator scope authorizes necessary hosted deployment/validation and the separate credential receipt authorizes managed secret transfer/identity wiring. Later exact public-review/index-release permissions authorize their stated public source/network scopes; the separate owner grant authorizes only the measured legacy token ceiling. None restarts stopped billing, resets historical charges, creates another monetary allocation or activates availability fallback. Existing private Qdrant minimum-instance/startup settings are recorded history. Delayed reporting prevents an instantaneous exact cap.

## 10. Validation and implementation gaps

Use source-checked tuning/regression and held-out cases with exact source/checksum/runtime bindings. Held-out answers are never prompt/index enrichment. Evaluate complete and partial questions, specifications, tables, warnings, unsupported repairs, short follow-ups, injection, wrong variant, source gaps, provider failures, quota/store failures, correction and disconnect/replay. For the present owner-authorized functional demo, do not independently review output against original manual pages. Prove real retrieval, separate finalized verification, returned answers and delivery behavior; retain the exact owner waiver and make no independent factual-quality acceptance claim. Source/content changes still require their exact scoped approval.

For this functional scope, record actual retrieval/rerank behavior, returned direct/partial/follow-up outcomes, per-role counts/usage/cache reads, saved/stream/recovery equality, ownership/replay, stage timings and retained costs/capacity. Independent factual support/coverage and false-verifier metrics are not established by those functional checks. Keep software, count-only, hosted functional and historical factual-review receipts separately labelled; no new manual-review or optional tuning work is introduced.

The candidate implements authenticated hybrid retrieval, reviewed final-anchor dependency assembly, complete context, deictic follow-ups, persistent admission, private worker dispatch and exact saved delivery. Frozen v10.11 remains superseded and unbuilt. V10.12 passed hosted counts and rollback but failed live claim-to-object citation and draft validation. V10.13 sends complete literal evidence/history, constrains original admitted source IDs in both role schemas and applies conservative per-object measurement checks. The 36-call Haiku-only native preflight passed with zero generation/reservations, frozen module origins and unchanged ledgers. The owner approved a 2,000,000-token legacy ceiling; the exact hosted application passed while retaining historical counters/charges; the launcher was repaired and one direct SUPPORTED answer passed, while USB returned an operational SYSTEM_ERROR. Complete the bound functional answer/cache/delivery/public-browser probe under that exact grant; independent manual answer review is waived for this demo. Historical charges, source approvals and USD1/attempt/INR controls remain unchanged.

The preserved v8 software checks passed, but its real-provider run released zero technical answers and covered 0 of 4 clearly answerable/partially answerable turns. It is a failed coverage baseline, not release acceptance. Preserve exact approval packages, runtime receipts and failed-run adjudications needed for reproducibility. Cleanup removes obsolete active designs and duplicate generated outputs without discarding the evidence governing this contract.
