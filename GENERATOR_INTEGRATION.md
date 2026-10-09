# Constrained generator integration

Current selected provider: Google Gemini API `gemma-4-31b-it`. See the Gemma integration update below; the v1 sections record the earlier OpenAI candidate and initial credential state.

The hosted service now composes only after the existing controller chooses an eligible step and verifies the reviewed dependency bundle. `ReviewedService` defaults to an unconfigured, fail-closed generator. No source approval, public deployment or change to Qdrant/GCP/billing is part of this work. The eleven actual step records and empty review ledger remain unchanged.

## Composition and validation

`generation_contracts.py` pins prompt, generator, schema, verifier and transport revisions. `constrained_generator.py` builds an allowlisted envelope from the selected approved step: every claim, mandatory warning/prerequisite, immutable evidence ID and PDF page. The model selects a wording from each claim's canonical text and optional `reviewed_wording_variants`. These variants, roles and display classifications live inside the content-hashed step and therefore require the same independent original-page review. Changing them invalidates approval. Arbitrary paraphrasing is deliberately outside this first engineering contract; this restriction reduces the unreviewed text surface.

Each reviewed claim requires `response_role` (`ACTION`, `FACT`, `WARNING`, `PREREQUISITE`). Exactly one ACTION is permitted for an action step; lookups have none. All claims remain in reviewed order and all citations are retained. Required warnings and prerequisites must be mapped by the corresponding roles. Number/unit/specification substitutions are rejected by exact approved-wording membership; this is deterministic constraint validation, **not semantic entailment**. Reviewers must independently assess complete table headers, units, scope and that each action wording actually describes a single step. The model cannot add an action or question.

The separate `SemanticSupportAdapter` submits the final claims and complete selected evidence objects to its own configured provider. It requires a boolean support verdict for every exact claim ID and no unsupported additions. It checks entailment against the original evidence, not against another model's answer. A text adapter cannot validate image-dependent claims: a required figure blocks with `FIGURE_SEMANTIC_ADAPTER_UNAVAILABLE` until a separately evaluated image verifier exists. Tables retain their raw object structure. Deterministic wording membership and scripted test verdicts do not establish semantic accuracy. Independent source adjudication and live verifier calibration remain release gates.

Output schema, route, selected step, claim IDs/order/count, evidence IDs and exact page registry are checked before semantic inference. Missing dependencies stop before composition. Malformed/invented/rejected drafts and provider failures yield SYSTEM_ERROR, withholding technical output and pending action records. Established source review/display gaps yield UNSUPPORTED. Default retries are zero: at most one generation and one verification call. Context exceeds a conservative UTF-8 byte budget rather than losing mandatory evidence through truncation. Output tokens and provider HTTP payloads are bounded.

Safety stops and nontechnical clarification, escalation and customer-reported resolution remain controller-generated. A verified source stop takes precedence over ordinary outages. End-user projection preserves a stop while suppressing source excerpts; engineering excerpts are not sent to end users. All ordinary end-user claim wording requires reviewed paraphrase classification before any model call. No generation prompt contains rider text, media, free-form attempt details or observation values. A bounded typed attempt summary preserves unresolved as unresolved; it cannot establish component health.

## Provider configuration and authorization

`build_generator(RuntimeConfig(...))` constructs independent generator and verifier adapters. Defaults use `UnconfiguredProvider`. The optional standard-library OpenAI Responses adapter uses a fixed HTTPS endpoint, strict JSON schema, `store: false`, no tools/history/streaming, one POST, no redirects and no automatic retries. Credentials come only from server environment `MOTOMEDIC_OPENAI_API_KEY`. Errors are reduced to fixed reason codes; request bodies, HTTP error bodies and credentials are never routine telemetry.

Optional evaluation candidate: `gpt-4.1-mini-2025-04-14` for composition and separately configured verification. This is a modest, non-reasoning snapshot with structured outputs documented by [OpenAI's model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini). The [Responses contract](https://developers.openai.com/api/reference/resources/responses/methods/create) documents the request interface. Selection is a candidate rationale, not a comparison win or proof of account access. Provider, model and transport revisions must be pinned in RuntimeConfig. Pricing is not hardcoded; capture approved pricing/account currency when allocating live spend.

No matching provider environment credentials or repository secret names were found during this build. Live calls are disabled and none were made. A caller must explicitly set `live_enabled=True` and a finite `authorized_calls_per_adapter` after authorizing that provider account and allocation. A key or model name alone does not authorize spending. The existing GCP budget guard does not cover an OpenAI account. Do not enable an additional billable provider merely because GCP engineering spending was authorized. This factory does not create or mutate provider accounts or budgets.

For example, a trusted server may construct the candidate config without enabling calls:

```python
from generation_contracts import RuntimeConfig
from constrained_generator import build_generator
config = RuntimeConfig(generator_provider='openai',
    generator_model='gpt-4.1-mini-2025-04-14', verifier_provider='openai',
    verifier_model='gpt-4.1-mini-2025-04-14')
pipeline = build_generator(config)  # Disabled; no charge or inference.
# Inject response_generator=pipeline into ReviewedService.
```

Synthetic adapters are dependency-injected test doubles. The legacy ReviewedController template/callback interface remains compatible for engineering regressions and deterministic safety rendering; the service uses the new constrained pipeline for ordinary technical answers. Neither interface approves draft source records.

## Version locks, cache and telemetry

The registry content/code lock covers the new pipeline modules. RuntimeConfig locks provider/model revisions, bounds, prompts and schema separately in `DiagnosticSession.generation_lock`. Store writes reject changing that lock in an existing session. Configuration changes require a new confirmed session. Exact cache keys include this runtime lock along with existing checksum/variant/path/review locks. Draft/stale caches still miss. A reviewed cache draft may enter `compose(..., cache_draft=...)` only from trusted cache lookup; it skips generation but must pass the same deterministic and semantic checks. The service does not enable cache serving automatically.

Redacted traces record runtime versions, stage timings, attempt counts, fixed reason codes, measured provider token counts when available and cost status. Provider prices and CI cost remain unknown unless measured. No raw source/query/media are logged. Synthetic usage numbers are fixture values; they are not cost/latency measurements. Public rate/upload/day-spend controls and durable managed session storage remain separate release gates.

## Hosted verification and remaining evaluation

The private `Verify reviewed evidence controller` workflow retains its ten-minute bound and reuses `owner-manual-index-37908240500`; no manual parse, document embedding or cloud deployment occurs. It runs existing controller/retrieval/budget regressions plus `test_constrained_generator.py`, then `verify_generation.py` exports `generation-engineering-evaluation-v1` with the exact checked commit, source/index/registry/runtime/dataset locks. All five direct real-manual questions and three multi-turn seeds must abstain with zero generation/verification calls. Unissued multi-turn feedback is rejected. These cases remain REGRESSION_NOT_HELD_OUT.

Synthetic fixtures are separately authored fictional bench procedures and test successful composition, mapping/specification/unit/page attacks, warning/prerequisite omission, semantic adapter rejection, malformed verdicts, outages, source/scope/runtime mismatch, unresolved vs normal, non-repeat, verified stop precedence, excerpt suppression, cache revalidation, transport bounds and store integration. Existing controller regressions cover corrections and documented persistent-fuse escalation. Scripted judges prove protocol behavior only.

Remaining work: independently approve real source/claim/role/dependency records; verify the original PDF download URL; authorize a provider allocation and configure credentials; run bounded candidate calls on independently adjudicated paraphrase/contradiction/unsupported-addition cases; measure verifier false acceptance/refusal, answerable coverage, token/cost and warm/cold p95; tune on regression cases and evaluate a genuinely held-out set. Review referenced figures with an image-capable adapter. Public UI, managed sessions, limits and independent release checks remain pending. No source record is silently promoted by CI.

Original PDF121 (printed119) was visually inspected for the persistent-fuse stopping condition during engineering review. The candidate registry already records escalation after unresolved fuse work. Legacy D024/D035 automatic continuation remains unapproved and is not used by ReviewedService. This is an agent observation, not independent source sign-off.

## Recorded online result

Private [run 37926678059](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/37926678059) passed on implementation commit `12b57afa856c6fb4d63f621ff9031a9f57551987`: 67 combined regressions, all eight real-source draft gates, and a separate 15-test synthetic composition/adapter suite. Real-source generation and semantic calls were zero. The source ledger remains empty and no real steps are approved. The versioned downloaded report is retained in `reports/generation_engineering_v1.json`; its commit identifies the implementation tested, not a later documentation-only commit. Hosted CI reused the immutable artifact and did not rebuild the index or modify GCP/billing. Provider cost was US$0; CI cost was not measured. This result does not establish live verifier accuracy, rider answer coverage or p95.


## Gemma integration and accepted-example reconciliation

The owner selected Gemma 4 Dense 31B. `gemma_runtime_config()` in `generation_providers.py` explicitly selects `gemini` for composition and separate semantic verification, model `gemma-4-31b-it`, `provider_revision=gemini-sse-json-v1`, minimal thinking, 30-second timeout, 24,000-byte request budget, 1,800 output-token bound and zero retries. No default service configuration silently changes: ordinary `ReviewedService` remains unconfigured/fail-closed unless trusted server code injects this pipeline. The model name is a provider alias, not an immutable snapshot; record returned model identifiers and revalidate when the provider changes it. The initial model discovery reported metadata version001, which is not proof of immutable weights.

```python
from generation_providers import gemma_runtime_config
from constrained_generator import build_generator
config = gemma_runtime_config()
pipeline = build_generator(config)  # selected adapters; calls disabled
# Only after source and eligibility gates and owner-authorized bounded evaluation:
# pipeline = build_generator(config, live_enabled=True,
#                            authorized_calls_per_adapter=1)
# One composer + one verifier, separately reserved; inject into ReviewedService.
```

`MOTOMEDIC_GEMINI_API_KEY` exists as a private GitHub repository secret for the separate unbilled inference sandbox. Credentials pass only via server environment and curl stdin. `gemini_transport.py` uses the fixed HTTPS SSE endpoint, no redirects/tools/history/fallback model, a hard curl request deadline and no automatic retries. Both adapters reject other model names. JSON schema is included in the system instruction and validated locally; provider-enforced structured output has not been established for this Gemma API. Malformed JSON, duplicate keys, nonfinite JSON, refusals, truncated output, wrong returned model and invalid usage fail closed. No Markdown stripping, model-repair call or hidden retry is performed.

Composition and verification traces independently retain first response byte, first visible non-thinking text, completion, HTTP status, safe reason codes, model identifiers and reported usage. Raw requests, source text, rider/media data, response bodies, generated text, credentials and full curl diagnostic metadata are excluded. API500/429/access/timeout errors remain SYSTEM_ERROR with separate provider reason codes; semantic rejection is a distinct validation reason. The same model in separate instances is not independent ground truth: human-adjudicated source cases must still measure false acceptance/refusal.

The original eleven conversations were accepted in `human_review/record_id_verification.md` and `human_review/subagent_feedback.md`. Those files are owned by the review/feedback chats and are not edited or automatically committed here. `reconcile_accepted_examples.py` emits the separate `registry/reconciled-accepted-eleven/` draft with source-context hashes, claim roles, draft paraphrases, immutable citation IDs, accepted branch plans and explicit authoring holds. It never overwrites the active registry or fabricates source decisions; a nonempty draft review ledger cannot be overwritten. Draft roles and text are proposals, not formal human source approval.

The new dependencies are candidate page/object associations for original-page review, not verified graph edges or complete sufficiency. Conditional branch scopes, exact claim spans, procedure boundaries and display classification still need final authoring. Base lookup versus actual action boundaries need explicit review (particularly starter, fan-fuse and tyre-replacement follow-ups). Page75 recovery/post-start additions stay pending; room-temperature/overnight cooling, starter-sound diagnosis, colour-only fuse identification and construction-specific tyre-model mapping stay excluded. Reconnection is drafted as service referral only, not an owner repair action. Failed fuse replacement preserves service-stop precedence; uncertain fuse condition goes to service; fuel-level/indicator discrepancy includes the accepted page63 refresh conditions and remains separate from no-start resolution.

`authoring_blockers` are enforced by `EvidenceRegistry.step_ready` and the formal step-review workflow. They must be resolved in the final content before exporting/signing its digest. A source-referenced conversation acceptance cannot remove these holds. The original review ledger remains empty. Original and reconciled registries both block all eleven real cases with zero provider calls. Figures and the newly scoped inline schematic permissions still require precise associations, display-policy reconciliation and a separately evaluated figure verifier; engineering-only policy has not been broadened here.

`verify_gemma_grounding.py` runs the eleven existing accepted seeds as regression/tuning gates using the immutable BGE index. It records exact code hashes, source/index/registry/runtime versions, routes and zero-call source holds. Its optional live mode permits only one reviewed lookup, with preflight source/dependency/role/figure/eligibility gates and at most one call per adapter; unreviewed cases stop before key access or transport. Live action tests need separately reviewed typed session fixtures. This is not the full future semantic-calibration harness or a held-out evaluation set. Unsupported additions, changed specifications/pages, warning omissions, semantic rejection, unresolved outcomes and API failures are currently covered by offline fictional contract doubles; those tests do not establish Gemma's semantic accuracy. No live grounding call was made in this integration because complete content-bound review is absent.
