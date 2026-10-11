# MotoMedic product requirements

Version 1.0 reset · 11 October 2026 · Status: implementation target; release acceptance pending.

This is the single current product specification. It consolidates the owner's latest open-manual draft, verify, stream decision. Together with [TRD.md](TRD.md), it replaces superseded planning methods for future work. It does not change source approvals, source display restrictions, model permissions, spending limits or deployment permissions. [ARCHITECTURE.md](ARCHITECTURE.md) shows the system; [TODO.md](../TODO.md) records the delivery sequence and completion evidence.

## 1. Product and purpose

A rider asks a question about the Royal Enfield New Himalayan 450. MotoMedic gives a concise answer or useful checklist supported by the selected owner's manual, with accurate source references and relevant conditions and warnings. When the manual supports only part of the question, the answer states that limit. When sufficient applicable evidence cannot be found, the assistant provides the verified OEM support route.

The supplied source is an owner's manual, not a service manual. MotoMedic cannot extend its coverage into undocumented repair instructions. It is an advisory aid and does not establish a root cause or verify a repair from a rider's report of success.

The product accepts arbitrary questions. A predefined question, answer card, diagnostic branch, StepDefinition or canonical answer is never a prerequisite for ordinary manual Q&A. Relevant conversation and typed outcomes inform follow-ups without restricting the questions the rider may ask.

## 2. Release scope

| Priority | Included |
| --- | --- |
| P0 | Text questions and follow-ups; confirmed Himalayan + BS6 selection; one immutable English manual; manual-supported complete or explicit partial answers; focused clarification; safety, abstention and error handling. |
| P0 | Versioned hosted ingestion and index reuse; concurrent dense + BM25 retrieval; rank fusion; bounded recovery and conditional reranking; separate draft and semantic verification; saved verified answer streaming and recovery. |
| P0 | Private authenticated web acceptance, server-side secrets, admission and spend controls, redacted traces, original-source evaluation and reproducible deployment/rollback instructions. Public opening follows its separate acceptance and authorization gates. |
| P1 | Visible-observation photo input, optional confirmed speech-to-text, copyable session summary and optional usefulness feedback, after text acceptance. |

Other manuals, undocumented internal repairs, aftermarket modifications, hidden-fault photo diagnosis and autonomous repair are outside this release. The retired whole-manual Claude design stays retired. Claude may only be the separately authorized, disabled-by-default provider availability fallback in the retrieved-evidence pipeline.

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

1. Confirm the supported motorcycle selection and see the manual's identity.
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
| FR-04 | Recover required reviewed context once and rerank uncertain ordering at most once. | Fixtures exercise recover, rerank, skip and fail routes; mandatory context survives reassembly. Missing review never triggers reranking. |
| FR-05 | Privately draft from the actual question, relevant history, typed outcomes and applicable assembled evidence. | No private or rejected draft appears in API/UI delivery, including on correction or disconnect. |
| FR-06 | Separately verify the exact finalized answer for question coverage and every technical claim. | Strict bound verdict checks statements, units, values, conditions, warnings, limitations and citations. Confidence alone cannot release an answer. |
| FR-07 | Permit at most one correction and a fresh verification. | Correctable rejection causes one bounded attempt; a second rejection yields fallback. Operational failure yields SYSTEM_ERROR. |
| FR-08 | Save the accepted response durably before technical answer delivery. | Accepted, saved, streamed and recovered response hashes match; duplicate operations do not repeat paid calls. |
| FR-09 | Preserve distinct application outcomes. | SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR have tested routing and correct user wording. |
| FR-10 | Preserve conversation meaning. | Short follow-ups retain topic; ACTION_COMPLETED_UNRESOLVED never becomes OBSERVED_NORMAL; corrections supersede immutable facts rather than erase history. |
| FR-11 | Show citations from immutable evidence and server page metadata. | Every released technical claim maps to admitted source evidence; model-invented page numbers and unavailable evidence IDs are rejected. |
| FR-12 | Keep prompt caching separate from answer authority. | Exact provider/model support and cached-token receipts are required for a caching claim. No exact or semantic answer cache bypasses verification. |
| FR-13 | Make Claude an optional availability fallback. | Only authorized availability errors qualify; semantic rejection, quota, malformed output and source/integrity failure never trigger model switching. All calls remain source bound and budget reserved. |
| FR-14 | Apply resource, ownership and privacy controls. | Hosted admission/store/provider failures fail closed; secrets stay server-side; published deletion and redaction behavior is exercised. |

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

Hosted operation is required. Keep existing GCP and provider allocations and the billing stop guard. No reset document authorizes extra spending, a billing restart, public access, fallback activation or a new deployment.

## 8. Current implementation departures

The existing code is material to improve, not an accepted implementation of every requirement. The current serving dense path computes local NumPy similarity instead of calling the available Qdrant service. Ordinary Q&A does not activate conditional recovery/reranking because the scheduler still depends on legacy step manifests. Admission may reject the second call of a valid draft/verify turn; some admitted contexts exceed the 8,192-token input bound; short follow-up retrieval can lose its topic. Durable worker completion after an SSE disconnect remains unproven in Cloud Run.

The v8 provider run produced no technical releases and answered 0 of 4 clearly answerable or partially answerable turns. Three turns failed before generation on input size. Passing software boundaries do not close answer coverage, original-source correctness or deployed-service acceptance. Preserve these receipts while resolving the causes.

## 9. Release gate

Release only after the current runtime proves useful source-supported complete and partial answers, correct safety/abstention/error handling, exact durable stream/recovery equality and resource/privacy controls on hosted infrastructure. Independent source review must be separate from serving generation and verification; tuning and held-out cases remain disjoint. Record exact source/index/runtime/model/prompt/evaluation identities and remaining limitations. Public opening and operational changes retain their existing authorization requirements.
