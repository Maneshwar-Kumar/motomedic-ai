# Gemma/controller handoff for the refinement chat

This is the handoff from the completed Gemini/Gemma integration work to refinement chat `01a121fc-f04c-7983-bb9e-e3acbd3aa072`. The feedback-loop chat owns the additional100 records; this chat did not start, duplicate or modify that batch. Human review and feedback files remain owned by their respective chats.

## Start gate for expanded refinement

The owner requires expanded grounding/controller refinement against the planned161 candidates only AFTER the additional100 feedback loops complete. Verify `human_review/record_workflow/batch_100_completion.json` against the producer's schema, catalogue IDs and loop-terminal records; existence alone is insufficient. The file was absent at handoff inspection. Until that gate is valid, use read-only preparation and do not launch expanded refinement or overlapping code writes. Read `human_review/blockers` without rewriting another chat's decisions. Agent-loop completion or blocked-loop closure does not confer source approval.

## Exact code and verification

Implementation checked: `b5c4efc9ff9d8c05d24ca47ef4441551528eaab8` on branch `codex/reviewed-evidence-controller`, private repo `Maneshwar-Kumar/motomedic-ai`, draft PR1. The handoff/report commit may be newer; it does not change the implementation tested.

Hosted verification: [37975947723](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/37975947723) passed. The combined suite ran88 tests. Existing export commands separately reran24 controller and15 constrained-generator tests; do not sum these as additional independent tests. All11 accepted-example source gates and all8 legacy real-source draft gates passed with zero live provider calls. Scripted fictional transport/semantic answers establish protocol behavior only. Semantic accuracy and held-out coverage remain unmeasured.

Retained machine-readable evidence:
- `reports/gemma_integration_verification_v1.json`: run/commit/test/source-gate summary.
- `reports/gemma_grounding_hosted_v1.json`: exact source/index/registry/runtime/code hashes and all11 routes.
- `reports/gemma_grounding_gates_existing_v1.json`: unchanged active registry's zero-call checks (local working-tree code hashes).
- `registry/reconciled-accepted-eleven/reconciliation_report.json`: draft provenance/status.

The source checksum is `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`. Index remains `index_a3282c4d98cf54595e4ba168`; CI reused the existing immutable hosted BGE snapshot. No parse/re-embedding, Qdrant change, deployment or billing operation occurred.

## Provider and trust boundaries

Selected model stays `gemma-4-31b-it` via Google Gemini API. Do not silently substitute a Gemma MoE, Gemini or another provider/model. Explicit config is `generation_providers.gemma_runtime_config()`; service defaults stay unconfigured and fail closed. Secret name is `MOTOMEDIC_GEMINI_API_KEY`, stored in the private GitHub repository. The initial access report records separate inference project `motomedic-inference-20261009` with billing disabled and separate owner-authorized$10 allocation; this integration made no new live inference calls or account changes.

Versions: provider `gemini-sse-json-v1`; transport `gemini-curl-sse-v1`; generator `reviewed-composer-v1`; prompt `reviewed-composer-prompt-v1`; verifier `claim-entailment-v1`; schema `constrained-response-v1`. Runtime lock: `7bf681034b0ea1aa6aa31897f53ac132ba77791684ae3de98dde33b8ef875c57`. Runtime bounds:24,000 UTF-8 request bytes,1,800 output tokens,30second hard curl request timeout, minimal thinking, zero retries, finite caller allocation per adapter. One allocated call each permits at most one composer and one verifier attempt. Failed requests consume reservations. No tools, model fallback, redirects, model-repair loop or automatic retry.

The provider model is an alias, not an immutable snapshot. Initial discovery version001 does not prove immutable weights. Record returned identifiers and revalidate changes. JSON schema is supplied as a system instruction and strictly validated locally; provider-enforced schema output is not established for this Gemma API. Wrong model, truncation, refusal, malformed/duplicate/nonfinite JSON, invalid usage or extra calls fail closed.

`gemini_transport.py` records first HTTP byte, first visible non-thinking text, completion, safe HTTP/curl status, usage and model identifiers. Composer/verifier timing is separate. Prior verifier telemetry is cleared for each composition. No credentials, raw rider text/media, model output text, source excerpts, HTTP bodies or full curl metadata enter routine reports. API outages/quota/access/timeouts are SYSTEM_ERROR with provider reason codes; claim-support rejection is distinct. Earlier timing probes reproduced Google500 on local and GitHub networks; see GEMMA_OBSERVABILITY.md. This integration did not retry those probes.

## Registry and accepted-source handoff

Active `registry/candidate_registry.json` and its empty review ledger are preserved. The eleven accepted conversations were reconciled into the separate `registry/reconciled-accepted-eleven/` DRAFT. Candidate digest: `c54ba305d3005a4b79b60d456e140499e372441668c35e31c28ad646185d7353`. It includes source-context hashes, proposed claim roles, draft paraphrases, immutable IDs/page references, conditional branch plans, versioned draft rules/dependencies and explicit authoring holds. New associations are page/object candidates, not verified procedure edges, precise claim spans or complete sufficient evidence. Formal source decisions remain0.

`EvidenceRegistry.step_ready` and `registry_workflow.review` enforce `authoring_blockers`. Resolve authoring gaps in final content BEFORE exporting/signing its digest. Removing a hold is not approval; each source/evidence/procedure/rule/dependency/step still needs the content-bound independent original-page review. A changed record invalidates its old approval. `DRAFT_PARAPHRASE` does not authorize end-user display. Do not approve the unchanged old records merely because the conversations were accepted.

Retained limits from the first eleven:
- Tyre pressure is a direct lookup; replacement branches need named CEAT specs, separate tyre/rim observations, both rim conditions and no invented construction-specific model mapping or alternate-brand compatibility.
- Fuse discovery uses position/colour/sticker, never blue alone; uncertain condition goes directly to service, failed replacement stops at service, and reported success retains after-failure inspection. No invented fuse test.
- Starting uses the accepted compact conditional setup and source-backed limits; setting switches is separate from starter permission. Page75 recovery-after-three-attempts and scoped post-start cautions remain separately pending in this snapshot.
- Fuel-level and blinking-indicator reports stay distinct, with accepted page63 stand/ignition refresh conditions. Preserve open discrepancy, avoid repeat refuelling and retain it if no-start resolves. Full multi-issue controller/session routing and compact observation-group presentation are explicit pending runtime boundaries, not already implemented merely by branch metadata.
- Reconnection is a service-only draft because supporting owner guidance lacks access/fitting instructions. Cooling has no supported overnight/room-temperature endpoint, fixed time, numerical hot threshold or safe restart clearance. Unknown source threshold is not a rider-resolvable question.
- Required typed pictures block before text-only inference even when a figure category is missing. Inline schematic permissions need precise scoped display-policy reconciliation, figure/legend review and a separately evaluated figure verifier. No blanket source-display permission was added.

The original eleven are regression/tuning references. Any expanded records are generated from feedback on those eleven and remain drafts until scoped review. All available expanded/blocked examples stay source gated; do not call a feedback-tuned set held out or fill source approval from agent consensus.

## Reproduction and next evaluation

Offline/hosted commands reuse the immutable index:

```text
python -m unittest test_gemini_provider test_constrained_generator test_accepted_reconciliation
python verify_gemma_grounding.py --index build/index --output build/gemma-grounding-gates.json
```

Set MOTOMEDIC_TEST_INDEX to the existing index directory for local index-dependent tests. The hosted Verify reviewed evidence controller workflow already covers these paths without the API secret. `reconcile_accepted_examples.py` requires the review-chat source files locally and refuses to overwrite a nonempty review ledger; use a new output version when re-authoring reviewed content.

After the additional100 completion gate, refinement should first finalize exact source spans, branch-specific mandatory context, source/applicability rules, action boundaries, multi-issue typed state and scoped figures against the producer's records. Compare the deterministic canonical baseline with the grounded pipeline on the same independently adjudicated cases. Keep unsupported additions, changed numbers/units, missing warnings/prerequisites, invalid citations, unresolved-action outcomes and provider errors separate in results. A negative observation or unsuccessful action never establishes component health.

Only then use bounded live grounding when all applicable formal source/controller/provider gates permit it. The current `verify_gemma_grounding.py --live --case-id ...` preflights a single reviewed lookup and reserves at most one call per adapter; draft cases stop before key access or transport. It is not a complete161-case calibration runner. Live action branches require approved typed session fixtures; figure-dependent cases require an evaluated figure adapter. Independent human/source truth must measure the semantic verifier's false acceptance/refusal; the same Gemma model in two adapters is not independent ground truth. Preserve separate tuning/held-out partitions, model/API errors, first-byte/token/completion and usage/cost uncertainty. No technical advice, source approval, cache promotion, public deployment or billing re-enable follows from this handoff.
