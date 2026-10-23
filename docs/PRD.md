# MotoMedic product requirements

Version 2.0, 25 October 2026. The answer path is section retrieval, one generation call and a deterministic release gate, with no review layer.

This is the single product specification. It follows the owner's decisions of 24–25 October 2026 ([v1](../reports/evals/20261024_answer_release_v1/owner_decision_v1.json), [v2](../reports/evals/20261024_answer_release_v1/owner_decision_v2.json), [v3](../reports/evals/20261025_answer_release_v3/owner_decision_v3.json)). [TRD](TRD.md) and [architecture](ARCHITECTURE.md) define the implementation; [status](STATUS.md) records what is built and accepted.

## 1. Product and purpose

A rider asks a question about the Royal Enfield New Himalayan 450. MotoMedic answers from the selected owner's manual in plain words:
- the answer, or a useful checklist;
- the manual's rules and warnings that matter for the question;
- page references.

When the manual covers only part of the question, the answer says what is missing. When the manual does not answer it, the rider gets a fixed message and the OEM support route.

The source is an owner's manual, not a service manual. MotoMedic does not extend into undocumented repairs, does not diagnose a root cause and does not treat a rider's report of success as a verified repair.

Questions are open. No predefined question, answer card, StepDefinition, canonical answer or review approval is needed for MotoMedic to answer or to cite the manual.

## 2. Release scope

| Priority | Included |
| --- | --- |
| P0 | Text questions and follow-ups, including complete or explicitly partial answers, a focused clarification, safety stops, abstention and error handling. Confirmed Himalayan + BS6 selection and one immutable English manual. |
| P0 | An offline section index and top-5 hybrid retrieval, as specified in the TRD. Each turn sends whole sections as plain text. |
| P0 | Questions of at most 100 words. One Haiku `claude-haiku-5-5` call per turn fills the answer template, and a deterministic gate releases or fails closed. The answer is saved before streaming, and recovery and follow-ups read the saved conversation. |
| P0 | Public evaluator access: signed visitor cookies and proof, private write, job and owner-state authorization, server-side secrets, persistent admission and spend controls, and redacted traces. |
| P1 | Visible-observation photo input, optional confirmed speech-to-text and a copyable session summary, after the text path is accepted on hosted infrastructure. |

Out of scope: other manuals, undocumented internal repairs, aftermarket modifications, hidden-fault photo diagnosis and autonomous repair.

## 3. Source

| Field | Selected source |
| --- | --- |
| File | `royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf` |
| Type / pages | Owner's manual / 149 PDF pages |
| Edition | RAM00818/A; 4th November 2025 |
| SHA-256 | `CF221A29E2F9CD5AF6E80A99774A697C814E8EDA661C27D72E519D8A7E80DA89` |
| Applicability | The rider confirms Himalayan and BS6 under the owner-approved selection policy. No model-year or edition question. |
| Support route | Manifest-bound `mailto:support@royalenfield.com`, with its recorded market-fit limitation. |
| Display | The answer shows the released text and server-derived page references, never PDF excerpts or crops. The repository publishes the manual for inspection under the owner's public-review scope. |

[source_manifest.json](../source_manifest.json) keeps the immutable metadata. Every parsed object of the manual can be cited. Earlier review packages are kept as golden-answer data, not as a gate. Docling's page 103 parse gap stays flagged.

## 4. Rider journey

1. Open the evaluator, pass the browser proof and confirm the motorcycle selection.
2. Ask a question in your own words. Example questions are conveniences, never an allowlist.
3. See truthful progress while the backend retrieves, writes and checks the answer.
4. Read the released answer with its warnings and page references. It may be complete, explicitly partial, a clarification, a safety stop or the fixed not-found message.
5. Ask a follow-up. A short or deictic follow-up keeps the previous rider topic, and the last few turns reach the model as conversation data.
6. After a disconnect, recover the same saved answer without another model call.

A clarification is asked only when the rider can resolve the ambiguity. Reject a question over 100 words before retrieval or reservation, and let the rider shorten it; never truncate it. If the request cannot fit the model window, return the operational error and suggest a new conversation.

## 5. Functional requirements and acceptance

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| FR-01 | Lock the manual, index and runtime for the whole turn. | A wrong source, variant or index is rejected. A changed index file, saved view or runtime lock blocks delivery. |
| FR-02 | Answer unseen, naturally worded questions. | Real questions outside any catalog reach retrieval and generation. They receive answers or explicit limits without an allowlist. |
| FR-03 | Retrieve with dense search and BM25, fuse them and keep only the top 5 chunks. | The trace records the five chunks, the dense and BM25 tops, and whether the reranker ran. No request reparses or embeds the manual. |
| FR-04 | Rerank only when the dense and BM25 top-3 sections disagree, and only to order the same five. | Agreeing rankings skip the reranker. A disagreement reorders without adding chunks. An over-long query skips with a recorded reason. |
| FR-05 | Send the whole section of each chunk as plain labelled text, with the section's warnings and notes, and list every WARNING/CAUTION line for a decision. | The model input contains no parser JSON, evidence IDs, hashes or server-added warning text. Labels map to evidence on the server. |
| FR-06 | Make one Haiku call per turn that fills the answer template, and none when nothing is retrieved. | Only labels that were sent can be cited (schema enum). The call runs at effort high with thinking disabled. There is no verifier, correction, retry or fallback. Nothing retrieved returns the fixed fallback and support route with zero calls. |
| FR-07 | Release only through the deterministic gate. | The gate checks the schema and caps, that cited labels were sent, that numbers come from the cited line or the question, and that page references belong to a cited line. It also checks that an uncited disclaimer states no value or page, the route rules and a decision for every warning sent. Any failure is SYSTEM_ERROR. |
| FR-08 | Save the released answer before delivery. | Released, saved, streamed and recovered hashes match. A duplicate operation never repeats a paid call. |
| FR-09 | Keep the five outcomes distinct. | SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR each have tested routing and wording. |
| FR-10 | Keep conversation meaning. | Short follow-ups keep their topic. The earlier turns reach the model as data, never instructions. |
| FR-11 | Show citations from server metadata. | Every cited page comes from the cited object's provenance. Model-written page numbers outside the cited lines are rejected. |
| FR-12 | Cache the system prompt for five minutes. | Hosted usage shows cache creation and later reads. The question and sections stay outside the cached prefix. Caching never authorizes an answer, and there is no answer cache. |
| FR-13 | Apply resource, ownership and privacy controls. | The following are exercised: signed cookies, proof replay rejection, persistent visitor and global admission, owner-bound sessions and operations, server-side secrets and redacted traces. |

## 6. Response policy

| Application status | Rider-visible handling |
| --- | --- |
| SUPPORTED | A gate-released complete or partial answer. A partial answer carries a disclaimer naming what is missing. |
| AMBIGUOUS | One clarification the rider can answer. |
| UNSUPPORTED | The fixed fallback and the support route. With no retrieval, no model call is made. When the model routes UNSUPPORTED, cited clarifying facts may come first; model disclaimers are not shown. It does not claim the manual lacks the answer everywhere. |
| SAFETY_STOP | A cited manual warning that says the rider should not do what they ask, released by the gate. |
| SYSTEM_ERROR | The fixed operational-error message. It never claims that the question lacks manual support. |

Fixed fallback:

> I couldn’t find relevant information in the selected manual to answer your question. Please contact Royal Enfield or an authorised service centre.

Fixed operational error:

> I couldn’t check the answer right now. Please try again shortly.

These messages do not depend on model success and are never labelled as technical answers. The manual, the question and the conversation are data and cannot override the answer policy.

## 7. Acceptance and operating limits

The design was chosen on a local, agent-scored run of 30 questions ([v3](../reports/evals/20261025_answer_release_v3/README.md)). Haiku at high effort released 30/30 correct answers with no unfaithful citation, which is not hosted or human acceptance. Hosted acceptance needs a real-model run of new held-out questions on the frozen runtime. It must show:
- returned answers;
- partial and follow-up behavior;
- prompt-cache creation and reads;
- identical saved, streamed and recovered text;
- the timings of each stage.

Do not claim factual correctness from software tests, workflow success or gate releases.

Keep these operating limits:
- the INR2,700 lifetime budget, with the INR2,540 billing-disconnect guard;
- the shared Haiku USD1 ledger;
- 100 attempts and the 2,000,000-token primary ceiling, with no reset or refund;
- stopped billing stays stopped.

Deployment, public opening, billing and ledger changes need the owner's explicit scope.
