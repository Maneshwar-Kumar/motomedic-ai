# MotoMedic project instructions

## Current contract

The owner requested a clean repository and fresh PRD, TRD, architecture diagram and sequenced TODO on 11 October 2026. Read [PRD](docs/PRD.md), [TRD](docs/TRD.md), [architecture](docs/ARCHITECTURE.md) and [TODO](TODO.md) before changing behavior. These consolidate the latest open-manual draft/verify/stream decision and supersede earlier method-specific planning documents. Follow [CONTRIBUTING](CONTRIBUTING.md).

Ordinary Q&A accepts arbitrary manual-supported questions, including concise partial answers and checklists. Authored catalogs, canonical wording, answer scopes and StepDefinitions are not input gates. Preserve optional typed observations/attempts. ACTION_COMPLETED_UNRESOLVED is never an observed normal result; reported success is not a verified repair.

## Source and immutable approval

The sole source is the 149-page royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf, SHA-256 CF221A29E2F9CD5AF6E80A99774A697C814E8EDA661C27D72E519D8A7E80DA89, edition RAM00818/A, 4th November 2025. It is an owner's manual. The owner approved Himalayan + BS6 selection; do not invent mandatory model-year or manual-edition rider questions.

Read source_manifest.json, human_review/agent_release_161/README.md and root_validation_v3.json in that package. The owner delegated source-content and initial-response approval for the exact 161-case v3 package to the coordinator agent. Its manifest is human_review/agent_release_161/coordinator/release_manifest_v3.json, SHA-256 b8f8c7b5a9e1a299f0a90eecbf10127779b62b35fc105f0cd587de433e235298. Do not recreate a blanket human-review blocker or label agent inspection as human signoff. Legacy human-only flags do not supersede this authority.

Approval remains exact-version and scope bound. Preserve required paths/bytes and additional pinned source-context/read-only/structural/prerequisite packages. A reviewed heading or child does not approve a whole parent body. Changed objects need new scoped review. Full adaptive transitions, general vision, public source display and deployment are separate scopes.

Preserve warning, prerequisite, condition, table-header/unit, figure and reference context for each claim. Docling's page 103 gap remains flagged. Missing review/extraction is a maintainer problem, not rider-resolvable ambiguity. Never invent repairs, page numbers, hidden faults or OEM diagnostic order.

Engineering use is permitted; rider-facing PDF, excerpts and figure crops are prohibited. The manifest binds the verified support route and its market-fit limitation. Keep credentials and raw rider media out of Git and routine telemetry.

## Pipeline

Ingestion/embedding run as a versioned hosted job before requests. Reuse index index_a3282c4d98cf54595e4ba168: BGE M3, 1,024-token chunk budgets, 532 chunks, 277 parents and BM25. Source/parser/chunk/embedding changes create a new index. Never reparse/re-embed the document per request.

Target: authenticated Qdrant dense retrieval concurrent with BM25, RRF, bounded reviewed-dependency recovery and conditional reranking, complete applicable evidence assembly, private draft, separate verification of the exact finalized response, final binding checks, durable save, then exact-buffer streaming. At most one correction/re-verification. No private/rejected tokens reach riders. Current departures are in docs/STATUS.md and TODO.

Keep SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR distinct. Malformed/outage/quota/integrity failures are SYSTEM_ERROR. Fixed messages are in the PRD. Verified source-specific safety takes precedence. Relevance/confidence is not answer authorization. Held-out cases cannot enrich prompts or retrieval tuning.

The primary model is pinned in the runtime. Evidence-only Claude Haiku availability fallback stays disabled until existing activation permission applies. Semantic rejection, quota, malformed output and integrity failure cannot trigger it. Full-manual Claude is retired; do not rerun it without new owner authorization. Prompt caching is separate from answer authority and has no demonstrated support/savings for the current primary. Answer-cache shortcuts are disabled.

## Operating permissions and evidence

Use current cloud/deployment_status.json and operational receipts rather than initial settings. Latest recorded lifetime budget: INR2,700, with INR2,540 billing-disconnect guard. Delayed reporting prevents an exact instantaneous cap. Recorded private Qdrant has min one instance and startup CPU boost. These are records, not new-change authorization. Never restart stopped billing without owner authorization.

This reset does not authorize deployment, public opening, extra provider spending, fallback activation, source-display changes or billing changes. Verify existing scope for each exact action. Builds and real-provider runs remain hosted. Label synthetic local checks.

The v8 real run released zero technical answers and answered 0/4 answerable/partial cases. Software passes, retrieval coverage and workflow success do not establish factual correctness, live acceptance or latency targets. Preserve failed-run evidence and exact bindings.

## Repository discipline

Keep main as the current baseline. Temporary implementation branches use codex/; remove them after checked integration. Historical files are recoverable from Git and the ignored reset backup. Do not restore competing designs into active navigation.

Run python tools/check_repository_structure.py after navigation/layout changes and relevant provider-free tests after runtime changes. Never alter frozen bindings to make a check pass. New reports belong under reports/<work-area>/<version-or-run>/. Coordinate disjoint ownership with active work before changing shared runtime objects.
