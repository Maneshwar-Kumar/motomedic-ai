# MotoMedic product requirements

Version 1.1 · 12 October 2026 · Selected public evaluator v10; hosted acceptance pending.

This is the single current product specification. It consolidates the owner's open-manual draft, verify, stream decision and subsequent request for a public evaluator URL, conditional ranking, prompt caching and verification by another LLM. The [exact operational scope](../reports/public_evaluator/20261012/owner_scope_v1.json) and [credential setup approval](../reports/public_evaluator/20261012/owner_credential_scope_v1.json) authorize the necessary public frontend, private backend/worker, managed identity and bounded hosted validation. Existing source approvals, source-display restrictions and spending limits remain unchanged. [TRD.md](TRD.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [TODO.md](../TODO.md) define implementation and acceptance.

## 1. Product and purpose

A rider asks a question about the Royal Enfield New Himalayan 450. MotoMedic gives a concise answer or useful checklist supported by the selected owner's manual, with accurate source references and relevant conditions and warnings. When the manual supports only part of the question, the answer states that limit. When sufficient applicable evidence cannot be found, the assistant provides the verified OEM support route.

The supplied source is an owner's manual, not a service manual. MotoMedic cannot extend its coverage into undocumented repair instructions. It is an advisory aid and does not establish a root cause or verify a repair from a rider's report of success.

The product accepts arbitrary questions. A predefined question, answer card, diagnostic branch, StepDefinition or canonical answer is never a prerequisite for ordinary manual Q&A. Relevant conversation and typed outcomes inform follow-ups without restricting the questions the rider may ask.

## 2. Release scope

| Priority | Included |
| --- | --- |
| P0 | Text questions and follow-ups; confirmed Himalayan + BS6 selection; one immutable English manual; manual-supported complete or explicit partial answers; focused clarification; safety, abstention and error handling. |
| P0 | Versioned hosted ingestion and index reuse; authenticated Qdrant dense + concurrent BM25 retrieval; RRF; bounded recovery and conditional reranking when distinct parent ranks disagree. |
| P0 | Private Gemma drafting, independent Claude Haiku verification of the exact finalized response, five-minute policy/evidence-prefix prompt caching, saved verified answer streaming, recovery and follow-ups. |
| P0 | Public evaluator URL with signed visitor cookies and proof challenge; private IAM-protected backend, worker and Qdrant; server-side secrets, persistent admission/spend controls, redacted traces, original-source evaluation and exact deployment/rollback receipts. |
| P1 | Visible-observation photo input, optional confirmed speech-to-text, copyable session summary and optional usefulness feedback, after text acceptance. |

Other manuals, undocumented internal repairs, aftermarket modifications, hidden-fault photo diagnosis and autonomous repair are outside this release. Claude Haiku is explicitly selected as the independent evidence-only verifier. The separate availability fallback remains disabled; the retired whole-manual Claude design stays retired.

## 3. Source and authority

| Field | Selected source |
| --- | --- |
| File | `royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf` |
| Type / pages | Owner's manual / 149 PDF pages |
| Edition | RAM00818/A; 4th November 2025 |
| SHA-256 | `CF221A29E2F9CD5AF6E80A99774A697C814E8EDA661C27D72E519D8A7E80DA89` |
| Applicability | Rider confirms Himalayan and BS6 under the owner-approved selection policy. No invented model-year or edition-selection requirement. |
| Support route | Manifest-bound `mailto:support@royalenfield.com`; preserve its recorded market-fit limitation. |
| Display | Rider-facing PDF, source excerpts and figure crops remain prohibited. Show supported paraphrases and server-derived evidence/page references. |

[source_manifest.json](../source_manifest.json) governs metadata and display. Exact owner-delegated source approvals remain version and scope bound. Legacy human-review flags do not override the approved v3 package; agents must not represent agent review as human inspection. Approving an initial answer or source object does not approve all adaptive transitions, whole parent text, photographs or deployment. Changed objects require a new scoped review.

## 4. Rider journey

1. Open the public evaluator link, complete its browser proof challenge and receive a signed visitor cookie, then confirm the supported motorcycle selection and see the manual's identity.
2. Ask a natural text question. An example question is a convenience, never an input allowlist.
3. See truthful progress as the backend retrieves, drafts privately and checks the complete answer.
4. Receive the complete supported answer or explicitly limited partial answer, applicable warnings/conditions and exact source references. A concise checklist is allowed when the manual supports every item.
5. Ask a follow-up or report an outcome. Relevant topic, prior evidence and typed facts remain available. The assistant does not repeat an unresolved action without a documented or corrected-context reason.
6. After a disconnect, recover the same saved outcome without another generation call.

One focused question is used only when the rider can resolve an ambiguity needed for the answer. Missing extraction, source review or table context belongs to the maintainer and must not be turned into a rider question.

## 5. Functional requirements and acceptance

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| FR-01 | Lock the selected manual, applicability and runtime/index versions throughout a turn. | Wrong-source, changed-object and mismatched-index tests reject the affected answer; a valid Himalayan BS6 selection is accepted. |
| FR-02 | Answer unseen, naturally worded manual questions. | Independent cases outside authored questions receive useful supported answers or justified limits, without a question/step allowlist. |
| FR-03 | Use the hosted immutable Qdrant dense index and BM25 concurrently, then RRF. | A hosted trace proves both searches ran and the dense request reached Qdrant with source/version filters; no request reparses or embeds the document. |
| FR-04 | Recover required reviewed context once and rerank observed dense/BM25 distinct-parent rank disagreement at most once. | Matching ranks, sibling chunks and absent backend ranks do not trigger reranking; fixtures exercise recover, rerank, skip and fail routes. Mandatory context survives reassembly and missing review never triggers reranking. |
| FR-05 | Privately draft from the actual question, relevant history, typed outcomes and applicable assembled evidence. | No private or rejected draft appears in API/UI delivery, including on correction or disconnect. |
| FR-06 | Verify the exact finalized Gemma answer with the separately selected Claude Haiku model for question coverage and every technical claim. | Strict verdict binds both exact model contracts and checks statements, units, values, conditions, warnings, limitations and citations. Confidence alone cannot release an answer. |
| FR-07 | Permit at most one correction and a fresh verification. | Correctable rejection causes one bounded attempt; a second rejection yields fallback. Operational failure yields SYSTEM_ERROR. |
| FR-08 | Save the accepted response durably before technical answer delivery. | Accepted, saved, streamed and recovered response hashes match; duplicate operations do not repeat paid calls. |
| FR-09 | Preserve distinct application outcomes. | SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR have tested routing and correct user wording. |
| FR-10 | Preserve conversation meaning. | Short follow-ups retain topic; ACTION_COMPLETED_UNRESOLVED never becomes OBSERVED_NORMAL; corrections supersede immutable facts rather than erase history. |
| FR-11 | Show citations from immutable evidence and server page metadata. | Every released technical claim maps to admitted source evidence; model-invented page numbers and unavailable evidence IDs are rejected. |
| FR-12 | Cache the verifier's exact policy and source-evidence prefix for five minutes, separately from answer authority. | Hosted exact-model receipts demonstrate cache creation followed by positive reads; question/history/final response remain outside the cached prefix. No padding or answer-cache bypass; savings need paired measurements. |
| FR-13 | Keep the separate availability fallback disabled in v10. | Selecting Claude as verifier does not activate fallback. Its retained contract permits only separately authorized availability errors; semantic rejection, quota, malformed output and integrity failure never trigger switching. |
| FR-14 | Apply resource, ownership and privacy controls to public evaluator access. | Signed cookies, proof replay rejection and persistent private visitor/global admission fail closed. Only the UI service identity may issue visitors; backend/worker/Qdrant stay private. No client-IP trust claim; secrets stay server-side and retention/redaction is exercised. |

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

## 7. Quality and operating targets

The release suite must contain zero independently reviewed unsupported technical instructions and zero unjustified repeat actions. Draft benchmark targets remain at least 95% proper abstention recall, 80% answerable coverage, 90% complete required-evidence recall, 95% next-step correctness where applicable and 98% citation support. Record denominators and partial-answer adjudication; measure verifier false acceptance and false refusal separately against original pages.

The previous warm text p95 under five seconds and photo p95 under ten seconds are hypotheses for this pipeline. Measure cold starts separately. First progress is not first verified answer. Report retrieval, assembly, rerank, draft, verification, correction, save and delivery timings, plus cost per correctly handled case. Do not claim a target achieved from retrieval-only timing, software fixtures, workflow success or a static judge.

Hosted operation is required. Keep the INR2,700 lifetime budget and INR2,540 billing-disconnect guard, persistent provider allocation and current stopped inference billing. The 11 October reset did not authorize deployment or public access. The subsequent exact public-evaluator and credential receipts authorize this candidate's necessary deployment and bounded validation; they do not authorize billing restart, a new allocation, source display or availability-fallback activation.

## 8. Current implementation departures

The v10 code implements authenticated Qdrant/BM25 retrieval, distinct-parent rank-disagreement scheduling, compact reviewed evidence, history-aware follow-ups, persistent whole-turn admission, different draft/verifier models and exact saved-response delivery. A dedicated private Cloud Tasks worker separates generation from long browser SSE requests. The public gateway implements signed cookies, a 14-bit proof challenge and private persistent visitor issuance. These software checks do not yet prove the v10 hosted build, actual cache reuse, useful answers, live identity/worker behavior or browser recovery. [STATUS.md](STATUS.md) records the current evidence and remaining gates.

The v8 provider run produced no technical releases and answered 0 of 4 clearly answerable or partially answerable turns. Three turns failed before generation on input size. Passing software boundaries do not close answer coverage, original-source correctness or deployed-service acceptance. Preserve these receipts while resolving the causes.

## 9. Release gate

Complete the authorized evaluator only after the same frozen runtime proves useful source-supported complete and partial answers, correct safety/abstention/error handling, positive prompt-cache reads, exact durable stream/recovery equality and resource/privacy controls on hosted infrastructure. Independent source review must be separate from serving generation and verification; tuning and held-out cases remain disjoint. Record exact source/index/runtime/model/prompt/evaluation identities, compatible revisions/rollback, the public URL and remaining limitations. Operational authorization is recorded; live acceptance remains pending.
