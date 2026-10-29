# MotoMedic technical requirements

Version 2.2, 25 October 2026. Paired with the [PRD](PRD.md), [architecture](ARCHITECTURE.md) and [status](STATUS.md). The owner's decisions are [v1](../evals/20261024_answer_release_v1/owner_decision_v1.json), [v2](../evals/20261024_answer_release_v1/owner_decision_v2.json), [v3](../evals/20261025_answer_release_v3/owner_decision_v3.json), [v4](../evals/20261025_answer_release_v3/owner_decision_v4.json), [v5](../releases/owner_decision_v5.json) and [v6](../releases/owner_decision_v6.json).

## 1. Components

| Component | Contract | Code |
| --- | --- | --- |
| Section index | Offline regrouping of the cached Docling parse into content sections, re-embedded once. Requests only load and verify it. | [section_index.py](../cloud/grounded_generation/section_index.py) |
| Retrieval | BGE-M3 dense search and BM25, reciprocal rank fusion, top 5, conditional reranking, a relevance floor. | [section_retrieval.py](../cloud/grounded_generation/section_retrieval.py) |
| Assembly | The whole section of each chunk as plain labelled text, a server-side label map and the warnings to decide. | [section_assembly.py](../cloud/grounded_generation/section_assembly.py) |
| Answer template and gate | System prompt, native answer schema, deterministic release gate, fixed fallback. | [template_answer.py](../cloud/grounded_generation/template_answer.py) |
| Generation call | One `claude-haiku-5-5` request with ledger reservation and strict response validation. | [haiku_answer.py](../cloud/grounded_generation/haiku_answer.py) |
| Turn pipeline | Session checks, the stages above, the saved view and its release binding. | [section_questions.py](../cloud/grounded_generation/section_questions.py) |
| Admission ledger | Persistent attempt and USD reservations, token accounting without a ceiling, pacing and sealing. | [whole_turn_admission.py](../cloud/grounded_generation/whole_turn_admission.py), [claude_budget.py](../cloud/grounded_generation/claude_budget.py) |
| Shared types | Session records, the provider error and the content hash, unchanged from the retired root modules. | [cloud/common/](../cloud/common/) |
| Local experiments | The serving retrieval, assembly and gate, with a Claude Code subagent in place of the API call | [tools/local_answer.py](../tools/local_answer.py), [EXPERIMENTS](EXPERIMENTS.md) |
| Delivery | Operation binding, saved-buffer streaming and recovery. | [delivery.py](../cloud/grounded_generation/delivery.py) |
| API, worker and store | Rider routes, Cloud Tasks dispatch, fenced worker, Firestore transactions. | [rider_api.py](../cloud/arm_a/rider_api.py), [durable_dispatch.py](../cloud/arm_a/durable_dispatch.py), [store.py](../cloud/arm_a/store.py), [app.py](../cloud/arm_a/app.py) |

Qdrant and BM25 rank candidates; they do not authorize answers. The model is probabilistic. The gate checks structure, citations, numbers and warning decisions, not meaning.

## 2. Section index

The index is built from an existing index directory whose `docling_document.json` matches its manifest's `cached_parse_sha256`. Nothing is re-parsed. Usage, from the project root:

`python -m cloud.grounded_generation.section_index <source_index_dir> <out_dir> <bge_m3_dir>`

The build applies these rules:
- **Boxes.** Every chunk whose Docling heading is WARNING, CAUTION or NOTE joins the content section it follows in reading order, labelled with its box.
- **Running headers.** A section-header text printed on 3 or more pages, always in the top 12% of the page, is a running header. After its first appearance it does not start a new section, so a page-break continuation stays in one section.
- **Search text.** Each chunk's search text is `<content heading>\n[<box label>\n]<text>`. It is embedded with the pinned BGE-M3 (revision `5617a9f61b028005a4858fdac845db406aefb181`), and the BM25 postings are rebuilt.
- **Evidence ownership.** Each evidence object belongs to exactly one section.
- **Related warnings.** Docling sometimes splits a subsection from its parent, leaving the parent's warnings behind. A section with no WARNING or CAUTION of its own records the previous section's WARNING/CAUTION boxes as `related_warnings` when:
  - the previous section has some;
  - it starts on the same page as the previous section ends, or the next one;
  - the first content word of its heading appears in the previous heading.

  On this manual that links 2 sections: LUGGAGE CATEGORIES to ACCESSORIES AND LUGGAGE (5 warnings) and FUEL FILLING LEVEL to FUEL TANK CAP (6). Chapter-wide attachment was measured first and would add nothing, because chapter-title sections rarely hold warnings ([measurement](../evals/20261025_quality_round_v1/README.md)).
- **Identity.** The index ID hashes the source, the cached parse, the sectioning configuration, the embedding identity (including the weights SHA-256) and the build code.

The manifest records the identity, `review_layer: NONE` and a QA block covering counts, attached boxes, continuations, page coverage and parser gap pages. `identity()` returns the manifest SHA, every declared file SHA and the counts. `verify()` fails closed on any changed manifest, inventory or file.

The current index is `index_a609ca61c635641e0a22dc48`:
- 154 sections and 532 chunks;
- 121 boxes attached and 116 continuations;
- 145 of 149 pages covered, with page 103 flagged as a parse gap.

It was built by the [v3 candidate script](../evals/20261025_answer_release_v3/candidate/section_index.py). The serving copy differs only in its import path. A changed source, parser, sectioning or embedding creates a new index ID.

## 3. Retrieval

| Setting | Value |
| --- | --- |
| Version | `section-top5-hybrid-v2` |
| Dense candidates | 20, by cosine over normalized BGE-M3 vectors |
| BM25 | k1 1.5, b 0.75, the index's own postings |
| Fusion | Reciprocal rank fusion, k 60, over the first 50 of each ranking |
| Kept | Top 5 fused chunks; ties broken by chunk ID |
| Rerank trigger | The ordered first 3 distinct sections of dense and BM25 differ, compared over their common depth |
| Rerank | The pinned cross-encoder scores the 5 on every turn, and reorders them only on the trigger. A query over 128 tokens skips scoring with `QUERY_EXCEEDS_RERANK_LIMIT`. |
| Relevance floor | When the best of the 5 scores is below −9.0, the turn sends the fixed fallback and support route with no model call (`BELOW_RELEVANCE_FLOOR`). The floor was set on development questions only (lowest answerable −7.95) and can only refuse, never authorize, an answer. A skipped score never triggers it. |

A short or deictic follow-up keeps the previous rider question as topic context (`retrieval_query`). A topic-change phrase drops it. The dense backend is chosen once at startup:
- With `MOTOMEDIC_QDRANT_URL` set, it is hosted Qdrant with an identity token. The response must name the same index, mark `candidate_evidence_only`, and return only known chunks of the same source.
- Otherwise it is exact search over the pinned vectors in the image.

A backend failure is SYSTEM_ERROR, never a switch.

## 4. Model input

The model input is built as follows:
- **Order.** Sections appear in retrieval order, deduplicated, each under `## <heading> (page N[-M])`.
- **Lines.** Every object with readable text becomes one line `[E<n>] [(<BOX>) ]<text>`. Tables become `header: value` rows. Headers, pictures, page headers and footers are skipped.
- **Server side.** The label → evidence ID, pages, box and type map stays on the server.
- **Warnings.** WARNING and CAUTION lines form `WARNINGS TO DECIDE`; NOTE lines are content only. A section's related warnings follow its own lines as `(WARNING, from <parent heading>)` and join the list, unless the parent section is itself sent.

The user message carries the rider question, the earlier conversation and the sections. The earlier conversation is the last 3 saved turns, with each prior answer cut to 600 characters. It contains no parser JSON, evidence IDs, hashes, review state, source-gap IDs or server-added warning text. If no section has a readable line, generation is skipped.

## 5. Generation call

Each request has this form:
- **Model and output.** Model `claude-haiku-5-5`, `max_tokens` 1,800.
- **Thinking and effort.** `thinking: disabled` and `output_config.effort: high`.
- **Schema.** `output_config.format` is the native JSON schema from `answer_schema(assembled)`:
  - route and coverage enums;
  - `evidence_ids` items restricted to the labels sent;
  - `watchout_review.display_id` restricted to the warnings sent, and required when any were sent;
  - `additionalProperties: false` on every object.

  Array caps are not expressible in the schema; the gate enforces them.
- **Caching.** The system prompt is one block with `cache_control: ephemeral, 5m`. The user content is uncached.

Effort `high` is used because default effort released 24/30 in the evaluation, with six structural gate failures, against 30/30 at high effort.

The call sequence is:
1. Count the request with `messages/count_tokens`. Reserve the counted input plus 512 tokens of counter headroom, and fail before reservation if that exceeds the native window minus the output bound.
2. Reserve one `generate` slot in the whole-turn ledger. The slot holds the input envelope, the 1,800 output tokens and the worst-case cost (all input written to the cache, plus full output, at the matching price tier).
3. Take the permit, then send the request once, with a 60-second timeout and redirects rejected.
4. Validate the response:
   - the same model and `stop_reason: end_turn`;
   - exactly one text block with no citations;
   - complete non-negative usage within the reserved input and output;
   - 5-minute cache usage consistent with the reported creation;
   - actual cost within the reserved maximum;
   - at most 16 KiB of strict JSON with unique keys, forming one object.
5. End the turn, which seals the slot unused if it was never consumed. Reservations stay charged after any failure. Nothing is retried automatically.

The trace keeps counts, cost, cache usage and ledger outcome only, never prompt, section or draft text.

## 6. Release gate

`gate(draft, assembled, question, support_uri)` releases or raises `ReleaseRejected`:
- **Shape.** Route and coverage are always present; other fields are optional; there are no extra fields. Caps: answer 6, policy 3, watchouts 5, disclaimers 3. No empty or over-long item.
- **Citations.** Answer, policy and watchout items cite at least one label, and only labels that were sent. A disclaimer may cite; if it does not, it may not state a measurement or page the rider did not give.
- **Numbers.** Every number with a unit must appear in a cited line or in the question, with a matching unit and no derived values. Every page reference must belong to a cited line or the question.
- **Routes.** SUPPORTED needs coverage other than NONE and an answer. PARTIAL needs a disclaimer. UNSUPPORTED needs coverage NONE. SAFETY_STOP needs a cited answer or watchout. A clarification question is present exactly when the route is AMBIGUOUS.
- **Warnings.** Every warning sent has one decision. INCLUDED must be cited in `watchouts`. NOT_APPLICABLE needs a non-empty reason.
- **Internal wording.** A label or field name in any rider-visible item fails closed as `INTERNAL_LABEL_IN_RIDER_TEXT`: `[E12]`, `line E12`, `watchout_review`, `display_id`, `evidence_ids` or a prompt heading. `E20` as a fuel name passes. Meta phrases such as "the supplied sections" are rewritten to "the parts of the manual I checked" and recorded in `rewritten_phrases`. They are rewritten rather than rejected, because rejecting them turned 2 correct development answers into errors.
- **Repetition.** A policy, watchout or disclaimer item of 5 or more content words is left out when at most 20% of them are new against a kept item of an earlier section. It is counted in `suppressed_duplicates`, and its citations still count. Answer items and the clarification question are always kept. A watchout that adds a consequence, or a list item that differs in one key word, is kept. Gate v4 also compared answer items with each other. On the held-out test, that dropped a refit step that reversed the removal step's word order; v5 removed that comparison ([held-out run](../evals/20261025_heldout_v1/README.md)).
- **Composition.** The rider text is the answer, then policy, then `Watch out:` watchouts, then disclaimers (or the fixed fallback for UNSUPPORTED), then the clarification. Citations and pages come from the server label map.

`no_evidence_release` returns the fixed fallback and support route with zero provider calls. The gate does not judge relevance or meaning; a non-numeric claim in an uncited disclaimer is the accepted residual risk.

## 7. Saved view and delivery

The view is schema `motomedic-rider-api-v1`, runtime policy `open-manual-section-template-v1`. Its fields are:
- `response`: type, natural_language, technical_content, release_gate_passed, cited_pages, reason_codes, clarification_question and escalation_uri;
- `cited_pages`: evidence ID, PDF page, page index, manual and index;
- `runtime_controls`: retrieval chunk IDs and rerank flags; assembly counts and text SHA; generation counts, cost and ledger outcome; gate route and counts. It carries no draft, section text or warning reasons.

A gate-released view carries `release_delivery`, binding:
- the operation ID and runtime lock;
- the manual and index;
- the response hash and text SHA;
- the SHA of the text sent to the model;
- the SHA of the private release record (gate output, chunk IDs and label map).

`bind_view` adds `delivery` with the operation, response hash, runtime lock, evidence payload SHA, `release_binding_sha256` and event protocol `operation-sequence-v1`. `validate_saved` delivers a saved view only under the same runtime policy, manual, index, runtime lock and bindings.

Progress stages are `retrieving`, `drafting` and `checking`, then `displaying` once the saved view is read. Every event carries the operation ID and a consecutive sequence. `verified_block` (the wire name of the gate-released block) carries the saved view. `answer_chunk` slices exactly that saved text, and `complete` repeats the identical view. Fallback and error views emit only `complete`.

The runtime lock hashes:
- the questions version and runtime policy;
- the source identity and index identity;
- the retrieval constants, the assembly and template versions and the system prompt SHA;
- the generation contract.

New sessions carry it, and every turn and recovery checks it.

## 8. Session and operation integrity

Sessions and turns are stored as follows:
- **Session record.** `DiagnosticSession` snapshots record manual, variant, edition, the index manifest SHA (`version_lock`) and the runtime lock (`generation_lock`).
- **Turns.** Each turn increments the version. The store applies compare-and-set on the session version and keeps immutable per-version snapshots.
- **Conversation.** The conversation (question, response, route) is saved with each commit and passed to the next turn.

Operations run as follows:
- **Admission.** The browser request only admits the operation: idempotency key plus payload hash, owner-bound. It stores a work snapshot and dispatches a named Cloud Tasks task carrying no rider text.
- **Worker.** The dedicated worker verifies the exact task identity and audience. It claims a fenced lease, checks the work against the current manual, index, index lock and runtime lock, and runs the turn under the operation's 1,200-second deadline. It then binds, validates and commits atomically.
- **Failure and redelivery.** A redelivered task observes the terminal state or lease and never regenerates. An uncertain provider result or an expired lease ends terminally, with no paid replay.
- **Streaming.** Server-sent events (SSE) observe durable progress and the saved buffer for up to 150 seconds. Disconnecting does not cancel the operation.

Open Q&A issues no feedback choices, and there is no feedback route.

## 9. Admission, privacy and operations

Admission and ledgers:
- **Single slot.** Each turn reserves one `generate` slot, and none when nothing is retrieved, in the existing ledgers: the 100-attempt allocation and the shared Haiku USD1 ledger.
- **No token ceiling.** Since 25 October 2026 ([decision v5](../releases/owner_decision_v5.json)), reserved tokens are counted but neither a lifetime nor a rolling-day token total limits a turn. Each call's native window still does. The next hosted admission drops the retired ceiling fields from the allocation document it writes; events reserved under the ceiling stay readable.
- **Pacing.** Slots keep the 61-second pacing and the rolling 24-hour event limits.
- **History.** Earlier draft/verify events remain valid and charged when read.
- **Limits.** There is no reset, refund or new allocation without the owner.

Input and session limits:
- Rider text is at most 100 words, 2,000 characters and 8,000 UTF-8 bytes, checked in both UI and API before retrieval or reservation.
- Six accepted turns per minute, 30 per rolling day and 20 per conversation.
- 30-minute idle and 24-hour session retention.
- The request JSON is at most 16 KiB.

Identity and secrets:
- **Credentials.** Managed secrets hold the Anthropic key and the visitor-signing secret.
- **Service routes.** All API and worker routes except GET `/v1/health` need a cryptographically verified Google identity with the exact audience and an allowlisted service email, before visitor, Tasks or owner checks.
- **Public gateway.** The gateway issues signed, HttpOnly, SameSite 24-hour cookies after a proof challenge and a private visitor reservation. No client IP is trusted.
- **Logs.** Traces are redacted, and no credentials, rider records or raw media go to Git.

Availability fallback, answer caching and whole-manual prompting do not exist in this runtime; `MOTOMEDIC_CLAUDE_FALLBACK_ENABLED=true` refuses startup. The budget is INR3,120 with an INR2,960 billing-disconnect guard, as raised for the [23 October private test](../evals/20261023_private_hosted_v5/README.md); [deployment_status.json](../cloud/deployment_status.json) still records the earlier INR2,700/2,540. Stopped billing is never restarted implicitly.

## 10. Release and validation

[serving_release.py](../tools/serving_release.py) freezes and verifies schema `motomedic-serving-release-v11`; the current file is [v11.2](../releases/serving_manifest_v11_2.json). The manifest binds:
- every code, UI and workflow file under `cloud/arm_a`, `cloud/common`, `cloud/grounded_generation`, `rider_ui` and `.github/workflows`;
- `ingest/online_ingest.py`;
- the manual and source manifest;
- the owner decisions v3–v6 and the [held-out evaluation](../evals/20261025_heldout_v1/README.md);
- the previous v11 and v11.1 manifests;
- the section index identity and the generation contract.

It records `token_ceiling: NONE` and `deployment_authorized: false`. [check_installed_serving_release.py](../tools/check_installed_serving_release.py) re-checks the installed bytes, the policy and the section index inside an image. Manifests v8–v10.14 are in `archive/`; their bindings were last verified in their original layout at commit `7c412369f055b4d0ee747501e6b026f5987d1564`.

The provider-free tests listed in [CI](../.github/workflows/ci.yml) cover:
- the index, retrieval, assembly, gate and generation call, on a synthetic index with a fake transport and ledger;
- the full API → worker → saved stream → UI parser path;
- durable operations, admission and release tooling.

The [parity check](../evals/20261025_answer_release_v3/serving_parity.py) runs the serving modules on the real index against the v3 run. The [held-out test](../evals/20261025_heldout_v1/README.md) ran 33 new questions locally with a blind agent judge. Hosted acceptance needs a real-model run of new held-out questions on the frozen runtime: returned answers, cache reads, saved/stream/recovery equality, ownership and replay, and stage timings. Evaluations live in [reports/evals](../evals/README.md) and are labelled local, private or hosted.
