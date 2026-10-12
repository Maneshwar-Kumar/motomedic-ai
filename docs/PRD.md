# MotoMedic product requirements

**Current work: complete the Haiku-only functional demonstration.** Public answering and anonymous core inspection are enabled. Frozen v10.13/CI/builds and native retrieval counts passed; one direct SUPPORTED answer passed exact-finalized verification and saved stream/recovery; broader checks remain open. The [latest exact owner instruction](../reports/public_evaluator/20261012/public_review/owner_functional_acceptance_scope_v1.json) waives independent manual answer review for this demo. Immutable source approval and separate exact-finalized Haiku verification remain required; no independent factual acceptance is claimed.

Version 1.6 · 12 October 2026 · Haiku-only functional demonstration and recorded owner review waiver.

This is the single current product specification. It consolidates the owner's open-manual draft, verify, stream decision and subsequent request for a public evaluator URL, conditional ranking, prompt caching and separate finalized-response verification. The latest instruction selects Haiku for both calls. The [operational scope](../reports/public_evaluator/20261012/owner_scope_v1.json), [credential approval](../reports/public_evaluator/20261012/owner_credential_scope_v1.json), [public-review scope](../reports/public_evaluator/20261012/public_review/owner_public_review_scope_v1.json) and [index-release approval](../reports/public_evaluator/20261012/public_review/owner_index_release_scope_v1.json) authorize bounded hosted validation, public repository/manual/index inspection and public read-only service routes. Writes, worker jobs and owner-private reads retain exact verified service identities and application capabilities. Immutable source approvals, historical charges and USD1/attempt/INR controls remain; a separate measured owner grant changes only the legacy primary token ceiling. [TRD.md](TRD.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [TODO.md](../TODO.md) define implementation and acceptance.

Public answering is enabled by the [later direct owner instruction](../reports/public_evaluator/20261012/public_review/owner_public_answer_enablement_scope_v1.json), before full six-case acceptance. [Routed UI health](../reports/public_evaluator/20261012/haiku_v10_13_helpers/functional_ui_promotion_v2/enabled_health.json) passed for `motomedic-rider-ui-v10-13-functional-enabled`. The [anonymous browser](../reports/public_evaluator/20261012/public_review/browser_enabled_v1/receipt.json) observed a 97-character SUPPORTED answer in 71.06 seconds with enabled input and all four progress stages; it did not capture incremental chunk rendering or session/operation identity. The separate [private direct audit](../reports/public_evaluator/20261012/haiku_v10_13_runtime/direct_delivery_a77d_v1.json) proves exact-finalized verification and identical saved/stream/recovery. USB returned `PROVIDER_INCOMPLETE_OR_REFUSED` without a retained exact stop reason, four cases remain unrun and positive cache reads are unproven. Broader functional acceptance and merge remain pending; independent manual answer review was waived.

## 1. Product and purpose

A rider asks a question about the Royal Enfield New Himalayan 450. MotoMedic gives a concise answer or useful checklist supported by the selected owner's manual, with accurate source references and relevant conditions and warnings. When the manual supports only part of the question, the answer states that limit. When sufficient applicable evidence cannot be found, the assistant provides the verified OEM support route.

The supplied source is an owner's manual, not a service manual. MotoMedic cannot extend its coverage into undocumented repair instructions. It is an advisory aid and does not establish a root cause or verify a repair from a rider's report of success.

The product accepts arbitrary questions. A predefined question, answer card, diagnostic branch, StepDefinition or canonical answer is never a prerequisite for ordinary manual Q&A. Relevant conversation and typed outcomes inform follow-ups without restricting the questions the rider may ask.

## 2. Release scope

| Priority | Included |
| --- | --- |
| P0 | Text questions and follow-ups; confirmed Himalayan + BS6 selection; one immutable English manual; manual-supported complete or explicit partial answers; focused clarification; safety, abstention and error handling. |
| P0 | Versioned hosted ingestion and index reuse; Source/index-bound Qdrant dense + concurrent BM25 retrieval; RRF; bounded recovery and conditional reranking when distinct parent ranks disagree. |
| P0 | Questions of at most 100 words; private Haiku drafting and separate Haiku verification; five-minute role-specific policy/evidence-prefix caching; saved verified streaming, recovery and follow-ups. |
| P0 | Public evaluator URL with signed visitor cookies/proof, public repository/manual/index and anonymous read-only API/worker health and Qdrant inspection; private write/job/owner-state authorization, server-side secrets, persistent admission/spend controls, redacted traces, functional proof and exact deployment/rollback receipts. |
| P1 | Visible-observation photo input, optional confirmed speech-to-text, copyable session summary and optional usefulness feedback, after text acceptance. |

Other manuals, undocumented internal repairs, aftermarket modifications, hidden-fault photo diagnosis and autonomous repair are outside this release. The [latest model scope](../reports/public_evaluator/20261012/owner_model_scope_v3.json) selects Claude `claude-haiku-5-5` as the sole model. Drafting and verification use separate calls, distinct role policies/schemas and exact response bindings. This supersedes Gemini and the earlier requirement for different model identities. Same-model calls do not establish cross-model agreement. The owner waived independent manual answer review for this functional demonstration; exact approved source-object admission and the separate finalized runtime verifier remain required.

## 3. Source and authority

| Field | Selected source |
| --- | --- |
| File | `royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf` |
| Type / pages | Owner's manual / 149 PDF pages |
| Edition | RAM00818/A; 4th November 2025 |
| SHA-256 | `CF221A29E2F9CD5AF6E80A99774A697C814E8EDA661C27D72E519D8A7E80DA89` |
| Applicability | Rider confirms Himalayan and BS6 under the owner-approved selection policy. No invented model-year or edition-selection requirement. |
| Support route | Manifest-bound `mailto:support@royalenfield.com`; preserve its recorded market-fit limitation. |
| Display | Supplied manual and exact existing evidence/figure/index archive are public for inspection/reproduction under the latest owner scopes. The answer UI retains supported paraphrases and server-derived evidence/page references; no additional source-display feature is added. |

[source_manifest.json](../source_manifest.json) retains exact immutable metadata and historical display-policy bytes. The latest public-review/index-export instructions supersede its earlier public-display restriction for the authorized inspection scope. Exact owner-delegated source approvals remain version and scope bound. Legacy human-review flags do not override the approved v3 package; agents must not represent agent review as human inspection. Approving an initial answer or source object does not approve all adaptive transitions, whole parent text, photographs or deployment. Changed objects require a new scoped review.

## 4. Rider journey

1. Open the public evaluator link, complete its browser proof challenge and receive a signed visitor cookie, then confirm the supported motorcycle selection and see the manual's identity.
2. Ask a natural text question. An example question is a convenience, never an input allowlist.
3. See truthful progress as the backend retrieves, drafts privately and checks the complete answer.
4. Receive the complete supported answer or explicitly limited partial answer, applicable warnings/conditions and exact source references. A concise checklist is allowed when the manual supports every item.
5. Ask a follow-up or report an outcome. Relevant topic, prior evidence and typed facts remain available. The assistant does not repeat an unresolved action without a documented or corrected-context reason.
6. After a disconnect, recover the same saved outcome without another generation call.

One focused question is used only when the rider can resolve an ambiguity needed for the answer. Missing extraction, source review or table context belongs to the maintainer and must not be turned into a rider question.

The owner's latest instruction limits each rider question to 100 words. Reject a longer question before retrieval or provider reservation and let the rider shorten it; never silently truncate it. This replaces the earlier advisory design envelope, while arbitrary manual-supported wording remains allowed. Retrieved chunks and applicable evidence may be large. Count the complete policy, relevant history, evidence and finalized verification request against the selected providers' native windows and the existing lifetime budget; do not impose the former 8,192-token assembled-prompt cap or remove mandatory source context to meet it.

If complete accumulated context exceeds a real model window, retain the operational-error outcome and show a separate instruction to start a new chat. After serving an accepted answer whose actual input reaches 80% of the smaller paired native input allowance, show a separate new-chat notice. These notices do not modify the verified answer. No compaction layer, silent evidence removal or automatic history reset is required; a new chat retains visitor and global spending controls.

## 5. Functional requirements and acceptance

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| FR-01 | Lock the selected manual, applicability and runtime/index versions throughout a turn. | Wrong-source, changed-object and mismatched-index tests reject the affected answer; a valid Himalayan BS6 selection is accepted. |
| FR-02 | Answer unseen, naturally worded manual questions. | Hosted functional questions outside authored catalogues reach the real retrieval/draft/verification path and receive answers or explicit limits, without a question/step allowlist. This is functional proof, not independent factual adjudication. |
| FR-03 | Use the hosted immutable Qdrant dense index and BM25 concurrently, then RRF. | A hosted trace proves both searches ran and the dense request reached Qdrant with source/version filters; no request reparses or embeds the document. |
| FR-04 | Recover required reviewed context once and rerank observed dense/BM25 distinct-parent rank disagreement at most once. | Matching ranks, sibling chunks and absent backend ranks do not trigger reranking; fixtures exercise recover, rerank, skip and fail routes. Mandatory context survives reassembly and missing review never triggers reranking. |
| FR-05 | Privately draft from the actual question, relevant history, typed outcomes and applicable assembled evidence. | No private or rejected draft appears in API/UI delivery, including on correction or disconnect. |
| FR-06 | Haiku privately drafts; a separate Haiku call verifies the exact finalized response for question coverage and every technical claim. | Bind distinct call roles/policies/schemas and exact response/evidence/history. Check statements, units, conditions, warnings, limitations and citations. Confidence alone cannot release an answer. |
| FR-07 | Permit at most one correction and a fresh verification. | Correctable rejection causes one bounded attempt; a second rejection yields fallback. Operational failure yields SYSTEM_ERROR. |
| FR-08 | Save the accepted response durably before technical answer delivery. | Accepted, saved, streamed and recovered response hashes match; duplicate operations do not repeat paid calls. |
| FR-09 | Preserve distinct application outcomes. | SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR have tested routing and correct user wording. |
| FR-10 | Preserve conversation meaning. | Short follow-ups retain topic; ACTION_COMPLETED_UNRESOLVED never becomes OBSERVED_NORMAL; corrections supersede immutable facts rather than erase history. |
| FR-11 | Show citations from immutable evidence and server page metadata. | Every released technical claim maps to admitted source evidence; model-invented page numbers and unavailable evidence IDs are rejected. |
| FR-12 | Cache the selected Haiku role's exact policy and source-evidence prefix for five minutes, separately from answer authority. | Hosted exact-role/model receipts demonstrate cache creation followed by positive reads; question/history/final response remain outside the cached prefix. No padding or answer-cache bypass; savings need paired measurements. |
| FR-13 | Keep the separate availability fallback disabled. | Quota, malformed output, semantic rejection and integrity failure cannot trigger model switching. |
| FR-14 | Apply resource, ownership and privacy controls to public evaluator access. | Signed cookies, proof replay rejection and persistent private visitor/global admission fail closed. Only the exact verified UI service identity may issue visitors; API/worker anonymous health and read-only Qdrant are public, while writes/jobs/owner-private reads retain cryptographic service identity and application authorization. No client-IP trust claim; secrets stay server-side and retention/redaction is exercised. |

## 6. Response policy

| Application status | Rider-visible handling |
| --- | --- |
| SUPPORTED | Verified complete or explicitly partial answer. A partial response explains its limitation before verification. |
| AMBIGUOUS | One verified, source-relevant clarification the rider can answer. |
| UNSUPPORTED | Fixed fallback and the manifest-bound support route. It does not assert that the manual contains no answer anywhere. |
| SAFETY_STOP | Applicable source-supported stop/warning, separately verified and saved. Preserve a known verified safety response if another component fails. |
| SYSTEM_ERROR | Fixed operational-error message; never a claim that the question lacks manual support. |

Fixed fallback:

> I couldn’t find relevant information in the selected manual to answer your question. Please contact Royal Enfield or an authorised service centre.

Fixed operational error:

> I couldn’t check the answer right now. Please try again shortly.

These neutral application messages remain available without successful generation or verification. They are not labelled as verified technical answers. Unsafe requests cannot authorize undocumented advice; PDF, user and image content cannot override the source-only policy.

## 7. Functional acceptance and operating limits

For the present demo, the owner asks for proof that the deployed agent receives questions, performs real retrieval and returns answers. Independently comparing outputs with original manual pages is waived; do not claim factual correctness from functional success. Immutable source checks, private drafting, exact finalized verification, useful direct/partial/follow-up behavior, current-role cache use and saved-stream/recovery bindings remain required. Historical quality targets of 95% abstention, 80% answerable coverage, 90% complete-evidence recall, 95% next-step correctness and 98% citation support are not measured or accepted by this functional scope. No additional manual-review or tuning work is introduced.

The previous warm text p95 under five seconds and photo p95 under ten seconds are hypotheses for this pipeline. Measure cold starts separately. First progress is not first verified answer. Report retrieval, assembly, rerank, draft, verification, correction, save and delivery timings, plus recorded provider reservations/usage. Independent correctness denominators are unavailable under this functional scope. Do not claim a target achieved from retrieval-only timing, software fixtures, workflow success or a static judge.

Hosted operation is required. Keep the INR2,700 lifetime budget and INR2,540 billing-disconnect guard, persistent provider allocation and current stopped inference billing. The 11 October reset did not authorize deployment or public access. Subsequent exact public-evaluator, credential, public-review and index-release receipts authorize their stated deployment/validation/publication scopes. The owner separately approved only a 2,000,000-token legacy ceiling; its exact hosted grant was applied without resetting counters or increasing USD1/attempt/INR guards; current usage and launcher failure are recorded in [status](STATUS.md). These instructions do not restart billing, create another monetary allocation or activate availability fallback.

## 8. Current implementation departures

Frozen v10.13 implements the Haiku-only runtime, exact role guards, complete literal evidence/history, distinct admitted-ID schemas, persistent admission and durable worker delivery. Hosted CI/builds, readiness, rollback/restore, public paused preview and 36 native counters passed. Public answer submission is now enabled under the owner's later direct instruction. [Status](STATUS.md) records current receipts and remaining cache/delivery/public-answer proof. Frozen v10.11 and failed v10.12/v8 receipts remain history; the owner waiver does not reclassify them as factual successes.

The v8 provider run produced no technical releases and answered 0 of 4 clearly answerable or partially answerable turns. Three turns failed before generation on input size. Passing software boundaries do not close answer coverage, original-source correctness or deployed-service acceptance. Preserve these receipts while resolving the causes.

## 9. Release gate

Complete the authorized functional evaluator when the same frozen runtime actually retrieves and answers questions, with separate exact-finalized Haiku verification, direct/partial/follow-up behavior, current-role cache creation/reads, identical durable stream/recovery and existing resource/ownership controls on hosted infrastructure. Independent manual answer review is explicitly waived for this demo; no independent factual acceptance is claimed. Immutable source approval stays binding and held-out cases may not enrich prompts/retrieval. Record exact source/index/runtime/role/grant/operation identities, compatible revisions/rollback, the public URL and limitations. The owner explicitly authorized enabling public answering after the direct SUPPORTED result, before the full six-case suite. Answering and routed health are now enabled; broader functional acceptance remains incomplete.
