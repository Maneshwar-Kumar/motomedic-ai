# Constrained generator engineering v1

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
