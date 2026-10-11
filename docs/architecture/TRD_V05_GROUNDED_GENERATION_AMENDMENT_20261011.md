# TRD v0.5 amendment: restored grounded answer generation

Owner clarification, 11 October 2026. This amendment supersedes section 14's A exact-reviewed-wording-only restriction and the corresponding methodology decision note. It does not supersede manual applicability, source/dependency review, typed eligibility, safety, non-repeat, privacy or immutable citation requirements.

The inspected serving path contradicted the intended product: `cloud/arm_a/questions.py` required exact canonical propositions or listed paraphrases; `composer.py` made zero answer-provider calls and released exact authored text; `rider_contract.py` rejected other wording. The earlier open-question amendment accepted raw text but preserved these restrictions. Acceptance of arbitrary input alone did not deliver open question answering. The owner explicitly authorized replacing that restriction.

The corrected serving path is versioned BGE M3 embeddings and BM25 -> hybrid retrieval and source-linked assembly -> independent factual source-object admission plus deterministic procedural eligibility -> Gemma 4 26B A4B grounded answer generation -> structured-output, citation, permitted-step and mandatory-display checks -> durable session commit -> complete-unit SSE. The manual and immutable index are reused; neither parsing nor embedding runs per rider request. Canonical questions, answer scopes and paraphrases are not factual admission criteria.

The model receives the rider's actual question, complete admitted source objects and freshly bound original procedure/section labels, immutable evidence IDs, server-owned citation mappings and complete typed active state. It can explain or combine supported facts, or give one eligible action. It cannot authorize a new repair, hidden diagnosis, variant, prerequisite, evidence object or OEM step order. Procedural step authority, figure/quality holds and source-dependency limitations remain; this runtime does not assert that every page is releasable. Missing source review is an abstention, never a rider question.

The server appends every selected scope's required reviewed warning, prerequisite and product-policy caveat. Provider-written claims must cite admitted IDs. The server supplies pages; model-written page numbers are not accepted as citations. Checks validate structure and permissions, not semantic entailment. There is no separate final semantic-verifier request. Original-page claim review is an offline evaluation activity, with answerable coverage reported separately from unsupported claims.

Reviewed canonical responses are eligible only for exact-query, current-source/index/registry/prompt/runtime and empty-active-state cache hits after fresh retrieval and eligibility/dependency checks. Any unseen wording, typed outcome, stale version or unreviewed response misses into generation. Generated misses are not auto-approved for response caching. Semantic similarity is never cache authorization.

Provider prompt caching is separate. A stable hashed policy/schema prefix and version-bound evidence context precede variable rider/state data. Explicit cached content is enabled only when the exact model/account capability is established; cache creation is bounded, TTL-limited and reserved. Provider-reported cached tokens are recorded. Unsupported capability or a minimum-length miss is reported; prompts are not padded and models are not substituted to manufacture hits.

The complete request is counted by the exact model's `countTokens` API, including policy/schema wrappers. Limits are 8,192 input tokens, 24,000 complete request bytes and 1,800 generated output tokens; final displayed text including appended warnings is independently counted and must also fit 1,800 tokens. Mandatory context is never truncated. A complete bundle that cannot fit returns SYSTEM_ERROR. Input text/JSON limits, atomic visitor/global quotas, session ownership, 20-turn conversation cap, idempotency and 24-hour/30-minute retention remain in the rider API.

At most one generation is active per worker. At most one retry is allowed after an explicit 429 or 503 rejection; uncertain transport failures, malformed output and invalid citations are withheld without a retry. Every attempt reserves worst-case tokens in managed shared counters: at most 100 generation attempts and 999,200 reserved tokens per rolling day, six attempts per minute, and a conservative 10,000 reserved tokens per minute including cache creation. Unknown account quotas may reject earlier; these are application limits, not measured provider quota guarantees. The exact Gemma model is currently free-tier-only in Google's pricing table; paid-model fallback is prohibited. GCP's existing project budget stop remains unchanged. New deployment/public access requires fresh exact runtime review and held-out evidence; the fixed-answer candidate is not completion of this amendment.

Implementation: `cloud/grounded_generation/`. Current runtime freeze and fresh evaluation: `reports/grounded_generation/v4/`. Earlier failed runs are retained in v1–v3. The source-context package approves 184 labels and holds 334; it authorizes no parent-body injection or new procedures. A separate exact original-source fuse scope permits refusal warnings only, without authorizing replacement. Release status is recorded in the versioned receipts; this amendment itself is not a successful deployment or a semantic certification.

Provider references checked 11 October 2026: [token counting](https://ai.google.dev/gemini-api/docs/tokens), [context caching](https://ai.google.dev/gemini-api/docs/caching), [Gemma pricing](https://ai.google.dev/gemini-api/docs/pricing#gemma_4).

Independent original-page review of the v3 run found one unsupported contextual claim among 14 released claim units, despite all 29 citation mappings being valid. Only two of six answerable questions received complete answers. That candidate failed acceptance. V4 restores the missing procedure context and is evaluated on new post-freeze question/fact compositions; route counts alone remain insufficient for acceptance.
# Generic source admission correction 11 October 2026

The owner's subsequent clarification supersedes any wording in this amendment
that makes factual generation depend on registered answer scopes. The serving
entry point now imports `cloud/grounded_generation/generic_runtime.py` from
`cloud/arm_a/app.py`. The old grounded runtime remains a compatibility module
for its reviewed procedural payload helper and historical regressions.

Factual admission is separate from StepDefinition. SourceAuthority consumes
immutable hybrid-retrieval chunk identities and exact source-object approvals,
then restores independently reviewed document structure and mandatory source
context. It does not consume authored questions, canonical answers, paraphrases,
the eight experimental fact groups, or a semantic allowlist. New structural
review binds source children and cross-parent context to original manual pages;
unreviewed context remains an explicit source gap. Full parent text is never
implicitly authorized by a parent label.

StepDefinition remains the procedural authority for actions, prerequisites,
warnings, eligible clarifications and state transitions. Historical unresolved
actions, including superseded events, block further actions and diagnostic
clarifications without reviewed successor authority. Descriptive source facts
can remain available. Free wording never converts an unresolved action into a
normal observation.

The answer LLM receives admitted raw source content, section context, typed
state, eligible actions and rider-resolvable clarifications. Its structured
output cites evidence IDs directly; there is no factual `scope_ids` field.
The server checks schema, evidence membership, permitted actions, required
warning/prerequisite display, immutable bindings and original-page citations.
These checks are not semantic entailment proof. No separate final semantic
verifier call has been restored. Original-page generated-claim adjudication is
an offline acceptance gate.

The runtime keeps real provider input counting, 8,192 input tokens, 1,800 output
tokens, a 65,536-byte request bound, one inference worker and at most two attempts
on explicit 429/503 rejection only. Full mandatory evidence is never truncated.
Each attempt reserves conservative tokens against shared minute/day application
quotas. Those quotas are not a verified Google account entitlement. The exact
Gemma model's prior explicit-cache probe returned 404; cached tokens and claimed
savings remain zero. Eligible reviewed exact-response caching is independent of
source admission, and every miss returns to grounded generation.

V3 and v4 failed acceptance records remain unchanged. V5 source/software review,
post-freeze rider-style held-out execution and original-page claim adjudication
are required before any release claim. The private deployed revisions remain
unchanged and public access remains closed. This correction grants no public
PDF/excerpt/image display rights and makes no billing change.

